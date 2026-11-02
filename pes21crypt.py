"""
Cifrado / descifrado del archivo EDIT00000000 de eFootball PES 2021 (PC).

Port a Python del pesXdecrypter de the4chancup (dominio publico / Unlicense).
Usa numpy para que el cifrado de ~10 MB tarde menos de un segundo.
"""
import struct

import numpy as np

MASTER_KEY_PES21 = bytes([
    0x90, 0x61, 0xD8, 0x66, 0x43, 0x77, 0x24, 0xF8,
    0x92, 0xBA, 0xB8, 0x71, 0x21, 0xC7, 0x60, 0x63,
    0xF0, 0x91, 0x9A, 0x7D, 0xED, 0x47, 0x80, 0xDE,
    0x51, 0xF5, 0xDD, 0xD1, 0x08, 0xFE, 0x32, 0x84,
    0xF5, 0x09, 0x92, 0x00, 0xB2, 0x3E, 0x88, 0x9F,
    0xEB, 0x24, 0x43, 0x05, 0x58, 0x76, 0x00, 0x22,
    0x9B, 0xFE, 0xEC, 0xF6, 0x50, 0x00, 0x29, 0xD3,
    0x42, 0x75, 0x50, 0xB9, 0xEC, 0xD2, 0xF6, 0x75,
])

ENCRYPTION_HEADER_SIZE = 320
# FileHeader de PES18+: 64 misterio + 4 tamanos + 64 hash + 32 tipo + 32 version
FILE_HEADER_SIZE = 208
_M32 = 0xFFFFFFFF


# ---------------------------------------------------------------- MT19937
def _mt_state_from_key(key64: bytes) -> np.ndarray:
    """init_by_array de MT19937 con 16 palabras de 32 bits (little endian)."""
    init_key = struct.unpack("<16I", key64)
    n = 624
    mt = [0] * n
    mt[0] = 19650218
    for i in range(1, n):
        mt[i] = (1812433253 * (mt[i - 1] ^ (mt[i - 1] >> 30)) + i) & _M32
    i, j = 1, 0
    klen = len(init_key)
    for _ in range(max(n, klen)):
        mt[i] = ((mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1664525)) + init_key[j] + j) & _M32
        i += 1
        j += 1
        if i >= n:
            mt[0] = mt[n - 1]
            i = 1
        if j >= klen:
            j = 0
    for _ in range(n - 1):
        mt[i] = ((mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1566083941)) - i) & _M32
        i += 1
        if i >= n:
            mt[0] = mt[n - 1]
            i = 1
    mt[0] = 0x80000000
    return np.array(mt, dtype=np.uint32)


def _mt_outputs(key64: bytes, count: int) -> np.ndarray:
    bg = np.random.MT19937()
    bg.state = {"bit_generator": "MT19937",
                "state": {"key": _mt_state_from_key(key64), "pos": 624}}
    return bg.random_raw(count).astype(np.uint32)


def _rol(x, s):
    return ((x << np.uint32(s)) | (x >> np.uint32(32 - s))).astype(np.uint32)


def _ror(x, s):
    return ((x >> np.uint32(s)) | (x << np.uint32(32 - s))).astype(np.uint32)


def _keystream(key64: bytes, words: int) -> np.ndarray:
    """Palabras XOR que aplica cryptStream() para 'words' bloques de 4 bytes."""
    g = _mt_outputs(key64, words + 4)
    ks = np.empty(words, dtype=np.uint32)
    # Primeras iteraciones (las rotaciones aun no estan en regimen estable)
    c0, c1, c2, c3 = (int(v) for v in g[:4])
    r32 = lambda a, s: ((a >> s) | (a << (32 - s))) & _M32
    l32 = lambda a, s: ((a << s) | (a >> (32 - s))) & _M32
    head = min(words, 4)
    for i in range(head):
        c4 = int(g[i + 4])
        ks[i] = c4 ^ c3 ^ c2 ^ c1 ^ c0
        c0, c1, c2, c3 = r32(c1, 15), l32(c2, 11), l32(c3, 7), r32(c4, 13)
    if words > 4:
        i = np.arange(4, words)
        ks[4:] = (g[i + 4] ^ _ror(g[i + 3], 13) ^ _ror(g[i + 2], 6)
                  ^ _rol(g[i + 1], 5) ^ _ror(g[i], 10))
    return ks


