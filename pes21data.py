"""
Modelo de datos del EDIT00000000 de eFootball PES 2021 (PC).

Offsets y campos de bits tomados de 4ccEditor (the4chancup, licencia zlib),
archivo pes20.cpp + main.cpp (rama PES 20/21).

Los campos se leen y escriben directamente sobre los bytes descifrados, de modo
que todo lo que el editor no toca queda exactamente igual que en el original.
"""
from __future__ import annotations

import struct

# ------------------------------------------------------------- offsets PES21
OFF_NUM_PLAYERS = 96
OFF_NUM_TEAMS = 100
OFF_PLAYERS = 0x7C
PLAYER_SIZE = 0x138            # 0xF0 de datos + 0x48 de apariencia
PLAYER_CAPACITY = 30000        # (OFF_TEAMS - OFF_PLAYERS) / PLAYER_SIZE
OFF_TEAMS = 0x8ED2FC
TEAM_SIZE = 0x24C
OFF_ROSTERS = 0x9D4648
ROSTER_SIZE = 0x11C
OFF_TACTICS = 0xA09880
TACTICS_SIZE = 0x274
TACT_STARTING11 = 0x1E4
TACT_CAPTAIN = 0x215
ROSTER_SLOTS = 40

# ------------------------------------------------------------- textos (ES)
POSITIONS = ["PT", "DFC", "LI", "LD", "MCD", "MC", "MI", "MD", "MCO",
             "EI", "ED", "SD", "DC"]          # orden de reg_pos (0..12)
POSITIONS_LONG = ["Portero", "Defensa central", "Lateral izquierdo",
                  "Lateral derecho", "Mediocentro defensivo", "Mediocentro",
                  "Interior izquierdo", "Interior derecho",
                  "Mediapunta", "Extremo izquierdo", "Extremo derecho",
                  "Segundo delantero", "Delantero centro"]
# Campo de "posicion jugable" que corresponde a cada posicion (mismo orden)
PLAYABLE_FIELDS = ["pos_GK", "pos_CB", "pos_LB", "pos_RB", "pos_DMF", "pos_CMF",
                   "pos_LMF", "pos_RMF", "pos_AMF", "pos_LWF", "pos_RWF",
                   "pos_SS", "pos_CF"]

PLAY_STYLES = ["Ninguno", "Cazagoles", "Señuelo", "Hombre de área", "Delantero centro (target)",
               "Creador de jugadas", "Extremo prolífico", "Extremo móvil",
               "Especialista en centros", "10 clásico", "Jugador de huecos",
               "Box to box", "Destructor", "Organizador", "Ancla",
               "Lateral ofensivo", "Lateral finalizador", "Lateral defensivo",
               "Salida de balón", "Atacante extra", "Portero ofensivo",
               "Portero defensivo"]

# (campo, etiqueta) de habilidades de 7 bits, rango 40-99
ABILITIES = [
    ("atk", "Actitud ofensiva"), ("ball_ctrl", "Control de balón"),
    ("drib", "Regate"), ("tight_pos", "Posesión estrecha"),
    ("lowpass", "Pase al ras"), ("loftpass", "Pase bombeado"),
    ("finish", "Finalización"), ("header", "Cabezazo"),
    ("place_kick", "Balón parado"), ("swerve", "Efecto"),
    ("speed", "Velocidad"), ("exp_pwr", "Aceleración"),
    ("kick_pwr", "Potencia de tiro"), ("jump", "Salto"),
    ("phys_cont", "Contacto físico"), ("body_ctrl", "Equilibrio"),
    ("stamina", "Resistencia"), ("def", "Actitud defensiva"),
    ("ball_win", "Recuperación"), ("aggres", "Agresividad"),
    ("gk", "Actitud de portero"), ("catching", "Atajar"),
    ("clearing", "Despejar"), ("reflex", "Reflejos"),
    ("cover", "Cobertura (PT)"),
]

