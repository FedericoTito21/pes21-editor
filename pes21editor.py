"""
PES 2021 Editor de Plantillas — aplicación de escritorio (Tkinter).

Abre el EDIT00000000 de eFootball PES 2021 (PC/Steam), deja editar
plantillas, traspasos, jugadores y equipos, y lo vuelve a guardar cifrado.

Uso:  python pes21editor.py   (requiere: pip install numpy)
"""
from __future__ import annotations

import csv
import glob
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

import gamedb as G
import pes21crypt as crypt
from pes21data import (ABILITIES, COM_STYLES, EYE_COLORS, HANDS, INNERS, MOTIONS, PHYSIQUE,
                       PLAY_STYLES, PLAYABLE_FIELDS, POSITIONS, POSITIONS_LONG, ROSTER_SLOTS,
                       SHIRTTAIL, SKILLS, SKIN_COLORS, SLEEVES, SOCKS, SPEC_COLORS, SPEC_STYLES,
                       UNDERSHORTS, WRIST_TAPE, EditDB, RawPlayer)

# Grupos de campos extra: (nombre, flag de "editado", [(campo, etiqueta, tipo, opciones)])
#   tipo "combo": opciones = lista de textos (se guarda el índice)
#   tipo "spin":  opciones = (mín. mostrado, máx. mostrado, mostrado - guardado)
#   tipo "check" / "str" (opciones = longitud máxima)
EXTRA_GROUPS = [
    ("otros", "b_edit_basicset", [
        ("strong_hand", "Mano buena", "combo", HANDS),
        ("star", "Estrellas (valoración)", "spin", (0, 7, 0)),
        ("play_attit", "Actitud de juego (0-3)", "spin", (0, 3, 0)),
    ]),
    ("impreso", None, [("print_name", "Nombre impreso (selección)", "str", 63)]),
    ("fisico", "b_edit_phys",
     [(k, lbl, "spin", (-7, 7, -7)) for k, lbl in PHYSIQUE]
     + [("skin_col", "Color de piel", "combo", SKIN_COLORS),
        ("iris_col", "Color de ojos", "combo", EYE_COLORS)]),
    ("equipacion", "b_edit_strip", [
        ("sleeve", "Mangas", "combo", SLEEVES), ("inners", "Camiseta interior", "combo", INNERS),
        ("untucked", "Camiseta", "combo", SHIRTTAIL), ("socks", "Medias", "combo", SOCKS),
        ("undershorts", "Mallas", "combo", UNDERSHORTS), ("wrist_tape", "Muñequera", "combo", WRIST_TAPE),
        ("wrist_col_l", "Color muñequera izq. (0-7)", "spin", (0, 7, 0)),
        ("wrist_col_r", "Color muñequera der. (0-7)", "spin", (0, 7, 0)),
        ("spec_style", "Gafas", "combo", SPEC_STYLES), ("spec_col", "Color de gafas", "combo", SPEC_COLORS),
        ("gloves", "Guantes de jugador", "check", None), ("gloves_col", "Color de guantes (0-7)", "spin", (0, 7, 0)),
        ("ankle_tape", "Vendaje de tobillo", "check", None),
    ]),
    ("botas", None, [("boot_id", "ID de botas", "spin", (0, 16383, 0)),
                     ("glove_id", "ID de guantes de portero", "spin", (0, 16383, 0))]),
    ("animaciones", "b_edit_motion",
     [(k, lbl, "spin", (lo, hi, off)) for k, lbl, lo, hi, off in MOTIONS]),
]
APPEARANCE_FIELDS = {f for g, _, specs in EXTRA_GROUPS if g in ("fisico", "equipacion", "botas") for f, *_ in specs}

APP_TITLE = "PES 2021 · Editor de Plantillas"
PES_EXE = "PES2021.exe"
NO_TEAM = 0x3FFFF          # valor que usa el juego para "sin rival"
PES_STEAM_URL = "steam://rungameid/1259970"
NO_DATA_MSG = ("No hay datos editables de este jugador: el EDIT solo guarda los jugadores que se han "
               "editado alguna vez, y el resto vive en los archivos del juego. Indica la carpeta del juego "
               "(📁 Carpeta del juego…) para leer sus nombres y, si el formato lo permite, sus datos.\n\n"
               "Puedes ficharlo, darlo de baja, cambiarle el dorsal o hacerlo capitán. Para editar sus "
               "habilidades, edítalo una vez dentro del juego (Editar › Jugadores, basta con guardar) "
               "o usa el EDIT de un parche, que ya incluye todos los jugadores.")
MAX_ROWS = 1500

# Paleta
BG = "#14181f"
PANEL = "#1c222c"
PANEL2 = "#242c38"
FG = "#e6eaf0"
MUTED = "#8b96a8"
ACCENT = "#2fd27a"
WARN = "#ffb547"
SEL = "#2b6b4a"


def find_default_edit() -> str | None:
    home = os.path.expanduser("~")
    pats = []
    for docs in (os.path.join(home, "Documents"), os.path.join(home, "Documentos"),
                 os.path.join(home, "OneDrive", "*")):
        base = os.path.join(docs, "KONAMI", "eFootball PES 2021*")
        pats += [os.path.join(base, "*", "save", "EDIT00000000"),   # Steam: carpeta con el ID
                 os.path.join(base, "save", "EDIT00000000")]        # versiones sin ID de Steam
    hits = [h for p in pats for h in glob.glob(p)]
    return max(hits, key=os.path.getmtime) if hits else None