def crypt_stream(key64: bytes, data: bytes) -> bytes:
    """Simetrico: sirve tanto para cifrar como para descifrar."""
    n = len(data)
    if n == 0:
        return b""
    words = (n + 3) // 4
    padded = np.frombuffer(bytes(data) + b"\0" * (words * 4 - n), dtype="<u4")
    out = (padded ^ _keystream(key64, words)).astype("<u4").tobytes()
    return out[:n]


# --------------------------------------------------------------- helpers
def _xor_repeating(out: bytearray, inp: bytes):
    for i, b in enumerate(inp):
        out[i & 63] ^= b


def _xor_long(key64: bytes, param: int) -> bytes:
    vals = struct.unpack("<8Q", key64)
    return struct.pack("<8Q", *[v ^ param for v in vals])


def _reverse_longs(key64: bytes) -> bytes:
    return b"".join(key64[i * 8:(i + 1) * 8][::-1] for i in range(8))


def _crypt_header(raw320: bytes, master: bytes) -> bytes:
    header_key = bytearray(raw320[256:320])
    _xor_repeating(header_key, _reverse_longs(master))
    out = bytearray(crypt_stream(bytes(header_key), raw320[:ENCRYPTION_HEADER_SIZE]))
    out[256:320] = raw320[256:320]
    return bytes(out)


def _rolling_key(enc_header: bytes) -> bytes:
    rk = bytearray(enc_header[:64])
    _xor_repeating(rk, enc_header[64:320])
    return bytes(rk)


# ------------------------------------------------------------ API publica
class EditFile:
    """Contenido descifrado de un EDIT00000000."""

    def __init__(self, enc_header, file_header, description, logo, data, serial):
        self.enc_header = enc_header        # 320 bytes descifrados
        self.file_header = bytearray(file_header)  # 208 bytes
        self.description = description
        self.logo = logo
        self.data = bytearray(data)        # aqui estan jugadores y equipos
        self.serial = serial

    @property
    def game_version(self) -> str:
        return bytes(self.file_header[176:208]).split(b"\0")[0].decode("ascii", "replace")

    @property
    def file_type(self) -> str:
        return bytes(self.file_header[144:176]).split(b"\0")[0].decode("ascii", "replace")


def decrypt(raw: bytes, master: bytes = MASTER_KEY_PES21) -> EditFile:
    if len(raw) < ENCRYPTION_HEADER_SIZE + FILE_HEADER_SIZE:
        raise ValueError("El archivo es demasiado pequeno para ser un EDIT de PES.")
    enc_header = _crypt_header(raw[:ENCRYPTION_HEADER_SIZE], master)
    rk = _rolling_key(enc_header)
    pos = ENCRYPTION_HEADER_SIZE
    fh = crypt_stream(_xor_long(rk, FILE_HEADER_SIZE), raw[pos:pos + FILE_HEADER_SIZE])
    pos += FILE_HEADER_SIZE
    data_size, logo_size, desc_size, serial_len = struct.unpack_from("<4I", fh, 64)
    expected = (ENCRYPTION_HEADER_SIZE + FILE_HEADER_SIZE + data_size + logo_size
                + desc_size + serial_len * 2)
    if expected != len(raw):
        raise ValueError(
            "No se pudo descifrar: el archivo no parece un EDIT de PES 2021 de PC "
            f"(tamano esperado {expected}, real {len(raw)}).")
    parts = []
    for idx, size in ((0, desc_size), (1, logo_size), (2, data_size), (3, serial_len * 2)):
        parts.append(crypt_stream(_xor_long(rk, idx), raw[pos:pos + size]))
        pos += size
    desc, logo, data, serial = parts
    return EditFile(enc_header, fh, desc, logo, data, serial)


def encrypt(ef: EditFile, master: bytes = MASTER_KEY_PES21) -> bytes:
    fh = bytearray(ef.file_header)
    struct.pack_into("<4I", fh, 64, len(ef.data), len(ef.logo),
                     len(ef.description), len(ef.serial) // 2)
    rk = _rolling_key(ef.enc_header)
    out = [_crypt_header(ef.enc_header, master),
           crypt_stream(_xor_long(rk, FILE_HEADER_SIZE), bytes(fh))]
    for idx, part in ((0, ef.description), (1, ef.logo), (2, bytes(ef.data)), (3, ef.serial)):
        out.append(crypt_stream(_xor_long(rk, idx), part))
    return b"".join(out)


def load(path: str) -> EditFile:
    with open(path, "rb") as f:
        return decrypt(f.read())


def save(ef: EditFile, path: str):
    blob = encrypt(ef)
    with open(path, "wb") as f:
        f.write(blob)