SKILLS = ["Tijera", "Flip flap", "Ruleta (Marsella)", "Sombrero", "Recorte y giro",
          "Bicicleta escocesa", "Cabezazo", "Tiro lejano potente", "Tiro con nudillo",
          "Remate acrobático", "Taconazo", "Disparo de primera", "Pase al primer toque",
          "Pase medido", "Centro preciso", "Rosca exterior", "Rabona",
          "Pase bombeado bajo", "Saque bajo (PT)", "Saque de banda largo",
          "Saque largo (PT)", "Malicia", "Marcaje", "Repliegue",
          "Despeje acrobático", "Capitanía", "Revulsivo", "Espíritu de lucha",
          "Doble toque", "Giro cruzado", "Pisada", "Vaselina", "Tiro con caída",
          "Tiro ascendente", "Pase sin mirar", "Saque alto (PT)",
          "Especialista en penaltis", "Parapenaltis (PT)", "Interceptación",
          "Tiro de larga distancia", "Pase al hueco"]

COM_STYLES = ["Trucos (Trickster)", "Regateador (Mazing Runner)",
              "Bala (Speeding Bullet)", "Desmarque incisivo (Incisive Run)",
              "Pase largo (Long Ball Expert)", "Centro temprano (Early Cross)",
              "Tirador lejano (Long Ranger)"]

PHYSIQUE = [("head_len", "Longitud de cabeza"), ("head_wid", "Anchura de cabeza"),
            ("head_dep", "Profundidad de cabeza"), ("neck_len", "Longitud del cuello"),
            ("neck_size", "Grosor del cuello"), ("shldr_hi", "Altura de hombros"),
            ("shldr_wid", "Anchura de hombros"), ("chest", "Pecho"), ("waist", "Cintura"),
            ("arm_size", "Grosor de brazos"), ("arm_len", "Longitud de brazos"),
            ("thigh", "Muslos"), ("calf", "Gemelos"), ("leg_len", "Longitud de piernas")]
SKIN_COLORS = ["Por defecto", "Clara", "Pálida", "Media", "Oliva", "Morena", "Negra"]
EYE_COLORS = ["Negro", "Castaño oscuro", "Castaño", "Marrón claro", "Azul marino", "Carbón",
              "Gris", "Azul", "Siena", "Verde", "Violeta"]
WRIST_TAPE = ["Ninguna", "Derecha", "Izquierda", "Ambas"]
SPEC_STYLES = ["Ninguna", "Rectangular (sin montura)", "Rectangular (media montura)",
               "Rectangular (montura completa)", "Ovalada (sin montura)", "Ovalada (media montura)",
               "Ovalada (montura completa)", "Redonda (montura completa)"]
SPEC_COLORS = ["Blanco", "Negro", "Rojo", "Azul", "Amarillo", "Verde", "Rosa", "Turquesa"]
SLEEVES = ["Según temporada", "Corta", "Larga"]
INNERS = ["Ninguna", "Normal", "Cuello alto"]
SOCKS = ["Estándar", "Largas", "Cortas"]
UNDERSHORTS = ["Verano: no / Invierno: no", "Verano: cortas / Invierno: cortas",
               "Verano: no / Invierno: largas", "Verano: cortas / Invierno: largas"]
SHIRTTAIL = ["Por dentro", "Por fuera"]
HANDS = ["Derecha", "Izquierda"]
# (campo, etiqueta, mínimo mostrado, máximo mostrado, desplazamiento guardado = mostrado - offset)
MOTIONS = [("mo_hunchd", "Encorvado al regatear", 1, 5, 1), ("mo_armd", "Brazos al regatear", 1, 10, 1),
           ("mo_hunchr", "Encorvado al correr", 1, 5, 1), ("mo_armr", "Brazos al correr", 1, 10, 1),
           ("mo_ck", "Saque de esquina", 1, 10, 1), ("mo_fk", "Tiro libre", 1, 20, 1),
           ("mo_pk", "Penalti", 1, 7, 1), ("mo_drib", "Animación de regate", 0, 3, 0),
           ("gc1", "Celebración 1", 0, 162, 0), ("gc2", "Celebración 2", 0, 162, 0)]