def short_path(path: str) -> str:
    parts = os.path.normpath(path).split(os.sep)
    return path if len(parts) <= 4 else os.path.join("…", *parts[-3:])


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1440x860")
        self.minsize(1100, 680)
        self.configure(bg=BG)
        self.db: EditDB | None = None
        self.path: str | None = None
        self.backup_done = False
        self.cur_player = None
        self.cur_team = None
        self.cur_team_edit = None
        self.gdb: G.GameDB | None = None
        self.gdb_loading = False
        self.cfg = G.load_config()
        self._q: queue.Queue = queue.Queue()
        self._jobs = 0
        self._style()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind_all("<Control-o>", lambda e: self.open_file())
        self.bind_all("<Control-s>", lambda e: self.save_file())

    # ------------------------------------------------------------ estilo
    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        base = ("Segoe UI", 10) if sys.platform == "win32" else ("DejaVu Sans", 10)
        self.option_add("*Font", base)
        s.configure(".", background=BG, foreground=FG, fieldbackground=PANEL2,
                    bordercolor=PANEL2, lightcolor=PANEL2, darkcolor=PANEL2, font=base)
        s.configure("TFrame", background=BG)
        s.configure("Panel.TFrame", background=PANEL)
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("Panel.TLabel", background=PANEL, foreground=FG)
        s.configure("Muted.TLabel", background=PANEL, foreground=MUTED)
        s.configure("Head.TLabel", background=PANEL, foreground=FG, font=(base[0], 13, "bold"))
        s.configure("Title.TLabel", background=BG, foreground=ACCENT, font=(base[0], 15, "bold"))
        s.configure("Info.TLabel", background=BG, foreground=MUTED)
        s.configure("TButton", background=PANEL2, foreground=FG, padding=(8, 5), borderwidth=0)
        s.map("TButton", background=[("active", "#2f3a4a"), ("disabled", PANEL)],
              foreground=[("disabled", MUTED)])
        s.configure("Accent.TButton", background=ACCENT, foreground="#08130c", font=(base[0], 10, "bold"))
        s.map("Accent.TButton", background=[("active", "#4be393"), ("disabled", PANEL2)])
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(16, 7))
        s.map("TNotebook.Tab", background=[("selected", PANEL2)], foreground=[("selected", FG)])
        s.configure("Inner.TNotebook", background=PANEL)
        s.configure("Inner.TNotebook.Tab", padding=(9, 5))
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG,
                    rowheight=24, borderwidth=0)
        s.configure("Treeview.Heading", background=PANEL2, foreground=MUTED, relief="flat")
        s.map("Treeview", background=[("selected", SEL)])
        s.configure("TEntry", fieldbackground=PANEL2, foreground=FG, insertcolor=FG)
        s.configure("TSpinbox", fieldbackground=PANEL2, foreground=FG, arrowcolor=FG)
        s.configure("TCombobox", fieldbackground=PANEL2, foreground=FG, arrowcolor=FG)
        s.map("TCombobox", fieldbackground=[("readonly", PANEL2)], foreground=[("readonly", FG)])
        s.configure("TCheckbutton", background=PANEL, foreground=FG)
        s.configure("TRadiobutton", background=PANEL, foreground=FG)
        s.map("TRadiobutton", background=[("active", PANEL)])
        s.map("TCheckbutton", background=[("active", PANEL)])
        s.configure("TLabelframe", background=PANEL, bordercolor=PANEL2)
        s.configure("TLabelframe.Label", background=PANEL, foreground=MUTED)
        self.option_add("*TCombobox*Listbox.background", PANEL2)
        self.option_add("*TCombobox*Listbox.foreground", FG)

    # ------------------------------------------------------------ layout
    def _build(self):
        top = ttk.Frame(self, padding=(14, 10))
        top.pack(fill="x")
        ttk.Label(top, text="⚽ PES 2021 · Editor de Plantillas", style="Title.TLabel").pack(side="left")
        self.btn_save = ttk.Button(top, text="Guardar  (Ctrl+S)", style="Accent.TButton",
                                   command=self.save_file, state="disabled")
        self.btn_save.pack(side="right")
        self.btn_play = ttk.Button(top, text="▶ Guardar y jugar", style="Accent.TButton",
                                   command=self.save_and_play, state="disabled")
        self.btn_play.pack(side="right", padx=(10, 0))
        self.btn_save.configure(style="TButton")
        self.btn_saveas = ttk.Button(top, text="Guardar como…", command=self.save_as, state="disabled")
        self.btn_saveas.pack(side="right", padx=6)
        ttk.Button(top, text="Abrir EDIT…  (Ctrl+O)", command=self.open_file).pack(side="right")
        ttk.Button(top, text="📁 Carpeta del juego…", command=self.game_dialog).pack(side="right", padx=6)
        self.info = ttk.Label(self, text="Abre tu archivo EDIT00000000 para empezar.", style="Info.TLabel",
                              padding=(16, 0, 16, 6))
        self.info.pack(fill="x")

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.tab_squads = ttk.Frame(self.nb, style="Panel.TFrame")
        self.tab_players = ttk.Frame(self.nb, style="Panel.TFrame")
        self.tab_teams = ttk.Frame(self.nb, style="Panel.TFrame")
        self.nb.add(self.tab_squads, text="Plantillas")
        self.nb.add(self.tab_players, text="Jugadores")
        self.nb.add(self.tab_teams, text="Equipos")
        self._build_squads()
        self._build_players()
        self._build_teams()

        self.status = ttk.Label(self, text="", style="Info.TLabel", padding=(16, 2, 16, 8))
        self.status.pack(fill="x")

    def _tree(self, parent, cols, widths, height=20):
        frame = ttk.Frame(parent, style="Panel.TFrame")
        tv = ttk.Treeview(frame, columns=cols, show="headings", height=height, selectmode="browse")
        for c, w in zip(cols, widths):
            tv.heading(c, text=c)
            tv.column(c, width=w, anchor="w" if w > 90 else "center", stretch=w > 90)
        sb = ttk.Scrollbar(frame, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        tv.tag_configure("odd", background="#202733")
        tv.tag_configure("starter", foreground=ACCENT)
        return frame, tv

    # ---------------------------------------------------- pestaña plantillas
    def _build_squads(self):
        t = self.tab_squads
        left = ttk.Frame(t, style="Panel.TFrame", padding=10)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Equipos", style="Head.TLabel").pack(anchor="w")
        self.team_filter = tk.StringVar()
        self.team_filter.trace_add("write", lambda *a: self.fill_team_list())
        ttk.Entry(left, textvariable=self.team_filter, width=30).pack(fill="x", pady=6)
        f, self.tv_teams = self._tree(left, ("Equipo", "Jug."), (220, 50), height=12)
        f.pack(fill="both", expand=True)
        self.tv_teams.bind("<<TreeviewSelect>>", lambda e: self.on_team_select())

        right = ttk.Frame(t, style="Panel.TFrame", padding=10)
        right.pack(side="left", fill="both", expand=True)
        head = ttk.Frame(right, style="Panel.TFrame")
        head.pack(fill="x")
        self.lbl_team = ttk.Label(head, text="Selecciona un equipo", style="Head.TLabel")
        self.lbl_team.pack(side="left")
        self.lbl_team_sub = ttk.Label(head, text="", style="Muted.TLabel")
        self.lbl_team_sub.pack(side="left", padx=12)

        cols = ("#", "Dorsal", "Nombre", "Pos", "Edad", "Media", "Rol")
        f, self.tv_roster = self._tree(right, cols, (40, 60, 280, 60, 50, 60, 120), height=12)
        f.pack(fill="both", expand=True, pady=8)
        self.tv_roster.configure(selectmode="extended")
        self.tv_roster.bind("<Double-1>", lambda e: self.edit_roster_player())

        bar = ttk.Frame(right, style="Panel.TFrame")
        bar.pack(fill="x")
        for txt, cmd in (("➕ Fichar jugador…", self.sign_player),
                         ("➖ Dar de baja", self.release_player),
                         ("Cambiar dorsal", self.change_number),
                         ("Hacer capitán", self.make_captain),
                         ("▲ Subir", lambda: self.move_slot(-1)),
                         ("▼ Bajar", lambda: self.move_slot(1)),
                         ("Titular ↔ suplente", self.swap_starter),
                         ("Mejorar equipo…", self.boost_team),
                         ("Editar jugador", self.edit_roster_player)):
            ttk.Button(bar, text=txt, command=cmd).pack(side="left", padx=(0, 6))
        ttk.Label(right, text="En verde: los 11 titulares. Tras traspasos, revisa la alineación "
                  "y lanzadores dentro del juego (Editar › Equipos).",
                  style="Muted.TLabel").pack(anchor="w", pady=(8, 0))

    def fill_team_list(self):
        tv = self.tv_teams
        tv.delete(*tv.get_children())
        if not self.db:
            return
        q = self.team_filter.get().strip().lower()
        for i, team in enumerate(self.db.visible_teams()):
            if q and q not in team.name.lower():
                continue
            tv.insert("", "end", iid=str(team.id), values=(team.name, len(team.roster())),
                      tags=("odd",) if i % 2 else ())

    def on_team_select(self):
        sel = self.tv_teams.selection()
        if not sel or not self.db:
            return
        self.cur_team = self.db.team_by_id[int(sel[0])]
        self.fill_roster()

    def fill_roster(self, keep_slot: int | None = None):
        tv = self.tv_roster
        tv.delete(*tv.get_children())
        team = self.cur_team
        if not team:
            return
        roster = team.roster()
        lineup = set(team.starting11())
        cap = team.captain()
        self.lbl_team.configure(text=team.name)
        self.lbl_team_sub.configure(text=f"{len(roster)}/{ROSTER_SLOTS} jugadores · ID {team.id}")
        for slot, (pid, num) in enumerate(roster):
            p = self.view(pid)
            rol = ("Titular" if slot in lineup else "Suplente") + (" · C" if slot == cap else "")
            if p is None:
                vals = (slot + 1, num, self.pname(pid), "", "", "", rol)
            else:
                vals = (slot + 1, num, self.pname(pid), POSITIONS[p["reg_pos"]] if p["reg_pos"] < 13 else "?",
                        p["age"], p.overall(), rol)
            tags = ["starter"] if slot in lineup else []
            if slot % 2:
                tags.append("odd")
            tv.insert("", "end", iid=str(slot), values=vals, tags=tags)
        if keep_slot is not None and 0 <= keep_slot < len(roster):
            tv.selection_set(str(keep_slot))
            tv.see(str(keep_slot))

    def _roster_sel(self):
        sel = self.tv_roster.selection()
        if not sel or not self.cur_team:
            messagebox.showinfo(APP_TITLE, "Selecciona un jugador de la plantilla.")
            return None
        slot = int(sel[0])
        return slot, self.cur_team.roster()[slot][0]

    def sign_player(self):
        if not self.cur_team:
            messagebox.showinfo(APP_TITLE, "Selecciona primero el equipo que ficha.")
            return
        dlg = PlayerPicker(self, f"Fichar para {self.cur_team.name}")
        if dlg.result is None:
            return
        pid, from_team, keep_in_origin = dlg.result
        try:
            if keep_in_origin or from_team is None:
                num = self.db.add_to_team(self.cur_team, pid)
            else:
                num = self.db.transfer(pid, from_team, self.cur_team)
        except ValueError as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        origin = "agente libre" if from_team is None else from_team.name
        self.set_status(f"{self.pname(pid)} fichado por {self.cur_team.name} (desde {origin}) con el dorsal {num}.")
        self.after_change(keep_slot=len(self.cur_team.roster()) - 1)

    def release_player(self):
        r = self._roster_sel()
        if not r:
            return
        slot, pid = r
        name = self.pname(pid)
        others = [t.name for t in self.db.teams_of.get(pid, []) if t is not self.cur_team]
        extra = "" if others else "\n\nNo está en ningún otro equipo: pasará a ser agente libre."
        if not messagebox.askyesno(APP_TITLE, f"¿Dar de baja a {name} de {self.cur_team.name}?{extra}"):
            return
        try:
            self.db.remove_from_team(self.cur_team, pid)
        except ValueError as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        self.set_status(f"{name} dado de baja de {self.cur_team.name}.")
        self.after_change(keep_slot=max(0, slot - 1))

    def change_number(self):
        r = self._roster_sel()
        if not r:
            return
        slot, pid = r
        current = self.cur_team.roster()[slot][1]
        n = simpledialog.askinteger(APP_TITLE, "Nuevo dorsal (1-99):", initialvalue=current,
                                    minvalue=1, maxvalue=99, parent=self)
        if n is None:
            return
        clash = [s for s, (_, num) in enumerate(self.cur_team.roster()) if num == n and s != slot]
        if clash and not messagebox.askyesno(APP_TITLE, f"El dorsal {n} ya lo lleva otro jugador. "
                                                        "¿Intercambiar los dorsales?"):
            return
        if clash:
            self.cur_team.set_number(clash[0], current)
        self.cur_team.set_number(slot, n)
        self.after_change(keep_slot=slot)

    def make_captain(self):
        r = self._roster_sel()
        if not r:
            return
        self.cur_team.set_captain(r[0])
        self.after_change(keep_slot=r[0])

    def move_slot(self, delta):
        r = self._roster_sel()
        if not r:
            return
        slot = r[0]
        other = slot + delta
        if not 0 <= other < len(self.cur_team.roster()):
            return
        self.db.swap_slots(self.cur_team, slot, other)
        self.after_change(keep_slot=other)

    def swap_starter(self):
        sel = self.tv_roster.selection()
        if not self.cur_team or len(sel) != 2:
            messagebox.showinfo(APP_TITLE, "Selecciona dos jugadores (Ctrl+clic): un titular y un suplente. "
                                "El suplente ocupará el puesto del titular en la alineación.")
            return
        team = self.cur_team
        a, b = (int(x) for x in sel)
        lineup = team.starting11()
        if (a in lineup) == (b in lineup):
            messagebox.showinfo(APP_TITLE, "Tiene que ser un titular y un suplente.")
            return
        starter, bench = (a, b) if a in lineup else (b, a)
        k = lineup.index(starter)
        self.db.data[team.tactics_base + 0x1E4 + k] = bench
        if team.captain() == starter:
            team.set_captain(bench)
        self.db.dirty = True
        self.set_status(f"{self.pname(team.roster()[bench][0])} entra de titular por "
                        f"{self.pname(team.roster()[starter][0])}.")
        self.after_change(keep_slot=bench)

    def boost_team(self):
        if not self.cur_team:
            return
        d = simpledialog.askinteger(APP_TITLE, f"¿Cuántos puntos sumar a todas las habilidades de los jugadores "
                                    f"de {self.cur_team.name}?\n(negativo para restar, de -30 a 30)",
                                    minvalue=-30, maxvalue=30, parent=self)
        if not d:
            return
        done = skipped = 0
        for pid, _ in self.cur_team.roster():
            p = self.db.player_by_id.get(pid)
            if p is None:
                v = self.view(pid)
                if v is None:
                    skipped += 1
                    continue
                p = self.db.import_player(bytes(v.db.data[:0xF0]))
            for key, _lbl in ABILITIES:
                p[key] = max(40, min(99, p[key] + d))
            p["b_edit_ability"] = 1
            p["b_edit_player"] = 1
            done += 1
        msg = f"{done} jugadores de {self.cur_team.name} modificados ({d:+d})."
        if skipped:
            msg += f" {skipped} sin datos editables (indica la carpeta del juego para incluirlos)."
        self.set_status(msg)
        self.after_change()

    def edit_roster_player(self):
        r = self._roster_sel()
        if not r:
            return
        pid = r[1]
        p = self.view(pid)
        if p is None:
            messagebox.showinfo(APP_TITLE, NO_DATA_MSG)
            return
        self.nb.select(self.tab_players)
        self.player_search.set(self.pname(pid))
        self.fill_player_list()
        self.select_player(p)

    # ---------------------------------------------------- pestaña jugadores
    def _build_players(self):
        t = self.tab_players
        left = ttk.Frame(t, style="Panel.TFrame", padding=10)
        left.pack(side="left", fill="both")
        ttk.Label(left, text="Jugadores", style="Head.TLabel").pack(anchor="w")
        flt = ttk.Frame(left, style="Panel.TFrame")
        flt.pack(fill="x", pady=6)
        self.player_search = tk.StringVar()
        e = ttk.Entry(flt, textvariable=self.player_search, width=26)
        e.pack(side="left")
        e.bind("<Return>", lambda ev: self.fill_player_list())
        self.pos_filter = ttk.Combobox(flt, values=["Todas"] + POSITIONS, width=6, state="readonly")
        self.pos_filter.set("Todas")
        self.pos_filter.pack(side="left", padx=4)
        self.pos_filter.bind("<<ComboboxSelected>>", lambda ev: self.fill_player_list())
        ttk.Button(flt, text="Buscar", command=self.fill_player_list).pack(side="left")
        self.only_free = tk.BooleanVar()
        ttk.Checkbutton(left, text="Solo agentes libres", variable=self.only_free,
                        command=self.fill_player_list).pack(anchor="w")
        f, self.tv_players = self._tree(left, ("Nombre", "Equipo", "Pos", "Edad", "Media"),
                                        (150, 105, 42, 40, 46), height=12)
        f.pack(fill="both", expand=True, pady=6)
        self.tv_players.bind("<<TreeviewSelect>>", lambda ev: self.on_player_select())
        bb = ttk.Frame(left, style="Panel.TFrame")
        bb.pack(fill="x")
        ttk.Button(bb, text="Crear jugador…", command=self.create_player).pack(side="left")
        ttk.Button(bb, text="Exportar CSV…", command=self.export_csv).pack(side="left", padx=6)

        right = ttk.Frame(t, style="Panel.TFrame", padding=10)
        right.pack(side="left", fill="both", expand=True)
        head = ttk.Frame(right, style="Panel.TFrame")
        head.pack(fill="x")
        self.lbl_player = ttk.Label(head, text="Selecciona un jugador", style="Head.TLabel")
        self.lbl_player.pack(side="left")
        self.btn_apply = ttk.Button(head, text="Aplicar cambios", style="Accent.TButton",
                                    command=self.apply_player, state="disabled")
        self.btn_apply.pack(side="right")
        self.lbl_player_sub = ttk.Label(right, text="", style="Muted.TLabel")
        self.lbl_player_sub.pack(anchor="w", pady=(2, 6))

        nb = ttk.Notebook(right, style="Inner.TNotebook")
        nb.pack(fill="both", expand=True)
        self.pvars: dict[str, tk.Variable] = {}
        self._tab_basic(nb)
        self._tab_abilities(nb)
        self._tab_positions(nb)
        self._tab_skills(nb)
        self._tab_extra(nb)

    def _grid_field(self, parent, row, col, label, widget):
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(row=row, column=col * 2, sticky="w",
                                                                 padx=(0, 8), pady=4)
        widget.grid(row=row, column=col * 2 + 1, sticky="w", padx=(0, 28), pady=4)

    def _spin(self, parent, key, lo, hi, width=6):
        v = tk.IntVar()
        self.pvars[key] = v
        return ttk.Spinbox(parent, from_=lo, to=hi, textvariable=v, width=width)

    def _tab_basic(self, nb):
        f = ttk.Frame(nb, style="Panel.TFrame", padding=14)
        nb.add(f, text="Básico")
        for key in ("name", "shirt_name"):
            self.pvars[key] = tk.StringVar()
        self._grid_field(f, 0, 0, "Nombre", ttk.Entry(f, textvariable=self.pvars["name"], width=34))
        self._grid_field(f, 1, 0, "Nombre camiseta", ttk.Entry(f, textvariable=self.pvars["shirt_name"], width=22))
        self._grid_field(f, 2, 0, "Edad", self._spin(f, "age", 15, 50))
        self._grid_field(f, 3, 0, "Altura (cm)", self._spin(f, "height", 100, 255))
        self._grid_field(f, 4, 0, "Peso (kg)", self._spin(f, "weight", 30, 255))
        nat = ttk.Frame(f, style="Panel.TFrame")
        self._spin(nat, "nation", 0, 65535, 8).pack(side="left")
        self.nation_lbl = ttk.Label(nat, text="", style="Muted.TLabel")
        self.nation_lbl.pack(side="left", padx=8)
        self.pvars["nation"].trace_add("write", lambda *a: self._update_nation_lbl())
        self._grid_field(f, 5, 0, "Nacionalidad (ID)", nat)
        self.pvars["strong_foot"] = tk.StringVar()
        self._grid_field(f, 6, 0, "Pie bueno", ttk.Combobox(f, textvariable=self.pvars["strong_foot"],
                                                           values=["Derecho", "Izquierdo"], state="readonly", width=12))
        self.pvars["reg_pos"] = tk.StringVar()
        self._grid_field(f, 7, 0, "Posición", ttk.Combobox(f, textvariable=self.pvars["reg_pos"],
                                                          values=[f"{a} · {b}" for a, b in zip(POSITIONS, POSITIONS_LONG)],
                                                          state="readonly", width=28))
        self.pvars["play_style"] = tk.StringVar()
        self._grid_field(f, 8, 0, "Estilo de juego", ttk.Combobox(f, textvariable=self.pvars["play_style"],
                                                                 values=PLAY_STYLES, state="readonly", width=28))
        self._grid_field(f, 0, 1, "Uso pie malo (1-4)", self._spin(f, "weak_use", 1, 4))
        self._grid_field(f, 1, 1, "Precisión pie malo (1-4)", self._spin(f, "weak_acc", 1, 4))
        self._grid_field(f, 2, 1, "Forma (1-8)", self._spin(f, "form", 1, 8))
        self._grid_field(f, 3, 1, "Resist. lesiones (1-3)", self._spin(f, "injury", 1, 3))
        self.basic_extra_frame = f
        ttk.Label(f, text="La nacionalidad es el código interno del juego; si hay carpeta del juego, al lado "
                  "aparece el país que le corresponde.", style="Muted.TLabel", wraplength=560
                  ).grid(row=10, column=0, columnspan=4, sticky="w", pady=(16, 0))

    def _extra_widget(self, parent, field, kind, opts):
        if kind == "combo":
            v = tk.StringVar()
            w = ttk.Combobox(parent, textvariable=v, values=opts, state="readonly",
                             width=max(10, min(24, max(len(o) for o in opts) + 1)))
        elif kind == "spin":
            v = tk.IntVar()
            w = ttk.Spinbox(parent, from_=opts[0], to=opts[1], textvariable=v, width=7)
        elif kind == "check":
            v = tk.BooleanVar()
            w = ttk.Checkbutton(parent, variable=v)
        else:
            v = tk.StringVar()
            w = ttk.Entry(parent, textvariable=v, width=24)
        self.pvars[field] = v
        return w

    def _tab_extra(self, nb):
        specs = {g: sp for g, _, sp in EXTRA_GROUPS}
        # Básico: campos "otros" + nombre impreso en la segunda columna
        f = self.basic_extra_frame
        for i, (field, label, kind, opts) in enumerate(specs["otros"] + specs["impreso"]):
            self._grid_field(f, 4 + i, 1, label, self._extra_widget(f, field, kind, opts))

        def page(title, groups, per_col, note):
            pf = ttk.Frame(nb, style="Panel.TFrame", padding=14)
            nb.add(pf, text=title)
            items = [s for g in groups for s in specs[g]]
            for i, (field, label, kind, opts) in enumerate(items):
                self._grid_field(pf, i % per_col, i // per_col, label, self._extra_widget(pf, field, kind, opts))
            ttk.Label(pf, text=note, style="Muted.TLabel", wraplength=600
                      ).grid(row=per_col + 1, column=0, columnspan=6, sticky="w", pady=(14, 0))
            return pf
        page("Físico", ["fisico"], 8, "Medidas de -7 a +7 (0 = normal). Si el jugador nunca se editó en el "
             "juego, parte de valores neutros y solo se guardan si cambias algo aquí.")
        page("Equipación", ["equipacion", "botas"], 8, "Los ID de botas y guantes son los del juego "
             "(0 = por defecto). Los colores se indican con su número interno (0-7).")
        page("Animaciones", ["animaciones"], 6, "Estilos de movimiento, lanzamientos y celebraciones "
             "(números de las listas del juego).")

    def _extra_snapshot(self, p) -> dict:
        blank = not any(p.db.data[p.base + 0xF4:p.base + 0x138])
        snap = {}
        for _g, _flag, specs in EXTRA_GROUPS:
            for field, _label, kind, opts in specs:
                stored = p[field]
                if blank and field in APPEARANCE_FIELDS and kind == "spin" and opts[2] == -7:
                    stored = 7                      # sin apariencia guardada: medida neutra
                if kind == "combo":
                    val = opts[min(stored, len(opts) - 1)]
                elif kind == "spin":
                    val = stored + opts[2]
                elif kind == "check":
                    val = bool(stored)
                else:
                    val = stored
                snap[field] = val
        return snap

    def _apply_extra(self, p, dry: bool = False):
        for _g, flag, specs in EXTRA_GROUPS:
            changed = False
            new = {}
            for field, label, kind, opts in specs:
                raw = self.pvars[field].get()
                if kind == "spin":
                    try:
                        val = int(raw)
                    except (tk.TclError, ValueError):
                        raise ValueError(f"{label}: número no válido")
                    # solo se exige el rango si lo has cambiado (respeta valores raros ya guardados)
                    if val != self._snap.get(field) and not opts[0] <= val <= opts[1]:
                        raise ValueError(f"{label}: debe estar entre {opts[0]} y {opts[1]}")
                elif kind == "check":
                    val = bool(raw)
                else:
                    val = raw
                new[field] = val
                if val != self._snap.get(field):
                    changed = True
            if not changed or dry:
                continue
            for field, label, kind, opts in specs:
                val = new[field]
                if kind == "combo":
                    if val in opts:
                        p[field] = opts.index(val)
                elif kind == "spin":
                    if val == self._snap.get(field) and not opts[0] <= val <= opts[1]:
                        continue                    # valor original sin tocar
                    p[field] = val - opts[2]
                elif kind == "check":
                    p[field] = int(val)
                else:
                    p[field] = val
            if flag:
                p[flag] = 1

    def nation_names(self) -> dict:
        """Código de nacionalidad -> nombre de la selección (deducido de las plantillas)."""
        key = (id(self.db), id(self.gdb), self.db.num_players if self.db else 0)
        if getattr(self, "_nat_key", None) == key:
            return self._nat_cache
        votes: dict[int, tuple[float, str]] = {}
        if self.db:
            for t in self.db.visible_teams():
                codes = []
                for pid, _ in t.roster():
                    v = self.view(pid)
                    if v is not None:
                        codes.append(v["nation"])
                if len(codes) < 11:
                    continue
                top = max(set(codes), key=codes.count)
                share = codes.count(top) / len(codes)
                if share >= 0.8 and share > votes.get(top, (0, ""))[0]:
                    votes[top] = (share, t.name)
        self._nat_cache = {k: v[1] for k, v in votes.items()}
        self._nat_key = key
        return self._nat_cache

    def _update_nation_lbl(self):
        try:
            code = int(self.pvars["nation"].get())
        except (tk.TclError, ValueError):
            self.nation_lbl.configure(text="")
            return
        name = self.nation_names().get(code) if self.db else None
        self.nation_lbl.configure(text=name or "")

    def _tab_abilities(self, nb):
        f = ttk.Frame(nb, style="Panel.TFrame", padding=14)
        nb.add(f, text="Habilidades")
        per_col = 9
        for i, (key, label) in enumerate(ABILITIES):
            self._grid_field(f, i % per_col, i // per_col, label, self._spin(f, key, 40, 99, 5))
        btns = ttk.Frame(f, style="Panel.TFrame")
        btns.grid(row=per_col + 1, column=0, columnspan=6, sticky="w", pady=(14, 0))
        ttk.Label(btns, text="Ajuste rápido:", style="Muted.TLabel").pack(side="left", padx=(0, 8))
        for d in (-5, -1, +1, +5):
            ttk.Button(btns, text=f"{d:+d} a todo", command=lambda d=d: self.bump_all(d)).pack(side="left", padx=2)

    def bump_all(self, d):
        for key, _ in ABILITIES:
            v = self.pvars[key]
            try:
                v.set(max(40, min(99, int(v.get()) + d)))
            except (tk.TclError, ValueError):
                pass

    def _tab_positions(self, nb):
        f = ttk.Frame(nb, style="Panel.TFrame", padding=14)
        nb.add(f, text="Posiciones")
        ttk.Label(f, text="Dominio de cada posición (la registrada se marca sola como A).",
                  style="Muted.TLabel").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))
        for i, (short, long_, field) in enumerate(zip(POSITIONS, POSITIONS_LONG, PLAYABLE_FIELDS)):
            v = tk.StringVar()
            self.pvars[field] = v
            cb = ttk.Combobox(f, textvariable=v, values=["C", "B", "A"], state="readonly", width=4)
            self._grid_field(f, 1 + i % 7, i // 7, f"{short} · {long_}", cb)

    def _tab_skills(self, nb):
        f = ttk.Frame(nb, style="Panel.TFrame", padding=14)
        nb.add(f, text="Especiales")
        per_col = 14
        for i, name in enumerate(SKILLS):
            v = tk.BooleanVar()
            self.pvars[f"skill{i}"] = v
            ttk.Checkbutton(f, text=name, variable=v).grid(row=i % per_col, column=i // per_col,
                                                           sticky="w", padx=(0, 24), pady=1)
        lf = ttk.Frame(nb, style="Panel.TFrame", padding=14)
        nb.add(lf, text="IA")
        ttk.Label(lf, text="Cómo juega el jugador cuando lo controla la máquina.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        for i, name in enumerate(COM_STYLES):
            v = tk.BooleanVar()
            self.pvars[f"com{i}"] = v
            ttk.Checkbutton(lf, text=name, variable=v).pack(anchor="w", pady=1)

    def fill_player_list(self):
        tv = self.tv_players
        tv.delete(*tv.get_children())
        if not self.db:
            return
        q = self.player_search.get().strip().lower()
        pos = self.pos_filter.get()
        posi = POSITIONS.index(pos) if pos in POSITIONS else None
        free_only = self.only_free.get()
        n = 0
        total = 0
        for p in self.db.players:
            if not p.id:
                continue
            if q and q not in p.name.lower():
                continue
            if posi is not None and p["reg_pos"] != posi:
                continue
            teams = self.db.teams_of.get(p.id, [])
            if free_only and teams:
                continue
            total += 1
            if n >= MAX_ROWS:
                continue
            team_name = teams[0].name if teams else "Agente libre"
            tv.insert("", "end", iid=str(p.index),
                      values=(p.name, team_name, POSITIONS[p["reg_pos"]] if p["reg_pos"] < 13 else "?",
                              p["age"], p.overall()),
                      tags=("odd",) if n % 2 else ())
            n += 1
        # jugadores de la base del juego que aún no están en el EDIT
        if self.gdb:
            for pid, name in self.gdb.names.items():
                if pid in self.db.player_by_id or (q and q not in name.lower()):
                    continue
                teams = self.db.teams_of.get(pid, [])
                if free_only and teams:
                    continue
                v = self.view(pid)
                if posi is not None and (v is None or v["reg_pos"] != posi):
                    continue
                total += 1
                if n >= MAX_ROWS:
                    continue
                vals = (name, teams[0].name if teams else "Agente libre",
                        POSITIONS[v["reg_pos"]] if v is not None and v["reg_pos"] < 13 else "",
                        v["age"] if v is not None else "", v.overall() if v is not None else "")
                tv.insert("", "end", iid=f"g{pid}", values=vals, tags=("odd",) if n % 2 else ())
                n += 1
        more = f" (mostrando {MAX_ROWS}, afina la búsqueda)" if total > MAX_ROWS else ""
        self.set_status(f"{total} jugadores encontrados{more}.")

    def select_player(self, p):
        iid = str(p.index) if p.index >= 0 else f"g{p.id}"
        if self.tv_players.exists(iid):
            self.tv_players.selection_set(iid)
            self.tv_players.see(iid)
        else:
            self.load_player(p)

    def on_player_select(self):
        sel = self.tv_players.selection()
        if not sel or not self.db:
            return
        iid = sel[0]
        if iid.startswith("g"):
            pid = int(iid[1:])
            v = self.view(pid)
            if v is None:
                self.cur_player = None
                self.lbl_player.configure(text=self.pname(pid))
                self.lbl_player_sub.configure(text=f"ID {pid} · sin datos editables (el formato de la base del "
                                                   "juego no coincide con el del EDIT)")
                self.btn_apply.configure(state="disabled")
                return
            self.load_player(v)
        else:
            self.load_player(self.db.players[int(iid)])

    def load_player(self, p):
        self.cur_player = p
        pv = self.pvars
        pv["name"].set(p["name"])
        pv["shirt_name"].set(p["shirt_name"])
        for k in ("age", "height", "weight", "nation"):
            pv[k].set(p[k])
        pv["strong_foot"].set("Izquierdo" if p["strong_foot"] else "Derecho")
        rp = p["reg_pos"]
        pv["reg_pos"].set(f"{POSITIONS[rp]} · {POSITIONS_LONG[rp]}" if rp < 13 else "")
        ps = p["play_style"]
        pv["play_style"].set(PLAY_STYLES[ps] if ps < len(PLAY_STYLES) else PLAY_STYLES[0])
        pv["weak_use"].set(p["weak_use"] + 1)
        pv["weak_acc"].set(p["weak_acc"] + 1)
        pv["form"].set(p["form"] + 1)
        pv["injury"].set(min(3, p["injury"] + 1))
        for k, _ in ABILITIES:
            pv[k].set(p[k])
        for f in PLAYABLE_FIELDS:
            pv[f].set("CBA"[min(2, p[f])])
        for i in range(len(SKILLS)):
            pv[f"skill{i}"].set(bool(p[f"skill{i}"]))
        for i in range(len(COM_STYLES)):
            pv[f"com{i}"].set(bool(p[f"com{i}"]))
        self._snap = self._extra_snapshot(p)
        for field, val in self._snap.items():
            pv[field].set(val)
        self._update_nation_lbl()
        teams = ", ".join(t.name for t in self.db.teams_of.get(p.id, [])) or "Agente libre"
        self.lbl_player.configure(text=p.name or "(sin nombre)")
        extra = " · de la base del juego: se copiará al EDIT al aplicar" if p.index < 0 else ""
        self.lbl_player_sub.configure(text=f"ID {p.id} · {teams} · media aprox. {p.overall()}{extra}")
        self.btn_apply.configure(state="normal",
                                 text="Añadir al EDIT y aplicar" if p.index < 0 else "Aplicar cambios")

    def apply_player(self):
        p = self.cur_player
        if not p:
            return
        pv = self.pvars
        try:
            vals = {k: int(pv[k].get()) for k in ("age", "height", "weight", "nation")}
            ab = {k: int(pv[k].get()) for k, _ in ABILITIES}
            extra = {"weak_use": int(pv["weak_use"].get()) - 1, "weak_acc": int(pv["weak_acc"].get()) - 1,
                     "form": int(pv["form"].get()) - 1, "injury": int(pv["injury"].get()) - 1}
        except (tk.TclError, ValueError):
            messagebox.showerror(APP_TITLE, "Hay algún número mal escrito.")
            return
        bad = [lbl for k, lbl in ABILITIES if not 40 <= ab[k] <= 99]
        if bad:
            messagebox.showerror(APP_TITLE, "Las habilidades deben estar entre 40 y 99:\n" + ", ".join(bad))
            return
        if not 15 <= vals["age"] <= 50:
            messagebox.showerror(APP_TITLE, "La edad debe estar entre 15 y 50.")
            return
        name = pv["name"].get().strip()
        if not name:
            messagebox.showerror(APP_TITLE, "El nombre no puede estar vacío.")
            return
        try:
            self._apply_extra(p, dry=True)      # validar antes de tocar nada
        except ValueError as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        if p.index < 0:                 # jugador de la base del juego: copiarlo al EDIT (ya validado)
            try:
                p = self.db.import_player(bytes(p.db.data[:0xF0]))
            except ValueError as e:
                messagebox.showerror(APP_TITLE, str(e))
                return
            self.cur_player = p
        try:
            before = p.raw()
            changed_name = name != p["name"]
            if changed_name:
                p["name"] = name
            if pv["shirt_name"].get() != p["shirt_name"]:
                p["shirt_name"] = pv["shirt_name"].get().upper()
            basic_before = {k: p[k] for k in ("age", "height", "weight", "nation", "strong_foot")}
            for k, v in vals.items():
                p[k] = v
            p["strong_foot"] = 1 if pv["strong_foot"].get() == "Izquierdo" else 0
            if basic_before != {k: p[k] for k in basic_before}:
                p["b_edit_basicset"] = 1
            # posición registrada y jugables
            pos_before = (p["reg_pos"], [p[f] for f in PLAYABLE_FIELDS])
            rp_txt = pv["reg_pos"].get().split(" · ")[0]
            if rp_txt in POSITIONS:
                p["reg_pos"] = POSITIONS.index(rp_txt)
            for f in PLAYABLE_FIELDS:
                p[f] = "CBA".index(pv[f].get() or "C")
            p[PLAYABLE_FIELDS[p["reg_pos"]]] = 2
            if pos_before != (p["reg_pos"], [p[f] for f in PLAYABLE_FIELDS]):
                p["b_edit_regpos"] = 1
                p["b_edit_playpos"] = 1
            # habilidades
            if any(p[k] != v for k, v in {**ab, **extra}.items()):
                for k, v in {**ab, **extra}.items():
                    p[k] = v
                p["b_edit_ability"] = 1
            sk = [int(pv[f"skill{i}"].get()) for i in range(len(SKILLS))]
            if sk != [p[f"skill{i}"] for i in range(len(SKILLS))]:
                for i, v in enumerate(sk):
                    p[f"skill{i}"] = v
                p["b_edit_skill"] = 1
            style = PLAY_STYLES.index(pv["play_style"].get()) if pv["play_style"].get() in PLAY_STYLES else 0
            if style != p["play_style"]:
                p["play_style"] = style
                p["b_edit_style"] = 1
            com = [int(pv[f"com{i}"].get()) for i in range(len(COM_STYLES))]
            if com != [p[f"com{i}"] for i in range(len(COM_STYLES))]:
                for i, v in enumerate(com):
                    p[f"com{i}"] = v
                p["b_edit_com"] = 1
            self._apply_extra(p)
            if p.raw() != before:
                p["b_edit_player"] = 1
        except ValueError as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        self.set_status(f"Cambios aplicados a {p.name}. Recuerda guardar (Ctrl+S).")
        self.load_player(p)
        sel = self.tv_players.selection()
        if sel:
            self.tv_players.item(sel[0], values=(p.name, self.tv_players.item(sel[0])["values"][1],
                                                 POSITIONS[p["reg_pos"]], p["age"], p.overall()))
        self.after_change()

    def create_player(self):
        if not self.db:
            return
        if not self.db.players:
            messagebox.showinfo(APP_TITLE, "Para crear un jugador hace falta copiar uno base que tenga "
                                "datos en el EDIT, y tu archivo aún no tiene ninguno.\n\n" + NO_DATA_MSG)
            return
        dlg = CreatePlayerDialog(self)
        if not dlg.result:
            return
        name, template, mode, team = dlg.result
        try:
            if mode == "recycle":
                free = [p for p in self.db.free_agents() if p is not template]
                if not free:
                    messagebox.showerror(APP_TITLE, "No hay agentes libres que reutilizar. "
                                         "Prueba el modo experimental.")
                    return
                slot = min(free, key=lambda x: x.overall())
                if not messagebox.askyesno(APP_TITLE, f"Se reutilizará el hueco del agente libre "
                                           f"«{slot.name}» (media {slot.overall()}), que desaparecerá.\n\n¿Continuar?"):
                    return
                p = self.db.recycle_player(slot, template, name)
            else:
                p = self.db.create_player(template, name)
            num = self.db.add_to_team(team, p.id) if team else None
        except ValueError as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        where = f" y añadido a {team.name} con el dorsal {num}" if team else ""
        self.player_search.set(name)
        self.fill_player_list()
        self.select_player(p)
        self.after_change()
        self.set_status(f"Jugador «{name}» creado{where}. Ajusta sus datos y guarda.")

    def export_csv(self):
        if not self.db:
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="jugadores_pes2021.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["ID", "Nombre", "Equipos", "Posicion", "Edad", "Altura", "Peso", "Media aprox."]
                       + [lbl for _, lbl in ABILITIES])
            for p in self.db.players:
                if not p.id:
                    continue
                teams = " / ".join(t.name for t in self.db.teams_of.get(p.id, []))
                w.writerow([p.id, p.name, teams, POSITIONS[p["reg_pos"]] if p["reg_pos"] < 13 else "",
                            p["age"], p["height"], p["weight"], p.overall()] + [p[k] for k, _ in ABILITIES])
        self.set_status(f"Exportado a {path}")

    # ---------------------------------------------------- pestaña equipos
    def _build_teams(self):
        t = self.tab_teams
        left = ttk.Frame(t, style="Panel.TFrame", padding=10)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Equipos", style="Head.TLabel").pack(anchor="w")
        self.team_filter2 = tk.StringVar()
        self.team_filter2.trace_add("write", lambda *a: self.fill_team_list2())
        ttk.Entry(left, textvariable=self.team_filter2, width=30).pack(fill="x", pady=6)
        f, self.tv_teams2 = self._tree(left, ("Equipo", "Abrev."), (220, 60), height=12)
        f.pack(fill="both", expand=True)
        self.tv_teams2.bind("<<TreeviewSelect>>", lambda e: self.on_team2_select())

        right = ttk.Frame(t, style="Panel.TFrame", padding=20)
        right.pack(side="left", fill="both", expand=True)
        self.lbl_team2 = ttk.Label(right, text="Selecciona un equipo", style="Head.TLabel")
        self.lbl_team2.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 14))
        self.tvar_name = tk.StringVar()
        self.tvar_short = tk.StringVar()
        ttk.Label(right, text="Nombre", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(right, textvariable=self.tvar_name, width=40).grid(row=1, column=1, sticky="w")
        ttk.Label(right, text="Abreviatura (3)", style="Panel.TLabel").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(right, textvariable=self.tvar_short, width=6).grid(row=2, column=1, sticky="w")
        self.color_btns = []
        for n in (1, 2):
            ttk.Label(right, text=f"Color {n}", style="Panel.TLabel").grid(row=2 + n, column=0, sticky="w", pady=6)
            b = tk.Button(right, width=10, relief="flat", command=lambda n=n: self.pick_color(n),
                          bg=PANEL2, activebackground=PANEL2)
            b.grid(row=2 + n, column=1, sticky="w")
            self.color_btns.append(b)
        self.tvars: dict[str, tk.Variable] = {}
        rows = [("stadium_name", "Nombre del estadio", 40), ("banner1", "Pancarta 1", 18),
                ("banner2", "Pancarta 2", 18), ("banner3", "Pancarta 3", 18), ("banner4", "Pancarta 4", 18)]
        for i, (key, label, w) in enumerate(rows):
            self.tvars[key] = tk.StringVar()
            ttk.Label(right, text=label, style="Panel.TLabel").grid(row=5 + i, column=0, sticky="w", pady=4)
            ttk.Entry(right, textvariable=self.tvars[key], width=w).grid(row=5 + i, column=1, sticky="w")
        for i, (key, label) in enumerate((("manager_id", "ID de entrenador"), ("stadium_id", "ID de estadio"))):
            self.tvars[key] = tk.IntVar()
            ttk.Label(right, text=label, style="Panel.TLabel").grid(row=1 + i, column=2, sticky="w", padx=(30, 8))
            ttk.Spinbox(right, from_=0, to=(1 << 32) - 1 if key == "manager_id" else 65535,
                        textvariable=self.tvars[key], width=10).grid(row=1 + i, column=3, sticky="w")
        self.rival_cbs = []
        for i in range(3):
            ttk.Label(right, text=f"Rival {i + 1}", style="Panel.TLabel").grid(row=3 + i, column=2, sticky="w",
                                                                           padx=(30, 8))
            cb = ttk.Combobox(right, state="readonly", width=24)
            cb.grid(row=3 + i, column=3, sticky="w")
            self.rival_cbs.append(cb)
        self.btn_team_apply = ttk.Button(right, text="Aplicar cambios", style="Accent.TButton",
                                         command=self.apply_team, state="disabled")
        self.btn_team_apply.grid(row=11, column=0, columnspan=2, sticky="w", pady=(18, 0))
        ttk.Label(right, text="Los colores se guardan con 64 niveles por canal (pueden variar ligeramente). "
                  "Los ID de entrenador y estadio son los internos del juego; el estadio se usa "
                  "como campo local del equipo.", style="Muted.TLabel", wraplength=640
                  ).grid(row=12, column=0, columnspan=4, sticky="w", pady=(14, 0))
        self.new_colors = {}

    def fill_team_list2(self):
        tv = self.tv_teams2
        tv.delete(*tv.get_children())
        if not self.db:
            return
        q = self.team_filter2.get().strip().lower()
        for i, team in enumerate(self.db.visible_teams()):
            if q and q not in team.name.lower():
                continue
            tv.insert("", "end", iid=str(team.id), values=(team.name, team["short_name"]),
                      tags=("odd",) if i % 2 else ())

    def on_team2_select(self):
        sel = self.tv_teams2.selection()
        if not sel or not self.db:
            return
        team = self.db.team_by_id[int(sel[0])]
        self.cur_team_edit = team
        self.new_colors = {}
        self.lbl_team2.configure(text=f"{team.name}  ·  ID {team.id}")
        self.tvar_name.set(team.name)
        self.tvar_short.set(team["short_name"])
        for n, b in zip((1, 2), self.color_btns):
            c = team.color(n)
            b.configure(bg=c, activebackground=c)
        for key, var in self.tvars.items():
            var.set(team[key])
        self._rival_teams = [None] + sorted((t for t in self.db.visible_teams() if t is not team),
                                            key=lambda t: t.name)
        names = ["(ninguno)"] + [t.name for t in self._rival_teams[1:]]
        for i, cb in enumerate(self.rival_cbs):
            cb.configure(values=names)
            rid = team[f"rival{i + 1}"]
            idx = next((k for k, t in enumerate(self._rival_teams) if t is not None and t.id == rid), 0)
            cb.current(idx)
        self.btn_team_apply.configure(state="normal")

    def pick_color(self, n):
        if not self.cur_team_edit:
            return
        cur = self.new_colors.get(n, self.cur_team_edit.color(n))
        res = colorchooser.askcolor(color=cur, title=f"Color {n}", parent=self)
        if res and res[1]:
            self.new_colors[n] = res[1]
            b = self.color_btns[n - 1]
            b.configure(bg=res[1], activebackground=res[1])

    def apply_team(self):
        team = self.cur_team_edit
        if not team:
            return
        name = self.tvar_name.get().strip()
        short = self.tvar_short.get().strip().upper()
        if not name:
            messagebox.showerror(APP_TITLE, "El nombre no puede estar vacío.")
            return
        if name != team.name:
            team["name"] = name
        if short != team["short_name"]:
            team["short_name"] = short[:3]
        try:
            for key in ("manager_id", "stadium_id"):
                v = int(self.tvars[key].get())
                if v != team[key]:
                    team[key] = v
                    if key == "stadium_id":
                        team["b_edit_stadium"] = 1
        except (tk.TclError, ValueError) as e:
            messagebox.showerror(APP_TITLE, f"ID no válido: {e}")
            return
        for key in ("stadium_name", "banner1", "banner2", "banner3", "banner4"):
            v = self.tvars[key].get().strip()
            if v != team[key]:
                team[key] = v
        for i, cb in enumerate(self.rival_cbs):
            t = self._rival_teams[cb.current()] if cb.current() > 0 else None
            rid = t.id if t else NO_TEAM
            cur = team[f"rival{i + 1}"]
            if rid != cur and not (t is None and cur not in self.db.team_by_id):
                team[f"rival{i + 1}"] = rid
        for n, c in self.new_colors.items():
            team.set_color(n, c)
        self.new_colors = {}
        self.set_status(f"Equipo «{name}» actualizado. Recuerda guardar.")
        self.after_change()
        self.fill_team_list2()
        self.fill_team_list()
        iid = str(team.id)
        if self.tv_teams2.exists(iid):
            self.tv_teams2.selection_set(iid)
            self.tv_teams2.see(iid)
        if self.cur_team is team:
            self.lbl_team.configure(text=team.name)

    # ---------------------------------------------------- archivo
    def open_file(self):
        if not self.confirm_discard():
            return
        guess = find_default_edit()
        path = filedialog.askopenfilename(
            title="Abrir EDIT00000000 de PES 2021",
            initialdir=os.path.dirname(guess) if guess else os.path.expanduser("~"),
            initialfile="EDIT00000000",
            filetypes=[("Archivo EDIT de PES", "EDIT*"), ("Todos", "*.*")])
        if path:
            self.load_path(path)

    def load_path(self, path):
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            ef = crypt.load(path)
            db = EditDB(ef)
        except Exception as e:  # noqa: BLE001
            self.config(cursor="")
            messagebox.showerror(APP_TITLE, f"No se pudo abrir el archivo:\n\n{e}")
            return
        self.config(cursor="")
        self.db, self.path = db, path
        self.backup_done = False
        self.cur_team = self.cur_player = self.cur_team_edit = None
        self.btn_save.configure(state="normal")
        self.btn_saveas.configure(state="normal")
        self.btn_play.configure(state="normal")
        self.refresh_info()
        self.fill_team_list()
        self.fill_team_list2()
        self.fill_player_list()
        self.tv_roster.delete(*self.tv_roster.get_children())
        self.set_status("Archivo cargado. Haz los cambios y pulsa Guardar.")
        if self.gdb is None:
            if self.game_dir():
                self.start_gdb_load()
            elif not self.db.players:
                self.set_status("Archivo cargado. Para ver los nombres de los jugadores, indica la carpeta "
                                "del juego (📁 Carpeta del juego…).")

    def refresh_info(self):
        if not self.db:
            return
        mark = "  ·  ● cambios sin guardar" if self.db.dirty else ""
        self.info.configure(
            text=f"{short_path(self.path)}   ·   versión {self.db.ef.game_version or '?'}   ·   "
                 f"{self.db.num_players} jugadores en el EDIT   ·   {len(self.db.visible_teams())} equipos   ·   "
                 f"{len(self.gdb) if self.gdb else 0} nombres del juego{mark}",
            foreground=WARN if self.db.dirty else MUTED)
        self.title(("● " if self.db.dirty else "") + APP_TITLE)

    # ---------------------------------------------------- guardar y jugar
    def pes_running(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {PES_EXE}", "/NH"],
                                 capture_output=True, text=True, creationflags=0x08000000).stdout
        except OSError:
            return False
        return PES_EXE.lower() in out.lower()

    def save_and_play(self):
        """PES solo lee el EDIT al arrancar: cerrar el juego, guardar y volver a abrirlo."""
        if not self.db:
            return
        if self.pes_running():
            if not messagebox.askyesno(
                    APP_TITLE, "PES 2021 está abierto. El juego solo carga el EDIT al arrancar, "
                               "así que hay que cerrarlo para ver los cambios.\n\n"
                               "Se cerrará sin guardar lo que tengas a medias dentro del juego "
                               "(partido, Liga Master…). ¿Cerrar PES 2021 y continuar?"):
                return
            subprocess.run(["taskkill", "/IM", PES_EXE, "/F"], capture_output=True,
                           creationflags=0x08000000)
            for _ in range(40):          # esperar a que suelte el archivo
                if not self.pes_running():
                    break
                time.sleep(0.25)
            time.sleep(1.0)
        if not self._write(self.path):
            return
        try:
            gd = self.game_dir()
            exe = os.path.join(gd, PES_EXE) if gd else None
            if exe and os.path.isfile(exe):
                subprocess.Popen([exe], cwd=gd)          # abre el ejecutable de tu instalación
                self.set_status("Guardado. Abriendo PES 2021… los cambios se verán al cargar.")
            elif sys.platform == "win32":
                os.startfile(PES_STEAM_URL)  # noqa: S606
                self.set_status("Guardado. Abriendo PES 2021 desde Steam… los cambios se verán al cargar.")
            else:
                subprocess.Popen(["xdg-open", PES_STEAM_URL])
        except OSError as e:
            messagebox.showinfo(APP_TITLE, f"Guardado, pero no se pudo abrir Steam ({e}). Abre PES 2021 a mano.")

    def save_file(self):
        if self.db and self.path:
            self._write(self.path)

    def save_as(self):
        if not self.db:
            return
        path = filedialog.asksaveasfilename(title="Guardar EDIT como", initialfile="EDIT00000000",
                                            initialdir=os.path.dirname(self.path))
        if path:
            self._write(path)

    def _write(self, path):
        try:
            blob = crypt.encrypt(self.db.ef)
            # Verificación: el archivo cifrado debe descifrar a los mismos datos
            check = crypt.decrypt(blob)
            if bytes(check.data) != bytes(self.db.data):
                raise RuntimeError("La verificación del cifrado ha fallado; no se ha escrito nada.")
            if os.path.exists(path) and not self.backup_done:
                stamp = time.strftime("%Y%m%d_%H%M%S")
                shutil.copy2(path, f"{path}.backup_{stamp}")
                self.backup_done = True
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(blob)
            os.replace(tmp, path)
        except Exception as e:  # noqa: BLE001
            extra = ("\n\n¿Está PES 2021 abierto? Ciérralo o usa «Guardar y jugar»."
                     if isinstance(e, PermissionError) else "")
            messagebox.showerror(APP_TITLE, f"No se pudo guardar:\n\n{e}{extra}")
            return False
        self.path = path
        self.db.dirty = False
        self.refresh_info()
        self.set_status(f"Guardado en {short_path(path)}. Copia de seguridad creada junto al original.")
        return True

    def confirm_discard(self) -> bool:
        if self.db and self.db.dirty:
            return messagebox.askyesno(APP_TITLE, "Hay cambios sin guardar. ¿Descartarlos?")
        return True

    def on_close(self):
        if self.confirm_discard():
            self.destroy()

    # ---------------------------------------------------- utilidades
    def after_change(self, keep_slot=None):
        if self.cur_team:
            self.fill_roster(keep_slot)
        self._refresh_team_counts()
        self.refresh_info()

    def _refresh_team_counts(self):
        for iid in self.tv_teams.get_children():
            t = self.db.team_by_id[int(iid)]
            self.tv_teams.set(iid, "Jug.", len(t.roster()))

    def pname(self, pid: int) -> str:
        p = self.db.player_by_id.get(pid) if self.db else None
        if p and p.name:
            return p.name
        if self.gdb and pid in self.gdb.names:
            return self.gdb.names[pid]
        return f"Jugador #{pid}"

    def view(self, pid: int):
        """Jugador del EDIT, o vista de solo lectura de la base del juego, o None."""
        p = self.db.player_by_id.get(pid) if self.db else None
        if p is not None:
            return p
        if self.gdb and pid in self.gdb.raw:
            return RawPlayer(self.gdb.raw[pid])
        return None

    # ---------------------------------------------------- base del juego
    def game_dir(self) -> str | None:
        d = self.cfg.get("game_dir")
        if d and os.path.isdir(d):
            return d
        guesses = G.guess_game_dirs()
        return guesses[0] if guesses else None

    def start_gdb_load(self, use_cache=True):
        d = self.game_dir()
        if not d or not self.db or self.gdb_loading:
            return
        self.gdb_loading = True
        self._jobs += 1
        ids = set(self.db.teams_of)

        def work():
            try:
                res = G.load_game_db(d, ids, progress=lambda m: self._q.put(("status", m)), use_cache=use_cache)
                self._q.put(("gdb", res))
            except Exception as e:  # noqa: BLE001
                self._q.put(("gdb_error", str(e)))
        threading.Thread(target=work, daemon=True).start()
        self.after(100, self._poll)

    def _poll(self):
        try:
            while True:
                kind, val = self._q.get_nowait()
                if kind == "status":
                    self.set_status(val)
                elif kind == "gdb":
                    self.gdb_loading = False
                    self._jobs -= 1
                    self.gdb = val
                    self._gdb_refresh()
                    n = len(val)
                    self.set_status(f"Nombres cargados desde el juego: {n}." if n else
                                    "No se pudieron leer nombres de la carpeta del juego "
                                    "(📁 Carpeta del juego… › Ver informe).")
                elif kind == "gdb_error":
                    self.gdb_loading = False
                    self._jobs -= 1
                    self.set_status(f"Error leyendo la carpeta del juego: {val}")
                elif kind == "dump":
                    self._jobs -= 1
                    self.set_status("Diagnóstico terminado.")
                    messagebox.showinfo(APP_TITLE, val)
        except queue.Empty:
            pass
        if self._jobs > 0 or not self._q.empty():
            self.after(150, self._poll)

    def _gdb_refresh(self):
        if not self.db:
            return
        self.refresh_info()
        if self.cur_team:
            sel = self.tv_roster.selection()
            self.fill_roster(int(sel[0]) if sel else None)

    def game_dialog(self):
        GameFolderDialog(self)

    def set_game_dir(self, path: str):
        self.cfg["game_dir"] = path
        G.save_config(self.cfg)
        self.gdb = None
        self.start_gdb_load(use_cache=True)

    def set_status(self, text):
        self.status.configure(text=text)


class PlayerPicker(tk.Toplevel):
    """Diálogo para elegir el jugador a fichar: por nombre, por ID o desde la plantilla de un equipo."""

    def __init__(self, app: App, title: str):
        super().__init__(app)
        self.app, self.db = app, app.db
        self.result = None
        self.title(title)
        self.configure(bg=PANEL)
        self.geometry("720x580")
        self.transient(app)
        frm = ttk.Frame(self, style="Panel.TFrame", padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=title, style="Head.TLabel").pack(anchor="w")
        row0 = ttk.Frame(frm, style="Panel.TFrame")
        row0.pack(fill="x", pady=(8, 2))
        ttk.Label(row0, text="Ver plantilla de:", style="Panel.TLabel").pack(side="left")
        self.teams = [t for t in self.db.visible_teams() if t is not app.cur_team]
        self.team_cb = ttk.Combobox(row0, values=[t.name for t in self.teams], state="readonly", width=36)
        self.team_cb.pack(side="left", padx=6)
        self.team_cb.bind("<<ComboboxSelected>>", lambda ev: self.show_team())
        row = ttk.Frame(frm, style="Panel.TFrame")
        row.pack(fill="x", pady=(2, 8))
        ttk.Label(row, text="o buscar nombre / ID:", style="Panel.TLabel").pack(side="left")
        self.q = tk.StringVar()
        e = ttk.Entry(row, textvariable=self.q, width=24)
        e.pack(side="left", padx=6)
        e.bind("<Return>", lambda ev: self.search())
        ttk.Button(row, text="Buscar", command=self.search).pack(side="left")
        self.free = tk.BooleanVar()
        ttk.Checkbutton(row, text="Solo agentes libres", variable=self.free, command=self.search).pack(side="left", padx=6)
        f, self.tv = app._tree(frm, ("Dorsal", "Jugador", "Equipo actual", "Pos", "Edad"),
                               (55, 230, 220, 50, 50), height=13)
        f.pack(fill="both", expand=True)
        self.tv.bind("<<TreeviewSelect>>", lambda ev: self.on_sel())
        self.tv.bind("<Double-1>", lambda ev: self.ok())
        orow = ttk.Frame(frm, style="Panel.TFrame")
        orow.pack(fill="x", pady=(8, 0))
        ttk.Label(orow, text="Sale de:", style="Panel.TLabel").pack(side="left")
        self.origin = ttk.Combobox(orow, state="readonly", width=40)
        self.origin.pack(side="left", padx=6)
        self.keep = tk.BooleanVar()
        ttk.Checkbutton(frm, text="No quitarlo del equipo de origen (útil para selecciones nacionales)",
                        variable=self.keep).pack(anchor="w", pady=6)
        btns = ttk.Frame(frm, style="Panel.TFrame")
        btns.pack(fill="x")
        ttk.Button(btns, text="Fichar", style="Accent.TButton", command=self.ok).pack(side="right")
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="right", padx=6)
        self.team_cb.focus_set()
        self.grab_set()
        self.wait_window()

    def _row(self, pid, num, n):
        p = self.app.view(pid)
        teams = self.db.teams_of.get(pid, [])
        pos = POSITIONS[p["reg_pos"]] if p and p["reg_pos"] < 13 else ""
        self.tv.insert("", "end", iid=str(pid),
                       values=(num, self.app.pname(pid), " / ".join(t.name for t in teams) or "Agente libre",
                               pos, p["age"] if p else ""),
                       tags=("odd",) if n % 2 else ())

    def show_team(self):
        self.tv.delete(*self.tv.get_children())
        i = self.team_cb.current()
        if i < 0:
            return
        for n, (pid, num) in enumerate(self.teams[i].roster()):
            self._row(pid, num, n)

    def search(self):
        q = self.q.get().strip().lower()
        self.tv.delete(*self.tv.get_children())
        if len(q) < 2 and not self.free.get():
            return
        if q.isdigit() and int(q) in self.db.teams_of or (q.isdigit() and int(q) in self.db.player_by_id):
            self._row(int(q), "", 0)
            return
        n = 0
        seen = set()
        for p in self.db.players:
            if not p.id or (q and q not in p.name.lower()):
                continue
            if self.free.get() and self.db.teams_of.get(p.id):
                continue
            self._row(p.id, "", n)
            seen.add(p.id)
            n += 1
            if n >= 400:
                return
        if self.app.gdb:
            for pid, name in self.app.gdb.names.items():
                if pid in seen or (q and q not in name.lower()):
                    continue
                if self.free.get() and self.db.teams_of.get(pid):
                    continue
                if self.tv.exists(str(pid)):
                    continue
                self._row(pid, "", n)
                n += 1
                if n >= 400:
                    return

    def on_sel(self):
        sel = self.tv.selection()
        if not sel:
            return
        teams = self.db.teams_of.get(int(sel[0]), [])
        names = [t.name for t in teams] or ["(agente libre)"]
        self.origin.configure(values=names)
        cur = self.team_cb.current()
        self.origin.current(teams.index(self.teams[cur]) if cur >= 0 and self.teams[cur] in teams else 0)

    def ok(self):
        sel = self.tv.selection()
        if not sel:
            return
        pid = int(sel[0])
        teams = self.db.teams_of.get(pid, [])
        origin = teams[self.origin.current()] if teams and self.origin.current() >= 0 else None
        self.result = (pid, origin, self.keep.get())
        self.destroy()


