"""
Base de datos de jugadores de la instalación de PES 2021 (Player.bin dentro de los .cpk).

El formato exacto de Player.bin no está documentado, así que se detecta solo:
se prueban tamaños de registro hasta que los IDs coinciden con los jugadores
que aparecen en las plantillas del EDIT, y se busca el campo del nombre.
"""
from __future__ import annotations

import json
import os
import struct
import time
import unicodedata
from dataclasses import dataclass, field

import numpy as np

from cpkreader import Cpk, CpkError, find_cpks

PLAYER_FILE = "Player.bin"
CACHE_VERSION = 2


def config_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "PES21EditorPlantillas")
    os.makedirs(d, exist_ok=True)
    return d


def load_config() -> dict:
    try:
        with open(os.path.join(config_dir(), "config.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg: dict):
    try:
        with open(os.path.join(config_dir(), "config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def guess_game_dirs() -> list[str]:
    """Rutas típicas de instalación de PES 2021 en Steam."""
    cands = []
    for drive in "CDEFGH":
        for sub in (r"Program Files (x86)\Steam\steamapps\common", r"Program Files\Steam\steamapps\common",
                    r"SteamLibrary\steamapps\common", r"Steam\steamapps\common", r"Games\Steam\steamapps\common"):
            cands.append(os.path.join(f"{drive}:\\", sub, "eFootball PES 2021"))
    return [c for c in cands if os.path.isdir(c)]


# ------------------------------------------------------------------ detección
@dataclass
class Layout:
    header: int
    rec_size: int
    id_off: int
    name_off: int
    name_len: int
    score: float
    edit_compatible: bool = False


def _looks_like_name(b: bytes) -> bool:
    if len(b) < 2:
        return False
    try:
        s = b.decode("utf-8")
    except UnicodeDecodeError:
        return False
    letters = 0
    for ch in s:
        cat = unicodedata.category(ch)
        if cat.startswith("L"):
            letters += 1
        elif ch not in " .'-":
            return False
    return letters >= 2


def detect_layout(buf: bytes, known_ids: set[int]) -> Layout | None:
    if len(buf) < 64 or not known_ids:
        return None
    ids = np.fromiter(known_ids, dtype=np.uint32)
    best = None
    for header in (0, 4, 8, 16, 32):
        body = len(buf) - header
        for rec in range(16, 0x400, 4):
            if body % rec or body // rec < 20:
                continue
            n = body // rec
            arr = np.frombuffer(buf, dtype="<u4", offset=header, count=n * rec // 4).reshape(n, rec // 4)
            for col in range(min(rec // 4, 8)):
                score = float(np.isin(arr[:, col], ids).mean())
                if best is None or score > best[0]:
                    best = (score, header, rec, col * 4)
    if best is None or best[0] < 0.3:
        return None
    score, header, rec, id_off = best
    n = (len(buf) - header) // rec
    sample = range(0, n, max(1, n // 1500))
    # Para cada registro se buscan los inicios de textos "con pinta de nombre";
    # el campo del nombre es el offset que más veces es inicio (bonus si hay minúsculas).
    starts = np.zeros(rec, dtype=float)
    total = 0
    for i in sample:
        base = header + i * rec
        r = buf[base:base + rec]
        total += 1
        prev = False
        for off in range(rec - 2):
            s = r[off:].split(b"\0", 1)[0]
            cur = _looks_like_name(s)
            if cur and not prev:
                starts[off] += 1.5 if any(c.islower() for c in s.decode("utf-8")) else 1.0
            prev = cur
    best_name = None
    if total:
        off = int(np.argmax(starts))
        best_name = (starts[off] / total, off)
    if best_name is None or best_name[0] < 0.3:
        return None
    name_off = best_name[1]
    # longitud del campo: hasta el siguiente campo de texto o fin del registro
    name_len = 61 if rec - name_off >= 61 else rec - name_off
    layout = Layout(header, rec, id_off, name_off, name_len, score)
    layout.edit_compatible = (rec == 0xF0 and id_off == 0 and name_off == 54)
    return layout


@dataclass
class GameDB:
    names: dict[int, str] = field(default_factory=dict)
    raw: dict[int, bytes] = field(default_factory=dict)   # solo si el formato coincide con el EDIT
    sources: list[str] = field(default_factory=list)
    report: list[str] = field(default_factory=list)
    layout: dict | None = None

    def __len__(self):
        return len(self.names)


def _signature(cpks: list[str]) -> list:
    out = []
    for p in cpks:
        try:
            st = os.stat(p)
            out.append([p, st.st_size, int(st.st_mtime)])
        except OSError:
            pass
    return out


def load_game_db(game_dir: str, known_ids: set[int], progress=None, use_cache=True,
                 dump_dir: str | None = None) -> GameDB:
    """Escanea los .cpk, extrae Player.bin y devuelve nombres por ID."""
    db = GameDB()
    cpks = sorted(find_cpks(game_dir), key=lambda p: p.lower())
    db.report.append(f"Carpeta: {game_dir}")
    db.report.append(f"Archivos .cpk encontrados: {len(cpks)}")
    if not cpks:
        db.report.append("No hay .cpk: ¿es la carpeta de instalación del juego (la que contiene 'Data')?")
        return db
    sig = _signature(cpks)
    cache_path = os.path.join(config_dir(), "nombres_cache.json")
    if use_cache and not dump_dir:
        try:
            with open(cache_path, encoding="utf-8") as f:
                c = json.load(f)
            if c.get("version") == CACHE_VERSION and c.get("signature") == sig:
                db.names = {int(k): v for k, v in c["names"].items()}
                db.raw = {int(k): bytes.fromhex(v) for k, v in c.get("raw", {}).items()}
                db.sources = c.get("sources", [])
                db.layout = c.get("layout")
                db.report.append(f"Nombres cargados de la caché: {len(db.names)}")
                return db
        except (OSError, ValueError, KeyError):
            pass
    found = []
    for i, path in enumerate(cpks):
        if progress:
            progress(f"Leyendo índice {i + 1}/{len(cpks)}: {os.path.basename(path)}")
        try:
            cpk = Cpk(path)
        except (CpkError, OSError, struct.error, ValueError, IndexError) as e:
            db.report.append(f"  {os.path.basename(path)}: no legible ({e})")
            continue
        hits = [e for e in cpk.entries if e.name.lower() == PLAYER_FILE.lower()]
        others = [e.path for e in cpk.entries if "pesdb" in e.dir.lower()][:12]
        db.report.append(f"  {os.path.relpath(path, game_dir)}: {len(cpk.entries)} archivos"
                         + (f", Player.bin en {[h.path for h in hits]}" if hits else "")
                         + (f" | pesdb: {others}" if others and not hits else ""))
        for h in hits:
            found.append((cpk, h))
    if not found:
        db.report.append("No se encontró ningún Player.bin dentro de los .cpk.")
        return db
    for cpk, entry in found:          # en orden: lo más nuevo (download/dlc) pisa a lo base
        label = f"{os.path.basename(cpk.path)}:{entry.path}"
        if progress:
            progress(f"Descomprimiendo {label}…")
        try:
            buf = cpk.read(entry)
        except (CpkError, OSError, ValueError, IndexError) as e:
            db.report.append(f"  {label}: error al extraer ({e})")
            continue
        if dump_dir:
            safe = label.replace(":", "__").replace("/", "_")
            with open(os.path.join(dump_dir, safe), "wb") as f:
                f.write(buf)
        lay = detect_layout(buf, known_ids)
        if lay is None:
            db.report.append(f"  {label}: {len(buf)} bytes, formato no reconocido")
            continue
        db.report.append(f"  {label}: {len(buf)} bytes, registro {lay.rec_size} bytes (cabecera {lay.header}), "
                         f"ID en +{lay.id_off}, nombre en +{lay.name_off}, "
                         f"coincidencia de IDs {lay.score:.0%}, compatible EDIT: {lay.edit_compatible}")
        db.layout = lay.__dict__
        n = (len(buf) - lay.header) // lay.rec_size
        for i in range(n):
            base = lay.header + i * lay.rec_size
            pid = struct.unpack_from("<I", buf, base + lay.id_off)[0]
            if not pid:
                continue
            nm = buf[base + lay.name_off:base + lay.name_off + lay.name_len].split(b"\0", 1)[0]
            try:
                name = nm.decode("utf-8").strip()
            except UnicodeDecodeError:
                continue
            if name:
                db.names[pid] = name
            if lay.edit_compatible:
                db.raw[pid] = bytes(buf[base:base + lay.rec_size])
        db.sources.append(label)
    db.report.append(f"Total de nombres: {len(db.names)} | con datos completos: {len(db.raw)}")
    if known_ids:
        cov = len(known_ids & set(db.names)) / len(known_ids)
        db.report.append(f"Jugadores de las plantillas con nombre: {cov:.0%}")
    if not dump_dir:
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({"version": CACHE_VERSION, "signature": sig, "created": time.time(),
                           "names": db.names, "raw": {k: v.hex() for k, v in db.raw.items()},
                           "sources": db.sources, "layout": db.layout}, f, ensure_ascii=False)
        except OSError:
            pass
    return db