# ------------------------------------------------- secuencia de campos (pes20.cpp)
# ("nombre", bit_inicio, bits) | ("+", bytes_a_saltar) | ("str", nombre, bytes)
_skill_order = [0, 28, 1, 2, 3, 29, 4, 5, 30, 6, 7, 31, 39, 8, 32, 33, 9, 10, 11,
                12, 40, 13, 14, 15, 16, 34, 17, 18, 35, 19, 20, 36, 37, 21, 22, 23,
                38, 24, 25, 26, 27]

_PLAYER_SEQ = [
    ("id", 0, 32), ("+", 4), ("nation", 0, 16), ("height", 0, 8), ("weight", 0, 8),
    ("gc1", 0, 8), ("gc2", 0, 8),
    ("atk", 0, 7), ("ball_ctrl", 7, 7), ("weak_use", 6, 2), ("tight_pos", 0, 7),
    ("lowpass", 7, 7), ("loftpass", 6, 7), ("finish", 5, 7), ("mo_armd", 4, 4),
    ("place_kick", 0, 7), ("swerve", 7, 7), ("speed", 6, 7), ("exp_pwr", 5, 7),
    ("mo_armr", 4, 4), ("jump", 0, 7), ("phys_cont", 7, 7), ("body_ctrl", 6, 7),
    ("stamina", 5, 7), ("mo_ck", 4, 4), ("ball_win", 0, 7), ("aggres", 7, 7),
    ("gk", 6, 7), ("catching", 5, 7), ("form", 4, 3), ("b_edit_player", 7, 1),
    ("cover", 0, 7), ("age", 7, 6), ("reg_pos", 5, 4), ("play_style", 2, 5),
    ("mo_fk", 7, 5), ("star", 4, 3), ("b_edit_basicset", 7, 1), ("def", 0, 7),
    ("clearing", 7, 7), ("header", 6, 7), ("mo_hunchd", 5, 3), ("mo_hunchr", 0, 3),
    ("mo_pk", 3, 3), ("weak_acc", 6, 2), ("drib", 0, 7), ("injury", 7, 2),
    ("play_attit", 1, 2), ("mo_drib", 3, 2),
    ("pos_GK", 5, 2), ("pos_CB", 7, 2), ("pos_LB", 1, 2), ("pos_RB", 3, 2),
    ("pos_DMF", 5, 2), ("pos_CMF", 7, 2), ("pos_LMF", 1, 2), ("pos_RMF", 3, 2),
    ("pos_AMF", 5, 2), ("b_edit_regpos", 7, 1), ("pos_RWF", 0, 2), ("pos_SS", 2, 2),
    ("pos_CF", 4, 2), ("reflex", 6, 7), ("kick_pwr", 5, 7), ("pos_LWF", 4, 2),
    ("b_edit_playpos", 6, 1), ("b_edit_ability", 7, 1), ("b_edit_skill", 0, 1),
    ("b_edit_style", 1, 1), ("b_edit_com", 2, 1), ("b_edit_motion", 3, 1),
    ("strong_foot", 5, 1), ("strong_hand", 6, 1),
] + [(f"com{i}", (7 + i) % 8, 1) for i in range(7)] \
  + [(f"skill{s}", (6 + k) % 8, 1) for k, s in enumerate(_skill_order)] + [
    ("+", 1),
    ("str", "name", 61), ("str", "shirt_name", 61), ("str", "print_name", 64),
    # --- apariencia
    ("+", 4), ("b_edit_face", 0, 1), ("b_edit_hair", 1, 1), ("b_edit_phys", 2, 1),
    ("b_edit_strip", 3, 1), ("boot_id", 4, 14), ("glove_id", 2, 14),
    ("copy_id", 0, 32),
    ("neck_len", 0, 4), ("neck_size", 4, 4), ("shldr_hi", 0, 4), ("shldr_wid", 4, 4),
    ("chest", 0, 4), ("waist", 4, 4), ("arm_size", 0, 4), ("arm_len", 4, 4),
    ("thigh", 0, 4), ("calf", 4, 4), ("leg_len", 0, 4), ("head_len", 4, 4),
    ("head_wid", 0, 4), ("head_dep", 4, 4),
    ("wrist_col_l", 0, 3), ("wrist_col_r", 3, 3), ("wrist_tape", 6, 2),
    ("spec_col", 0, 3), ("spec_style", 3, 3), ("sleeve", 6, 2),
    ("inners", 0, 2), ("socks", 2, 2), ("undershorts", 4, 2), ("untucked", 6, 1), ("ankle_tape", 7, 1),
    ("gloves", 0, 1), ("gloves_col", 1, 3), ("+", 23),        # (datos de cara: sin documentar)
    ("skin_col", 0, 3), ("+", 19),
    ("iris_col", 0, 4), ("+", 8),                            # (pelo: sin documentar)
]

