#!/usr/bin/env python3
"""
Pokemon Insurgence Save Editor
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os, shutil, re, sys, time, copy

from rubymarshal.reader import loads
from rubymarshal.writer import writes

from rubymarshal.writer import Writer
from rubymarshal.constants import TYPE_FIXNUM, TYPE_BIGNUM
import math

class Ruby18Writer(Writer):
    def write_int(self, obj):
        if -1073741824 <= obj <= 1073741823:
            self.fd.write(TYPE_FIXNUM)
            self.write_long(obj)
        else:
            if not self.must_write(obj): return
            self.fd.write(TYPE_BIGNUM)
            self.fd.write(b'+' if obj >= 0 else b'-')
            obj = abs(obj)
            size = int(math.ceil(obj.bit_length() / 16.0))
            self.write_long(size)
            for i in range(size):
                self.write_short(obj % 65536)
                obj //= 65536
                
    def write_bytes(self, obj):
        if not self.must_write(obj): return
        super().write_bytes(obj)

    def write_string(self, obj):
        if not self.must_write(obj): return
        super().write_string(obj)

    def write_float(self, obj):
        if not self.must_write(obj): return
        super().write_float(obj)

from rubymarshal.classes import RubyObject

def resource_path(relative: str) -> str:
    """Resolve paths for both normal runs and PyInstaller bundles."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)

def get_latest_save_file() -> str:
    base_dir = os.path.join(os.path.expanduser("~"), "Saved Games", "Pokemon Insurgence")
    if not os.path.isdir(base_dir):
        return ""
    # Only load actual save slots, not the game's automatic backups
    rx_files = [
        os.path.join(base_dir, f) for f in os.listdir(base_dir) 
        if f.lower().startswith("game") and f.lower().endswith(".rxdata")
    ]
    if not rx_files:
        return ""
    return max(rx_files, key=os.path.getmtime)

DEFAULT_SAVE_DIR = os.path.join(os.path.expanduser("~"), "Saved Games", "Pokemon Insurgence")

STATS   = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]
NATURES = ["Hardy","Lonely","Brave","Adamant","Naughty","Bold","Docile","Relaxed",
           "Impish","Lax","Timid","Hasty","Serious","Jolly","Naive","Modest","Mild",
           "Quiet","Bashful","Rash","Calm","Gentle","Sassy","Careful","Quirky"]
EV_PRESETS = {
    "Fresh / zero EVs": [0, 0, 0, 0, 0, 0],
    "Balanced": [85, 85, 85, 85, 85, 85],
    "Physical attacker": [4, 252, 0, 0, 0, 252],
    "Special attacker": [4, 0, 0, 252, 0, 252],
    "Bulky physical": [252, 252, 4, 0, 0, 0],
    "Bulky special": [252, 0, 0, 252, 4, 0],
    "Custom": [0, 0, 0, 0, 0, 0],
}

