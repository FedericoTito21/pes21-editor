"""
Lector mínimo de archivos CPK de CRI Middleware (los .cpk de PES).

Solo lee: índice de archivos (TOC en formato @UTF) y extracción de un archivo,
descomprimiendo CRILAYLA si hace falta. Lee con seek, sin cargar el .cpk entero.
Basado en la documentación de CriPakTools / PyCriCodecs.
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass

import numpy as np

_TYPE_SIZE = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 8, 7: 8, 8: 4, 9: 8, 0xA: 4, 0xB: 8}
_FLAG_NAME, _FLAG_DEFAULT, _FLAG_ROW = 0x10, 0x20, 0x40


class CpkError(Exception):
    pass


def _decrypt_utf(data: bytes) -> bytes:
    out = bytearray(len(data))
    m = 0x655F
    for i, b in enumerate(data):
        out[i] = b ^ (m & 0xFF)
        m = (m * 0x4115) & 0xFFFFFFFF
    return bytes(out)


def _read_value(buf, pos, typ):
    if typ in (0, 1):
        return buf[pos] if typ == 0 else struct.unpack_from(">b", buf, pos)[0]
    if typ == 2:
        return struct.unpack_from(">H", buf, pos)[0]
    if typ == 3:
        return struct.unpack_from(">h", buf, pos)[0]
    if typ == 4:
        return struct.unpack_from(">I", buf, pos)[0]
    if typ == 5:
        return struct.unpack_from(">i", buf, pos)[0]
    if typ == 6:
        return struct.unpack_from(">Q", buf, pos)[0]
    if typ == 7:
        return struct.unpack_from(">q", buf, pos)[0]
    if typ == 8:
        return struct.unpack_from(">f", buf, pos)[0]
    if typ == 9:
        return struct.unpack_from(">d", buf, pos)[0]
    raise CpkError(f"tipo @UTF desconocido {typ}")


def parse_utf(buf: bytes) -> list[dict]:
    """Devuelve las filas de una tabla @UTF como lista de diccionarios."""
    if buf[:4] != b"@UTF":
        buf = _decrypt_utf(buf)
        if buf[:4] != b"@UTF":
            raise CpkError("tabla @UTF no válida")
    (table_size, _version, rows_off, strings_off, data_off, _name_off,
     ncols, row_width, nrows) = struct.unpack_from(">IHHIIIHHI", buf, 4)
    rows_off += 8
    strings_off += 8
    data_off += 8

    def cstr(off):
        start = strings_off + off
        end = buf.index(b"\0", start)
        return buf[start:end].decode("utf-8", "replace")

    def cell(pos, typ):
        if typ == 0xA:
            return cstr(struct.unpack_from(">I", buf, pos)[0])
        if typ == 0xB:
            off, size = struct.unpack_from(">II", buf, pos)
            return bytes(buf[data_off + off:data_off + off + size])
        return _read_value(buf, pos, typ)

    cols = []
    pos = 32
    for _ in range(ncols):
        info = buf[pos]
        flag, typ = info & 0xF0, info & 0x0F
        name = cstr(struct.unpack_from(">I", buf, pos + 1)[0]) if flag & _FLAG_NAME else ""
        pos += 5
        size = _TYPE_SIZE.get(typ)
        if size is None:
            raise CpkError(f"tipo @UTF desconocido {typ}")
        default = None
        if flag & _FLAG_DEFAULT:
            default = cell(pos, typ)
            pos += size
        cols.append((name, typ, flag, size, default))
    rows = []
    for r in range(nrows):
        p = rows_off + r * row_width
        row = {}
        for name, typ, flag, size, default in cols:
            if flag & _FLAG_ROW:
                row[name] = cell(p, typ)
                p += size
            else:
                row[name] = default
        rows.append(row)
    return rows


@dataclass
class CpkEntry:
    dir: str
    name: str
    offset: int
    size: int
    extract_size: int

    @property
    def path(self) -> str:
        return f"{self.dir}/{self.name}" if self.dir else self.name


def _read_packet(f, offset: int, tag: bytes) -> bytes:
    f.seek(offset)
    head = f.read(16)
    if len(head) < 16 or head[:4] != tag:
        raise CpkError(f"no se encontró el bloque {tag!r}")
    size = struct.unpack_from("<Q", head, 8)[0]
    if size > 512 * 1024 * 1024:
        raise CpkError("bloque demasiado grande")
    return f.read(size)


class Cpk:
    def __init__(self, path: str):
        self.path = path
        self.entries: list[CpkEntry] = []
        with open(path, "rb") as f:
            header = parse_utf(_read_packet(f, 0, b"CPK "))[0]
            toc_off = header.get("TocOffset") or 0
            content_off = header.get("ContentOffset") or toc_off
            if not toc_off or toc_off == 0xFFFFFFFFFFFFFFFF:
                raise CpkError("este cpk no tiene índice por nombres (TOC)")
            base = min(toc_off, content_off) if content_off else toc_off
            for row in parse_utf(_read_packet(f, toc_off, b"TOC ")):
                size = row.get("FileSize") or 0
                self.entries.append(CpkEntry(
                    dir=row.get("DirName") or "", name=row.get("FileName") or "",
                    offset=base + (row.get("FileOffset") or 0), size=size,
                    extract_size=row.get("ExtractSize") or size))

    def find(self, filename: str) -> list[CpkEntry]:
        low = filename.lower()
        return [e for e in self.entries if e.name.lower() == low]

    def read(self, entry: CpkEntry) -> bytes:
        with open(self.path, "rb") as f:
            f.seek(entry.offset)
            raw = f.read(entry.size)
        if raw[:8] == b"CRILAYLA":
            return decompress_crilayla(raw)
        return raw


def decompress_crilayla(data: bytes) -> bytes:
    if data[:8] != b"CRILAYLA":
        raise CpkError("no es CRILAYLA")
    usize, hdr_off = struct.unpack_from("<II", data, 8)
    if usize > 512 * 1024 * 1024:
        raise CpkError("tamaño descomprimido absurdo")
    header = data[hdr_off + 0x10:hdr_off + 0x10 + 0x100]
    body = np.frombuffer(data, dtype=np.uint8, count=len(data) - 0x100)[::-1]
    bits = np.unpackbits(body).tobytes()  # bits en orden de lectura (MSB primero)
    # bytes 0/1 -> cadena '0'/'1' para usar int(s, 2) rapido
    bitstr = bits.translate(bytes.maketrans(b"\x00\x01", b"01")).decode("ascii")
    pos = 0
    out = bytearray(usize)
    w = usize - 1               # posición de escritura (de atrás hacia delante)
    vle = (2, 3, 5, 8)
    n_out = 0
    while n_out < usize:
        flag = bitstr[pos]
        pos += 1
        if flag == "1":
            off = int(bitstr[pos:pos + 13], 2)
            pos += 13
            length = 3
            level = 0
            for nb in vle:
                v = int(bitstr[pos:pos + nb], 2)
                pos += nb
                length += v
                if v != (1 << nb) - 1:
                    break
                level += 1
            if level == len(vle):
                while True:
                    v = int(bitstr[pos:pos + 8], 2)
                    pos += 8
                    length += v
                    if v != 255:
                        break
            src = w + off + 3
            if src >= usize or length > usize - n_out:
                raise CpkError("CRILAYLA corrupto")
            for _ in range(length):
                out[w] = out[src]
                w -= 1
                src -= 1
            n_out += length
        else:
            out[w] = int(bitstr[pos:pos + 8], 2)
            pos += 8
            w -= 1
            n_out += 1
    return bytes(header) + bytes(out)


def find_cpks(game_dir: str) -> list[str]:
    """Todos los .cpk bajo la carpeta del juego (Data y download)."""
    found = []
    for root, _dirs, files in os.walk(game_dir):
        for fn in files:
            if fn.lower().endswith(".cpk"):
                found.append(os.path.join(root, fn))
    return sorted(found)