_TEAM_SEQ = [
    ("id", 0, 32), ("manager_id", 0, 32), ("+", 2), ("stadium_id", 0, 16),
    ("+", 0xA), ("color1_red", 2, 6), ("color1_green", 0, 6), ("b_edit_name", 6, 1),
    ("b_edit_emblem", 7, 1), ("color2_green", 0, 6), ("color2_blue", 6, 6), ("+", 2),
    ("b_edit_stadium", 6, 1), ("b_edit_stadium_name", 7, 1), ("+", 2), ("color1_blue", 0, 6),
    ("color2_red", 6, 6), ("+", 0x39),
    ("rival1", 0, 32), ("rival2", 0, 32), ("rival3", 0, 32), ("banner_flags", 0, 32),
    ("str", "name", 0x46), ("str", "short_name", 4),
    ("str", "stadium_name", 181),
    ("str", "banner1", 16), ("str", "banner2", 16), ("str", "banner3", 16), ("str", "banner4", 16),
]


def _layout(seq):
    """Simula el cursor de read_data() de 4ccEditor y devuelve offsets absolutos."""
    fields, strings = {}, {}
    cb = 0
    for item in seq:
        if item[0] == "+":
            cb += item[1]
        elif item[0] == "str":
            strings[item[1]] = (cb, item[2])
            cb += item[2]
        else:
            name, sb, bits = item
            fields[name] = (cb * 8 + sb, bits)
            cb += (sb + bits) // 8
    return fields, strings, cb


PLAYER_FIELDS, PLAYER_STRINGS, _pend = _layout(_PLAYER_SEQ)
TEAM_FIELDS, TEAM_STRINGS, _tend = _layout(_TEAM_SEQ)
# Comprobaciones de coherencia con los tamanos que usa 4ccEditor
assert PLAYER_STRINGS["name"][0] + 61 + 61 + 64 == 0xF0, "layout jugador"
assert PLAYER_FIELDS["copy_id"][0] // 8 == 0xF0 + 8, "layout apariencia"
assert _pend == PLAYER_SIZE and PLAYER_FIELDS["skin_col"][0] // 8 == 0xF0 + 0x2D \
    and PLAYER_FIELDS["iris_col"][0] // 8 == 0xF0 + 0x40, "layout apariencia (fin)"
assert TEAM_STRINGS["banner4"][0] + 16 + 165 == TEAM_SIZE, "layout equipo (textos)"
assert TEAM_STRINGS["short_name"][0] + 4 + 181 + 64 + 165 == TEAM_SIZE, "layout equipo"


# ------------------------------------------------------------- bits
def get_bits(buf, base: int, bitpos: int, nbits: int) -> int:
    start = base + bitpos // 8
    end = base + (bitpos + nbits + 7) // 8
    v = int.from_bytes(buf[start:end], "little")
    return (v >> (bitpos % 8)) & ((1 << nbits) - 1)