class GameFolderDialog(tk.Toplevel):
    """Elegir la carpeta de instalación de PES 2021 y ver qué se ha leído de ella."""

    def __init__(self, app: App):
        super().__init__(app)
        self.app = app
        self.title("Carpeta del juego")
        self.configure(bg=PANEL)
        self.geometry("760x520")
        self.transient(app)
        frm = ttk.Frame(self, style="Panel.TFrame", padding=14)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Carpeta de instalación de PES 2021", style="Head.TLabel").pack(anchor="w")
        ttk.Label(frm, text="Es la carpeta que contiene «Data» y «download», normalmente\n"
                  r"C:\Program Files (x86)\Steam\steamapps\common\eFootball PES 2021",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 8))
        row = ttk.Frame(frm, style="Panel.TFrame")
        row.pack(fill="x")
        self.path = tk.StringVar(value=app.game_dir() or "")
        ttk.Entry(row, textvariable=self.path, width=70).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Elegir…", command=self.choose).pack(side="left", padx=6)
        btns = ttk.Frame(frm, style="Panel.TFrame")
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="Usar esta carpeta y leer nombres", style="Accent.TButton",
                   command=self.use).pack(side="left")
        ttk.Button(btns, text="Releer (sin caché)", command=self.reload).pack(side="left", padx=6)
        ttk.Button(btns, text="Guardar diagnóstico…", command=self.dump).pack(side="left")
        ttk.Label(frm, text="Informe de la última lectura:", style="Muted.TLabel").pack(anchor="w", pady=(6, 2))
        self.txt = tk.Text(frm, height=16, bg=PANEL2, fg=FG, relief="flat", wrap="none",
                           insertbackground=FG, font=("Consolas", 9) if sys.platform == "win32" else ("DejaVu Sans Mono", 9))
        self.txt.pack(fill="both", expand=True)
        self.show_report()

    def show_report(self):
        self.txt.delete("1.0", "end")
        g = self.app.gdb
        if self.app.gdb_loading:
            self.txt.insert("end", "Leyendo… (mira la barra de estado)")
            self.after(800, self.show_report)
        elif g is None:
            self.txt.insert("end", "Todavía no se ha leído ninguna carpeta del juego.")
        else:
            self.txt.insert("end", "\n".join(g.report))

    def choose(self):
        d = filedialog.askdirectory(title="Carpeta de instalación de PES 2021", parent=self,
                                    initialdir=self.path.get() or None)
        if d:
            self.path.set(d)

    def _check(self) -> str | None:
        d = self.path.get().strip()
        if not d or not os.path.isdir(d):
            messagebox.showerror(APP_TITLE, "Esa carpeta no existe.", parent=self)
            return None
        if not self.app.db:
            messagebox.showinfo(APP_TITLE, "Abre primero tu EDIT: se usa para reconocer el formato.", parent=self)
            return None
        return d

    def use(self):
        d = self._check()
        if d:
            self.app.set_game_dir(d)
            self.show_report()

    def reload(self):
        d = self._check()
        if d:
            self.app.cfg["game_dir"] = d
            G.save_config(self.app.cfg)
            self.app.gdb = None
            self.app.start_gdb_load(use_cache=False)
            self.show_report()

    def dump(self):
        d = self._check()
        if not d:
            return
        out = filedialog.askdirectory(title="¿Dónde guardo el diagnóstico?", parent=self)
        if not out:
            return
        ids = set(self.app.db.teams_of)
        app = self.app

        def work():
            try:
                g = G.load_game_db(d, ids, progress=lambda m: app._q.put(("status", m)), dump_dir=out)
                with open(os.path.join(out, "informe.txt"), "w", encoding="utf-8") as f:
                    f.write("\n".join(g.report))
                app._q.put(("dump", f"Diagnóstico guardado en:\n{out}\n\nIncluye informe.txt y los Player.bin "
                                    "extraídos."))
            except Exception as e:  # noqa: BLE001
                app._q.put(("dump", f"Error al generar el diagnóstico: {e}"))
        app._jobs += 1
        threading.Thread(target=work, daemon=True).start()
        app.after(150, app._poll)
        app.set_status("Generando diagnóstico…")