POKEMON_TYPES = [
    "Normal","Fire","Water","Electric","Grass","Ice","Fighting","Poison",
    "Ground","Flying","Psychic","Bug","Rock","Ghost","Dragon","Dark","Steel","Shadow","Bird","Crystal","Fairy",
]
PKMN_STAGE_LIST  = ["All", "Baby", "1", "2", "3"]
PKMN_RARITY_LIST = ["All", "Common", "Legendary", "Mythical"]
def _exp_for_level(growth: str, level: int) -> int:
    n = level
    if growth == "fast":
        return 4 * n**3 // 5
    elif growth == "medium-slow":
        return max(0, int(6 * n**3 / 5 - 15 * n**2 / 4 + 100 * n / 3 - 140))
    elif growth == "slow":
        return 5 * n**3 // 4
    elif growth == "erratic":
        if n <= 50:  return n**3 * (100 - n) // 50
        elif n <= 68: return n**3 * (150 - n) // 100
        elif n <= 98: return n**3 * ((1911 - 10 * n) // 3) // 500
        else:         return n**3 * (160 - n) // 100
    elif growth == "fluctuating":
        if n <= 15:  return n**3 * ((n + 1) // 3 + 24) // 50
        elif n <= 35: return n**3 * (n + 14) // 50
        else:         return n**3 * (n // 2 + 32) // 50
    else:  # medium-fast (default)
        return n**3

def _default_level(stage: str, rarity: str) -> int:
    if rarity in ("Legendary", "Mythical"):
        return 50
    return {"Baby": 5, "1": 15, "2": 35, "3": 50}.get(stage, 15)

def _sanitize_evs(evs) -> list:
    result = []
    for i in range(6):
        try:
            val = int(evs[i])
        except (TypeError, ValueError, IndexError):
            val = 0
        result.append(min(252, max(0, val)))
    while sum(result) > 510:
        idx = max(range(6), key=lambda j: result[j])
        result[idx] -= 1
    return result

def _load_pokemon_data():
    path = resource_path("pokemon_data.txt")
    data = {}
    if not os.path.exists(path):
        return data
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 12:
                continue
            try:
                sid = int(parts[0])
                if sid in data:
                    continue
                data[sid] = {
                    "name":   parts[1],
                    "type1":  parts[2],
                    "type2":  parts[3],
                    "stage":  parts[4],
                    "rarity": parts[5],
                    "hp":  int(parts[6]),
                    "atk": int(parts[7]),
                    "def": int(parts[8]),
                    "spa": int(parts[9]),
                    "spd": int(parts[10]),
                    "spe": int(parts[11]),
                    "growth": parts[12] if len(parts) > 12 else "medium-fast",
                    "kind": parts[13] if len(parts) > 13 else "",
                    "entry": parts[14] if len(parts) > 14 else "",
                    "color": parts[15] if len(parts) > 15 else "",
                    "habitat": parts[16] if len(parts) > 16 else "",
                    "gender_rate": parts[17] if len(parts) > 17 else "",
                    "base_happiness": int(parts[18]) if len(parts) > 18 and parts[18].isdigit() else 70,
                    "steps_to_hatch": int(parts[19]) if len(parts) > 19 and parts[19].isdigit() else 0,
                    "height": int(parts[20]) if len(parts) > 20 and parts[20].isdigit() else 0,
                    "weight": int(parts[21]) if len(parts) > 21 and parts[21].isdigit() else 0,
                    "base_exp": int(parts[22]) if len(parts) > 22 and parts[22].isdigit() else 0,
                    "ev_yield": [
                        int(parts[i]) if len(parts) > i and parts[i].isdigit() else 0
                        for i in range(23, 29)
                    ],
                    "abilities": [p for p in (parts[29] if len(parts) > 29 else "", parts[30] if len(parts) > 30 else "") if p],
                    "hidden_ability": parts[31] if len(parts) > 31 else "",
                    "egg_groups": [p for p in (parts[32] if len(parts) > 32 else "", parts[33] if len(parts) > 33 else "") if p],
                    "catch_rate": int(parts[34]) if len(parts) > 34 and parts[34].isdigit() else 0,
                }
            except (ValueError, IndexError):
                pass
    return data

# Pocket 0 = unused, 1 = Items, 2 = Medicine, 3 = Balls, 4 = TMs, 5 = Berries,
# 6 = Mail, 7 = Clothes/Mail depending on save data, 8 = Key Items
POCKET_NAMES = ["Pocket 0","Items","Medicine","Poke Balls","TMs & HMs",
                "Berries","Mail","Clothes","Key Items","Pocket 9"]

# ── item data ─────────────────────────────────────────────────────────────────

def _load_item_data():
    item_file = resource_path("item_data.txt")
    if not os.path.exists(item_file):
        item_file = resource_path("item_ids.txt")
    data:  dict[int, dict] = {}
    names: dict[int, str] = {}
    cats:  dict[int, str] = {}
    if not os.path.exists(item_file):
        return data, names, cats
    with open(item_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            try:
                iid = int(parts[0])
            except (ValueError, IndexError):
                continue
            if len(parts) >= 12:
                name = parts[2]
                data[iid] = {
                    "id": iid,
                    "source_id": int(parts[1]) if parts[1].isdigit() else (iid - 1) // 2,
                    "name": name,
                    "pocket": parts[3],
                    "price": int(parts[4]) if parts[4].isdigit() else 0,
                    "description": parts[5],
                    "field_use": parts[6],
                    "battle_use": parts[7],
                    "item_type": parts[8],
                    "move_id": int(parts[9]) if parts[9].isdigit() else 0,
                    "machine_type": int(parts[10]) if parts[10].isdigit() else 100,
                    "machine_category": int(parts[11]) if parts[11].isdigit() else 101,
                }
                names[iid] = name
                cats[iid] = parts[3]
            elif len(parts) >= 11:
                name = parts[1]
                data[iid] = {
                    "id": iid,
                    "source_id": (iid - 1) // 2,
                    "name": name,
                    "pocket": parts[2],
                    "price": int(parts[3]) if parts[3].isdigit() else 0,
                    "description": parts[4],
                    "field_use": parts[5],
                    "battle_use": parts[6],
                    "item_type": parts[7],
                    "move_id": int(parts[8]) if parts[8].isdigit() else 0,
                    "machine_type": int(parts[9]) if parts[9].isdigit() else 100,
                    "machine_category": int(parts[10]) if parts[10].isdigit() else 101,
                }
                names[iid] = name
                cats[iid] = parts[2]
            elif len(parts) >= 2:
                name = parts[1]
                data[iid] = {"id": iid, "name": name, "pocket": "Items", "description": ""}
                names[iid] = name
                cats[iid] = "Items"
    return data, names, cats

ITEM_DATA, ITEM_NAMES, ITEM_CATS = _load_item_data()
ITEM_CAT_LIST = ["All"] + sorted(set(ITEM_CATS.values()))
PKMN_DATA = _load_pokemon_data()
POKEMON_DATA = {
    sid: {"name": d["name"], "t1": d["type1"], "t2": d["type2"], "stage": d["stage"], "rarity": d["rarity"]}
    for sid, d in PKMN_DATA.items()
}

def _load_move_data():
    path = resource_path("move_data.txt")
    data = {}
    if not os.path.exists(path):
        return data
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 7:
                continue
            try:
                mid = int(parts[0])
                data[mid] = {
                    "name":        parts[1],
                    "type":        parts[2],
                    "category":    parts[3],
                    "pp":          int(parts[4]),
                    "power":       int(parts[5]),
                    "accuracy":    int(parts[6]),
                    "description": parts[7] if len(parts) > 7 else "",
                }
            except (ValueError, IndexError):
                pass
    return data

def _load_learnset_data():
    path = resource_path("learnset_data.txt")
    data = {}
    if not os.path.exists(path):
        return data
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|", 1)
            if len(parts) < 2:
                continue
            try:
                sid = int(parts[0].strip())
                move_str = parts[1].strip()
                moves = []
                for token in move_str.split():
                    lv, mid = token.split(":")
                    moves.append((int(lv), int(mid)))
                data[sid] = moves
            except (ValueError, IndexError):
                pass
    return data

MOVE_DATA     = _load_move_data()
LEARNSET_DATA = _load_learnset_data()

# ── helpers ───────────────────────────────────────────────────────────────────

def ds(s):
    if isinstance(s, (bytes, bytearray)): return s.decode("utf-8", "replace")
    return str(s) if s is not None else ""

def split_streams(raw: bytes):
    return [i for i in range(len(raw) - 1) if raw[i] == 0x04 and raw[i+1] == 0x08]

def find_pid(nature_i, shiny, trainer_id, secret_id):
    if shiny:
        for hi in range(0x10000):
            for k in range(8):
                lo = (trainer_id ^ secret_id ^ hi ^ k) & 0xFFFF
                pid = (hi << 16) | lo
                if pid % 25 == nature_i:
                    return pid
    else:
        pid = nature_i
        while pid < 0x100000000:
            if (trainer_id ^ secret_id ^ (pid >> 16) ^ (pid & 0xFFFF)) >= 8:
                return pid
            pid += 25
    return nature_i

def is_shiny(pid, trainer_id, secret_id):
    if not isinstance(pid, int): return False
    return (trainer_id ^ secret_id ^ (pid >> 16) ^ (pid & 0xFFFF)) < 8

def item_display_name(internet_id: int) -> str:
    return ITEM_NAMES.get(internet_id, f"Unknown (#{internet_id})")

_CAT_TO_POCKET = {
    "Items":        1,
    "Medicine":     2,
    "Poke Balls":   3,
    "TMs & HMs":    4,
    "Berries":      5,
    "Mail":         6,
    "Clothes":      7,
    "Key Items":    8,
}

def pocket_for_item(internet_id: int) -> int:
    cat = ITEM_CATS.get(internet_id, "Items")
    return _CAT_TO_POCKET.get(cat, 1)


# ── main editor ───────────────────────────────────────────────────────────────

class Editor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pokemon Insurgence Save Editor")
        self.resizable(True, True)
        self.minsize(900, 600)

        # Fix taskbar icon on Windows
        if os.name == "nt":
            import ctypes
            try:
                myappid = "hebopaul.pokemoninsurgencesaveeditor.1.0"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass

        # Icon
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass

        # Native Windows theme — much cleaner than the default
        ttk.Style().theme_use("vista")

        self.raw          = None
        self.positions    = []
        self.trainer      = None
        self.bag          = None
        self.bag_idx      = None
        self.storage      = None
        self.storage_idx  = None
        self.save_path    = get_latest_save_file() or os.path.join(DEFAULT_SAVE_DIR, "Game.rxdata")
        self.trainer_id   = 0
        self.secret_id    = 0

        self.var_money  = tk.StringVar()
        self.var_bp     = tk.StringVar()
        self.var_sid    = tk.StringVar(value="—")
        self.badge_vars = [tk.BooleanVar() for _ in range(8)]
        self.pkmn_vars  = []
        self.bag_rows   = []
        self.box_vars   = []
        self._scroll_canvases: set = set()
        self._pokemon_sprite_cache = {}
        self._item_icon_cache = {}

        self._build_ui()
        self.bind_all("<MouseWheel>", self._on_mousewheel)
        if os.path.exists(self.save_path):
            self._do_load(self.save_path)

    def _on_mousewheel(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        while w is not None:
            if w in self._scroll_canvases:
                w.yview_scroll(int(-1 * (e.delta / 120)), "units")
                return
            w = getattr(w, "master", None)

    def _make_scrollable(self, canvas: tk.Canvas):
        self._scroll_canvases.add(canvas)

    def _pokemon_types_text(self, data: dict) -> str:
        type1 = data.get("type1", "")
        type2 = data.get("type2", "")
        return type1 + (f" / {type2}" if type2 else "")

    def _pokemon_measure_text(self, data: dict) -> str:
        height = data.get("height", 0)
        weight = data.get("weight", 0)
        h_text = f"{height / 10:.1f} m" if height else "-"
        w_text = f"{weight / 10:.1f} kg" if weight else "-"
        return f"{h_text}, {w_text}"

    def _pokemon_abilities_text(self, data: dict) -> str:
        abilities = list(data.get("abilities", []))
        hidden = data.get("hidden_ability", "")
        if hidden:
            abilities.append(f"Hidden: {hidden}")
        return ", ".join(abilities) if abilities else "-"

    def _pokemon_sprite_paths(self, species_id: int, form: int = 0) -> list:
        names = []
        if form:
            names.extend([f"{species_id:03d}_{form}.png", f"{species_id:03d}-{form}.png", f"{species_id:03d}{form}.png"])
        names.append(f"{species_id:03d}.png")
        dirs = [
            resource_path(os.path.join("game_resources", "Graphics", "Battlers")),
            os.path.join(r"G:\Games\Insurgence\Pokemon Insurgence 1.2.7 Core", "Graphics", "Battlers"),
        ]
        return [os.path.join(base, name) for base in dirs for name in names]

    def _load_pokemon_sprite(self, species_id: int, form: int = 0, max_size: int = 96):
        for path in self._pokemon_sprite_paths(species_id, form):
            if not os.path.exists(path):
                continue
            key = (path, max_size)
            if key in self._pokemon_sprite_cache:
                return self._pokemon_sprite_cache[key]
            try:
                img = tk.PhotoImage(file=path)
                scale = max(1, math.ceil(max(img.width(), img.height()) / max_size))
                if scale > 1:
                    img = img.subsample(scale, scale)
                self._pokemon_sprite_cache[key] = img
                return img
            except Exception:
                continue
        return None

    def _set_pokemon_dex_vars(self, v: dict, species_id: int, form: int = 0):
        data = PKMN_DATA.get(species_id, {})
        name = data.get("name", f"Species#{species_id}" if species_id else "-")
        v["dex_name"].set(f"#{species_id} {name}" if species_id else "-")
        v["dex_types"].set(self._pokemon_types_text(data) if data else "-")
        v["dex_kind"].set((data.get("kind", "") + " Pokemon").strip() if data.get("kind") else "-")
        v["dex_size"].set(self._pokemon_measure_text(data) if data else "-")
        v["dex_color_habitat"].set(" / ".join(p for p in (data.get("color", ""), data.get("habitat", "")) if p) or "-")
        v["dex_abilities"].set(self._pokemon_abilities_text(data) if data else "-")
        v["dex_entry"].set(data.get("entry", "") or "-")
        img = self._load_pokemon_sprite(species_id, form)
        label = v.get("dex_sprite")
        if label:
            label.configure(image=img if img else "", text="" if img else "(no sprite)")
            label.image = img

    def _make_pokemon_dex_panel(self, parent, species_id: int, form: int = 0, compact: bool = False):
        data = PKMN_DATA.get(species_id, {})
        frame = ttk.LabelFrame(parent, text="Pokedex", padding=4)
        sprite = ttk.Label(frame, anchor="center", width=12)
        sprite.grid(row=0, column=0, rowspan=5, sticky="n", padx=(0, 6))
        img = self._load_pokemon_sprite(species_id, form, max_size=72 if compact else 96)
        sprite.configure(image=img if img else "", text="" if img else "(no sprite)")
        sprite.image = img
        name = data.get("name", f"Species#{species_id}")
        lines = [
            f"#{species_id} {name}",
            self._pokemon_types_text(data),
            (data.get("kind", "") + " Pokemon").strip(),
            self._pokemon_measure_text(data),
            self._pokemon_abilities_text(data),
        ]
        for row, text in enumerate(lines):
            ttk.Label(frame, text=text or "-", anchor="w", width=28 if compact else 34).grid(row=row, column=1, sticky="w")
        ttk.Label(frame, text=data.get("entry", "") or "-", wraplength=240 if compact else 320, justify="left").grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )
        return frame

    def _item_icon_paths(self, item_id: int) -> list:
        source_id = ITEM_DATA.get(item_id, {}).get("source_id", (item_id - 1) // 2 if item_id else 0)
        names = [f"item{source_id:03d}.png", f"item{source_id:04d}.png", "item000.png"]
        dirs = [
            resource_path(os.path.join("game_resources", "Graphics", "Icons")),
            os.path.join(r"G:\Games\Insurgence\Pokemon Insurgence 1.2.7 Core", "Graphics", "Icons"),
        ]
        return [os.path.join(base, name) for base in dirs for name in names]

    def _load_item_icon(self, item_id: int, max_size: int = 32):
        for path in self._item_icon_paths(item_id):
            if not os.path.exists(path):
                continue
            key = (path, max_size)
            if key in self._item_icon_cache:
                return self._item_icon_cache[key]
            try:
                img = tk.PhotoImage(file=path)
                scale = max(1, math.ceil(max(img.width(), img.height()) / max_size))
                if scale > 1:
                    img = img.subsample(scale, scale)
                self._item_icon_cache[key] = img
                return img
            except Exception:
                continue
        return None

    def _show_item_info(self, item_id: int):
        data = ITEM_DATA.get(item_id, {"name": item_display_name(item_id), "description": ""})
        win = tk.Toplevel(self)
        win.title(data.get("name", f"Item #{item_id}"))
        win.geometry("460x330")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        top = ttk.Frame(win, padding=12)
        top.pack(fill="x")
        icon = self._load_item_icon(item_id, max_size=48)
        icon_label = ttk.Label(top, image=icon if icon else "", text="" if icon else "(no icon)", width=8, anchor="center")
        icon_label.image = icon
        icon_label.pack(side="left", padx=(0, 12))

        title = ttk.Frame(top)
        title.pack(side="left", fill="x", expand=True)
        ttk.Label(title, text=data.get("name", f"Item #{item_id}"), font=("", 12, "bold")).pack(anchor="w")
        ttk.Label(title, text=data.get("pocket", ""), foreground="gray").pack(anchor="w")

        body = ttk.Frame(win, padding=(12, 0, 12, 8))
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=data.get("description", "") or "No description available.", wraplength=420, justify="left").pack(
            anchor="w", fill="x", pady=(0, 10)
        )

        details = [
            ("Price", f"${data.get('price', 0)}" if data.get("price", 0) else "-"),
            ("Field use", data.get("field_use", "-")),
            ("Battle use", data.get("battle_use", "-")),
            ("Type", data.get("item_type", "-")),
        ]
        move_id = data.get("move_id", 0)
        if move_id:
            move_name = MOVE_DATA.get(move_id, {}).get("name", f"Move #{move_id}")
            details.append(("Teaches", f"{move_name} (#{move_id})"))
        grid = ttk.Frame(body)
        grid.pack(anchor="w", fill="x")
        for row, (label, value) in enumerate(details):
            ttk.Label(grid, text=label + ":", width=12, anchor="e").grid(row=row, column=0, sticky="e", pady=2, padx=(0, 6))
            ttk.Label(grid, text=str(value), anchor="w", wraplength=300).grid(row=row, column=1, sticky="w", pady=2)

        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))

    def _make_info_button(self, parent, command):
        canvas = tk.Canvas(parent, width=22, height=22, highlightthickness=0, bd=0)
        canvas.create_oval(2, 2, 20, 20, outline="#8aa9c8", fill="#f7fbff")
        canvas.create_text(11, 11, text="i", fill="#1266d6", font=("", 9, "bold"))
        canvas.bind("<Button-1>", lambda _e: command())
        canvas.bind("<Enter>", lambda _e: canvas.configure(cursor="hand2"))
        return canvas

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        ttk.Button(top, text="Load Save",          command=self._ask_load).pack(side="left", padx=4)
        ttk.Button(top, text="Save (auto-backup)", command=self._do_save).pack(side="left", padx=4)
        self.status = ttk.Label(top, text="No file loaded", foreground="gray")
        self.status.pack(side="left", padx=10)

        ttk.Separator(self, orient="horizontal").pack(fill="x")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        self.tab_trainer = ttk.Frame(nb, padding=10)
        self.tab_party   = ttk.Frame(nb, padding=10)
        self.tab_bag     = ttk.Frame(nb, padding=4)
        self.tab_boxes   = ttk.Frame(nb, padding=4)

        nb.add(self.tab_trainer, text="  Trainer  ")
        nb.add(self.tab_party,   text="  Party    ")
        nb.add(self.tab_bag,     text="  Bag      ")
        nb.add(self.tab_boxes,   text="  PC Boxes ")

        self._build_trainer_tab()
        self._build_party_tab()
        self._build_bag_tab()
        self._build_boxes_tab()

    # ── Trainer tab ──────────────────────────────────────────────────────────

    def _build_trainer_tab(self):
        f = self.tab_trainer
        row = 0

        ttk.Label(f, text="Trainer", font=("", 12, "bold")).grid(
            row=row, column=0, columnspan=3, pady=(0, 8)); row += 1

        def lbl_entry(label, var, r):
            ttk.Label(f, text=label, width=22, anchor="e").grid(row=r, column=0, sticky="e", pady=3, padx=4)
            ttk.Entry(f, textvariable=var, width=18).grid(row=r, column=1, sticky="w", pady=3, padx=4)

        lbl_entry("Money  (max 999999) :", self.var_money, row); row += 1
        lbl_entry("Battle Points :",       self.var_bp,    row); row += 1

        ttk.Label(f, text="Secret ID :", width=22, anchor="e").grid(row=row, column=0, sticky="e", pady=3, padx=4)
        ttk.Label(f, textvariable=self.var_sid, foreground="gray").grid(row=row, column=1, sticky="w", pady=3, padx=4)
        row += 1

        ttk.Label(f, text="Badges :", width=22, anchor="e").grid(row=row, column=0, sticky="e", pady=3, padx=4)
        bf = ttk.Frame(f)
        bf.grid(row=row, column=1, sticky="w")
        for i, v in enumerate(self.badge_vars):
            ttk.Checkbutton(bf, variable=v, text=f"#{i+1}").grid(row=0, column=i, padx=2)
        ttk.Button(f, text="All Badges", command=self._all_badges).grid(row=row, column=2, padx=8)
        row += 1

        ttk.Button(f, text="Heal All Party", command=self._heal_all_party).grid(
            row=row, column=1, sticky="w", pady=12)

    def _all_badges(self):
        for bv in self.badge_vars:
            bv.set(True)

    def _heal_all_party(self):
        party = self.trainer.attributes.get("@party", []) if self.trainer else []
        for slot, v in enumerate(self.pkmn_vars):
            if slot < len(party) and isinstance(party[slot], RubyObject):
                v["hp"].set(v["totalhp"].get())
                v["status"].set("0")
                self._restore_pp_from_obj(v, party[slot])
        self.status.config(text="All party healed.", foreground="blue")

    # ── Party tab ────────────────────────────────────────────────────────────

    def _build_party_tab(self):
        self.party_nb = ttk.Notebook(self.tab_party)
        self.party_nb.pack(fill="both", expand=True)
        self.pkmn_vars = []
        for slot in range(6):
            frame = ttk.Frame(self.party_nb, padding=8)
            self.party_nb.add(frame, text=f" Slot {slot+1} ")
            self.pkmn_vars.append(self._build_pkmn_slot(frame, slot))

    def _build_pkmn_slot(self, parent, slot: int = 0):
        v = {}
        v["editor_frame"] = ttk.Frame(parent)
        e = v["editor_frame"]

        lf = ttk.LabelFrame(e, text="Core Stats", padding=6)
        lf.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        for i, (key, lbl) in enumerate([
            ("species_id","Species ID"),("form","Form ID"),("nickname","Nickname"),
            ("hp","Current HP"),("totalhp","Max HP"),("attack","Attack"),
            ("defense","Defense"),("spatk","Sp.Atk"),("spdef","Sp.Def"),
            ("speed","Speed"),("exp","Experience"),
        ]):
            v[key] = tk.StringVar()
            ttk.Label(lf, text=lbl+":", width=14, anchor="e").grid(row=i, column=0, sticky="e", pady=2)
            ttk.Entry(lf, textvariable=v[key], width=10).grid(row=i, column=1, sticky="w", pady=2, padx=3)

        rf = ttk.LabelFrame(e, text="Extra", padding=6)
        rf.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        for i, (key, lbl) in enumerate([
            ("item","Held Item ID"),("happiness","Happiness"),
            ("status","Status (0=OK)"),("ball","Ball Used ID"),("obtain_lv","Obtained Lv"),
        ]):
            v[key] = tk.StringVar()
            ttk.Label(rf, text=lbl+":", width=14, anchor="e").grid(row=i, column=0, sticky="e", pady=2)
            ttk.Entry(rf, textvariable=v[key], width=10).grid(row=i, column=1, sticky="w", pady=2, padx=3)

        r = 5
        v["nature_idx"] = tk.StringVar()
        ttk.Label(rf, text="Nature:", width=14, anchor="e").grid(row=r, column=0, sticky="e", pady=2)
        ttk.Combobox(rf, textvariable=v["nature_idx"], values=NATURES, width=10, state="readonly").grid(
            row=r, column=1, sticky="w", padx=3, pady=2); r += 1

        v["ability_slot"] = tk.StringVar(value="0")
        ttk.Label(rf, text="Ability Slot:", width=14, anchor="e").grid(row=r, column=0, sticky="e", pady=2)
        ttk.Combobox(rf, textvariable=v["ability_slot"], values=["0","1"], width=10, state="readonly").grid(
            row=r, column=1, sticky="w", padx=3, pady=2); r += 1

        v["shiny"] = tk.BooleanVar()
        ttk.Label(rf, text="Shiny:", width=14, anchor="e").grid(row=r, column=0, sticky="e", pady=2)
        ttk.Checkbutton(rf, variable=v["shiny"]).grid(row=r, column=1, sticky="w", padx=3)

        bf = ttk.LabelFrame(e, text="Quick Actions", padding=6)
        bf.grid(row=0, column=2, sticky="n", padx=4, pady=4)
        ttk.Button(bf, text="Heal",       width=12, command=lambda vv=v: self._heal_slot(vv)).pack(pady=2)
        ttk.Button(bf, text="Max IVs",    width=12, command=lambda vv=v: self._max_ivs(vv)).pack(pady=2)
        ttk.Button(bf, text="Zero EVs",   width=12, command=lambda vv=v: self._zero_evs(vv)).pack(pady=2)
        ttk.Button(bf, text="Restore PP", width=12, command=lambda vv=v: self._restore_pp(vv)).pack(pady=2)

        df = ttk.LabelFrame(e, text="Pokedex", padding=6)
        df.grid(row=0, column=3, rowspan=3, sticky="nsew", padx=4, pady=4)
        v["dex_sprite"] = ttk.Label(df, width=14, anchor="center")
        v["dex_sprite"].grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        for row, (key, lbl) in enumerate([
            ("dex_name", "Species"),
            ("dex_types", "Type"),
            ("dex_kind", "Kind"),
            ("dex_size", "Size"),
            ("dex_color_habitat", "Color/Habitat"),
            ("dex_abilities", "Abilities"),
        ], start=1):
            v[key] = tk.StringVar(value="-")
            ttk.Label(df, text=lbl + ":", width=12, anchor="e").grid(row=row, column=0, sticky="e", pady=1)
            ttk.Label(df, textvariable=v[key], width=28, anchor="w", wraplength=220).grid(row=row, column=1, sticky="w", pady=1)
        v["dex_entry"] = tk.StringVar(value="-")
        ttk.Label(df, textvariable=v["dex_entry"], wraplength=300, justify="left").grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(6, 0)
        )

        ivf = ttk.LabelFrame(e, text="IVs  (0-31)", padding=6)
        ivf.grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        for i, stat in enumerate(STATS):
            v["iv_"+stat.lower()] = tk.StringVar()
            ttk.Label(ivf, text=stat, width=5).grid(row=0, column=i)
            ttk.Entry(ivf, textvariable=v["iv_"+stat.lower()], width=4).grid(row=1, column=i)

        evf = ttk.LabelFrame(e, text="EVs  (0–252, total ≤510)", padding=6)
        evf.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        for i, stat in enumerate(STATS):
            v["ev_"+stat.lower()] = tk.StringVar()
            ttk.Label(evf, text=stat, width=5).grid(row=0, column=i)
            ttk.Entry(evf, textvariable=v["ev_"+stat.lower()], width=4).grid(row=1, column=i)

        mf = ttk.LabelFrame(e, text="Moves", padding=6)
        mf.grid(row=2, column=0, columnspan=3, sticky="ew", padx=4, pady=4)
        for i in range(4):
            v[f"move{i}"]       = tk.StringVar(value="0")
            v[f"move{i}_name"]  = tk.StringVar(value="—")
            v[f"movepp{i}"]     = tk.StringVar(value="0")
            v[f"move{i}_maxpp"] = tk.StringVar(value="/0")
            ttk.Label(mf, text=f"Move {i+1}:", anchor="e", width=8).grid(row=i, column=0, sticky="e", padx=(2,0), pady=2)
            ttk.Label(mf, textvariable=v[f"move{i}_name"], width=20, anchor="w",
                      relief="sunken").grid(row=i, column=1, sticky="ew", padx=2, pady=2)
            ttk.Button(mf, text="Change", width=7,
                       command=lambda vv=v, ii=i: self._change_move(vv, ii)
                       ).grid(row=i, column=2, padx=(4,2), pady=2)
            ttk.Label(mf, text="PP:", anchor="e").grid(row=i, column=3, sticky="e", padx=(8,0))
            ttk.Entry(mf, textvariable=v[f"movepp{i}"], width=4).grid(row=i, column=4, padx=2)
            ttk.Label(mf, textvariable=v[f"move{i}_maxpp"], anchor="w", width=4).grid(row=i, column=5, sticky="w")
        mf.columnconfigure(1, weight=1)

        e.columnconfigure(0, weight=1)
        e.columnconfigure(1, weight=1)
        e.columnconfigure(3, weight=1)
        v["_pkmn_obj"] = None

        add_btn = ttk.Button(parent, text="+ Add Pokémon to this slot",
                             command=lambda s=slot: self._add_to_party_slot(s))
        v["add_btn"] = add_btn
        return v

    def _heal_slot(self, v):
        v["hp"].set(v["totalhp"].get())
        v["status"].set("0")
        pkmn = v.get("_pkmn_obj")
        if isinstance(pkmn, RubyObject):
            self._restore_pp_from_obj(v, pkmn)

    def _max_ivs(self, v):
        for stat in STATS: v["iv_"+stat.lower()].set("31")

    def _zero_evs(self, v):
        for stat in STATS: v["ev_"+stat.lower()].set("0")

    def _restore_pp(self, v):
        self._restore_pp_from_obj(v, None)

    def _restore_pp_from_obj(self, v, pkmn):
        for i in range(4):
            try:
                mid = int(v[f"move{i}"].get() or 0)
            except (ValueError, KeyError):
                mid = 0
            max_pp = MOVE_DATA.get(mid, {}).get("pp", 0)
            if max_pp:
                v[f"movepp{i}"].set(str(max_pp))


    def _open_pkmn_picker(self, callback):
        win = tk.Toplevel(self)
        win.title("Select Pokémon")
        win.geometry("700x600")
        win.transient(self); win.grab_set()

        top = ttk.Frame(win, padding=10); top.pack(fill="x")
        ttk.Label(top, text="Search:").pack(side="left")
        search_var = tk.StringVar()
        ent = ttk.Entry(top, textvariable=search_var)
        ent.pack(side="left", padx=5, fill="x", expand=True)
        ent.focus_set()

        filters = ttk.Frame(win, padding=5); filters.pack(fill="x")
        
        ttk.Label(filters, text="Type:").pack(side="left", padx=2)
        type_var = tk.StringVar(value="All")
        types = ["All", "Normal", "Fire", "Water", "Grass", "Electric", "Ice", "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Steel", "Dark", "Fairy"]
        ttk.Combobox(filters, textvariable=type_var, values=types, width=10, state="readonly").pack(side="left", padx=2)

        ttk.Label(filters, text="Stage:").pack(side="left", padx=2)
        stage_var = tk.StringVar(value="All")
        stages = ["All", "1st Stage", "2nd Stage", "3rd Stage", "Mega"]
        ttk.Combobox(filters, textvariable=stage_var, values=stages, width=10, state="readonly").pack(side="left", padx=2)

        ttk.Label(filters, text="Rarity:").pack(side="left", padx=2)
        rarity_var = tk.StringVar(value="All")
        rarities = ["All", "Standard", "Legendary", "Mythical"]
        ttk.Combobox(filters, textvariable=rarity_var, values=rarities, width=10, state="readonly").pack(side="left", padx=2)

        frame = ttk.Frame(win, padding=10); frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=("id", "name", "types", "stage", "rarity"), show="headings", selectmode="browse")
        tree.heading("id", text="ID"); tree.column("id", width=50)
        tree.heading("name", text="Name"); tree.column("name", width=150)
        tree.heading("types", text="Types"); tree.column("types", width=120)
        tree.heading("stage", text="Stage"); tree.column("stage", width=80)
        tree.heading("rarity", text="Rarity"); tree.column("rarity", width=80)
        
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        def refresh(*_):
            tree.delete(*tree.get_children())
            search = search_var.get().lower()
            t_filter = type_var.get()
            s_filter = stage_var.get()
            r_filter = rarity_var.get()

            for pid, p in POKEMON_DATA.items():
                if search and search not in p["name"].lower() and search not in str(pid): continue
                if t_filter != "All" and t_filter not in [p["t1"], p["t2"]]: continue
                if s_filter != "All" and s_filter != p.get("stage", "Unknown"): continue
                if r_filter != "All" and r_filter != p.get("rarity", "Standard"): continue
                
                t_str = p["t1"] + (f"/{p['t2']}" if p["t2"] else "")
                tree.insert("", "end", values=(pid, p["name"], t_str, p.get("stage", "Unknown"), p.get("rarity", "Standard")))

        search_var.trace_add("write", refresh)
        type_var.trace_add("write", refresh)
        stage_var.trace_add("write", refresh)
        rarity_var.trace_add("write", refresh)
        refresh()

        def on_select(*_):
            sel = tree.selection()
            if not sel: return
            vals = tree.item(sel[0], "values")
            win.destroy()
            callback(int(vals[0]))

        tree.bind("<Double-1>", on_select)
        ttk.Button(win, text="Select", command=on_select).pack(pady=5)

    # ── Bag tab ──────────────────────────────────────────────────────────────

    def _build_bag_tab(self):
        f = self.tab_bag
        f.columnconfigure(0, weight=1)
        f.rowconfigure(1, weight=1)

        hint = "Items are grouped by bag pocket. Use Change to swap an item, or i for source details."
        ttk.Label(f, text=hint, foreground="gray", padding=(4, 4)).grid(
            row=0, column=0, columnspan=2, sticky="w")

        canvas = tk.Canvas(f, highlightthickness=0)
        sb = ttk.Scrollbar(f, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.grid(row=1, column=0, sticky="nsew")
        sb.grid(row=1, column=1, sticky="ns")

        self.bag_inner = ttk.Frame(canvas)
        win = canvas.create_window((0, 0), window=self.bag_inner, anchor="nw")
        self.bag_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        self._make_scrollable(canvas)
        self.bag_canvas = canvas

    def _populate_bag(self):
        for w in self.bag_inner.winfo_children():
            w.destroy()
        self.bag_rows = []

        if not isinstance(self.bag, RubyObject):
            ttk.Label(self.bag_inner, text="No bag data found.").pack(); return

        pockets = self.bag.attributes.get("@pockets", [])
        pocket_list = pockets if isinstance(pockets, list) else list(pockets.values())

        grid_row = 0
        for pi, pocket in enumerate(pocket_list):
            pname = POCKET_NAMES[pi] if pi < len(POCKET_NAMES) else f"Pocket {pi}"
            if not isinstance(pocket, list) or not pocket:
                continue
            header = ttk.Frame(self.bag_inner, padding=(4, 8, 4, 2))
            header.grid(row=grid_row, column=0, columnspan=5, sticky="ew")
            ttk.Label(header, text=pname, font=("", 10, "bold")).pack(side="left")
            ttk.Label(header, text=f"{len(pocket)} item slots", foreground="gray").pack(side="left", padx=8)
            grid_row += 1

            for ei, entry in enumerate(pocket):
                if isinstance(entry, list) and len(entry) >= 2:
                    iid, qty = entry[0], entry[1]
                elif isinstance(entry, RubyObject):
                    iid = entry.attributes.get("@id", 0)
                    qty = entry.attributes.get("@quantity", 1)
                else:
                    continue

                internet_id = iid * 2 + 1
                id_var   = tk.StringVar(value=str(internet_id))
                qty_var  = tk.StringVar(value=str(qty))
                name_var = tk.StringVar(value=item_display_name(internet_id))

                icon_label = ttk.Label(self.bag_inner, width=3, anchor="center")
                icon_label.grid(row=grid_row, column=0, padx=(6, 1), pady=2)

                def _set_icon(label, item_id):
                    icon = self._load_item_icon(item_id, max_size=28)
                    label.configure(image=icon if icon else "", text="" if icon else "-")
                    label.image = icon

                _set_icon(icon_label, internet_id)

                # Keep row display in sync when Change updates the hidden ID.
                def _make_trace(iv, nv):
                    def _cb(*_):
                        try:
                            new_id = int(iv.get())
                            nv.set(item_display_name(new_id))
                            _set_icon(icon_label, new_id)
                        except ValueError:
                            pass
                    return _cb
                id_var.trace_add("write", _make_trace(id_var, name_var))

                info_btn = self._make_info_button(
                    self.bag_inner,
                    lambda iv=id_var: self._show_item_info(int(iv.get() or 0))
                )
                info_btn.grid(row=grid_row, column=1, padx=(0, 2), pady=1)

                ttk.Label(self.bag_inner, textvariable=name_var, width=30, anchor="w").grid(
                    row=grid_row, column=2, padx=(0, 4), pady=2, sticky="w")
                ttk.Entry(self.bag_inner, textvariable=qty_var, width=7).grid(
                    row=grid_row, column=3, padx=4, pady=2)
                ttk.Button(self.bag_inner, text="Change", width=7,
                           command=lambda iv=id_var, nv=name_var: self._open_item_picker(iv, nv)).grid(
                    row=grid_row, column=4, padx=4, pady=2)

                self.bag_rows.append((pi, ei, id_var, qty_var))
                grid_row += 1

        # Add-item section
        ttk.Separator(self.bag_inner, orient="horizontal").grid(
            row=grid_row, column=0, columnspan=5, sticky="ew", pady=4); grid_row += 1
        ttk.Label(self.bag_inner, text="Add item:", font=("", 9, "bold")).grid(
            row=grid_row, column=0, sticky="w", padx=4); grid_row += 1

        self._add_item_id = tk.StringVar()
        self._add_qty     = tk.StringVar(value="99")
        for col, lbl in enumerate(["Item", "Qty"]):
            ttk.Label(self.bag_inner, text=lbl, width=10).grid(row=grid_row, column=col, padx=4)
        grid_row += 1
        self._add_item_name = tk.StringVar(value="Choose an item...")
        ttk.Label(self.bag_inner, textvariable=self._add_item_name, width=34, anchor="w", relief="sunken").grid(
            row=grid_row, column=0, padx=4, pady=2, sticky="w")
        ttk.Entry(self.bag_inner, textvariable=self._add_qty, width=10).grid(row=grid_row, column=1, padx=4, pady=2)
        ttk.Button(self.bag_inner, text="Add", command=self._add_bag_item).grid(row=grid_row, column=2, padx=4)
        ttk.Button(self.bag_inner, text="Browse...",
                   command=lambda: self._open_item_picker(self._add_item_id, self._add_item_name)).grid(
            row=grid_row, column=3, padx=4)

    def _add_bag_item(self):
        try:
            internet_id = int(self._add_item_id.get())
            iid         = (internet_id - 1) // 2
            qty         = int(self._add_qty.get())
        except ValueError:
            messagebox.showerror("Input error", "Choose an item and enter an integer quantity."); return
        pockets = self.bag.attributes.get("@pockets", [])
        pocket_list = pockets if isinstance(pockets, list) else list(pockets.values())
        pi = pocket_for_item(internet_id)
        if pi >= len(pocket_list):
            pi = 1  # fallback to general items pocket
        if not isinstance(pocket_list[pi], list):
            pocket_list[pi] = []
        pocket_list[pi].append([iid, qty])
        self._populate_bag()
        self.bag_canvas.update_idletasks()
        self.bag_canvas.yview_moveto(1.0)
        name = item_display_name(internet_id)
        pocket_name = POCKET_NAMES[pi] if pi < len(POCKET_NAMES) else "bag"
        self.status.config(text=f"Added: {name} x{qty} to {pocket_name} - click Save to write.",
                           foreground="blue")

    def _open_item_picker(self, id_var: tk.StringVar, name_var):
        """Popup to pick an item by category + search. Updates id_var (and optionally name_var)."""
        dlg = tk.Toplevel(self)
        dlg.title("Pick Item")
        dlg.geometry("480x500")
        dlg.resizable(True, True)
        dlg.grab_set()

        # ── filter row ──
        top = ttk.Frame(dlg, padding=(8, 8, 8, 4))
        top.pack(fill="x")
        ttk.Label(top, text="Category:").pack(side="left")
        cat_var = tk.StringVar(value="All")
        cat_cb  = ttk.Combobox(top, textvariable=cat_var, values=ITEM_CAT_LIST, width=16, state="readonly")
        cat_cb.pack(side="left", padx=(4, 12))

        ttk.Label(top, text="Search:").pack(side="left")
        search_var = tk.StringVar()
        ttk.Entry(top, textvariable=search_var, width=18).pack(side="left", padx=4)

        # ── listbox ──
        lf = ttk.Frame(dlg, padding=(8, 0, 8, 4))
        lf.pack(fill="both", expand=True)
        lb  = tk.Listbox(lf, font=("Courier", 9), activestyle="dotbox", selectmode="single")
        vsb = ttk.Scrollbar(lf, orient="vertical",   command=lb.yview)
        hsb = ttk.Scrollbar(lf, orient="horizontal", command=lb.xview)
        lb.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        lb.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        lf.rowconfigure(0, weight=1)
        lf.columnconfigure(0, weight=1)

        filtered: list[tuple[int,str]] = []   # (internet_id, name)

        def refresh(*_):
            nonlocal filtered
            cat = cat_var.get()
            q   = search_var.get().strip().lower()
            if cat == "All":
                items = list(ITEM_NAMES.items())
            else:
                items = [(iid, n) for iid, n in ITEM_NAMES.items() if ITEM_CATS.get(iid) == cat]
            if q:
                items = [(iid, n) for iid, n in items if q in n.lower() or q in str(iid)]
            items.sort(key=lambda x: x[1].lower())
            filtered = items
            lb.delete(0, tk.END)
            for iid, n in items:
                lb.insert(tk.END, f"  {iid:5d}  {n}")

        cat_var.trace_add("write", refresh)
        search_var.trace_add("write", refresh)
        refresh()

        # Pre-select current item if possible
        try:
            cur = int(id_var.get())
            for idx, (iid, _) in enumerate(filtered):
                if iid == cur:
                    lb.selection_set(idx)
                    lb.see(idx)
                    break
        except (ValueError, TypeError):
            pass

        # Focus search box
        top.winfo_children()[-1].focus_set()

        def do_select(*_):
            sel = lb.curselection()
            if not sel:
                return
            iid, n = filtered[sel[0]]
            id_var.set(str(iid))
            if name_var is not None:
                name_var.set(n)
            dlg.destroy()

        lb.bind("<Double-Button-1>", do_select)
        lb.bind("<Return>",          do_select)

        # ── buttons ──
        bf = ttk.Frame(dlg, padding=(8, 0, 8, 8))
        bf.pack(fill="x")
        ttk.Button(bf, text="Select", width=10, command=do_select).pack(side="left", padx=4)
        ttk.Button(bf, text="Cancel", width=10, command=dlg.destroy).pack(side="left", padx=4)
        ttk.Label(bf, text=f"{len(ITEM_NAMES)} items loaded", foreground="gray").pack(side="right", padx=8)

    # ── PC Boxes tab ─────────────────────────────────────────────────────────

    def _build_boxes_tab(self):
        f = self.tab_boxes
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)
        self.boxes_nb = ttk.Notebook(f)
        self.boxes_nb.grid(row=0, column=0, sticky="nsew")

    def _populate_boxes(self):
        for tab in self.boxes_nb.tabs():
            self.boxes_nb.forget(tab)
        self.box_vars = []

        if not isinstance(self.storage, RubyObject): return
        boxes = self.storage.attributes.get("@boxes", [])
        if not isinstance(boxes, list): return

        for bi, box in enumerate(boxes):
            if not isinstance(box, RubyObject): continue
            pokemon_list = box.attributes.get("@pokemon", [])
            box_name = ds(box.attributes.get("@name", f"Box {bi+1}"))

            outer = ttk.Frame(self.boxes_nb, padding=4)
            outer.columnconfigure(0, weight=1)
            outer.rowconfigure(0, weight=1)
            self.boxes_nb.add(outer, text=f" {box_name[:10]} ")

            canvas = tk.Canvas(outer, highlightthickness=0)
            sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=sb.set)
            canvas.grid(row=0, column=0, sticky="nsew")
            sb.grid(row=0, column=1, sticky="ns")
            inner = ttk.Frame(canvas)
            win = canvas.create_window((0, 0), window=inner, anchor="nw")
            inner.bind("<Configure>", lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")))
            canvas.bind("<Configure>", lambda e, c=canvas, w=win: c.itemconfig(w, width=e.width))
            self._make_scrollable(canvas)

            slot_vars = []
            for si, pkmn in enumerate(pokemon_list):
                if not isinstance(pkmn, RubyObject):
                    ef = ttk.LabelFrame(inner, text=f"Slot {si}: Empty", padding=4)
                    ef.pack(fill="x", pady=2, padx=2)
                    ttk.Button(ef, text="+ Add Pokémon",
                               command=lambda b=bi, s=si, bx=box: self._add_to_box_slot(b, s, bx)
                               ).pack(padx=4, pady=2)
                    slot_vars.append(None)
                    continue

                a    = pkmn.attributes
                nick = ds(a.get("@name", b""))
                sp   = a.get("@species", "?")
                pid  = a.get("@personalID", 0) or 0

                label = f"Slot {si}: {nick or f'Species#{sp}'}  [#{sp}]"
                sf = ttk.LabelFrame(inner, text=label, padding=4)
                sf.pack(fill="x", pady=2, padx=2)

                sv = {}
                lp = ttk.Frame(sf); lp.pack(side="left", padx=4)
                rp = ttk.Frame(sf); rp.pack(side="left", padx=4)
                np = ttk.Frame(sf); np.pack(side="left", padx=4)
                ip = ttk.Frame(sf); ip.pack(side="left", padx=4)
                bp = ttk.Frame(sf); bp.pack(side="left", padx=4)

                for i, (key, lbl, val) in enumerate([
                    ("species_id","Species ID",str(sp)),("form","Form ID",str(a.get("@form",0))),("nickname","Nickname",nick),
                    ("hp","HP",str(a.get("@hp",0))),("totalhp","Max HP",str(a.get("@totalhp",0))),
                ]):
                    sv[key] = tk.StringVar(value=val)
                    ttk.Label(lp, text=lbl+":", width=12, anchor="e").grid(row=i, column=0, sticky="e", pady=1)
                    ttk.Entry(lp, textvariable=sv[key], width=8).grid(row=i, column=1, sticky="w", pady=1, padx=2)

                for i, (key, lbl, val) in enumerate([
                    ("item","Item ID",str(a.get("@item",0))),
                    ("happiness","Happiness",str(a.get("@happiness",0))),
                    ("status","Status",str(a.get("@status",0))),
                    ("exp","Exp",str(a.get("@exp",0))),
                ]):
                    sv[key] = tk.StringVar(value=val)
                    ttk.Label(rp, text=lbl+":", width=10, anchor="e").grid(row=i, column=0, sticky="e", pady=1)
                    ttk.Entry(rp, textvariable=sv[key], width=8).grid(row=i, column=1, sticky="w", pady=1, padx=2)

                sv["nature_idx"]   = tk.StringVar(value=NATURES[pid % 25])
                sv["shiny"]        = tk.BooleanVar(value=is_shiny(pid, self.trainer_id, self.secret_id))
                sv["ability_slot"] = tk.StringVar(value=str(pid & 1))

                ttk.Label(np, text="Nature:",  anchor="e", width=10).grid(row=0, column=0, sticky="e")
                ttk.Combobox(np, textvariable=sv["nature_idx"], values=NATURES, width=9, state="readonly").grid(row=0, column=1, padx=2)
                ttk.Label(np, text="Shiny:",   anchor="e", width=10).grid(row=1, column=0, sticky="e")
                ttk.Checkbutton(np, variable=sv["shiny"]).grid(row=1, column=1, sticky="w", padx=2)
                ttk.Label(np, text="Ability:", anchor="e", width=10).grid(row=2, column=0, sticky="e")
                ttk.Combobox(np, textvariable=sv["ability_slot"], values=["0","1"], width=4, state="readonly").grid(row=2, column=1, padx=2)

                iv = a.get("@iv", [])
                ttk.Label(ip, text="IVs:", font=("", 8, "bold")).grid(row=0, column=0, columnspan=6)
                for j, stat in enumerate(STATS):
                    sv["iv_"+stat.lower()] = tk.StringVar(
                        value=str(iv[j] if isinstance(iv, list) and j < len(iv) else 0))
                    ttk.Label(ip, text=stat, width=4).grid(row=1, column=j)
                    ttk.Entry(ip, textvariable=sv["iv_"+stat.lower()], width=3).grid(row=2, column=j)
                ev = a.get("@ev", [])
                ttk.Label(ip, text="EVs:", font=("", 8, "bold")).grid(row=3, column=0, columnspan=6, pady=(4, 0))
                for j, stat in enumerate(STATS):
                    sv["ev_"+stat.lower()] = tk.StringVar(
                        value=str(ev[j] if isinstance(ev, list) and j < len(ev) else 0))
                    ttk.Label(ip, text=stat, width=4).grid(row=4, column=j)
                    ttk.Entry(ip, textvariable=sv["ev_"+stat.lower()], width=3).grid(row=5, column=j)

                sv["_pkmn_obj"] = pkmn
                ttk.Button(bp, text="Max IVs", width=8, command=lambda vv=sv: self._max_ivs(vv)).pack(pady=2)
                ttk.Button(bp, text="Zero EVs", width=8, command=lambda vv=sv: self._zero_evs(vv)).pack(pady=2)
                ttk.Button(bp, text="Heal",    width=8, command=lambda vv=sv: self._heal_slot(vv)).pack(pady=2)
                ttk.Separator(bp, orient="horizontal").pack(fill="x", pady=4)
                ttk.Button(bp, text="Move",    width=8,
                           command=lambda b=bi, s=si, bx=box, pk=pkmn: self._move_box_pokemon(b, s, bx, pk)
                           ).pack(pady=2)
                ttk.Button(bp, text="Delete",  width=8,
                           command=lambda b=bi, s=si, bx=box: self._delete_box_pokemon(b, s, bx)
                           ).pack(pady=2)

                dp = self._make_pokemon_dex_panel(sf, sp if isinstance(sp, int) else 0, a.get("@form", 0), compact=True)
                dp.pack(side="left", padx=4, fill="y")

                # Moves panel
                mp = ttk.LabelFrame(sf, text="Moves", padding=4)
                mp.pack(side="left", padx=4, fill="y")
                box_moves = a.get("@moves", [])
                for i in range(4):
                    sv[f"move{i}"]       = tk.StringVar(value="0")
                    sv[f"move{i}_name"]  = tk.StringVar(value="—")
                    sv[f"movepp{i}"]     = tk.StringVar(value="0")
                    sv[f"move{i}_maxpp"] = tk.StringVar(value="/0")
                    if (isinstance(box_moves, list) and i < len(box_moves)
                            and isinstance(box_moves[i], RubyObject)):
                        mid = box_moves[i].attributes.get("@id", 0)
                        pp  = box_moves[i].attributes.get("@pp", 0)
                        bm  = MOVE_DATA.get(mid, {})
                        sv[f"move{i}"].set(str(mid))
                        sv[f"move{i}_name"].set(bm.get("name", "—") if mid else "—")
                        sv[f"movepp{i}"].set(str(pp))
                        sv[f"move{i}_maxpp"].set(f"/{bm.get('pp', 0)}" if mid else "/0")
                    rf2 = ttk.Frame(mp)
                    rf2.pack(fill="x", pady=1)
                    ttk.Label(rf2, text=f"{i+1}:", width=2).pack(side="left")
                    ttk.Label(rf2, textvariable=sv[f"move{i}_name"], width=14,
                              relief="sunken", anchor="w").pack(side="left", padx=2)
                    ttk.Button(rf2, text="Change", width=7,
                               command=lambda vv=sv, ii=i: self._change_move(vv, ii)
                               ).pack(side="left", padx=2)
                    ttk.Label(rf2, text="PP:", width=3).pack(side="left")
                    ttk.Entry(rf2, textvariable=sv[f"movepp{i}"], width=4).pack(side="left")
                    ttk.Label(rf2, textvariable=sv[f"move{i}_maxpp"], width=4,
                              anchor="w").pack(side="left")

                slot_vars.append((si, sv))

            self.box_vars.append((bi, box, slot_vars))

    # ── pokemon picker / add ─────────────────────────────────────────────────

    def _open_pokemon_picker(self, callback):
        """Popup to browse and pick a species. Calls callback(species_id) on confirm."""
        dlg = tk.Toplevel(self)
        dlg.title("Pick Pokémon")
        dlg.geometry("620x520")
        dlg.resizable(True, True)
        dlg.grab_set()

        # ── filter row ──
        top = ttk.Frame(dlg, padding=(8, 8, 8, 4))
        top.pack(fill="x")

        ttk.Label(top, text="Name:").pack(side="left")
        search_var = tk.StringVar()
        search_entry = ttk.Entry(top, textvariable=search_var, width=14)
        search_entry.pack(side="left", padx=(4, 12))

        ttk.Label(top, text="Type:").pack(side="left")
        type_var = tk.StringVar(value="All")
        ttk.Combobox(top, textvariable=type_var,
                     values=["All"] + POKEMON_TYPES, width=10, state="readonly").pack(side="left", padx=(4, 8))

        ttk.Label(top, text="Stage:").pack(side="left")
        stage_var = tk.StringVar(value="All")
        ttk.Combobox(top, textvariable=stage_var,
                     values=PKMN_STAGE_LIST, width=6, state="readonly").pack(side="left", padx=(4, 8))

        ttk.Label(top, text="Rarity:").pack(side="left")
        rarity_var = tk.StringVar(value="All")
        ttk.Combobox(top, textvariable=rarity_var,
                     values=PKMN_RARITY_LIST, width=10, state="readonly").pack(side="left", padx=4)

        # ── listbox ──
        lf = ttk.Frame(dlg, padding=(8, 0, 8, 4))
        lf.pack(fill="both", expand=True)
        lb  = tk.Listbox(lf, font=("Courier", 9), activestyle="dotbox", selectmode="single")
        vsb = ttk.Scrollbar(lf, orient="vertical",   command=lb.yview)
        hsb = ttk.Scrollbar(lf, orient="horizontal", command=lb.xview)
        lb.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        lb.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        lf.rowconfigure(0, weight=1)
        lf.columnconfigure(0, weight=1)

        filtered: list[tuple[int, str]] = []

        def refresh(*_):
            nonlocal filtered
            q      = search_var.get().strip().lower()
            typ    = type_var.get()
            stage  = stage_var.get()
            rarity = rarity_var.get()

            if PKMN_DATA:
                items = list(PKMN_DATA.items())
                if typ != "All":
                    items = [(sid, d) for sid, d in items
                             if d["type1"] == typ or d["type2"] == typ]
                if stage != "All":
                    items = [(sid, d) for sid, d in items if d["stage"] == stage]
                if rarity != "All":
                    items = [(sid, d) for sid, d in items if d["rarity"] == rarity]
                if q:
                    items = [(sid, d) for sid, d in items
                             if q in d["name"].lower() or q in str(sid)]
                items.sort(key=lambda x: x[0])
                filtered = [(sid, d["name"]) for sid, d in items]
                lb.delete(0, tk.END)
                for sid, _ in filtered:
                    d = PKMN_DATA[sid]
                    t2   = f"/{d['type2']}" if d["type2"] else ""
                    line = f"  #{sid:4d}  {d['name']:<14}  {d['type1'] + t2:<18}  Stage {d['stage']:<5}  {d['rarity']}"
                    lb.insert(tk.END, line)
            else:
                filtered = []
                lb.delete(0, tk.END)
                lb.insert(tk.END, "  (pokemon_data.txt not found)")
                lb.insert(tk.END, "  Run generate_pokemon_data.py first,")
                lb.insert(tk.END, "  or enter a species ID below.")

        search_var.trace_add("write", refresh)
        type_var.trace_add("write",   refresh)
        stage_var.trace_add("write",  refresh)
        rarity_var.trace_add("write", refresh)
        refresh()
        search_entry.focus_set()

        # ── manual ID fallback + buttons ──
        bf = ttk.Frame(dlg, padding=(8, 0, 8, 8))
        bf.pack(fill="x")

        manual_var = tk.StringVar()
        ttk.Label(bf, text="Species ID:").pack(side="left")
        ttk.Entry(bf, textvariable=manual_var, width=7).pack(side="left", padx=(4, 8))

        def do_select(*_):
            # Prefer listbox selection; fall back to manual ID field
            sel = lb.curselection()
            if sel and filtered:
                sid, _ = filtered[sel[0]]
            else:
                try:
                    sid = int(manual_var.get())
                except ValueError:
                    messagebox.showerror("Input error", "Select a Pokémon or enter a species ID.", parent=dlg)
                    return
            callback(sid)
            dlg.destroy()

        lb.bind("<Double-Button-1>", do_select)
        lb.bind("<Return>",          do_select)

        ttk.Button(bf, text="Select", width=9, command=do_select).pack(side="left", padx=4)
        ttk.Button(bf, text="Cancel", width=9, command=dlg.destroy).pack(side="left", padx=4)
        count = len(PKMN_DATA)
        ttk.Label(bf, text=f"{count} species loaded" if count else "No data file",
                  foreground="gray").pack(side="right", padx=8)

    def _find_template_pokemon(self):
        """Return any existing RubyObject Pokémon to use as a deep-copy template.
        Prefer a box Pokémon over a party Pokémon — box Pokémon lack party-specific
        attributes (e.g. @hypermode) that would be unexpected on a stored Pokémon."""
        if self.storage:
            for box in self.storage.attributes.get("@boxes", []):
                if isinstance(box, RubyObject):
                    for p in box.attributes.get("@pokemon", []):
                        if isinstance(p, RubyObject): return p
        if self.trainer:
            for p in self.trainer.attributes.get("@party", []):
                if isinstance(p, RubyObject): return p
        return None

    def _create_pokemon_obj(self, species_id: int, level: int = None, moves: list = None, evs: list = None) -> RubyObject:
        d      = PKMN_DATA.get(species_id, {})
        stage  = d.get("stage",  "1")
        rarity = d.get("rarity", "Common")
        if level is None:
            level = _default_level(stage, rarity)

        hp_b  = d.get("hp",  0)
        atk_b = d.get("atk", 0)
        def_b = d.get("def", 0)
        spa_b = d.get("spa", 0)
        spd_b = d.get("spd", 0)
        spe_b = d.get("spe", 0)

        iv_hp  = min(31, hp_b  // 4)
        iv_atk = min(31, atk_b // 4)
        iv_def = min(31, def_b // 4)
        iv_spa = min(31, spa_b // 4)
        iv_spd = min(31, spd_b // 4)
        iv_spe = min(31, spe_b // 4)
        ev_hp, ev_atk, ev_def, ev_spa, ev_spd, ev_spe = _sanitize_evs(evs or [0, 0, 0, 0, 0, 0])

        total_hp = (2 * hp_b + iv_hp + ev_hp // 4)  * level // 100 + level + 10
        def calc(b, iv, ev): return (2 * b + iv + ev // 4) * level // 100 + 5

        name_str = d.get("name", f"#{species_id}")
        growth   = d.get("growth", "medium-fast")
        exp      = _exp_for_level(growth, level)
        pid      = find_pid(NATURES.index("Hardy"), False, self.trainer_id, self.secret_id)

        ot_name     = b""
        combined_id = 0
        if self.trainer:
            ot_name     = self.trainer.attributes.get("@name", b"") or b""
            combined_id = self.trainer_id | (self.secret_id << 16)

        # Deep-copy a real Pokémon from the save as a structural template.
        # This guarantees every Insurgence-specific attribute is present with the
        # correct Ruby class names on sub-objects (moves, etc.).
        template = self._find_template_pokemon()
        if template:
            pkmn = copy.deepcopy(template)
            # Zero out all move slots so the new Pokémon starts with no moves
            for mv in pkmn.attributes.get("@moves", []):
                if isinstance(mv, RubyObject):
                    mv.attributes["@id"]    = 0
                    mv.attributes["@pp"]    = 0
                    mv.attributes["@ppup"]  = 0
                    mv.attributes.pop("@totalpp", None)
        else:
            # Fallback: no existing Pokémon in save — build from scratch
            pkmn = RubyObject("PokeBattle_Pokemon", {
                "@moves": [RubyObject("PBMove", {"@id": 0, "@pp": 0, "@ppup": 0})
                           for _ in range(4)],
                "@iv": [0]*6, "@ev": [0]*6, "@ribbons": [],
            })

        a = pkmn.attributes
        a["@species"]      = species_id
        a["@name"]         = name_str.encode("utf-8")
        a["@personalID"]   = pid
        a["@hp"]           = total_hp
        a["@totalhp"]      = total_hp
        a["@attack"]       = calc(atk_b, iv_atk, ev_atk)
        a["@defense"]      = calc(def_b, iv_def, ev_def)
        a["@spatk"]        = calc(spa_b, iv_spa, ev_spa)
        a["@spdef"]        = calc(spd_b, iv_spd, ev_spd)
        a["@speed"]        = calc(spe_b, iv_spe, ev_spe)
        a["@exp"]          = exp
        a["@item"]         = 0
        a["@happiness"]    = 70
        a["@status"]       = 0
        a["@statusCount"]  = 0
        a["@ballused"]     = 4
        a["@obtainLevel"]  = level
        a["@obtainMode"]   = 0
        a["@obtainMap"]    = 0
        a["@obtainText"]   = None
        a["@timeReceived"] = int(time.time())
        a["@iv"]           = [iv_hp, iv_atk, iv_def, iv_spa, iv_spd, iv_spe]
        a["@ev"]           = [ev_hp, ev_atk, ev_def, ev_spa, ev_spd, ev_spe]
        a["@form"]         = 0
        a["@abilityflag"]  = 0
        a["@trainerID"]    = combined_id
        a["@ot"]           = ot_name
        a["@otgender"]     = 0
        a["@eggsteps"]     = 0
        a["@markings"]     = 0
        a["@fused"]        = None
        a["@mail"]         = None
        a["@hatchedMap"]   = 0
        a["@language"]     = 3

        if moves:
            move_objs = a.get("@moves", [])
            while len(move_objs) < 4:
                move_objs.append(RubyObject("PBMove", {"@id": 0, "@pp": 0, "@ppup": 0}))
            for i in range(4):
                if not isinstance(move_objs[i], RubyObject):
                    continue
                move_objs[i].attributes.pop("@totalpp", None)
                if i < len(moves):
                    mid, pp = moves[i]
                    move_objs[i].attributes["@id"]   = mid
                    move_objs[i].attributes["@pp"]   = pp
                    move_objs[i].attributes["@ppup"] = 0
                else:
                    move_objs[i].attributes["@id"]   = 0
                    move_objs[i].attributes["@pp"]   = 0
                    move_objs[i].attributes["@ppup"] = 0
            a["@moves"] = move_objs

        return pkmn

    def _open_move_picker(self, species_id: int, callback):
        """Move selection popup. callback(level, [(move_id, pp), ...])"""
        d       = PKMN_DATA.get(species_id, {})
        name    = d.get("name", f"#{species_id}")
        growth  = d.get("growth", "medium-fast")
        def_lv  = _default_level(d.get("stage", "1"), d.get("rarity", "Common"))
        learnset = LEARNSET_DATA.get(species_id, [])

        win = tk.Toplevel(self)
        win.title(f"Choose Moves — {name}")
        win.geometry("800x540")
        win.resizable(False, False)
        win.grab_set()

        # ── Level row ────────────────────────────────────────────────────────
        top = ttk.Frame(win, padding=(10, 8, 10, 4))
        top.pack(fill="x")
        ttk.Label(top, text=f"Moves for {name}   —   Level:").pack(side="left")
        level_var = tk.IntVar(value=def_lv)
        ttk.Spinbox(top, from_=1, to=100, textvariable=level_var, width=5).pack(side="left", padx=6)
        ttk.Label(top, text="(double-click a move to add it)", foreground="gray").pack(side="left", padx=10)

        # ── Main split ───────────────────────────────────────────────────────
        mid_frame = ttk.Frame(win, padding=(10, 0, 10, 4))
        mid_frame.pack(fill="both", expand=True)

        # Left: available moves treeview
        left = ttk.LabelFrame(mid_frame, text="Available Moves", padding=4)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        cols = ("lv", "name", "type", "cat", "pwr", "acc", "pp")
        tree = ttk.Treeview(left, columns=cols, show="headings", height=13, selectmode="browse")
        for col, w, anchor, text in [
            ("lv",    36, "center", "Lv"),
            ("name", 130, "w",      "Name"),
            ("type",  68, "center", "Type"),
            ("cat",   65, "center", "Cat"),
            ("pwr",   40, "center", "Pwr"),
            ("acc",   40, "center", "Acc"),
            ("pp",    34, "center", "PP"),
        ]:
            tree.heading(col, text=text)
            tree.column(col, width=w, anchor=anchor, stretch=False)
        vsb = ttk.Scrollbar(left, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        # Right: selected slots + You Decide
        right = ttk.LabelFrame(mid_frame, text="Selected  (click to remove)", padding=6)
        right.pack(side="left", fill="y")

        selected: list[tuple[int, int]] = []  # (move_id, pp)
        slot_vars = [tk.StringVar(value=f"  {i+1}.  —") for i in range(4)]
        slot_btns = []
        for i in range(4):
            b = ttk.Button(right, textvariable=slot_vars[i], width=21,
                           command=lambda idx=i: _remove(idx))
            b.pack(pady=3, padx=2, fill="x")
            slot_btns.append(b)

        ttk.Separator(right, orient="horizontal").pack(fill="x", pady=8)
        ttk.Button(right, text="You Decide", command=lambda: _auto()).pack(fill="x", padx=2)

        # ── Description ──────────────────────────────────────────────────────
        desc_frame = ttk.LabelFrame(win, text="Description", padding=(6, 2))
        desc_frame.pack(fill="x", padx=10, pady=(0, 4))
        desc_lbl = ttk.Label(desc_frame, text="", wraplength=760, justify="left")
        desc_lbl.pack(fill="x")

        # ── Confirm / Cancel ─────────────────────────────────────────────────
        btn_row = ttk.Frame(win, padding=(10, 0, 10, 8))
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Confirm", command=lambda: _confirm()).pack(side="right", padx=4)
        ttk.Button(btn_row, text="Cancel",  command=win.destroy).pack(side="right")

        # ── Logic helpers ─────────────────────────────────────────────────────
        def _refresh_slots():
            for i in range(4):
                if i < len(selected):
                    mid, _ = selected[i]
                    mname = MOVE_DATA.get(mid, {}).get("name", f"#{mid}")
                    slot_vars[i].set(f"  {i+1}.  {mname}")
                else:
                    slot_vars[i].set(f"  {i+1}.  —")

        def _refresh_tree(*_):
            try:
                lvl = max(1, min(100, int(level_var.get())))
            except (ValueError, tk.TclError):
                return
            tree.delete(*tree.get_children())
            seen = set()
            for learn_lv, mid in learnset:
                if learn_lv > lvl or mid in seen:
                    continue
                seen.add(mid)
                m = MOVE_DATA.get(mid, {})
                pwr = m.get("power", 0)
                acc = m.get("accuracy", 0)
                tree.insert("", "end", iid=str(mid), values=(
                    learn_lv,
                    m.get("name", f"#{mid}"),
                    m.get("type", ""),
                    m.get("category", ""),
                    pwr if pwr > 0 else "—",
                    acc if acc > 0 else "—",
                    m.get("pp", 0),
                ))

        def _add(move_id: int):
            if len(selected) >= 4:
                return
            if any(m[0] == move_id for m in selected):
                return
            pp = MOVE_DATA.get(move_id, {}).get("pp", 0)
            selected.append((move_id, pp))
            _refresh_slots()

        def _remove(idx: int):
            if idx < len(selected):
                selected.pop(idx)
                _refresh_slots()

        def _auto():
            try:
                lvl = max(1, min(100, int(level_var.get())))
            except (ValueError, tk.TclError):
                lvl = def_lv
            available = [(lv, mid) for lv, mid in learnset if lv <= lvl]
            damaging = sorted(
                [(MOVE_DATA.get(m, {}).get("power", 0) * (MOVE_DATA.get(m, {}).get("accuracy", 0) or 100) / 100, lv, m)
                 for lv, m in available if MOVE_DATA.get(m, {}).get("power", 0) > 0],
                reverse=True,
            )
            status = sorted(
                [(lv, m) for lv, m in available if MOVE_DATA.get(m, {}).get("power", 0) == 0],
                reverse=True,
            )
            result = [m for _, _lv, m in damaging[:3]]
            if status:
                result.append(status[0][1])
            # Fill remaining slots if we got fewer than 4
            for _, _lv, m in damaging[3:]:
                if len(result) >= 4: break
                if m not in result: result.append(m)
            for _lv, m in status[1:]:
                if len(result) >= 4: break
                if m not in result: result.append(m)
            selected.clear()
            for mid in result[:4]:
                pp = MOVE_DATA.get(mid, {}).get("pp", 0)
                selected.append((mid, pp))
            _refresh_slots()

        def _on_select(event):
            sel = tree.selection()
            if not sel: return
            try:
                m = MOVE_DATA.get(int(sel[0]), {})
                desc_lbl.config(text=m.get("description", ""))
            except ValueError:
                pass

        def _on_double(event):
            sel = tree.selection()
            if not sel: return
            try:
                _add(int(sel[0]))
            except ValueError:
                pass

        def _confirm():
            try:
                lvl = max(1, min(100, int(level_var.get())))
            except (ValueError, tk.TclError):
                lvl = def_lv
            win.destroy()
            callback(lvl, list(selected))

        level_var.trace_add("write", _refresh_tree)
        tree.bind("<<TreeviewSelect>>", _on_select)
        tree.bind("<Double-1>", _on_double)

        _refresh_tree()
        _auto()

    # ── move browser (change existing move) ──────────────────────────────────

    def _open_ev_picker(self, species_id: int, callback):
        """EV selection popup. callback([hp, atk, def, spa, spd, spe]) on confirm."""
        d = PKMN_DATA.get(species_id, {})
        name = d.get("name", f"#{species_id}")

        win = tk.Toplevel(self)
        win.title(f"Choose EVs - {name}")
        win.geometry("520x320")
        win.resizable(False, False)
        win.grab_set()

        ttk.Label(win, text=f"EV spread for {name}", font=("", 10, "bold"),
                  padding=(10, 10, 10, 4)).pack(anchor="w")

        body = ttk.Frame(win, padding=(10, 0, 10, 8))
        body.pack(fill="both", expand=True)

        left = ttk.LabelFrame(body, text="Preset", padding=6)
        left.pack(side="left", fill="y", padx=(0, 8))

        preset_var = tk.StringVar(value="Fresh / zero EVs")
        for preset in EV_PRESETS:
            ttk.Radiobutton(left, text=preset, value=preset, variable=preset_var).pack(anchor="w", pady=2)

        right = ttk.LabelFrame(body, text="Values", padding=8)
        right.pack(side="left", fill="both", expand=True)

        ev_vars = []
        for i, stat in enumerate(STATS):
            ttk.Label(right, text=stat, width=5).grid(row=0, column=i, padx=2)
            var = tk.StringVar(value="0")
            ttk.Entry(right, textvariable=var, width=5).grid(row=1, column=i, padx=2, pady=2)
            ev_vars.append(var)

        total_var = tk.StringVar(value="Total: 0 / 510")
        total_lbl = ttk.Label(right, textvariable=total_var)
        total_lbl.grid(row=2, column=0, columnspan=6, sticky="w", pady=(8, 0))
        syncing_preset = {"active": False}

        ttk.Label(right, text="Each stat is clamped to 0-252. Total must be 510 or less.",
                  foreground="gray", wraplength=290).grid(row=3, column=0, columnspan=6, sticky="w", pady=(8, 0))

        btn_row = ttk.Frame(win, padding=(10, 0, 10, 10))
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Confirm", command=lambda: _confirm()).pack(side="right", padx=4)
        ttk.Button(btn_row, text="Cancel", command=win.destroy).pack(side="right")

        def _raw_values():
            values = []
            for var in ev_vars:
                try:
                    values.append(int(var.get() or 0))
                except ValueError:
                    values.append(0)
            return values

        def _refresh_total(*_):
            values = _raw_values()
            total = sum(values)
            ok = total <= 510 and all(0 <= v <= 252 for v in values)
            total_var.set(f"Total: {total} / 510")
            total_lbl.configure(foreground=("black" if ok else "red"))

        def _apply_preset(*_):
            preset = preset_var.get()
            if preset == "Custom":
                return
            syncing_preset["active"] = True
            for var, val in zip(ev_vars, EV_PRESETS[preset]):
                var.set(str(val))
            syncing_preset["active"] = False
            _refresh_total()

        def _mark_custom(*_):
            if syncing_preset["active"]:
                _refresh_total()
                return
            preset = preset_var.get()
            if preset != "Custom" and _raw_values() != EV_PRESETS.get(preset, []):
                preset_var.set("Custom")
            _refresh_total()

        def _confirm():
            values = _raw_values()
            if any(v < 0 or v > 252 for v in values) or sum(values) > 510:
                messagebox.showerror(
                    "Invalid EV spread",
                    "EVs must be 0-252 per stat and 510 total or less.",
                    parent=win)
                return
            win.destroy()
            callback(_sanitize_evs(values))

        preset_var.trace_add("write", _apply_preset)
        for var in ev_vars:
            var.trace_add("write", _mark_custom)
        _apply_preset()

    def _update_move_vars(self, v: dict, move_idx: int, move_id: int):
        m = MOVE_DATA.get(move_id, {})
        v[f"move{move_idx}"].set(str(move_id))
        v[f"move{move_idx}_name"].set(m.get("name", "—") if move_id else "—")
        v[f"move{move_idx}_maxpp"].set(f"/{m.get('pp', 0)}" if move_id else "/0")
        if move_id:
            v[f"movepp{move_idx}"].set(str(m.get("pp", 0)))

    def _change_move(self, v: dict, move_idx: int):
        try:
            sid = int(v["species_id"].get() or 0)
        except (ValueError, KeyError):
            sid = 0
        self._open_move_browser(sid, lambda mid: self._update_move_vars(v, move_idx, mid))

    def _open_move_browser(self, species_id: int, callback):
        """Browse all moves with filters/sort. callback(move_id) on select."""
        learnset_ids = {mid for _, mid in LEARNSET_DATA.get(species_id, [])}
        all_types = ["All"] + sorted({m["type"] for m in MOVE_DATA.values() if m.get("type")})

        win = tk.Toplevel(self)
        win.title("Move Browser")
        win.geometry("760x520")
        win.resizable(True, True)
        win.grab_set()

        # ── Filter row ───────────────────────────────────────────────────────
        frow = ttk.Frame(win, padding=(10, 8, 10, 4))
        frow.pack(fill="x")
        cat_var  = tk.StringVar(value="All")
        type_var = tk.StringVar(value="All")
        sort_var = tk.StringVar(value="Name")
        ttk.Label(frow, text="Category:").pack(side="left")
        ttk.Combobox(frow, textvariable=cat_var,
                     values=["All", "Physical", "Special", "Status"],
                     width=10, state="readonly").pack(side="left", padx=(2, 14))
        ttk.Label(frow, text="Type:").pack(side="left")
        ttk.Combobox(frow, textvariable=type_var, values=all_types,
                     width=12, state="readonly").pack(side="left", padx=(2, 14))
        ttk.Label(frow, text="Sort by:").pack(side="left")
        ttk.Combobox(frow, textvariable=sort_var,
                     values=["Name", "Power", "Accuracy", "PP"],
                     width=10, state="readonly").pack(side="left", padx=2)

        # ── Treeview ─────────────────────────────────────────────────────────
        tv_frame = ttk.Frame(win, padding=(10, 0, 10, 4))
        tv_frame.pack(fill="both", expand=True)
        cols = ("name", "type", "cat", "pwr", "acc", "pp", "compat")
        tree = ttk.Treeview(tv_frame, columns=cols, show="headings", height=16, selectmode="browse")
        for col, w, anch, text in [
            ("name",   145, "w",      "Name"),
            ("type",    78, "center", "Type"),
            ("cat",     72, "center", "Category"),
            ("pwr",     48, "center", "Power"),
            ("acc",     52, "center", "Accuracy"),
            ("pp",      36, "center", "PP"),
            ("compat",  92, "center", ""),
        ]:
            tree.heading(col, text=text)
            tree.column(col, width=w, anchor=anch, stretch=False)
        vsb = ttk.Scrollbar(tv_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")
        tree.tag_configure("incompatible", foreground="#cc0000")

        # ── Description ──────────────────────────────────────────────────────
        desc_frame = ttk.LabelFrame(win, text="Description", padding=(6, 2))
        desc_frame.pack(fill="x", padx=10, pady=(0, 4))
        desc_lbl = ttk.Label(desc_frame, text="", wraplength=740, justify="left")
        desc_lbl.pack(fill="x")

        # ── Buttons ──────────────────────────────────────────────────────────
        btn_row = ttk.Frame(win, padding=(10, 0, 10, 8))
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Select",  command=lambda: _confirm()).pack(side="right", padx=4)
        ttk.Button(btn_row, text="Cancel",  command=win.destroy).pack(side="right")

        # ── Helpers ──────────────────────────────────────────────────────────
        def _refresh(*_):
            cat  = cat_var.get()
            typ  = type_var.get()
            sort = sort_var.get()
            entries = [
                (mid, m) for mid, m in MOVE_DATA.items()
                if (cat == "All" or m.get("category") == cat)
                and (typ == "All" or m.get("type") == typ)
            ]
            key_fns = {
                "Name":     lambda x: x[1].get("name", "").lower(),
                "Power":    lambda x: -x[1].get("power", 0),
                "Accuracy": lambda x: -x[1].get("accuracy", 0),
                "PP":       lambda x: -x[1].get("pp", 0),
            }
            entries.sort(key=key_fns.get(sort, key_fns["Name"]))
            tree.delete(*tree.get_children())
            for mid, m in entries:
                pwr = m.get("power", 0)
                acc = m.get("accuracy", 0)
                compat = mid in learnset_ids
                tree.insert("", "end", iid=str(mid), values=(
                    m.get("name", f"#{mid}"),
                    m.get("type", ""),
                    m.get("category", ""),
                    pwr if pwr > 0 else "—",
                    acc if acc > 0 else "—",
                    m.get("pp", 0),
                    "" if compat else "incompatible",
                ), tags=(() if compat else ("incompatible",)))

        def _on_select(event):
            sel = tree.selection()
            if not sel: return
            try:
                m = MOVE_DATA.get(int(sel[0]), {})
                desc_lbl.config(text=m.get("description", ""))
            except ValueError:
                pass

        def _confirm():
            sel = tree.selection()
            if not sel: return
            try:
                mid = int(sel[0])
            except ValueError:
                return
            win.destroy()
            callback(mid)

        cat_var.trace_add("write", _refresh)
        type_var.trace_add("write", _refresh)
        sort_var.trace_add("write", _refresh)
        tree.bind("<<TreeviewSelect>>", _on_select)
        tree.bind("<Double-1>", lambda e: _confirm())
        _refresh()

    def _add_to_party_slot(self, slot: int):
        if not self.trainer:
            messagebox.showerror("No save loaded", "Load a save file first."); return
        def on_pick(sid):
            def on_moves(level, moves):
                def on_evs(evs):
                    party = self.trainer.attributes.setdefault("@party", [])
                    while len(party) <= slot:
                        party.append(None)
                    party[slot] = self._create_pokemon_obj(sid, level=level, moves=moves, evs=evs)
                    self._fill_party()
                    name = PKMN_DATA.get(sid, {}).get("name", f"#{sid}")
                    self.status.config(
                        text=f"Added {name} to party slot {slot+1}. Click Save to write.",
                        foreground="blue")
                self._open_ev_picker(sid, on_evs)
            self._open_move_picker(sid, on_moves)
        self._open_pokemon_picker(on_pick)

    def _delete_box_pokemon(self, bi: int, si: int, box: RubyObject):
        pokemon_list = box.attributes.get("@pokemon", [])
        if not (si < len(pokemon_list) and isinstance(pokemon_list[si], RubyObject)):
            return
        a    = pokemon_list[si].attributes
        nick = ds(a.get("@name", b"")) or f"Species#{a.get('@species', '?')}"
        if not messagebox.askyesno("Delete Pokémon",
                f"Permanently delete {nick}?\nThis cannot be undone.", icon="warning"):
            return
        pokemon_list[si] = None
        self._populate_boxes()
        self.boxes_nb.select(bi)
        self.status.config(
            text=f"Deleted {nick} from Box {bi+1} Slot {si}. Click Save to write.",
            foreground="blue")

    def _move_box_pokemon(self, bi: int, si: int, box: RubyObject, pkmn: RubyObject):
        a    = pkmn.attributes
        nick = ds(a.get("@name", b"")) or f"Species#{a.get('@species', '?')}"

        if not isinstance(self.storage, RubyObject): return
        boxes  = self.storage.attributes.get("@boxes", [])
        party  = self.trainer.attributes.get("@party", [])

        dlg = tk.Toplevel(self)
        dlg.title(f"Move {nick}")
        dlg.geometry("420x300")
        dlg.resizable(False, False)
        dlg.grab_set()

        ttk.Label(dlg, text=f"Move  {nick}", font=("", 10, "bold"),
                  padding=(0, 6, 0, 4)).pack()

        # ── Send to Party ────────────────────────────────────────────────────
        pf = ttk.LabelFrame(dlg, text="Send to Party Slot", padding=8)
        pf.pack(fill="x", padx=10, pady=(4, 6))

        def _party_label(ps):
            if ps < len(party) and isinstance(party[ps], RubyObject):
                pa  = party[ps].attributes
                pnm = ds(pa.get("@name", b"")) or f"Species#{pa.get('@species','?')}"
                return f"Slot {ps+1}: {pnm}"
            return f"Slot {ps+1}: (empty)"

        party_labels = [_party_label(ps) for ps in range(6)]
        party_var = tk.StringVar(value=party_labels[0])
        ttk.Combobox(pf, textvariable=party_var, values=party_labels,
                     width=26, state="readonly").pack(side="left", padx=(0, 8))
        ttk.Button(pf, text="Send", command=lambda: _to_party()).pack(side="left")

        # ── Send to Box ──────────────────────────────────────────────────────
        bf2 = ttk.LabelFrame(dlg, text="Send to Box", padding=8)
        bf2.pack(fill="x", padx=10, pady=(0, 6))

        box_labels = []
        for b2i, b2 in enumerate(boxes):
            bname = ds(b2.attributes.get("@name", f"Box {b2i+1}")) if isinstance(b2, RubyObject) else f"Box {b2i+1}"
            box_labels.append(bname)

        dest_box_var  = tk.StringVar(value=box_labels[bi] if box_labels else "")
        dest_slot_var = tk.StringVar()

        ttk.Label(bf2, text="Box:").pack(side="left")
        ttk.Combobox(bf2, textvariable=dest_box_var, values=box_labels,
                     width=12, state="readonly").pack(side="left", padx=(2, 10))
        ttk.Label(bf2, text="Slot:").pack(side="left")
        slot_cb = ttk.Combobox(bf2, textvariable=dest_slot_var, width=22, state="readonly")
        slot_cb.pack(side="left", padx=(2, 8))
        ttk.Button(bf2, text="Send", command=lambda: _to_box()).pack(side="left")

        def _refresh_slots(*_):
            dest_bi = box_labels.index(dest_box_var.get()) if dest_box_var.get() in box_labels else 0
            b2      = boxes[dest_bi] if dest_bi < len(boxes) else None
            blist   = b2.attributes.get("@pokemon", []) if isinstance(b2, RubyObject) else []
            n_slots = max(len(blist), 30)
            names   = []
            for s2i in range(n_slots):
                if s2i < len(blist) and isinstance(blist[s2i], RubyObject):
                    pa2  = blist[s2i].attributes
                    snm  = ds(pa2.get("@name", b"")) or f"Species#{pa2.get('@species','?')}"
                    names.append(f"Slot {s2i}: {snm}")
                else:
                    names.append(f"Slot {s2i}: (empty)")
            slot_cb["values"] = names
            dest_slot_var.set(names[0] if names else "")

        dest_box_var.trace_add("write", _refresh_slots)
        _refresh_slots()

        ttk.Button(dlg, text="Cancel", command=dlg.destroy).pack(pady=(2, 8))

        # ── Actions ──────────────────────────────────────────────────────────
        def _to_party():
            ps       = party_labels.index(party_var.get())
            src_list = box.attributes.get("@pokemon", [])
            occupied = ps < len(party) and isinstance(party[ps], RubyObject)
            if occupied:
                pa   = party[ps].attributes
                pnm  = ds(pa.get("@name", b"")) or f"Species#{pa.get('@species','?')}"
                if not messagebox.askyesno("Swap Pokémon",
                        f"Party Slot {ps+1} has {pnm}.\n"
                        f"Send {pnm} to Box {bi+1} Slot {si} and move {nick} to party?",
                        parent=dlg):
                    return
                src_list[si] = party[ps]
            else:
                while len(party) <= ps: party.append(None)
                src_list[si] = None
            party[ps] = pkmn
            dlg.destroy()
            self._fill_party()
            self._populate_boxes()
            self.boxes_nb.select(bi)
            self.status.config(
                text=f"Moved {nick} to Party Slot {ps+1}. Click Save to write.",
                foreground="blue")

        def _to_box():
            dest_bi  = box_labels.index(dest_box_var.get()) if dest_box_var.get() in box_labels else 0
            dest_si  = list(slot_cb["values"]).index(dest_slot_var.get())
            if dest_bi == bi and dest_si == si:
                messagebox.showinfo("Same slot", "Select a different destination.", parent=dlg)
                return
            src_list  = box.attributes.get("@pokemon", [])
            dest_b    = boxes[dest_bi]
            dest_list = dest_b.attributes.get("@pokemon", []) if isinstance(dest_b, RubyObject) else []
            while len(dest_list) <= dest_si: dest_list.append(None)
            if isinstance(dest_list[dest_si], RubyObject):
                dest_list[dest_si], src_list[si] = pkmn, dest_list[dest_si]
            else:
                dest_list[dest_si] = pkmn
                src_list[si] = None
            if isinstance(dest_b, RubyObject):
                dest_b.attributes["@pokemon"] = dest_list
            self.storage.attributes["@currentBox"] = dest_bi
            dlg.destroy()
            self._populate_boxes()
            self.boxes_nb.select(dest_bi)
            self.status.config(
                text=f"Moved {nick} to Box {dest_bi+1} Slot {dest_si}. Click Save to write.",
                foreground="blue")

    def _add_to_box_slot(self, box_idx: int, slot_idx: int, box: RubyObject):
        if not self.trainer:
            messagebox.showerror("No save loaded", "Load a save file first."); return
        def on_pick(sid):
            def on_moves(level, moves):
                def on_evs(evs):
                    pokemon_list = box.attributes.get("@pokemon", [])
                    while len(pokemon_list) <= slot_idx:
                        pokemon_list.append(None)
                    pokemon_list[slot_idx] = self._create_pokemon_obj(sid, level=level, moves=moves, evs=evs)
                    box.attributes["@pokemon"] = pokemon_list
                    # Point the PC to this box so it opens here directly, avoiding
                    # pbSwitchBoxToRight which can crash on nil slots in previously-empty boxes.
                    if isinstance(self.storage, RubyObject):
                        self.storage.attributes["@currentBox"] = box_idx
                    self._populate_boxes()
                    self.boxes_nb.select(box_idx)
                    name = PKMN_DATA.get(sid, {}).get("name", f"#{sid}")
                    self.status.config(
                        text=f"Added {name} to box {box_idx+1}. PC will open at this box. Click Save to write.",
                        foreground="blue")
                self._open_ev_picker(sid, on_evs)
            self._open_move_picker(sid, on_moves)
        self._open_pokemon_picker(on_pick)

    # ── load ─────────────────────────────────────────────────────────────────

    def _ask_load(self):
        path = filedialog.askopenfilename(
            title="Open save file",
            filetypes=[("rxdata files", "*.rxdata"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.save_path))
        if path:
            self._do_load(path)

    def _do_load(self, path):
        try:
            raw = open(path, "rb").read()
        except Exception as e:
            messagebox.showerror("Load error", str(e)); return

        positions = split_streams(raw)
        if not positions:
            messagebox.showerror("Error", "No Marshal streams found."); return

        trainer = bag = storage = None
        bag_idx = storage_idx = None
        for idx, start in enumerate(positions):
            end = positions[idx+1] if idx+1 < len(positions) else len(raw)
            try:
                obj = loads(raw[start:end])
            except Exception:
                continue
            if not isinstance(obj, RubyObject): continue
            cn = obj.ruby_class_name
            if cn == "PokeBattle_Trainer" and trainer is None:
                trainer = obj
            elif cn == "PokemonBag":
                bag = obj; bag_idx = idx
            elif cn == "PokemonStorage":
                storage = obj; storage_idx = idx

        if trainer is None:
            messagebox.showerror("Error", "PokeBattle_Trainer not found."); return

        self.raw         = raw
        self.positions   = positions
        self.trainer     = trainer
        self.bag         = bag;     self.bag_idx     = bag_idx
        self.storage     = storage; self.storage_idx = storage_idx
        self.save_path   = path

        ta = trainer.attributes
        full_id = ta.get("@id", 0) or 0
        self.trainer_id = full_id & 0xFFFF
        self.secret_id  = full_id >> 16

        self._fill_trainer()
        self._fill_party()
        self._populate_bag()
        self._populate_boxes()
        self.status.config(text=f"Loaded: {os.path.basename(path)}  ({len(raw):,} bytes)",
                           foreground="green")

    # ── fill UI ───────────────────────────────────────────────────────────────

    def _fill_trainer(self):
        ta = self.trainer.attributes
        self.var_money.set(str(ta.get("@money", 0)))
        self.var_bp.set(str(ta.get("@battle_points", 0)))
        self.var_sid.set(str(self.secret_id))
        badges = ta.get("@badges", [])
        for i, bv in enumerate(self.badge_vars):
            bv.set(badges[i] if isinstance(badges, list) and i < len(badges) else False)


    def _fill_pkmn_slot(self, v, pkmn, label_prefix="", tab_parent=None, tab_idx=None, title_frame=None):
        if isinstance(pkmn, RubyObject):
            a   = pkmn.attributes
            pid = a.get("@personalID", 0) or 0
            v["_pkmn_obj"] = pkmn
            for key, attr in [
                ("species_id","@species"),("form","@form"),("hp","@hp"),
                ("totalhp","@totalhp"),("attack","@attack"),("defense","@defense"),
                ("spatk","@spatk"),("spdef","@spdef"),("speed","@speed"),
                ("exp","@exp"),("item","@item"),("happiness","@happiness"),
                ("status","@status"),("ball","@ballused"),("obtain_lv","@obtainLevel"),
            ]:
                v[key].set(str(a.get(attr, 0)))
            v["nickname"].set(ds(a.get("@name", b"")))
            v["nature_idx"].set(NATURES[pid % 25])
            v["shiny"].set(is_shiny(pid, self.trainer_id, self.secret_id))
            ab = a.get("@abilityflag", None)
            v["ability_slot"].set(str(ab if isinstance(ab, int) else pid & 1))
            iv = a.get("@iv", [])
            ev = a.get("@ev", [])
            for j, stat in enumerate(STATS):
                key = stat.lower()
                v[f"iv_{key}"].set(str(iv[j] if isinstance(iv, list) and j < len(iv) else 0))
                v[f"ev_{key}"].set(str(ev[j] if isinstance(ev, list) and j < len(ev) else 0))
            moves = a.get("@moves", [])
            for i in range(4):
                if isinstance(moves, list) and i < len(moves) and isinstance(moves[i], RubyObject):
                    mid = moves[i].attributes.get("@id", 0)
                    pp  = moves[i].attributes.get("@pp", 0)
                    m   = MOVE_DATA.get(mid, {})
                    v[f"move{i}"].set(str(mid))
                    v[f"move{i}_name"].set(m.get("name", "—") if mid else "—")
                    v[f"movepp{i}"].set(str(pp))
                    v[f"move{i}_maxpp"].set(f"/{m.get('pp', 0)}" if mid else "/0")
                else:
                    v[f"move{i}"].set("0"); v[f"move{i}_name"].set("—")
                    v[f"movepp{i}"].set("0"); v[f"move{i}_maxpp"].set("/0")

            v["add_frame"].pack_forget()
            v["editor_frame"].pack(fill="both", expand=True)
            
            sp    = a.get("@species", 0)
            nick  = ds(a.get("@name", b""))
            label = (nick or f"Species#{sp}") + f" [#{sp}]"
            if tab_parent and tab_idx is not None:
                tab_parent.tab(tab_idx, text=f" {label[:16]} ")
            if title_frame:
                title_frame.config(text=f"{label_prefix}: {label}")
        else:
            v["_pkmn_obj"] = None
            for key, val in v.items():
                if isinstance(val, (tk.StringVar, tk.BooleanVar)):
                    val.set("")
            v["editor_frame"].pack_forget()
            v["add_frame"].pack(expand=True, fill="both")
            if tab_parent and tab_idx is not None:
                tab_parent.tab(tab_idx, text=f" {label_prefix} (empty)")
            if title_frame:
                title_frame.config(text=f"{label_prefix} (empty)")

    def _fill_party(self):
        party = self.trainer.attributes.get("@party", [])
        for slot, v in enumerate(self.pkmn_vars):
            if slot < len(party) and isinstance(party[slot], RubyObject):
                a   = party[slot].attributes
                pid = a.get("@personalID", 0) or 0
                v["_pkmn_obj"] = party[slot]
                for key, attr in [
                    ("species_id","@species"),("hp","@hp"),
                    ("totalhp","@totalhp"),("attack","@attack"),("defense","@defense"),
                    ("spatk","@spatk"),("spdef","@spdef"),("speed","@speed"),
                    ("exp","@exp"),("item","@item"),("happiness","@happiness"),
                    ("status","@status"),("ball","@ballused"),("obtain_lv","@obtainLevel"),
                ]:
                    v[key].set(str(a.get(attr, 0)))
                v["nickname"].set(ds(a.get("@name", b"")))
                v["nature_idx"].set(NATURES[pid % 25])
                v["shiny"].set(is_shiny(pid, self.trainer_id, self.secret_id))
                ab = a.get("@abilityflag", None)
                v["ability_slot"].set(str(ab if isinstance(ab, int) else pid & 1))
                iv = a.get("@iv", [])
                ev = a.get("@ev", [])
                for j, stat in enumerate(STATS):
                    key = stat.lower()
                    v[f"iv_{key}"].set(str(iv[j] if isinstance(iv, list) and j < len(iv) else 0))
                    v[f"ev_{key}"].set(str(ev[j] if isinstance(ev, list) and j < len(ev) else 0))
                moves = a.get("@moves", [])
                for i in range(4):
                    if isinstance(moves, list) and i < len(moves) and isinstance(moves[i], RubyObject):
                        mid = moves[i].attributes.get("@id", 0)
                        pp  = moves[i].attributes.get("@pp", 0)
                        m   = MOVE_DATA.get(mid, {})
                        v[f"move{i}"].set(str(mid))
                        v[f"move{i}_name"].set(m.get("name", "—") if mid else "—")
                        v[f"movepp{i}"].set(str(pp))
                        v[f"move{i}_maxpp"].set(f"/{m.get('pp', 0)}" if mid else "/0")
                    else:
                        v[f"move{i}"].set("0"); v[f"move{i}_name"].set("—")
                        v[f"movepp{i}"].set("0"); v[f"move{i}_maxpp"].set("/0")
                sp    = a.get("@species", slot+1)
                form  = a.get("@form", 0)
                self._set_pokemon_dex_vars(v, sp, form if isinstance(form, int) else 0)
                nick  = ds(a.get("@name", b""))
                label = (nick or f"Species#{sp}") + f" [#{sp}]"
                self.party_nb.tab(slot, text=f" {label[:16]} ")
                v["editor_frame"].pack(fill="both", expand=True)
                v["add_btn"].pack_forget()
            else:
                v["_pkmn_obj"] = None
                self.party_nb.tab(slot, text=f" Slot {slot+1} (empty)")
                for key, val in v.items():
                    if isinstance(val, (tk.StringVar, tk.BooleanVar)):
                        val.set("")
                if v.get("dex_sprite"):
                    v["dex_sprite"].configure(image="", text="")
                    v["dex_sprite"].image = None
                v["editor_frame"].pack_forget()
                v["add_btn"].pack(expand=True, pady=100)

    # ── apply UI → objects ────────────────────────────────────────────────────

    def _apply_trainer(self):
        ta = self.trainer.attributes
        try:
            ta["@money"]         = min(999999, max(0, int(self.var_money.get() or 0)))
            ta["@battle_points"] = max(0, int(self.var_bp.get() or 0))
        except ValueError as e:
            raise ValueError(f"Trainer fields: {e}")
        badges = ta.get("@badges", [])
        for i, bv in enumerate(self.badge_vars):
            if isinstance(badges, list) and i < len(badges):
                badges[i] = bool(bv.get())

    def _apply_party(self):
        party = self.trainer.attributes.get("@party", [])
        for slot, v in enumerate(self.pkmn_vars):
            if slot >= len(party) or not isinstance(party[slot], RubyObject): continue
            a = party[slot].attributes
            def gi(key, default=0, vv=v):
                try: return int(vv[key].get() or default)
                except: return default

            for key, attr in [
                ("hp","@hp"),("totalhp","@totalhp"),
                ("attack","@attack"),("defense","@defense"),("spatk","@spatk"),
                ("spdef","@spdef"),("speed","@speed"),("exp","@exp"),
                ("item","@item"),("happiness","@happiness"),("status","@status"),
                ("ball","@ballused"),("obtain_lv","@obtainLevel"),
            ]:
                a[attr] = gi(key)

            iv = a.get("@iv", [0]*6)
            ev = a.get("@ev", [0]*6)
            for j, stat in enumerate(STATS):
                key = stat.lower()
                if isinstance(iv, list) and j < len(iv): iv[j] = min(31,  max(0, gi(f"iv_{key}")))
                if isinstance(ev, list) and j < len(ev): ev[j] = min(252, max(0, gi(f"ev_{key}")))
            a["@form"] = max(0, min(gi("form"), 99))
            a["@iv"] = iv; a["@ev"] = _sanitize_evs(ev)

            old_pid = a.get("@personalID", 0) or 0
            old_nat = NATURES[old_pid % 25] if old_pid else ""
            old_shiny = is_shiny(old_pid, self.trainer_id, self.secret_id)
            old_ab = old_pid & 1
            
            nat_name = v["nature_idx"].get()
            nat_i    = NATURES.index(nat_name) if nat_name in NATURES else old_pid % 25
            shiny    = bool(v["shiny"].get())
            ab       = gi("ability_slot")
            
            if nat_name != old_nat or shiny != old_shiny or ab != old_ab:
                new_pid  = find_pid(nat_i, shiny, self.trainer_id, self.secret_id)
                new_pid  = (new_pid & 0xFFFFFFFE) | (ab & 1)
                a["@personalID"] = new_pid
            if "@abilityflag" in a: a["@abilityflag"] = ab

            moves = a.get("@moves", [])
            for i in range(4):
                if isinstance(moves, list) and i < len(moves) and isinstance(moves[i], RubyObject):
                    moves[i].attributes["@id"] = gi(f"move{i}")
                    moves[i].attributes["@pp"] = gi(f"movepp{i}")

            nick = v["nickname"].get()
            if nick and nick != ds(a.get("@name", b"")):
                a["@name"] = nick.encode("utf-8")

    def _apply_bag(self):
        if not isinstance(self.bag, RubyObject): return
        pockets = self.bag.attributes.get("@pockets", [])
        pocket_list = pockets if isinstance(pockets, list) else list(pockets.values())
        for pi, ei, id_var, qty_var in self.bag_rows:
            try:
                internet_id = int(id_var.get() or 0)
                iid = (internet_id - 1) // 2
                qty = int(qty_var.get() or 0)
            except ValueError:
                continue
            if pi < len(pocket_list) and isinstance(pocket_list[pi], list) and ei < len(pocket_list[pi]):
                entry = pocket_list[pi][ei]
                if isinstance(entry, list) and len(entry) >= 2:
                    entry[0] = iid; entry[1] = qty
                elif isinstance(entry, RubyObject):
                    entry.attributes["@id"] = iid; entry.attributes["@quantity"] = qty

    def _apply_boxes(self):
        for bi, box, slot_vars in self.box_vars:
            for item in slot_vars:
                if item is None: continue
                si, sv = item
                pkmn = sv.get("_pkmn_obj")
                if not isinstance(pkmn, RubyObject): continue
                a = pkmn.attributes
                def gi(key, default=0, vv=sv):
                    try: return int(vv[key].get() or default)
                    except: return default

                for key, attr in [
                    ("species_id","@species"),("hp","@hp"),
                    ("totalhp","@totalhp"),("item","@item"),("happiness","@happiness"),
                    ("status","@status"),("exp","@exp"),
                ]:
                    a[attr] = gi(key)

                nick = sv["nickname"].get()
                a["@form"] = max(0, min(gi("form"), 99))
                if nick and nick != ds(a.get("@name", b"")):
                    a["@name"] = nick.encode("utf-8")

                old_pid = a.get("@personalID", 0) or 0
                old_nat = NATURES[old_pid % 25] if old_pid else ""
                old_shiny = is_shiny(old_pid, self.trainer_id, self.secret_id)
                old_ab = old_pid & 1
                
                nat_name = sv["nature_idx"].get()
                nat_i    = NATURES.index(nat_name) if nat_name in NATURES else old_pid % 25
                shiny    = bool(sv["shiny"].get())
                ab       = gi("ability_slot")
                
                if nat_name != old_nat or shiny != old_shiny or ab != old_ab:
                    new_pid  = find_pid(nat_i, shiny, self.trainer_id, self.secret_id)
                    new_pid  = (new_pid & 0xFFFFFFFE) | (ab & 1)
                    a["@personalID"] = new_pid
                if "@abilityflag" in a: a["@abilityflag"] = ab

                iv = a.get("@iv", [0]*6)
                ev = a.get("@ev", [0]*6)
                for j, stat in enumerate(STATS):
                    if isinstance(iv, list) and j < len(iv):
                        iv[j] = min(31, max(0, gi("iv_"+stat.lower())))
                    if isinstance(ev, list) and j < len(ev):
                        ev[j] = min(252, max(0, gi("ev_"+stat.lower())))
                a["@iv"] = iv
                a["@ev"] = _sanitize_evs(ev)

                moves = a.get("@moves", [])
                for i in range(4):
                    if isinstance(moves, list) and i < len(moves) and isinstance(moves[i], RubyObject):
                        moves[i].attributes["@id"] = gi(f"move{i}")
                        moves[i].attributes["@pp"] = gi(f"movepp{i}")

    # ── save ──────────────────────────────────────────────────────────────────

    def _do_save(self):
        if self.raw is None:
            messagebox.showerror("Error", "No save loaded."); return
        try:
            self._apply_trainer()
            self._apply_party()
            self._apply_bag()
            self._apply_boxes()
        except Exception as e:
            messagebox.showerror("Validation error", str(e)); return

        positions = self.positions
        raw = self.raw

        try:
            trainer_bytes = writes(self.trainer, cls=Ruby18Writer)
        except Exception as e:
            messagebox.showerror("Serialization error", f"Trainer: {e}"); return

        bag_bytes = storage_bytes = None
        if self.bag is not None and self.bag_idx is not None:
            try:    bag_bytes     = writes(self.bag, cls=Ruby18Writer)
            except Exception as e:
                messagebox.showerror("Serialization error", f"Bag: {e}"); return
        if self.storage is not None and self.storage_idx is not None:
            try:    storage_bytes = writes(self.storage, cls=Ruby18Writer)
            except Exception as e:
                messagebox.showerror("Serialization error", f"Storage: {e}"); return

        trainer_end = positions[1] if len(positions) > 1 else len(raw)
        replacements = [(positions[0], trainer_end, trainer_bytes)]
        if self.bag_idx is not None and bag_bytes:
            bs = positions[self.bag_idx]
            be = positions[self.bag_idx+1] if self.bag_idx+1 < len(positions) else len(raw)
            replacements.append((bs, be, bag_bytes))
        if self.storage_idx is not None and storage_bytes:
            ss = positions[self.storage_idx]
            se = positions[self.storage_idx+1] if self.storage_idx+1 < len(positions) else len(raw)
            replacements.append((ss, se, storage_bytes))

        replacements.sort(key=lambda x: x[0])
        result = b""; cursor = 0
        for start, end, nb in replacements:
            result += raw[cursor:start] + nb
            cursor = end
        result += raw[cursor:]

        bak = self.save_path + ".bak"
        try: shutil.copy(self.save_path, bak)
        except Exception: pass

        try:
            with open(self.save_path, "wb") as f:
                f.write(result)
        except Exception as e:
            messagebox.showerror("Write error", str(e)); return

        self.status.config(
            text=f"Saved!  ({len(result):,} bytes)  Backup → {os.path.basename(bak)}",
            foreground="green")
        messagebox.showinfo("Saved", f"Save written.\nBackup: {bak}")


if __name__ == "__main__":
    app = Editor()
    app.mainloop()