def set_bits(buf, base: int, bitpos: int, nbits: int, value: int):
    start = base + bitpos // 8
    end = base + (bitpos + nbits + 7) // 8
    shift = bitpos % 8
    mask = ((1 << nbits) - 1) << shift
    v = int.from_bytes(buf[start:end], "little")
    v = (v & ~mask) | ((int(value) << shift) & mask)
    buf[start:end] = v.to_bytes(end - start, "little")


def _read_str(buf, off, size) -> str:
    raw = bytes(buf[off:off + size]).split(b"\0")[0]
    return raw.decode("utf-8", "replace")


def _write_str(buf, off, size, text: str, limit: int | None = None):
    limit = min(limit or size - 1, size - 1)
    data = text.encode("utf-8")
    while len(data) > limit:               # no cortar un caracter multibyte
        text = text[:-1]
        data = text.encode("utf-8")
    buf[off:off + size] = data + b"\0" * (size - len(data))


# ------------------------------------------------------------- entidades
class Player:
    def __init__(self, db: "EditDB", index: int):
        self.db = db
        self.index = index
        self.base = OFF_PLAYERS + index * PLAYER_SIZE

    def __getitem__(self, field):
        if field in PLAYER_STRINGS:
            off, size = PLAYER_STRINGS[field]
            return _read_str(self.db.data, self.base + off, size)
        bitpos, nbits = PLAYER_FIELDS[field]
        return get_bits(self.db.data, self.base, bitpos, nbits)

    def __setitem__(self, field, value):
        if field in PLAYER_STRINGS:
            off, size = PLAYER_STRINGS[field]
            limit = 20 if field == "shirt_name" else None   # 4ccEditor: 20 bytes
            _write_str(self.db.data, self.base + off, size, str(value), limit)
            self.db.dirty = True
            if field == "name":
                self["b_edit_player"] = 1
            return
        bitpos, nbits = PLAYER_FIELDS[field]
        value = int(value)
        if not 0 <= value < (1 << nbits):
            raise ValueError(f"{field}: {value} fuera de rango (0-{(1 << nbits) - 1})")
        set_bits(self.db.data, self.base, bitpos, nbits, value)
        self.db.dirty = True

    @property
    def id(self):
        return self["id"]

    @property
    def name(self):
        return self["name"]

    def overall(self) -> int:
        """Media simple de habilidades para ordenar (no es la media oficial del juego)."""
        if self["reg_pos"] == 0:
            keys = ["gk", "catching", "clearing", "reflex", "cover"]
        else:
            keys = [k for k, _ in ABILITIES if k not in ("gk", "catching", "clearing", "reflex", "cover")]
        return round(sum(self[k] for k in keys) / len(keys))

    def raw(self) -> bytes:
        return bytes(self.db.data[self.base:self.base + PLAYER_SIZE])


class RawPlayer(Player):
    """Vista de solo lectura de un registro de la base del juego (mismo formato que el EDIT)."""

    def __init__(self, raw: bytes):
        holder = type("Holder", (), {})()
        holder.data = bytearray(raw) + bytearray(PLAYER_SIZE - len(raw))
        holder.dirty = False
        self.db = holder
        self.index = -1
        self.base = 0