class CreatePlayerDialog(tk.Toplevel):
    def __init__(self, app: App):
        super().__init__(app)
        self.app, self.db = app, app.db
        self.result = None
        self.title("Crear jugador")
        self.configure(bg=PANEL)
        self.geometry("620x560")
        self.transient(app)
        frm = ttk.Frame(self, style="Panel.TFrame", padding=14)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Crear jugador", style="Head.TLabel").pack(anchor="w")
        ttk.Label(frm, text="El nuevo jugador parte de una copia de otro (cara, físico y habilidades); "
                  "después lo ajustas en la pestaña Jugadores.", style="Muted.TLabel",
                  wraplength=560).pack(anchor="w", pady=(2, 10))
        r = ttk.Frame(frm, style="Panel.TFrame")
        r.pack(fill="x")
        ttk.Label(r, text="Nombre:", style="Panel.TLabel").pack(side="left")
        self.name = tk.StringVar()
        ttk.Entry(r, textvariable=self.name, width=36).pack(side="left", padx=6)

        ttk.Label(frm, text="Copiar de (busca un jugador base):", style="Panel.TLabel").pack(anchor="w", pady=(10, 2))
        r2 = ttk.Frame(frm, style="Panel.TFrame")
        r2.pack(fill="x")
        self.q = tk.StringVar()
        e = ttk.Entry(r2, textvariable=self.q, width=30)
        e.pack(side="left")
        e.bind("<Return>", lambda ev: self.search())
        ttk.Button(r2, text="Buscar", command=self.search).pack(side="left", padx=6)
        f, self.tv = app._tree(frm, ("Nombre", "Pos", "Edad", "Media"), (260, 50, 50, 55), height=8)
        f.pack(fill="both", expand=True, pady=6)

        r3 = ttk.Frame(frm, style="Panel.TFrame")
        r3.pack(fill="x", pady=4)
        ttk.Label(r3, text="Añadir al equipo:", style="Panel.TLabel").pack(side="left")
        teams = app.db.visible_teams()
        self.teams = teams
        self.team_cb = ttk.Combobox(r3, values=["(ninguno)"] + [t.name for t in teams], state="readonly", width=34)
        self.team_cb.current(0)
        if app.cur_team in teams:
            self.team_cb.current(teams.index(app.cur_team) + 1)
        self.team_cb.pack(side="left", padx=6)

        self.mode = tk.StringVar(value="recycle")
        ttk.Radiobutton(frm, text="Reutilizar el hueco de un agente libre (recomendado, el juego lo acepta siempre)",
                        variable=self.mode, value="recycle").pack(anchor="w", pady=(8, 0))
        ttk.Radiobutton(frm, text="Añadir un registro nuevo (experimental: haz copia antes de probar)",
                        variable=self.mode, value="new").pack(anchor="w")
        btns = ttk.Frame(frm, style="Panel.TFrame")
        btns.pack(fill="x", pady=(12, 0))
        ttk.Button(btns, text="Crear", style="Accent.TButton", command=self.ok).pack(side="right")
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="right", padx=6)
        self.grab_set()
        self.wait_window()

    def search(self):
        q = self.q.get().strip().lower()
        self.tv.delete(*self.tv.get_children())
        if len(q) < 2:
            return
        n = 0
        for p in self.db.players:
            if p.id and q in p.name.lower():
                self.tv.insert("", "end", iid=str(p.index),
                               values=(p.name, POSITIONS[p["reg_pos"]] if p["reg_pos"] < 13 else "?",
                                       p["age"], p.overall()))
                n += 1
                if n >= 300:
                    break

    def ok(self):
        name = self.name.get().strip()
        sel = self.tv.selection()
        if not name or not sel:
            messagebox.showinfo(APP_TITLE, "Escribe un nombre y elige un jugador base.", parent=self)
            return
        template = self.db.players[int(sel[0])]
        i = self.team_cb.current()
        team = self.teams[i - 1] if i > 0 else None
        self.result = (name, template, self.mode.get(), team)
        self.destroy()


if __name__ == "__main__":
    app = App()
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        app.after(100, lambda: app.load_path(sys.argv[1]))
    app.mainloop()
