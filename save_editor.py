#!/usr/bin/env python3
"""
Pokemon Insurgence Save Editor
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os, shutil, re, sys

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

# Pocket 0 = unused, 1 = Items, 2 = Medicine, 3 = Balls, 4 = TMs, 5 = Berries,
# 6 = Mail, 7 = Battle Items, 8 = Key Items
POCKET_NAMES = ["Pocket 0","Items","Medicine","Poke Balls","TMs & HMs",
                "Berries","Mail","Battle Items","Key Items","Pocket 9"]

# ── item data ─────────────────────────────────────────────────────────────────

def _item_category(iid: int, name: str) -> str:
    n = name
    nl = name.lower()
    if n.startswith(("TM", "HM", "RB:", "AB:")):
        return "TMs & HMs"
    if nl.endswith("berry"):
        return "Berries"
    if nl.endswith("ball"):
        return "Poke Balls"
    if nl.endswith("mail"):
        return "Mail"
    if nl.endswith("ite") and iid > 1200:
        return "Mega Stones"
    if 435 <= iid <= 527:
        return "Medicine"
    if 931 <= iid <= 999:
        return "Battle Items"
    if iid >= 1001:
        return "Key Items"
    if iid <= 433:
        return "Hold Items"
    return "Items"

def _load_item_data():
    item_file = resource_path("item_ids.txt")
    names: dict[int, str] = {}
    cats:  dict[int, str] = {}
    if not os.path.exists(item_file):
        return names, cats
    with open(item_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r'^(?:\d+\.\s+)?(\d+)\s*\|\s*(.+)$', line)
            if m:
                iid  = int(m.group(1))
                name = m.group(2).strip()
                names[iid] = name
                cats[iid]  = _item_category(iid, name)
    return names, cats

ITEM_NAMES, ITEM_CATS = _load_item_data()
ITEM_CAT_LIST = ["All"] + sorted(set(ITEM_CATS.values()))

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
    "Hold Items":   1,
    "Mega Stones":  1,
    "Medicine":     2,
    "Poke Balls":   3,
    "TMs & HMs":    4,
    "Berries":      5,
    "Mail":         6,
    "Battle Items": 7,
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
            self.pkmn_vars.append(self._build_pkmn_slot(frame))

    def _build_pkmn_slot(self, parent):
        v = {}

        lf = ttk.LabelFrame(parent, text="Core Stats", padding=6)
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

        rf = ttk.LabelFrame(parent, text="Extra", padding=6)
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

        bf = ttk.LabelFrame(parent, text="Quick Actions", padding=6)
        bf.grid(row=0, column=2, sticky="n", padx=4, pady=4)
        ttk.Button(bf, text="Heal",       width=12, command=lambda vv=v: self._heal_slot(vv)).pack(pady=2)
        ttk.Button(bf, text="Max IVs",    width=12, command=lambda vv=v: self._max_ivs(vv)).pack(pady=2)
        ttk.Button(bf, text="Zero EVs",   width=12, command=lambda vv=v: self._zero_evs(vv)).pack(pady=2)
        ttk.Button(bf, text="Restore PP", width=12, command=lambda vv=v: self._restore_pp(vv)).pack(pady=2)

        ivf = ttk.LabelFrame(parent, text="IVs  (0–31)", padding=6)
        ivf.grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        for i, stat in enumerate(STATS):
            v["iv_"+stat.lower()] = tk.StringVar()
            ttk.Label(ivf, text=stat, width=5).grid(row=0, column=i)
            ttk.Entry(ivf, textvariable=v["iv_"+stat.lower()], width=4).grid(row=1, column=i)

        evf = ttk.LabelFrame(parent, text="EVs  (0–252, total ≤510)", padding=6)
        evf.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        for i, stat in enumerate(STATS):
            v["ev_"+stat.lower()] = tk.StringVar()
            ttk.Label(evf, text=stat, width=5).grid(row=0, column=i)
            ttk.Entry(evf, textvariable=v["ev_"+stat.lower()], width=4).grid(row=1, column=i)

        mf = ttk.LabelFrame(parent, text="Moves", padding=6)
        mf.grid(row=2, column=0, columnspan=3, sticky="ew", padx=4, pady=4)
        for i in range(4):
            v[f"move{i}"]   = tk.StringVar()
            v[f"movepp{i}"] = tk.StringVar()
            ttk.Label(mf, text=f"Move {i+1} ID:", anchor="e", width=10).grid(row=0, column=i*4,   padx=2)
            ttk.Entry(mf, textvariable=v[f"move{i}"],   width=6).grid(row=0, column=i*4+1, padx=2)
            ttk.Label(mf, text="PP:", width=4).grid(row=0, column=i*4+2)
            ttk.Entry(mf, textvariable=v[f"movepp{i}"], width=5).grid(row=0, column=i*4+3, padx=2)

        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        v["_pkmn_obj"] = None
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
        pkmn = v.get("_pkmn_obj")
        if isinstance(pkmn, RubyObject):
            self._restore_pp_from_obj(v, pkmn)

    def _restore_pp_from_obj(self, v, pkmn):
        moves = pkmn.attributes.get("@moves", [])
        for i in range(4):
            if isinstance(moves, list) and i < len(moves) and isinstance(moves[i], RubyObject):
                totalpp = moves[i].attributes.get("@totalpp", 0)
                if totalpp:
                    v[f"movepp{i}"].set(str(totalpp))

    # ── Bag tab ──────────────────────────────────────────────────────────────

    def _build_bag_tab(self):
        f = self.tab_bag
        f.columnconfigure(0, weight=1)
        f.rowconfigure(1, weight=1)

        hint = "Item IDs match the standard internet/wiki values.  Use Change to pick by category & name."
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

        # Header row
        for col, (txt, w) in enumerate([("Pocket",14),("Item ID",9),("Name",28),("Qty",7)]):
            ttk.Label(self.bag_inner, text=txt, font=("", 9, "bold"), width=w, anchor="w").grid(
                row=0, column=col, padx=4, pady=2)
        ttk.Separator(self.bag_inner, orient="horizontal").grid(
            row=1, column=0, columnspan=5, sticky="ew", pady=2)

        grid_row = 2
        for pi, pocket in enumerate(pocket_list):
            pname = POCKET_NAMES[pi] if pi < len(POCKET_NAMES) else f"Pocket {pi}"
            if not isinstance(pocket, list) or not pocket:
                continue
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

                # Keep name label in sync when user edits the ID field directly
                def _make_trace(iv, nv):
                    def _cb(*_):
                        try:
                            nv.set(item_display_name(int(iv.get())))
                        except ValueError:
                            pass
                    return _cb
                id_var.trace_add("write", _make_trace(id_var, name_var))

                ttk.Label(self.bag_inner, text=pname, width=14, anchor="w").grid(
                    row=grid_row, column=0, padx=4, pady=1)
                ttk.Entry(self.bag_inner, textvariable=id_var,  width=9).grid(
                    row=grid_row, column=1, padx=4, pady=1)
                ttk.Label(self.bag_inner, textvariable=name_var, width=28, anchor="w").grid(
                    row=grid_row, column=2, padx=4, pady=1)
                ttk.Entry(self.bag_inner, textvariable=qty_var, width=7).grid(
                    row=grid_row, column=3, padx=4, pady=1)
                ttk.Button(self.bag_inner, text="Change", width=7,
                           command=lambda iv=id_var, nv=name_var: self._open_item_picker(iv, nv)).grid(
                    row=grid_row, column=4, padx=4, pady=1)

                self.bag_rows.append((pi, ei, id_var, qty_var))
                grid_row += 1

        # Add-item section
        ttk.Separator(self.bag_inner, orient="horizontal").grid(
            row=grid_row, column=0, columnspan=5, sticky="ew", pady=4); grid_row += 1
        ttk.Label(self.bag_inner, text="Add item:", font=("", 9, "bold")).grid(
            row=grid_row, column=0, sticky="w", padx=4); grid_row += 1

        self._add_item_id = tk.StringVar()
        self._add_qty     = tk.StringVar(value="99")
        for col, lbl in enumerate(["Item ID", "Qty"]):
            ttk.Label(self.bag_inner, text=lbl, width=10).grid(row=grid_row, column=col, padx=4)
        grid_row += 1
        ttk.Entry(self.bag_inner, textvariable=self._add_item_id, width=10).grid(row=grid_row, column=0, padx=4, pady=2)
        ttk.Entry(self.bag_inner, textvariable=self._add_qty,     width=10).grid(row=grid_row, column=1, padx=4, pady=2)
        ttk.Button(self.bag_inner, text="Add",      command=self._add_bag_item).grid(row=grid_row, column=2, padx=4)
        ttk.Button(self.bag_inner, text="Browse...",
                   command=lambda: self._open_item_picker(self._add_item_id, None)).grid(
            row=grid_row, column=3, padx=4)

    def _add_bag_item(self):
        try:
            internet_id = int(self._add_item_id.get())
            iid         = (internet_id - 1) // 2
            qty         = int(self._add_qty.get())
        except ValueError:
            messagebox.showerror("Input error", "Item ID and Qty must be integers."); return
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
        self.status.config(text=f"Added: {name}  (ID {internet_id}) ×{qty} → pocket {pi}  — click Save to write.",
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
                    slot_vars.append(None); continue

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

                sv["_pkmn_obj"] = pkmn
                ttk.Button(bp, text="Max IVs", width=8, command=lambda vv=sv: self._max_ivs(vv)).pack(pady=2)
                ttk.Button(bp, text="Heal",    width=8, command=lambda vv=sv: self._heal_slot(vv)).pack(pady=2)

                slot_vars.append((si, sv))

            self.box_vars.append((bi, box, slot_vars))

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

    def _fill_party(self):
        party = self.trainer.attributes.get("@party", [])
        for slot, v in enumerate(self.pkmn_vars):
            if slot < len(party) and isinstance(party[slot], RubyObject):
                a   = party[slot].attributes
                pid = a.get("@personalID", 0) or 0
                v["_pkmn_obj"] = party[slot]
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
                        v[f"move{i}"].set(str(moves[i].attributes.get("@id", 0)))
                        v[f"movepp{i}"].set(str(moves[i].attributes.get("@pp", 0)))
                    else:
                        v[f"move{i}"].set("0"); v[f"movepp{i}"].set("0")
                sp    = a.get("@species", slot+1)
                nick  = ds(a.get("@name", b""))
                label = (nick or f"Species#{sp}") + f" [#{sp}]"
                self.party_nb.tab(slot, text=f" {label[:16]} ")
            else:
                v["_pkmn_obj"] = None
                self.party_nb.tab(slot, text=f" Slot {slot+1} (empty)")
                for key, val in v.items():
                    if isinstance(val, (tk.StringVar, tk.BooleanVar)):
                        val.set("")

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
                ("hp","@hp"),("totalhp","@totalhp"),("form","@form"),
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
            a["@iv"] = iv; a["@ev"] = ev

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
                    ("species_id","@species"),("form","@form"),("hp","@hp"),
                    ("totalhp","@totalhp"),("item","@item"),("happiness","@happiness"),
                    ("status","@status"),("exp","@exp"),
                ]:
                    a[attr] = gi(key)

                nick = sv["nickname"].get()
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
                for j, stat in enumerate(STATS):
                    if isinstance(iv, list) and j < len(iv):
                        iv[j] = min(31, max(0, gi("iv_"+stat.lower())))
                a["@iv"] = iv

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