class Team:
    def __init__(self, db: "EditDB", index: int):
        self.db = db
        self.index = index
        self.base = OFF_TEAMS + index * TEAM_SIZE
        self.roster_base: int | None = None
        self.tactics_base: int | None = None

    def __getitem__(self, field):
        if field in TEAM_STRINGS:
            off, size = TEAM_STRINGS[field]
            return _read_str(self.db.data, self.base + off, size)
        bitpos, nbits = TEAM_FIELDS[field]
        return get_bits(self.db.data, self.base, bitpos, nbits)

    def __setitem__(self, field, value):
        if field in TEAM_STRINGS:
            off, size = TEAM_STRINGS[field]
            limit = {"short_name": 3, "stadium_name": 180}.get(field, 15 if field.startswith("banner") else None)
            _write_str(self.db.data, self.base + off, size, str(value), limit)
            if field == "name":
                self["b_edit_name"] = 1
            elif field == "stadium_name":
                self["b_edit_stadium_name"] = 1
            self.db.dirty = True
            return
        bitpos, nbits = TEAM_FIELDS[field]
        if not 0 <= int(value) < (1 << nbits):
            raise ValueError(f"{field}: {value} fuera de rango (0-{(1 << nbits) - 1})")
        set_bits(self.db.data, self.base, bitpos, nbits, int(value))
        self.db.dirty = True

    @property
    def id(self):
        return self["id"]

    @property
    def name(self):
        return self["name"]

    # Colores: 6 bits por canal (0-63) -> se muestran como #RRGGBB
    def color(self, n: int) -> str:
        r, g, b = (self[f"color{n}_{c}"] for c in ("red", "green", "blue"))
        return "#%02x%02x%02x" % tuple(round(v * 255 / 63) for v in (r, g, b))

    def set_color(self, n: int, hexcolor: str):
        hexcolor = hexcolor.lstrip("#")
        for i, c in enumerate(("red", "green", "blue")):
            self[f"color{n}_{c}"] = round(int(hexcolor[i * 2:i * 2 + 2], 16) * 63 / 255)

    # --- plantilla
    def roster(self) -> list[tuple[int, int]]:
        """Lista de (player_id, dorsal) en orden; termina en el primer hueco."""
        if self.roster_base is None:
            return []
        d, rb = self.db.data, self.roster_base
        out = []
        for i in range(ROSTER_SLOTS):
            pid = struct.unpack_from("<I", d, rb + 4 + i * 4)[0]
            if pid == 0:
                break
            num = struct.unpack_from("<H", d, rb + 4 + 160 + i * 2)[0]
            out.append((pid, num))
        return out

    def _slot_extra(self, i) -> int:
        return self.db.data[self.roster_base + 4 + 160 + 80 + i]

    def _write_roster(self, entries: list[tuple[int, int, int]]):
        """entries: (player_id, dorsal, byte_extra) por hueco."""
        d, rb = self.db.data, self.roster_base
        for i in range(ROSTER_SLOTS):
            pid, num, extra = entries[i] if i < len(entries) else (0, 0, 0)
            struct.pack_into("<I", d, rb + 4 + i * 4, pid)
            struct.pack_into("<H", d, rb + 4 + 160 + i * 2, num)
            d[rb + 4 + 240 + i] = extra
        self.db.dirty = True

    def starting11(self) -> list[int]:
        if self.tactics_base is None:
            return []
        tb = self.tactics_base + TACT_STARTING11
        return list(self.db.data[tb:tb + 11])

    def captain(self) -> int:
        if self.tactics_base is None:
            return -1
        return self.db.data[self.tactics_base + TACT_CAPTAIN]

    def set_number(self, slot: int, number: int):
        if not 1 <= int(number) <= 99:
            raise ValueError("El dorsal debe estar entre 1 y 99")
        struct.pack_into("<H", self.db.data, self.roster_base + 4 + 160 + slot * 2, int(number))
        self.db.dirty = True

    def set_captain(self, slot: int):
        self.db.data[self.tactics_base + TACT_CAPTAIN] = slot
        self.db.dirty = True


# ------------------------------------------------------------- base de datos
class EditDB:
    def __init__(self, edit_file):
        self.ef = edit_file
        self.data = edit_file.data
        self.dirty = False
        self.num_players = struct.unpack_from("<H", self.data, OFF_NUM_PLAYERS)[0]
        self.num_teams = struct.unpack_from("<H", self.data, OFF_NUM_TEAMS)[0]
        if not (0 <= self.num_players <= PLAYER_CAPACITY and 0 < self.num_teams < 2000):
            raise ValueError(
                f"Los datos no cuadran con PES 2021 (jugadores={self.num_players}, "
                f"equipos={self.num_teams}). ¿Es un EDIT de PES 2021 de PC?")
        if len(self.data) < OFF_TACTICS + self.num_teams * TACTICS_SIZE:
            raise ValueError("El archivo es más pequeño de lo esperado para PES 2021.")
        self.players = [Player(self, i) for i in range(self.num_players)]
        self.teams = [Team(self, i) for i in range(self.num_teams)]
        self._index()

    def _index(self):
        self.player_by_id = {p.id: p for p in self.players}
        self.team_by_id = {t.id: t for t in self.teams}
        for i in range(self.num_teams):
            rb = OFF_ROSTERS + i * ROSTER_SIZE
            tid = struct.unpack_from("<I", self.data, rb)[0]
            if tid in self.team_by_id:
                self.team_by_id[tid].roster_base = rb
            tb = OFF_TACTICS + i * TACTICS_SIZE
            tid = struct.unpack_from("<I", self.data, tb)[0]
            if tid in self.team_by_id:
                self.team_by_id[tid].tactics_base = tb
        self.refresh_membership()

    def refresh_membership(self):
        self.teams_of = {}
        for t in self.teams:
            for pid, _ in t.roster():
                self.teams_of.setdefault(pid, []).append(t)

    def visible_teams(self) -> list[Team]:
        return [t for t in self.teams if t.roster()]

    def free_agents(self) -> list[Player]:
        return [p for p in self.players if p.id and p.id not in self.teams_of]

    # ---------------------------------------------------------- traspasos
    def remove_from_team(self, team: Team, player_id: int):
        entries = [(pid, num, team._slot_extra(i)) for i, (pid, num) in enumerate(team.roster())]
        slot = next((i for i, e in enumerate(entries) if e[0] == player_id), None)
        if slot is None:
            raise ValueError("El jugador no está en ese equipo")
        if len(entries) <= 1:
            raise ValueError("No se puede dejar un equipo sin jugadores")
        del entries[slot]
        team._write_roster(entries)
        self._fix_tactics_after_removal(team, slot, len(entries))
        self.refresh_membership()

    def _fix_tactics_after_removal(self, team: Team, removed: int, new_size: int):
        if team.tactics_base is None:
            return
        d, tb = self.data, team.tactics_base
        lineup = [d[tb + TACT_STARTING11 + k] for k in range(11)]
        lineup = [x - 1 if x > removed else x for x in lineup]
        if removed in lineup:
            # Sustituir al titular eliminado por el primer suplente disponible
            bench = [i for i in range(new_size) if i not in lineup]
            k = lineup.index(removed)
            lineup[k] = bench[0] if bench else 0
        for k in range(11):
            d[tb + TACT_STARTING11 + k] = lineup[k]
        cap = d[tb + TACT_CAPTAIN]
        if cap == removed:
            cap = lineup[0]
        elif cap > removed:
            cap -= 1
        d[tb + TACT_CAPTAIN] = cap
        self.dirty = True

    def add_to_team(self, team: Team, player_id: int, number: int | None = None):
        roster = team.roster()
        if any(pid == player_id for pid, _ in roster):
            raise ValueError("El jugador ya está en ese equipo")
        if len(roster) >= ROSTER_SLOTS:
            raise ValueError(f"{team.name} ya tiene {ROSTER_SLOTS} jugadores (máximo)")
        used = {n for _, n in roster}
        if number is None or number in used:
            number = next(n for n in range(1, 100) if n not in used)
        entries = [(pid, num, team._slot_extra(i)) for i, (pid, num) in enumerate(roster)]
        entries.append((player_id, number, 0))
        team._write_roster(entries)
        self.refresh_membership()
        return number

    def transfer(self, player_id: int, from_team: Team | None, to_team: Team,
                 number: int | None = None):
        if from_team is to_team:
            raise ValueError("El equipo de origen y destino es el mismo")
        if len(to_team.roster()) >= ROSTER_SLOTS:
            raise ValueError(f"{to_team.name} ya tiene {ROSTER_SLOTS} jugadores (máximo)")
        if from_team is not None:
            self.remove_from_team(from_team, player_id)
        return self.add_to_team(to_team, player_id, number)

    def swap_slots(self, team: Team, a: int, b: int):
        """Intercambia dos huecos de la plantilla (y ajusta alineación/capitán)."""
        roster = team.roster()
        entries = [(pid, num, team._slot_extra(i)) for i, (pid, num) in enumerate(roster)]
        entries[a], entries[b] = entries[b], entries[a]
        team._write_roster(entries)
        d, tb = self.data, team.tactics_base
        if tb is not None:
            for k in list(range(TACT_STARTING11, TACT_STARTING11 + 11)) + [TACT_CAPTAIN]:
                if d[tb + k] == a:
                    d[tb + k] = b
                elif d[tb + k] == b:
                    d[tb + k] = a

    # ---------------------------------------------------------- crear jugador
    def next_free_id(self) -> int:
        used = set(self.player_by_id) | set(self.teams_of)
        return max(used, default=0) + 1

    def create_player(self, template: Player, name: str) -> Player:
        """Añade un registro nuevo copiando otro como plantilla (EXPERIMENTAL)."""
        if self.num_players >= PLAYER_CAPACITY:
            raise ValueError("No queda espacio para más jugadores en el archivo")
        new = Player(self, self.num_players)
        raw = template.raw()
        self.data[new.base:new.base + PLAYER_SIZE] = raw
        new_id = self.next_free_id()
        new["id"] = new_id
        set_bits(self.data, new.base, (0xF0) * 8, 32, new_id)  # id de la apariencia
        new["name"] = name
        new["shirt_name"] = name.split(" ")[-1].upper()
        new["print_name"] = ""
        new["b_edit_player"] = 1
        self.num_players += 1
        struct.pack_into("<H", self.data, OFF_NUM_PLAYERS, self.num_players)
        self.players.append(new)
        self.player_by_id[new_id] = new
        self.dirty = True
        return new

    def import_player(self, raw_info: bytes) -> Player:
        """Copia al EDIT un jugador de la base del juego (registro de 0xF0 bytes)
        para poder editarlo, igual que hace el juego al editar un jugador."""
        if len(raw_info) != 0xF0:
            raise ValueError("Registro de jugador con tamaño inesperado")
        if self.num_players >= PLAYER_CAPACITY:
            raise ValueError("No queda espacio para más jugadores en el archivo")
        pid = struct.unpack_from("<I", raw_info, 0)[0]
        if pid in self.player_by_id:
            return self.player_by_id[pid]
        new = Player(self, self.num_players)
        appearance = bytearray(PLAYER_SIZE - 0xF0)
        struct.pack_into("<I", appearance, 0, pid)       # sin flags de apariencia editada
        self.data[new.base:new.base + PLAYER_SIZE] = bytes(raw_info) + bytes(appearance)
        new["b_edit_player"] = 1
        self.num_players += 1
        struct.pack_into("<H", self.data, OFF_NUM_PLAYERS, self.num_players)
        self.players.append(new)
        self.player_by_id[pid] = new
        self.dirty = True
        return new

    def recycle_player(self, slot_player: Player, template: Player, name: str) -> Player:
        """Sobrescribe un agente libre con los datos de otro jugador (método seguro)."""
        keep_id = slot_player.id
        base = slot_player.base
        self.data[base:base + PLAYER_SIZE] = template.raw()
        slot_player["id"] = keep_id
        set_bits(self.data, base, 0xF0 * 8, 32, keep_id)
        slot_player["name"] = name
        slot_player["shirt_name"] = name.split(" ")[-1].upper()
        slot_player["print_name"] = ""
        slot_player["b_edit_player"] = 1
        self.dirty = True
        return slot_player
