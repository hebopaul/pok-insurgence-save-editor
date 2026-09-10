#!/usr/bin/env python3
"""
Pokemon Insurgence Save Editor
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os, shutil, re, sys, time, copy, tempfile, json, hashlib, uuid
from datetime import datetime

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
MAX_LEVEL = 120
# The editor displays stats in the conventional order above, but Essentials'
# saved @iv/@ev arrays follow the dex/base-stat order:
# HP, Attack, Defense, Speed, Special Attack, Special Defense.
GAME_STAT_INDEX = {"hp": 0, "atk": 1, "def": 2, "spa": 4, "spd": 5, "spe": 3}
NATURES = ["Hardy","Lonely","Brave","Adamant","Naughty","Bold","Docile","Relaxed",
           "Impish","Lax","Timid","Hasty","Serious","Jolly","Naive","Modest","Mild",
           "Quiet","Bashful","Rash","Calm","Gentle","Sassy","Careful","Quirky"]
GENDERS = ["Male", "Female", "Genderless"]

# Forms with a `getForm` handler are not actually controlled by @form.  The
# game recomputes them whenever PokeBattle_Pokemon#form is read, so the editor
# must read/write the same prerequisite state rather than only changing the
# cosmetic form number.
MEWTWO_SPECIES_ID = 150
TYRANITAR_SPECIES_ID = 248
FLYGON_SPECIES_ID = 330
GIRATINA_SPECIES_ID = 487
SHAYMIN_SPECIES_ID = 492
ARCEUS_SPECIES_ID = 493
LEAVANNY_SPECIES_ID = 542
SEASONAL_FORM_SPECIES = {585, 586}  # Deerling and Sawsbuck
ZEKROM_SPECIES_ID = 644
KELDEO_SPECIES_ID = 647
GENESECT_SPECIES_ID = 649
DELTA_VOLCARONA_SPECIES_ID = 914

GRISEOUS_ORB_ITEM_ID = 197
GENESECT_FORM_ITEMS = {1: 199, 2: 200, 3: 201, 4: 198}
ARCEUS_FORM_ITEMS = {
    1: 158, 2: 161, 3: 159, 4: 160, 5: 164, 6: 163,
    7: 165, 8: 168, 10: 153, 11: 154, 12: 156, 13: 155,
    14: 162, 15: 157, 16: 166, 17: 167, 18: 723,
}
CRYSTAL_PIECE_ITEM_ID = 812
MEWTWO_ARMOR_ITEM_ID = 554
MEWTWONITE_Y_ITEM_ID = 635
MEWTWONITE_X_ITEM_ID = 637
ZEKROM_ARMOR_ITEM_ID = 752
TYRANITAR_ARMOR_ITEM_ID = 753
LEAVANNY_ARMOR_ITEM_ID = 754
FLYGON_ARMOR_ITEM_ID = 755
DELTA_VOLCARONA_ARMOR_ITEM_ID = 829

ITEM_DERIVED_FORMS = {
    ZEKROM_SPECIES_ID: {1: ZEKROM_ARMOR_ITEM_ID},
    LEAVANNY_SPECIES_ID: {1: LEAVANNY_ARMOR_ITEM_ID},
    DELTA_VOLCARONA_SPECIES_ID: {1: DELTA_VOLCARONA_ARMOR_ITEM_ID},
    GENESECT_SPECIES_ID: GENESECT_FORM_ITEMS,
}
COMPUTED_FORM_SPECIES = {
    MEWTWO_SPECIES_ID, TYRANITAR_SPECIES_ID, FLYGON_SPECIES_ID,
    GIRATINA_SPECIES_ID, SHAYMIN_SPECIES_ID, ARCEUS_SPECIES_ID,
    LEAVANNY_SPECIES_ID, *SEASONAL_FORM_SPECIES, ZEKROM_SPECIES_ID,
    KELDEO_SPECIES_ID, GENESECT_SPECIES_ID, DELTA_VOLCARONA_SPECIES_ID,
}
SECRET_SWORD_MOVE_ID = 95
FROZEN_STATUS_ID = 5
EV_PRESETS = {
    "Fresh / zero EVs": [0, 0, 0, 0, 0, 0],
    "Balanced": [85, 85, 85, 85, 85, 85],
    "Physical attacker": [6, 252, 0, 0, 0, 252],
    "Special attacker": [6, 0, 0, 252, 0, 252],
    "Bulky physical": [252, 252, 6, 0, 0, 0],
    "Bulky special": [252, 0, 0, 252, 6, 0],
    "Custom": [0, 0, 0, 0, 0, 0],
}
# Ball indices come from $BallTypes in the game's PokemonBalls script; Insurgence
# both reorders the vanilla list (2/3/4 are Safari/Ultra/Master, not Ultra/Master/
# Safari) and appends its own balls.  Icons reuse the bundled item graphics via
# BALL_ITEM_IDS, so no separate ball sprites are needed.
BALL_NAMES = {
    0: "Poké Ball", 1: "Great Ball", 2: "Safari Ball", 3: "Ultra Ball",
    4: "Master Ball", 5: "Net Ball", 6: "Dive Ball", 7: "Nest Ball",
    8: "Repeat Ball", 9: "Timer Ball", 10: "Luxury Ball", 11: "Premier Ball",
    12: "Dusk Ball", 13: "Heal Ball", 14: "Quick Ball", 15: "Cherish Ball",
    16: "Fast Ball", 17: "Level Ball", 18: "Lure Ball", 19: "Heavy Ball",
    20: "Love Ball", 21: "Friend Ball", 22: "Moon Ball", 23: "Sport Ball",
    24: "Nuzlocke Ball", 25: "Ancient Ball", 26: "Delta Ball", 27: "Snore Ball",
    28: "Shiny Ball", 29: "Sync Ball", 30: "Master Ball (alt)",
}
# Ball index -> the item's raw save ID, for the icon only.  29 has no item.
BALL_ITEM_IDS = {
    0: 535, 1: 533, 2: 537, 3: 531, 4: 529, 5: 541, 6: 543, 7: 545,
    8: 547, 9: 549, 10: 551, 11: 553, 12: 555, 13: 557, 14: 559, 15: 561,
    16: 563, 17: 565, 18: 567, 19: 569, 20: 571, 21: 573, 22: 575, 23: 539,
    24: 1105, 25: 1639, 26: 1641, 27: 1635, 28: 1643, 30: 1715,
}
BALL_CHOICES = [f"{ball_id} — {name}" for ball_id, name in BALL_NAMES.items()]
EV_TRAINING_LEVELS = {
    "Adapted": None,  # selected level / 100
    "Weak": 0.10,
    "Capable": 0.30,
    "Strong": 0.60,
    "Maxed": 1.00,
}

POKEMON_TYPES = [
    "Normal","Fire","Water","Electric","Grass","Ice","Fighting","Poison",
    "Ground","Flying","Psychic","Bug","Rock","Ghost","Dragon","Dark","Steel","Shadow","Bird","Crystal","Fairy",
]
PKMN_STAGE_LIST  = ["All", "Baby", "1", "2", "3"]
PKMN_RARITY_LIST = ["All", "Common", "Legendary", "Mythical"]
def _exp_for_level(growth: str, level: int) -> int:
    n = min(MAX_LEVEL, max(1, int(level)))
    if growth == "fast":
        return 4 * n**3 // 5
    elif growth == "medium-slow":
        return max(0, int(6 * n**3 / 5 - 15 * n**2 + 100 * n - 140))
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

def _level_for_exp(growth: str, exp: int) -> int:
    """Return the greatest supported level whose threshold does not exceed EXP."""
    try:
        value = max(0, int(exp))
    except (TypeError, ValueError):
        value = 0
    lo, hi = 1, MAX_LEVEL
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _exp_for_level(growth, mid) <= value:
            lo = mid
        else:
            hi = mid - 1
    return lo

_NATURE_STATS = ["Atk", "Def", "Spe", "SpA", "SpD"]

def nature_display_name(index: int) -> str:
    index = max(0, min(24, int(index)))
    name = NATURES[index]
    raised, lowered = index // 5, index % 5
    if raised == lowered:
        return f"{name} (neutral)"
    return f"{name} (+{_NATURE_STATS[raised]}, -{_NATURE_STATS[lowered]})"

NATURE_CHOICES = [nature_display_name(i) for i in range(len(NATURES))]

def nature_index_from_value(value, default: int = 0) -> int:
    text = str(value or "").strip()
    for index, label in enumerate(NATURE_CHOICES):
        if text == label or text == NATURES[index]:
            return index
    try:
        return max(0, min(24, int(text)))
    except ValueError:
        return max(0, min(24, int(default)))

def calculate_pokemon_stats(species_id: int, form_id: int, level: int,
                            nature_index: int, display_ivs, display_evs) -> list:
    """Calculate HP, Atk, Def, SpA, SpD and Spe using Essentials' formulas."""
    level = min(MAX_LEVEL, max(1, int(level)))
    base = pokemon_base_stats(int(species_id), int(form_id))
    ivs = [min(31, max(0, int(v))) for v in list(display_ivs)[:6]]
    evs = [min(252, max(0, int(v))) for v in list(display_evs)[:6]]
    ivs += [0] * (6 - len(ivs)); evs += [0] * (6 - len(evs))
    hp = (2 * base[0] + ivs[0] + evs[0] // 4) * level // 100 + level + 10
    result = [hp]
    nature_indices = [0, 1, 3, 4, 2]
    for i, game_index in zip(range(1, 6), nature_indices):
        raw = (2 * base[i] + ivs[i] + evs[i] // 4) * level // 100 + 5
        result.append(raw * _nature_stat_multiplier(nature_index, game_index) // 100)
    return result

def move_max_pp(move_id: int, pp_ups: int = 0) -> int:
    """Return the game's maximum PP for 0–3 applied PP Ups."""
    base = max(0, int(MOVE_DATA.get(int(move_id), {}).get("pp", 0)))
    ups = min(3, max(0, int(pp_ups)))
    return base * (5 + ups) // 5

def timestamped_backup_path(path: str, now=None) -> str:
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S-%f")
    return f"{path}.{stamp}.bak"

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

def _scale_ev_preset(values, multiplier: float) -> list:
    """Scale a legal EV preset using conventional half-up integer rounding."""
    multiplier = min(1.0, max(0.0, float(multiplier)))
    return _sanitize_evs([int((int(value) * multiplier) + 0.5) for value in values])

def _valid_ev_edit(values, index: int, proposed: str) -> bool:
    """Validate one custom EV entry without silently clamping user input."""
    if proposed == "":
        value = 0
    elif proposed.isdigit():
        value = int(proposed)
    else:
        return False
    if value > 252 or not 0 <= index < 6:
        return False
    candidate = list(values[:6]) + [0] * max(0, 6 - len(values))
    candidate[index] = value
    return sum(candidate) <= 510

def _nature_stat_multiplier(nature_index: int, game_stat_index: int) -> int:
    """Return the game's 90/100/110 modifier for Atk/Def/Spe/SpA/SpD."""
    nature_index = max(0, min(24, int(nature_index)))
    raised = nature_index // 5
    lowered = nature_index % 5
    if raised == lowered:
        return 100
    if game_stat_index == raised:
        return 110
    if game_stat_index == lowered:
        return 90
    return 100

def _game_stats_to_display(values) -> list:
    """Convert a saved IV/EV array to the order shown by the editor."""
    source = values if isinstance(values, list) else []
    result = []
    for stat in STATS:
        idx = GAME_STAT_INDEX[stat.lower()]
        result.append(source[idx] if idx < len(source) else 0)
    return result

def _display_stats_to_game(values) -> list:
    """Convert editor-ordered IV/EV values to Pokémon Essentials save order."""
    result = [0] * 6
    for display_idx, stat in enumerate(STATS):
        try:
            result[GAME_STAT_INDEX[stat.lower()]] = values[display_idx]
        except IndexError:
            pass
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
                    "ability_slots": [parts[29] if len(parts) > 29 else "", parts[30] if len(parts) > 30 else ""],
                    "abilities": [p for p in (parts[29] if len(parts) > 29 else "", parts[30] if len(parts) > 30 else "") if p],
                    "hidden_ability": parts[31] if len(parts) > 31 else "",
                    "egg_groups": [p for p in (parts[32] if len(parts) > 32 else "", parts[33] if len(parts) > 33 else "") if p],
                    "catch_rate": int(parts[34]) if len(parts) > 34 and parts[34].isdigit() else 0,
                }
            except (ValueError, IndexError):
                pass
    return data

def _load_form_data():
    path = resource_path("form_data.txt")
    data = {}
    if not os.path.exists(path):
        return data
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 4:
                continue
            try:
                sid = int(parts[0])
                form_id = int(parts[2])
            except ValueError:
                continue
            form_name = parts[3] or f"Form {form_id}"
            data.setdefault(sid, {})[form_id] = form_name
    return {sid: sorted(forms.items()) for sid, forms in data.items()}

def _load_form_override_data():
    path = resource_path("form_override_data.txt")
    data = {}
    if not os.path.exists(path):
        return data
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [part.strip() for part in line.split("|")]
            if len(parts) < 4:
                continue
            try:
                key = (int(parts[0]), int(parts[1]))
                stats = None if parts[2] == "-" else [int(value) for value in parts[2].split()]
                moves = None if parts[3] == "-" else [
                    tuple(int(value) for value in token.split(":", 1))
                    for token in parts[3].split()
                ]
            except (ValueError, IndexError):
                continue
            data[key] = {"stats": stats, "moves": moves}
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

def _load_ability_data():
    path = resource_path("ability_data.txt")
    by_id = {}
    by_name = {}
    if not os.path.exists(path):
        return by_id, by_name
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 2:
                continue
            try:
                aid = int(parts[0])
            except ValueError:
                continue
            name = parts[1]
            desc = parts[2] if len(parts) > 2 else ""
            entry = {"id": aid, "name": name, "description": desc}
            by_id[aid] = entry
            by_name[name.lower()] = entry
    return by_id, by_name

ITEM_DATA, ITEM_NAMES, ITEM_CATS = _load_item_data()
ABILITY_DATA, ABILITY_BY_NAME = _load_ability_data()
ITEM_CAT_LIST = ["All"] + sorted(set(ITEM_CATS.values()))
PKMN_DATA = _load_pokemon_data()
FORM_DATA = _load_form_data()
FORM_OVERRIDE_DATA = _load_form_override_data()
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

def _load_shadow_move_data():
    path = resource_path("shadow_move_data.txt")
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
                data[sid] = [int(t) for t in parts[1].split()]
            except (ValueError, IndexError):
                pass
    return data

MOVE_DATA        = _load_move_data()
def _load_teachable_data():
    """Species -> moves learnable only by TM, HM or tutor (from Data/tm.dat)."""
    path = resource_path("teachable_data.txt")
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
                data[int(parts[0].strip())] = {int(tok) for tok in parts[1].split()}
            except (ValueError, IndexError):
                pass
    return data

LEARNSET_DATA    = _load_learnset_data()
TEACHABLE_DATA   = _load_teachable_data()
SHADOW_MOVE_DATA = _load_shadow_move_data()

# ── maps ──────────────────────────────────────────────────────────────────────
# The player's position is editable, but only within the map the save was made
# on.  PokemonLoad does "$game_map = $MapFactory.map" with no setup() call, so
# the map that loads is the one serialised in stream 9 - tiles, events and all.
# That stream cannot even be parsed (object cycles), so changing its @map_id
# would leave the previous map's tiles under a new ID.  Cross-map relocation is
# offered through the respawn point instead, which is plain parseable data.

MAP_IMAGE_DIR = "map_images"
TOWNMAP_CELL = 16          # region images are 480x320 on a 16px grid


def _map_text(value) -> str:
    """Local decode: ds() is defined further down this module."""
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", "replace")
    return str(value) if value is not None else ""


def _load_map_names():
    """map_id -> name, from the game's MapInfos.rxdata."""
    path = resource_path(os.path.join("game_resources", "Data", "MapInfos.rxdata"))
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "rb") as stream:
            infos = loads(stream.read())
    except Exception:
        return {}
    names = {}
    for map_id, info in (infos.items() if isinstance(infos, dict) else []):
        raw = getattr(info, "attributes", {}).get("@name", b"")
        names[int(map_id)] = _map_text(raw)
    return names


def _load_town_map():
    """Regions from townmap.dat: [{name, image, points}, ...].

    A point is [cell_x, cell_y, name, subtitle, map_id, x, y, nil].  Only some
    points carry a map id - the rest are decorative labels - which is why the
    viewer also offers a plain searchable list of every map.
    """
    path = resource_path(os.path.join("game_resources", "Data", "townmap.dat"))
    if not os.path.exists(path):
        return []
    try:
        with open(path, "rb") as stream:
            raw = loads(stream.read())
    except Exception:
        return []
    regions = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, list) or len(entry) < 3:
            continue
        points = []
        for point in entry[2] or []:
            if not isinstance(point, list) or len(point) < 5:
                continue
            map_id = point[4] if isinstance(point[4], int) else None
            points.append({
                "cell": (int(point[0]), int(point[1])),
                "name": _map_text(point[2]),
                "subtitle": _map_text(point[3]) if len(point) > 3 else "",
                "map_id": map_id,
                "x": point[5] if len(point) > 5 and isinstance(point[5], int) else None,
                "y": point[6] if len(point) > 6 and isinstance(point[6], int) else None,
            })
        regions.append({"name": _map_text(entry[0]), "image": _map_text(entry[1]), "points": points})
    return regions


def _load_map_positions():
    """(region, cell_x, cell_y) -> [map_id, ...] from metadata.dat.

    townmap.dat only names 27 landmarks, but every outdoor map records its own
    town-map square in metadata entry 7 (MapPosition).  That is what makes the
    routes between towns clickable rather than dead space.
    """
    path = resource_path(os.path.join("game_resources", "Data", "metadata.dat"))
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "rb") as stream:
            table = loads(stream.read())
    except Exception:
        return {}
    cells = {}
    for map_id, entry in enumerate(table if isinstance(table, list) else []):
        if map_id == 0 or not isinstance(entry, list) or len(entry) < 8:
            continue
        position = entry[7]
        if not (isinstance(position, list) and len(position) == 3):
            continue
        try:
            key = (int(position[0]), int(position[1]), int(position[2]))
        except (TypeError, ValueError):
            continue
        cells.setdefault(key, []).append(map_id)
    return cells


def _load_map_meta():
    """(parents, doors, unused) as precomputed by tools/gen_map_index.py.

    All three come out of the 832 Map###.rxdata files, which take the better
    part of a minute to parse - far too long to do at startup - so they are
    generated once and shipped as JSON.

    parents  map_id -> parent_id, the MapInfos tree
    doors    map_id -> {(x, y): (target_map_id, direction)}
    unused   maps the game cannot reach and cannot draw: Insurgence still
             carries the whole Pokemon Essentials sample project
    """
    path = resource_path("map_meta.txt")
    if not os.path.exists(path):
        return {}, {}, frozenset()
    try:
        with open(path, encoding="utf-8") as stream:
            data = json.load(stream)
    except (ValueError, OSError):
        return {}, {}, frozenset()

    parents = {}
    for key, value in (data.get("parents") or {}).items():
        try:
            parents[int(key)] = int(value)
        except (TypeError, ValueError):
            continue

    doors = {}
    for key, cells in (data.get("doors") or {}).items():
        try:
            map_id = int(key)
        except (TypeError, ValueError):
            continue
        entry = {}
        for cell, target in (cells or {}).items():
            try:
                x, y = (int(part) for part in str(cell).split(","))
                entry[(x, y)] = (int(target[0]), str(target[1]))
            except (TypeError, ValueError, IndexError):
                continue
        if entry:
            doors[map_id] = entry

    unused = set()
    for value in (data.get("unused") or []):
        try:
            unused.add(int(value))
        except (TypeError, ValueError):
            continue
    return parents, doors, frozenset(unused)


MAP_NAMES = _load_map_names()
TOWN_MAP_REGIONS = _load_town_map()
MAP_POSITIONS = _load_map_positions()
MAP_PARENTS, MAP_DOORS, UNUSED_MAPS = _load_map_meta()

# Reverse of MAP_POSITIONS, so placing a map on the town map is a lookup.
MAP_CELL = {map_id: cell for cell, ids in MAP_POSITIONS.items() for map_id in ids}


def maps_at_town_cell(region_index: int, cell_x: int, cell_y: int) -> list:
    """Every map whose MapPosition is this town-map square."""
    return list(MAP_POSITIONS.get((int(region_index), int(cell_x), int(cell_y)), ()))


def map_ancestors(map_id) -> list:
    """A map followed by every map it sits inside, outermost last."""
    try:
        map_id = int(map_id)
    except (TypeError, ValueError):
        return []
    chain, seen = [], set()
    while map_id and map_id not in seen:
        seen.add(map_id)
        chain.append(map_id)
        map_id = MAP_PARENTS.get(map_id, 0)
    return chain


def town_cell_for_map(map_id):
    """(region, cell_x, cell_y, anchor_map_id, depth), or None if off the map.

    An interior has no MapPosition of its own - a Pokemon Center is not a square
    on the town map - so the square comes from the nearest ancestor that has
    one.  depth is how far up the chain that was: 0 means standing on the
    square's own map, anything higher means being inside something on it, which
    is what the viewer draws as an arrow rather than a box.
    """
    for depth, ancestor in enumerate(map_ancestors(map_id)):
        cell = MAP_CELL.get(ancestor)
        if cell is not None:
            return (cell[0], cell[1], cell[2], ancestor, depth)
    return None


def doors_to(view_map_id, target_map_id) -> list:
    """Doors on one map leading towards another, as (x, y, direction).

    "Towards" includes the maps the target is inside, which is what makes
    Metchi Town's Pokemon Center door the way to a player standing in the
    Center rather than nothing at all.
    """
    try:
        view_map_id = int(view_map_id)
    except (TypeError, ValueError):
        return []
    wanted = set(map_ancestors(target_map_id))
    if not wanted:
        return []
    return sorted((x, y, direction)
                  for (x, y), (target, direction) in MAP_DOORS.get(view_map_id, {}).items()
                  if target in wanted)


def map_display_name(map_id) -> str:
    try:
        map_id = int(map_id)
    except (TypeError, ValueError):
        return "-"
    name = MAP_NAMES.get(map_id, "")
    return f"{map_id} - {name}" if name else str(map_id)


def _load_map_image_index():
    """(crop offsets, skip reasons) written by tools/render_maps.py.

    The "skipped" section says why a map has no image, so the viewer can give
    the real reason rather than suggesting a re-render that would not help.
    """
    path = resource_path(os.path.join(MAP_IMAGE_DIR, "index.json"))
    if not os.path.exists(path):
        return {}, {}
    try:
        with open(path, encoding="utf-8") as stream:
            raw = json.load(stream)
    except (ValueError, OSError):
        return {}, {}
    reasons = {}
    for key, value in (raw.pop("skipped", None) or {}).items():
        try:
            reasons[int(key)] = str(value)
        except (TypeError, ValueError):
            continue
    offsets = {}
    for key, value in raw.items():
        try:
            offsets[int(key)] = value
        except (TypeError, ValueError):
            continue
    return offsets, reasons


MAP_IMAGE_INDEX, MAP_SKIP_REASONS = _load_map_image_index()


def map_skip_reason(map_id):
    """Plain-English reason a map has no rendered image, or None."""
    try:
        reason = MAP_SKIP_REASONS.get(int(map_id))
    except (TypeError, ValueError):
        return None
    if not reason:
        return None
    if reason.startswith("tileset graphic missing: "):
        return (f"This map is drawn with the tileset {reason.split(': ', 1)[1]}, which the "
                "game does not ship a graphic for.\n\nIt is leftover content the game itself "
                "cannot draw either.")
    if reason in ("no tiles", "empty tile table"):
        return "This map has no tiles at all - it is an empty placeholder in the game's data."
    return f"This map could not be rendered: {reason}."


def map_image_path(map_id, thumbnail=False):
    """Rendered PNG for a map, or None when it has not been generated."""
    try:
        map_id = int(map_id)
    except (TypeError, ValueError):
        return None
    suffix = ".thumb.png" if thumbnail else ".png"
    path = resource_path(os.path.join(MAP_IMAGE_DIR, f"map{map_id:03d}{suffix}"))
    return path if os.path.exists(path) else None


def map_image_offset(map_id):
    """(ox, oy) tile offset of a rendered image within its full map.

    Renders are cropped to the part of the map that actually has content, so a
    click has to add this back to land on the tile the game would use.
    """
    try:
        entry = MAP_IMAGE_INDEX.get(int(map_id)) or {}
    except (TypeError, ValueError):
        return (0, 0)
    return (int(entry.get("ox", 0)), int(entry.get("oy", 0)))

def species_id_from_text(value) -> int:
    """Resolve "25", "Pikachu" or "25 - Pikachu" to a species ID, else 0."""
    text = str(value or "").strip()
    match = re.match(r"^(\d+)", text)
    if match and int(match.group(1)) in PKMN_DATA:
        return int(match.group(1))
    folded = text.casefold()
    return next((sid for sid, data in PKMN_DATA.items()
                 if data.get("name", "").casefold() == folded), 0)

# Build tiers are scored, never hand-maintained: Insurgence has no competitive
# ladder, and a tier written into the file would go stale the moment a build was
# edited.  A build may still override the score by carrying its own Tier: line.
BUILD_TIERS = ("S", "A+", "A", "B+", "B", "C")
_BUILD_TIER_CUTS = ((76, "S"), (68, "A+"), (60, "A"), (55, "B+"), (48, "B"))

# Non-damaging moves that decide games.  Weights are relative worth, not power;
# every key is checked against MOVE_DATA by the test suite, because Insurgence's
# move names are the authority and a typo would silently score zero.
MOVE_UTILITY_VALUE = {
    # setup
    "Geomancy": 10, "Shell Smash": 10, "Quiver Dance": 9, "Swords Dance": 8,
    "Nasty Plot": 8, "Dragon Dance": 8, "Calm Mind": 7, "Bulk Up": 6, "Agility": 5,
    # recovery
    "Recover": 7, "Roost": 7, "Soft-Boiled": 7, "Slack Off": 7, "Wish": 6,
    "Synthesis": 5, "Moonlight": 5, "Morning Sun": 5, "Rest": 4,
    # hazards and control
    "Stealth Rock": 8, "Spikes": 6, "Sticky Web": 6, "Toxic Spikes": 5,
    "Defog": 5, "Rapid Spin": 4,
    # status
    "Spore": 9, "Sleep Powder": 7, "Toxic": 6, "Will-O-Wisp": 6, "Thunder Wave": 5,
    # field and disruption
    "Trick Room": 7, "Tailwind": 6, "Baton Pass": 6, "Taunt": 5, "Trick": 5,
    "Substitute": 4, "Protect": 3,
}

def _tier_for_score(score) -> str:
    for cutoff, label in _BUILD_TIER_CUTS:
        if score >= cutoff:
            return label
    return "C"

def _bst_points(species_id: int, form_id: int = 0) -> float:
    """0-50 points for the species' base stat total, over a 300-720 range."""
    total = sum(pokemon_base_stats(int(species_id), int(form_id)))
    return max(0.0, min(1.0, (total - 300) / 420.0)) * 50.0

def build_tier_for_species(species_id: int, form_id: int = 0) -> str:
    """Tier from base stats alone, for a species with no build attached."""
    return _tier_for_score(_bst_points(species_id, form_id) * 2)

# -- build blocks -------------------------------------------------------------

def _build_fields(build_text: str) -> dict:
    """The block's Key: value lines, lower-cased keys.  Move bullets excluded."""
    fields = {}
    for line in str(build_text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line[:1] in ("-", "*", "•"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip().casefold()] = value.strip()
    return fields

def _build_ivs_evs(fields: dict):
    ivs = [int(x) for x in re.findall(r"\d+", fields.get("ivs", ""))][:6]
    ivs = [min(31, max(0, v)) for v in ivs] + [31] * max(0, 6 - len(ivs))
    ev_map = {stat: 0 for stat in STATS}
    aliases = {"hp": "HP", "atk": "Atk", "def": "Def", "spa": "SpA", "spatk": "SpA",
               "spd": "SpD", "spdef": "SpD", "spe": "Spe", "speed": "Spe"}
    for amount, stat in re.findall(r"(\d+)\s*([A-Za-z]+)", fields.get("evs", "")):
        key = aliases.get(stat.casefold())
        if key:
            ev_map[key] = min(252, max(0, int(amount)))
    return ivs, [ev_map[stat] for stat in STATS]

def _build_move_ids(build_text: str) -> list:
    ids, in_moves = [], False
    for line in str(build_text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.casefold().startswith("moves:"):
            in_moves = True
            continue
        if not in_moves:
            continue
        if line[:1] in ("-", "*", "•"):
            name = line[1:].strip()
        elif ":" in line:
            in_moves = False
            continue
        else:
            name = line
        match = re.match(r"^(\d+)", name)
        move_id = int(match.group(1)) if match else next(
            (mid for mid, data in MOVE_DATA.items()
             if data.get("name", "").casefold() == name.casefold()), 0)
        if move_id in MOVE_DATA:
            ids.append(move_id)
    return ids[:4]

def build_score(build_text: str) -> int:
    """Score a build 0-100: base stats first, then how well it is actually built."""
    fields = _build_fields(build_text)
    species_id = species_id_from_text(fields.get("species", ""))
    if not species_id:
        return 0
    score = _bst_points(species_id)

    ivs, evs = _build_ivs_evs(fields)
    score += (sum(evs) / 510.0) * 9.0 + (sum(ivs) / 186.0) * 6.0

    move_ids = _build_move_ids(build_text)
    powers = [MOVE_DATA[m].get("power", 0) for m in move_ids
              if MOVE_DATA.get(m, {}).get("power", 0) > 0]
    if powers:
        score += max(0.0, min(1.0, (sum(powers) / len(powers)) / 120.0)) * 20.0

    utility = sum(MOVE_UTILITY_VALUE.get(MOVE_DATA.get(m, {}).get("name", ""), 0)
                  for m in move_ids)
    score += min(15.0, utility)
    return int(round(max(0.0, min(100.0, score))))

def build_tier(build_text: str) -> str:
    """A build's own Tier: line wins; otherwise the tier follows its score."""
    fields = _build_fields(build_text)
    stored = fields.get("tier", "").strip()
    if stored:
        return stored
    if not species_id_from_text(fields.get("species", "")):
        return "?"
    return _tier_for_score(build_score(build_text))

# -- style --------------------------------------------------------------------

BUILD_STYLES = ("Physical Sweeper", "Special Sweeper", "Mixed Sweeper",
                "Bulky Physical", "Bulky Special", "Physical Wall", "Special Wall",
                "Utility", "All-Rounder")

def style_for_stats(stats) -> str:
    """Name the role implied by final HP/Atk/Def/SpA/SpD/Spe values."""
    hp, atk, defense, spatk, spdef, speed = (list(stats) + [0] * 6)[:6]
    offence = max(atk, spatk)
    bulk = (hp + defense + spdef) / 3.0
    total = max(1.0, offence + bulk + speed)
    off_share, bulk_share, speed_share = offence / total, bulk / total, speed / total

    if atk >= spatk * 1.15:
        side, bulky = "Physical", "Bulky Physical"
    elif spatk >= atk * 1.15:
        side, bulky = "Special", "Bulky Special"
    else:
        side, bulky = "Mixed", None

    if off_share < 0.30:
        if bulk_share > 0.40:
            return "Special Wall" if spdef >= defense else "Physical Wall"
        return "Utility"
    if speed_share >= 0.30:
        return side + " Sweeper"
    if bulk_share >= 0.38:
        return bulky or ("Bulky Special" if spatk >= atk else "Bulky Physical")
    if off_share >= 0.36:
        return side + " Sweeper"
    return "All-Rounder"

def build_style(build_text: str) -> str:
    """Classify a build from its final stats: base, IVs, EVs and nature combined."""
    fields = _build_fields(build_text)
    species_id = species_id_from_text(fields.get("species", ""))
    if not species_id:
        return "?"
    ivs, evs = _build_ivs_evs(fields)
    digits = re.sub(r"\D", "", fields.get("level", "")) or "100"
    level = min(MAX_LEVEL, max(1, int(digits)))
    nature = next((i for i, name in enumerate(NATURES)
                   if name.casefold() == fields.get("nature", "").casefold()), 0)
    return style_for_stats(calculate_pokemon_stats(species_id, 0, level, nature, ivs, evs))

# -- display ------------------------------------------------------------------

def possessive(name: str) -> str:
    """Ash -> Ash's, Jesus -> Jesus' - the English apostrophe rule."""
    name = str(name or "").strip()
    if not name:
        return ""
    return name + ("'" if name[-1:].casefold() == "s" else "'s")

def build_summary(build_text: str) -> dict:
    """Everything the library table and Info tab show, derived from one block."""
    fields = _build_fields(build_text)
    species_id = species_id_from_text(fields.get("species", ""))
    return {
        "trainer": fields.get("trainer", "").strip() or "Wild",
        "species_id": species_id,
        "species_name": PKMN_DATA.get(species_id, {}).get("name", "")
                        or (fields.get("species", "").strip() or "Unknown"),
        "description": fields.get("description", "").strip(),
        "tier": build_tier(build_text),
        "style": build_style(build_text),
    }

# -- validation ---------------------------------------------------------------
# Only the keys something actually reads are legal, so a typo like "Abilty:" is
# caught rather than silently ignored.  Trainer and Description may be blank or
# absent; Species is the one field a build cannot do without.
BUILD_KEYS = ("trainer", "species", "description", "nickname", "level", "nature",
              "ability", "ivs", "evs", "moves", "item", "happiness", "tier")
BUILD_KEY_LABELS = {key: {"ivs": "IVs", "evs": "EVs"}.get(key, key.title()) for key in BUILD_KEYS}


def validate_build_block(block: str, first_line: int = 1) -> list:
    """Syntax problems in one block, as (line number, message).

    Line numbers are counted in the text as the user sees it, so a message can
    point at the line that is actually wrong.
    """
    problems = []
    seen, key_lines, in_moves, move_count = set(), {}, False, 0
    for offset, raw_line in enumerate(str(block or "").splitlines()):
        number = first_line + offset
        line = raw_line.strip()
        if not line or line.startswith("#") or line == "---":
            continue
        if line[:1] in ("-", "*", "•"):
            if not in_moves:
                problems.append((number, "Move bullet outside a Moves: list"))
            elif not line[1:].strip():
                problems.append((number, "Empty move bullet"))
            else:
                move_count += 1
            continue
        if ":" not in line:
            problems.append((number, f"Not a 'Key: value' line: {line!r}"))
            in_moves = False
            continue
        key = line.split(":", 1)[0].strip().casefold()
        if key == BUILD_ID_FIELD:
            continue                       # ours, not the user's - quietly ignored
        if key not in BUILD_KEYS:
            problems.append((number, f"Unknown field {line.split(':', 1)[0].strip()!r}. "
                                     f"Valid fields: {', '.join(BUILD_KEY_LABELS.values())}"))
        elif key in seen:
            problems.append((number, f"Duplicate field {BUILD_KEY_LABELS[key]!r}"))
        seen.add(key)
        key_lines.setdefault(key, number)
        in_moves = key == "moves"

    def at(key):
        return key_lines.get(key, first_line)

    if move_count > 4:
        problems.append((at("moves"), f"A Pokemon can hold four moves, this block lists {move_count}"))
    fields = _build_fields(block)
    if not fields.get("species", "").strip():
        problems.append((at("species"), "Species is required"))
    tier = fields.get("tier", "").strip()
    if tier and tier not in BUILD_TIERS:
        problems.append((at("tier"), f"Tier must be one of {', '.join(BUILD_TIERS)}"))
    for key, low, high in (("happiness", 0, 255), ("level", 1, MAX_LEVEL)):
        text = fields.get(key, "").strip()
        if text and (not text.isdigit() or not low <= int(text) <= high):
            problems.append((at(key), f"{BUILD_KEY_LABELS[key]} must be a whole number "
                                      f"from {low} to {high}"))
    if fields.get("evs", "").strip():
        total = sum(int(amount) for amount, _stat in re.findall(r"(\d+)\s*([A-Za-z]+)", fields["evs"]))
        if total > 510:
            problems.append((at("evs"), f"EVs total {total}, and the game allows 510"))
    return sorted(problems)


def build_validation_report(problems) -> str:
    """The message the dialog shows, one problem per line."""
    return "\n".join(f"Block {block}, line {line}: {message}"
                     for block, line, message in problems)


def build_title(build_text: str) -> str:
    """Ash's Pikachu, or just Pikachu for a wild or unowned build."""
    summary = build_summary(build_text)
    trainer = summary["trainer"]
    if trainer.casefold() in ("wild", "none", "-", ""):
        return summary["species_name"]
    return possessive(trainer) + " " + summary["species_name"]

def user_builds_path() -> str:
    """Where builds saved from the editor live.

    The bundled pokemon_builds.txt sits inside the PyInstaller archive and is
    read-only at runtime, so anything the user saves goes to their own file.
    """
    root = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(root, "PokemonInsurgenceSaveEditor", "pokemon_builds.user.txt")

def _read_build_blocks(path: str) -> list:
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as stream:
        raw = stream.read()
    builds = []
    for block in re.split(r"^---\s*$", raw, flags=re.MULTILINE):
        lines = [line.rstrip() for line in block.splitlines()
                 if line.strip() and not line.lstrip().startswith("#")]
        if not lines:
            continue
        # A legacy block opens with a "[Tier] Species - Set" display line; the
        # current format is fields only, so drop a leading non-field line.
        if ":" not in lines[0]:
            lines.pop(0)
        if lines:
            builds.append("\n".join(lines).strip())
    return [text for text in builds if _build_fields(text).get("species")]

# -- build identity -----------------------------------------------------------
# Every block carries an Id, which the editor strips before showing it: the user
# never sees it and never types it.  It exists so a block in the user's file can
# *replace* one of the bundled builds instead of sitting next to it as a near
# duplicate.  Bundled ids are derived from the block itself rather than being
# random, so regenerating pokemon_builds.txt does not silently orphan overrides.

BUILD_ID_FIELD = "id"


def build_content_id(build_text: str) -> str:
    """The id a block gets when it does not carry one of its own."""
    fields = _build_fields(build_text)
    seed = "|".join(fields.get(key, "").strip().casefold()
                    for key in ("trainer", "species", "description"))
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def new_build_id() -> str:
    """A fresh id for a build the user has just written."""
    return uuid.uuid4().hex[:12]


def build_id(build_text: str) -> str:
    return _build_fields(build_text).get(BUILD_ID_FIELD, "").strip() or build_content_id(build_text)


def strip_build_id(build_text: str) -> str:
    """The block as the user should see it, without its Id line."""
    return "\n".join(line for line in str(build_text or "").splitlines()
                     if line.split(":")[0].strip().casefold() != BUILD_ID_FIELD).strip()


def with_build_id(build_text: str, identifier: str) -> str:
    """The block as it is stored, with its Id line first."""
    return f"Id: {identifier}\n{strip_build_id(build_text)}"


def split_build_blocks(raw: str) -> list:
    """Split library text into blocks on a line containing only ---."""
    return [block for block, _line in split_build_blocks_with_lines(raw)]


def split_build_blocks_with_lines(raw: str) -> list:
    """(block, first line number) pairs, so a problem can name the real line."""
    blocks, current, start = [], [], 1
    for number, line in enumerate(str(raw or "").splitlines(), start=1):
        if re.match(r"^---\s*$", line):
            if any(text.strip() for text in current):
                blocks.append(("\n".join(current).strip(), start))
            current, start = [], number + 1
            continue
        if not current and not line.strip():
            start = number + 1              # keep the count off leading blank lines
            continue
        current.append(line)
    if any(text.strip() for text in current):
        blocks.append(("\n".join(current).strip(), start))
    return blocks


def _load_build_library():
    """(texts, ids, sources) with the user's builds overriding the bundled ones.

    A user block whose id matches a bundled one takes its place, keeping the
    bundled ordering so an edited build does not jump to the end of the list.
    """
    bundled = _read_build_blocks(resource_path("pokemon_builds.txt"))
    personal = _read_build_blocks(user_builds_path())

    texts, ids, sources = [], [], []
    position = {}
    for text in bundled:
        identifier = build_id(text)
        position[identifier] = len(texts)
        texts.append(text); ids.append(identifier); sources.append("bundled")
    for text in personal:
        identifier = build_id(text)
        if identifier in position:
            index = position[identifier]
            texts[index], sources[index] = text, "user"
        else:
            position[identifier] = len(texts)
            texts.append(text); ids.append(identifier); sources.append("user")
    return texts, ids, sources


def reload_build_library() -> list:
    """Re-read both library files after the user saves a build."""
    global BUILD_LIBRARY, BUILD_IDS, BUILD_SOURCES
    BUILD_LIBRARY, BUILD_IDS, BUILD_SOURCES = _load_build_library()
    return BUILD_LIBRARY


def read_user_builds() -> list:
    """The user's own blocks, each guaranteed to carry an explicit Id."""
    return [with_build_id(text, build_id(text)) for text in _read_build_blocks(user_builds_path())]


def write_user_builds(blocks) -> str:
    """Rewrite the user's library file, wholesale.

    Editing an existing build means replacing its block, not appending another,
    so the whole file is rewritten - through a temporary file and a rename, so a
    failure part-way cannot leave a half-written library behind.
    """
    path = user_builds_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    body = "\n---\n".join(block.strip() for block in blocks if block.strip())
    text = "# Builds saved from the Pokemon Insurgence Save Editor.\n\n" + body + "\n"
    handle, temporary = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    except Exception:
        if os.path.exists(temporary):
            os.remove(temporary)
        raise
    reload_build_library()
    return path


def save_user_builds(pairs) -> str:
    """Store (id, block text) pairs, replacing any entry already using that id."""
    existing = read_user_builds()
    by_id = {build_id(text): index for index, text in enumerate(existing)}
    for identifier, text in pairs:
        block = with_build_id(text, identifier)
        if identifier in by_id:
            existing[by_id[identifier]] = block
        else:
            by_id[identifier] = len(existing)
            existing.append(block)
    return write_user_builds(existing)


def append_user_build(build_text: str) -> str:
    """Add one new block to the user's library and return the file's path."""
    return save_user_builds([(new_build_id(), build_text)])


BUILD_LIBRARY, BUILD_IDS, BUILD_SOURCES = _load_build_library()

def pokemon_base_stats(species_id: int, form_id: int = 0) -> list:
    """Return HP/Atk/Def/SpA/SpD/Spe, honoring form script overrides."""
    override = FORM_OVERRIDE_DATA.get((species_id, form_id), {}).get("stats")
    if override:
        return list(override)
    data = PKMN_DATA.get(species_id, {})
    return [data.get(key, 0) for key in ("hp", "atk", "def", "spa", "spd", "spe")]

def pokemon_learnset(species_id: int, form_id: int = 0) -> list:
    """Return the level-up learnset resolved by PokemonMultipleForms."""
    override = FORM_OVERRIDE_DATA.get((species_id, form_id), {}).get("moves")
    return list(override) if override is not None else list(LEARNSET_DATA.get(species_id, []))

def required_form_moves(species_id: int, form_id: int) -> set:
    """Moves required for a form to remain valid in the game's getForm handler."""
    if species_id == KELDEO_SPECIES_ID and form_id == 1:
        return {SECRET_SWORD_MOVE_ID}
    return set()


# Move legality colours: green for what the species learns itself, light blue for
# what it can be taught, dark red for everything else.  Each filter toggle is
# tinted with the very same colour as the rows it controls.
MOVE_KIND_COLOURS = {
    "levelup": "#3fb950",
    "teachable": "#7cc4ff",
    "illegal": "#c0392b",
}
MOVE_KIND_LABELS = {
    "levelup": "Level-up",
    "teachable": "Teachable",
    "illegal": "Illegal",
}
def pokemon_teachable(species_id: int) -> set:
    """Move IDs a species can be taught but never learns by levelling up."""
    return set(TEACHABLE_DATA.get(int(species_id), ()))

def recommended_creation_move_ids(learnset: list, level: int,
                                   move_data: dict = None) -> list:
    """Choose up to four distinct creation moves using the picker slot rules.

    The slots are strongest damaging move, strongest remaining Special move,
    most accurate remaining move (power breaks ties), and latest-learned
    remaining Status move. A slot is omitted when it has no valid candidate.
    """
    data = MOVE_DATA if move_data is None else move_data
    level = max(1, min(MAX_LEVEL, int(level)))

    # Keep the latest eligible occurrence of a move. The source position makes
    # same-level support-move ties deterministic and follows learnset order.
    available = {}
    for position, (learn_level, move_id) in enumerate(learnset):
        if learn_level > level or move_id not in data:
            continue
        previous = available.get(move_id)
        if previous is None or (learn_level, position) > previous[:2]:
            available[move_id] = (learn_level, position, data[move_id])

    chosen = []

    def choose(predicate, key):
        candidates = [
            (move_id, details)
            for move_id, details in available.items()
            if move_id not in chosen and predicate(details[2])
        ]
        if candidates:
            move_id, _details = max(candidates, key=lambda entry: key(entry[0], entry[1]))
            chosen.append(move_id)

    # A lower move ID is the final tie-breaker so recommendations never depend
    # on dictionary ordering.
    choose(
        lambda move: move.get("power", 0) > 0,
        lambda move_id, details: (
            details[2].get("power", 0), details[0],
            details[2].get("accuracy", 0), -move_id,
        ),
    )
    choose(
        lambda move: move.get("category") == "Special" and move.get("power", 0) > 0,
        lambda move_id, details: (
            details[2].get("power", 0), details[0],
            details[2].get("accuracy", 0), -move_id,
        ),
    )
    choose(
        lambda move: move.get("accuracy", 0) > 0,
        lambda move_id, details: (
            details[2].get("accuracy", 0), details[2].get("power", 0),
            details[0], -move_id,
        ),
    )
    choose(
        lambda move: move.get("category") == "Status",
        lambda move_id, details: (details[0], details[1], -move_id),
    )
    return chosen


def move_party_pokemon_to_box(party: list, party_slot: int,
                              box_pokemon: list, box_slot: int):
    """Move a party member into a PC slot, swapping when that slot is occupied."""
    if not isinstance(party, list) or not isinstance(box_pokemon, list):
        raise ValueError("Party and box Pokémon collections must be lists.")
    if party_slot < 0 or party_slot >= len(party) or not isinstance(party[party_slot], RubyObject):
        raise ValueError("The selected party slot is empty.")
    if box_slot < 0:
        raise ValueError("The destination box slot is invalid.")

    while len(box_pokemon) <= box_slot:
        box_pokemon.append(None)
    pokemon = party[party_slot]
    displaced = box_pokemon[box_slot]
    box_pokemon[box_slot] = pokemon
    if isinstance(displaced, RubyObject):
        party[party_slot] = displaced
    else:
        # The game expects a compact party array, not empty gaps between slots.
        party.pop(party_slot)
        displaced = None
    return displaced

# ── helpers ───────────────────────────────────────────────────────────────────

def ds(s):
    if isinstance(s, (bytes, bytearray)): return s.decode("utf-8", "replace")
    return str(s) if s is not None else ""

MARSHAL_HEADER = b"\x04\x08"


class _MarshalScanner:
    """Walk one Marshal 4.8 stream and report where it ends.

    Only byte lengths matter here, so unlike a real reader this never builds
    objects and never resolves symlinks/links.  That makes it immune to the
    rubymarshal limitations (object cycles, unsupported classes) that stop
    ``loads()`` on streams such as ``Game_Map``.
    """

    def __init__(self, raw: bytes, offset: int):
        self.raw = raw
        self.pos = offset

    def _byte(self) -> int:
        if self.pos >= len(self.raw):
            raise ValueError("truncated Marshal stream")
        value = self.raw[self.pos]
        self.pos += 1
        return value

    def _skip(self, count: int):
        if count < 0 or self.pos + count > len(self.raw):
            raise ValueError("truncated Marshal stream")
        self.pos += count

    def _long(self) -> int:
        """Ruby's packed integer encoding (same rules as Reader.read_long)."""
        length = self._byte()
        if length > 127:
            length -= 256
        if length == 0:
            return 0
        if 5 < length < 128:
            return length - 5
        if -129 < length < -5:
            return length + 5
        result, factor = 0, 1
        for _ in range(abs(length)):
            result += self._byte() * factor
            factor *= 256
        return result - factor if length < 0 else result

    def _blob(self):
        self._skip(self._long())

    def _pairs(self, count: int):
        for _ in range(count):
            self._value()
            self._value()

    def _attributes(self):
        self._pairs(self._long())

    def _value(self):
        token = bytes([self._byte()])
        if token in (b"0", b"T", b"F"):
            return
        if token == b"i":
            self._long()
        elif token in (b":", b'"', b"f", b"c", b"m", b"M"):
            self._blob()
        elif token in (b";", b"@"):
            self._long()
        elif token == b"l":
            self._skip(1)                 # sign
            self._skip(2 * self._long())  # 16-bit words
        elif token == b"/":
            self._blob()
            self._skip(1)                 # regexp options
        elif token == b"[":
            for _ in range(self._long()):
                self._value()
        elif token == b"{":
            self._pairs(self._long())
        elif token == b"}":
            self._pairs(self._long())
            self._value()                 # default value
        elif token == b"I":
            self._value()
            self._attributes()
        elif token == b"o":
            self._value()                 # class symbol
            self._attributes()
        elif token == b"S":
            self._value()                 # class symbol
            self._pairs(self._long())
        elif token == b"u":
            self._value()                 # class symbol
            self._blob()
        elif token in (b"U", b"e", b"C", b"d"):
            self._value()                 # class symbol
            self._value()
        else:
            raise ValueError("unknown Marshal token %r" % token)


def marshal_stream_end(raw: bytes, offset: int) -> int:
    """Byte offset just past the Marshal stream starting at ``offset``."""
    if raw[offset:offset + 2] != MARSHAL_HEADER:
        raise ValueError("no Marshal 4.8 header at offset %d" % offset)
    scanner = _MarshalScanner(raw, offset + 2)
    scanner._value()
    return scanner.pos


def split_streams(raw: bytes):
    """Start offsets of every top-level Marshal stream in a save file.

    A save is a plain concatenation of Marshal streams, so each stream's real
    length has to be measured.  Scanning for the 0x04 0x08 header alone is
    not enough: that byte pair also shows up *inside* stream data (any 4-byte
    Fixnum or Bignum whose next byte is 0x08 produces it), which used to split a
    stream in half.  The half-stream then failed to parse - most visibly the PC
    storage, which is the last stream, leaving the PC Boxes tab empty - and made
    the save-time byte ranges wrong.
    """
    positions, offset = [], 0
    while offset < len(raw):
        try:
            end = marshal_stream_end(raw, offset)
        except (ValueError, IndexError):
            break
        if end <= offset:
            break
        positions.append(offset)
        offset = end
    if positions and offset == len(raw):
        return positions
    # Unrecognised layout: fall back to the header scan rather than dropping data.
    return [i for i in range(len(raw) - 1) if raw[i] == 0x04 and raw[i + 1] == 0x08]

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

def pokemon_nature(attributes: dict) -> int:
    """Return the nature the game will use, including its explicit override."""
    override = attributes.get("@natureflag")
    if isinstance(override, int) and not isinstance(override, bool) and 0 <= override < len(NATURES):
        return override
    pid = attributes.get("@personalID", 0)
    return (pid if isinstance(pid, int) else 0) % len(NATURES)

def pokemon_is_shiny(attributes: dict, trainer_id: int = 0, secret_id: int = 0) -> bool:
    """Return the shiny state the game will use, including its explicit override."""
    override = attributes.get("@shinyflag")
    if isinstance(override, bool):
        return override
    pid = attributes.get("@personalID", 0)
    original_trainer_id = attributes.get("@trainerID")
    if isinstance(original_trainer_id, int):
        trainer_id = original_trainer_id & 0xFFFF
        secret_id = (original_trainer_id >> 16) & 0xFFFF
    return is_shiny(pid, trainer_id, secret_id)

def ability_choices_for_species(species_id: int) -> list:
    """Return unique (slot, display name) choices supported by a species."""
    data = PKMN_DATA.get(species_id, {})
    normal_slots = list(data.get("ability_slots", []))
    if not normal_slots:
        normal_slots = list(data.get("abilities", []))
    normal_slots = (normal_slots + ["", ""])[:2]
    candidates = [(0, normal_slots[0]), (1, normal_slots[1]), (2, data.get("hidden_ability", ""))]

    choices = []
    seen_names = set()
    for slot, name in candidates:
        name = str(name or "").strip()
        key = name.casefold()
        if not name or key in seen_names:
            continue
        seen_names.add(key)
        label = f"{name} (Hidden)" if slot == 2 else name
        choices.append((slot, label))
    return choices or [(0, "Ability slot 0")]

def ability_slot_from_value(species_id: int, value, default: int = 0) -> int:
    text = str(value or "").strip()
    for slot, label in ability_choices_for_species(species_id):
        if text == label:
            return slot
    try:
        return min(2, max(0, int(text.split(" - ", 1)[0])))
    except ValueError:
        return default

def gender_choices_for_species(species_id: int) -> list:
    rate = PKMN_DATA.get(species_id, {}).get("gender_rate", "")
    if rate == "Genderless":
        return ["Genderless"]
    if rate == "Always female":
        return ["Female"]
    if rate == "Always male":
        return ["Male"]
    return ["Male", "Female"]

def pokemon_gender(attributes: dict) -> str:
    """Return the gender the game will display for a saved Pokemon."""
    override = attributes.get("@genderflag")
    if isinstance(override, int) and not isinstance(override, bool) and override in (0, 1):
        return GENDERS[override]

    species_id = attributes.get("@species", 0)
    rate = PKMN_DATA.get(species_id, {}).get("gender_rate", "")
    if rate == "Genderless":
        return "Genderless"
    if rate == "Always female":
        return "Female"
    if rate == "Always male":
        return "Male"

    thresholds = {
        "Female 12.5%": 30,
        "Female 25%": 63,
        "Female 50%": 126,
        "Female 75%": 190,
    }
    pid = attributes.get("@personalID", 0)
    low_byte = (pid if isinstance(pid, int) else 0) & 0xFF
    return "Female" if low_byte <= thresholds.get(rate, 126) else "Male"

def _raw_pokemon_form(attributes: dict) -> int:
    raw_form = attributes.get("@form", 0)
    return raw_form if isinstance(raw_form, int) and not isinstance(raw_form, bool) else 0


def _form_time_parts(now=None):
    """Return local (month, hour), accepting a datetime/time tuple in tests."""
    now = time.localtime() if now is None else now
    month = getattr(now, "month", getattr(now, "tm_mon", 1))
    hour = getattr(now, "hour", getattr(now, "tm_hour", 12))
    return int(month), int(hour)


def seasonal_pokemon_form(now=None) -> int:
    """Mirror Deerling/Sawsbuck's month-derived getForm handler."""
    month, _hour = _form_time_parts(now)
    return 3 if month in (1, 2) else (month // 3) - 1


def _saved_move_ids(attributes: dict) -> list:
    """Read move IDs without padding or otherwise mutating an untouched save."""
    result = []
    moves = attributes.get("@moves")
    if not isinstance(moves, list):
        return result
    for move in moves[:4]:
        if isinstance(move, RubyObject):
            move_id = move.attributes.get("@id", 0)
            result.append(move_id if isinstance(move_id, int) else 0)
        else:
            result.append(0)
    return result


def pokemon_form(attributes: dict, now=None) -> int:
    """Return exactly the form Insurgence's MultipleForms#getForm resolves.

    Species without a getForm handler persist @form directly.  The exceptional
    species below are recomputed by the game from items, moves, flags, time, or
    condition; a bare @form value is ignored for them.
    """
    raw_form = _raw_pokemon_form(attributes)
    species = attributes.get("@species")
    item = attributes.get("@item", 0)

    if species == GIRATINA_SPECIES_ID:
        if item == GRISEOUS_ORB_ITEM_ID:
            return 1
        if item == CRYSTAL_PIECE_ITEM_ID and attributes.get("@primalBattle"):
            return 2
        return 0

    if species == SHAYMIN_SPECIES_ID:
        _month, hour = _form_time_parts(now)
        if hour >= 20 or hour < 6 or attributes.get("@hp", 1) <= 0 \
                or attributes.get("@status", 0) == FROZEN_STATUS_ID:
            return 0
        return raw_form

    if species == ARCEUS_SPECIES_ID:
        if attributes.get("@abilityflag") != 2:
            for form_id, required_item in ARCEUS_FORM_ITEMS.items():
                if item == required_item:
                    return form_id
        if item == CRYSTAL_PIECE_ITEM_ID and attributes.get("@primalBattle"):
            return 19
        return raw_form if attributes.get("@abilityflag") == 2 else 0

    if species == MEWTWO_SPECIES_ID:
        is_shadow = bool(attributes.get("@shadowMewtwo"))
        if item == MEWTWO_ARMOR_ITEM_ID and not is_shadow:
            return 1
        if (item == MEWTWONITE_X_ITEM_ID and attributes.get("@normalMegaMewtwoX")
                and attributes.get("@normalMewtwo")):
            return 2
        if (item == MEWTWONITE_Y_ITEM_ID and attributes.get("@normalMegaMewtwoY")
                and attributes.get("@normalMewtwo")):
            return 3
        if is_shadow:
            return 5 if attributes.get("@shadowMegaMewtwo") else 4
        return 0

    if species in SEASONAL_FORM_SPECIES:
        return seasonal_pokemon_form(now)

    if species == KELDEO_SPECIES_ID:
        return 1 if SECRET_SWORD_MOVE_ID in _saved_move_ids(attributes) else 0

    if species == TYRANITAR_SPECIES_ID:
        if attributes.get("@megaTyranitar") and item != TYRANITAR_ARMOR_ITEM_ID:
            return 1
        return 2 if item == TYRANITAR_ARMOR_ITEM_ID else 0

    if species == FLYGON_SPECIES_ID:
        if item == FLYGON_ARMOR_ITEM_ID:
            return 1
        if attributes.get("@megaFlygon") and item != FLYGON_ARMOR_ITEM_ID:
            return 2
        return 0

    item_forms = ITEM_DERIVED_FORMS.get(species)
    if item_forms:
        for form_id, required_item in item_forms.items():
            if item == required_item:
                return form_id
        return 0

    return raw_form


def _clear_form_items(attributes: dict, item_ids):
    if attributes.get("@item") in item_ids:
        attributes["@item"] = 0


def _set_keldeo_form(attributes: dict, form_id: int):
    move_ids = _saved_move_ids(attributes)
    if form_id == 1 and SECRET_SWORD_MOVE_ID not in move_ids:
        if len(move_ids) >= 4 and all(move_ids):
            raise ValueError(
                "Resolute Keldeo requires Secret Sword. Put Secret Sword in a move slot first."
            )
        slots = _move_slots(attributes)
        empty = next(i for i, move_id in enumerate(pokemon_move_ids(attributes)) if not move_id)
        _write_move_slot(slots[empty], SECRET_SWORD_MOVE_ID)
    elif form_id == 0 and SECRET_SWORD_MOVE_ID in move_ids:
        if not any(move_id and move_id != SECRET_SWORD_MOVE_ID for move_id in move_ids):
            raise ValueError(
                "Ordinary Keldeo cannot keep Secret Sword. Give it another move before changing form."
            )
        for slot in _move_slots(attributes)[:4]:
            if isinstance(slot, RubyObject) and slot.attributes.get("@id") == SECRET_SWORD_MOVE_ID:
                _write_move_slot(slot, 0)
        _compact_moves(attributes)


def apply_pokemon_form(attributes: dict, form_id: int, now=None):
    """Apply a form plus every prerequisite used by the game's getForm code."""
    form_id = max(0, min(int(form_id), 99))
    species = attributes.get("@species")

    if species in SEASONAL_FORM_SPECIES:
        current = seasonal_pokemon_form(now)
        if form_id != current:
            raise ValueError(
                "Deerling and Sawsbuck forms are controlled by the current month "
                f"(the game currently resolves form {current})."
            )
        attributes["@form"] = current
        return

    if species == KELDEO_SPECIES_ID:
        if form_id not in (0, 1):
            raise ValueError("Keldeo only has Ordinary and Resolute forms.")
        _set_keldeo_form(attributes, form_id)
        attributes["@form"] = form_id
        return

    attributes["@form"] = form_id

    if species == GIRATINA_SPECIES_ID:
        if form_id not in (0, 1, 2):
            raise ValueError("Giratina only has Altered, Origin, and Primal forms.")
        attributes["@primalBattle"] = form_id == 2
        if form_id == 1:
            attributes["@item"] = GRISEOUS_ORB_ITEM_ID
        elif form_id == 2:
            attributes["@item"] = CRYSTAL_PIECE_ITEM_ID
        else:
            _clear_form_items(attributes, {GRISEOUS_ORB_ITEM_ID, CRYSTAL_PIECE_ITEM_ID})
        return

    if species == SHAYMIN_SPECIES_ID:
        if form_id not in (0, 1):
            raise ValueError("Shaymin only has Land and Sky forms.")
        return

    if species == ARCEUS_SPECIES_ID:
        valid_forms = {0, 9, 19, *ARCEUS_FORM_ITEMS}
        if form_id not in valid_forms:
            raise ValueError("That Arceus form is not defined by the game.")
        attributes["@primalBattle"] = form_id == 19
        controlling_items = {*ARCEUS_FORM_ITEMS.values(), CRYSTAL_PIECE_ITEM_ID}
        if form_id in ARCEUS_FORM_ITEMS:
            attributes["@item"] = ARCEUS_FORM_ITEMS[form_id]
        elif form_id == 19:
            attributes["@item"] = CRYSTAL_PIECE_ITEM_ID
        else:
            _clear_form_items(attributes, controlling_items)
            if form_id == 9:
                # Form 9 has no plate.  It persists only through the handler's
                # Protean (ability slot 2) branch, which deliberately returns nil.
                attributes["@abilityflag"] = 2
        return

    if species == MEWTWO_SPECIES_ID:
        if form_id not in range(6):
            raise ValueError("That Mewtwo form is not defined by the game.")
        is_normal = form_id in (0, 1, 2, 3)
        attributes["@normalMewtwo"] = is_normal
        attributes["@shadowMewtwo"] = form_id in (4, 5)
        attributes["@shadowMegaMewtwo"] = form_id == 5
        attributes["@normalMegaMewtwoX"] = form_id == 2
        attributes["@normalMegaMewtwoY"] = form_id == 3
        if form_id == 1:
            attributes["@item"] = MEWTWO_ARMOR_ITEM_ID
        elif form_id == 2:
            attributes["@item"] = MEWTWONITE_X_ITEM_ID
        elif form_id == 3:
            attributes["@item"] = MEWTWONITE_Y_ITEM_ID
        elif form_id == 0:
            _clear_form_items(attributes, {MEWTWO_ARMOR_ITEM_ID})
        return

    if species == TYRANITAR_SPECIES_ID:
        if form_id not in (0, 1, 2):
            raise ValueError("Tyranitar only has normal, Mega, and Armored forms.")
        attributes["@megaTyranitar"] = form_id == 1
        if form_id == 2:
            attributes["@item"] = TYRANITAR_ARMOR_ITEM_ID
        elif form_id in (0, 1):
            _clear_form_items(attributes, {TYRANITAR_ARMOR_ITEM_ID})
        return

    if species == FLYGON_SPECIES_ID:
        if form_id not in (0, 1, 2):
            raise ValueError("Flygon only has normal, Armored, and Mega forms.")
        attributes["@megaFlygon"] = form_id == 2
        if form_id == 1:
            attributes["@item"] = FLYGON_ARMOR_ITEM_ID
        elif form_id in (0, 2):
            _clear_form_items(attributes, {FLYGON_ARMOR_ITEM_ID})
        return

    item_forms = ITEM_DERIVED_FORMS.get(species)
    if item_forms:
        if form_id not in {0, *item_forms}:
            raise ValueError("That form is not defined by the game's item handler.")
        if form_id:
            attributes["@item"] = item_forms[form_id]
        else:
            _clear_form_items(attributes, set(item_forms.values()))

def apply_pokemon_identity(attributes: dict, nature_index: int, shiny: bool,
                           ability_slot: int, gender: str, changed_fields=None):
    """Apply PID-related choices using Insurgence's native override fields.

    Keeping the PID intact is important: nature, gender, shininess, ability, and
    several cosmetic forms can all derive from it.  Insurgence supplies explicit
    flags for the editable properties, so changing one must not disturb the rest.
    """
    fields = set(changed_fields) if changed_fields is not None else {
        "nature", "shiny", "ability", "gender"
    }
    if "nature" in fields and not 0 <= nature_index < len(NATURES):
        raise ValueError("Invalid Pokemon nature.")
    ability_slot = min(2, max(0, int(ability_slot)))
    species_id = attributes.get("@species", 0)
    choices = gender_choices_for_species(species_id)
    if "gender" in fields and gender not in choices:
        species_name = PKMN_DATA.get(species_id, {}).get("name", f"Species #{species_id}")
        raise ValueError(f"{species_name} cannot be set to {gender.lower()}.")

    if "nature" in fields:
        attributes["@natureflag"] = nature_index
    if "shiny" in fields:
        attributes["@shinyflag"] = bool(shiny)
    if "ability" in fields:
        attributes["@abilityflag"] = ability_slot
    if "gender" in fields:
        attributes["@genderflag"] = GENDERS.index(gender) if len(choices) > 1 else None

# ── shadow Pokemon ────────────────────────────────────────────────────────────
# Mirrors the PokemonShadowPokemon script (makeShadow / pbUpdateShadowMoves /
# pbReplaceMoves / pbPurify).  Shadow state lives entirely in save attributes:
#   @shadow @heartgauge @hypermode @savedev @savedexp @shadowmoves @shadowmovenum
# @shadowmoves is 8 long: [0..3] shadow moves, [4..7] the original move ids.

HEART_GAUGE_SIZE = 3840
SHADOW_RUSH_ID   = 593
# Original moves handed back per heart stage, straight from pbUpdateShadowMoves.
SHADOW_RELEARN_BY_STAGE = [3, 3, 2, 1, 1, 0]

def heart_stage(gauge) -> int:
    """0-5, matching PokeBattle_Pokemon#heartStage (5 = fully shadow)."""
    try:
        gauge = int(gauge or 0)
    except (TypeError, ValueError):
        gauge = 0
    if gauge <= 0:
        return 0
    return math.ceil(min(gauge, HEART_GAUGE_SIZE) / (HEART_GAUGE_SIZE / 5.0))

def pokemon_heart_gauge(attributes: dict) -> int:
    gauge = attributes.get("@heartgauge", 0)
    return gauge if isinstance(gauge, int) else 0

def pokemon_is_shadow(attributes: dict) -> bool:
    """isShadow? — the @shadow flag is the switch, the gauge only has to be >= 0."""
    return bool(attributes.get("@shadow")) and pokemon_heart_gauge(attributes) >= 0

def _shadow_move_ids() -> list:
    """Every Shadow move in the game, for the shadow move chooser.

    Matching is on the Shadow *type*, plus Shadow Sword, which is typed Normal
    but is a Shadow move in every other respect.  Deliberately not a name match:
    Shadow Ball, Claw, Punch, Sneak and Force are ordinary Ghost moves.
    """
    ids = [mid for mid, m in MOVE_DATA.items()
           if m.get("type") == "Shadow" or m.get("name") == "Shadow Sword"]
    return sorted(ids)

SHADOW_MOVE_IDS = _shadow_move_ids()

def set_shadow_move_sets(attributes: dict, shadow_moves: list, originals: list):
    """Rewrite @shadowmoves / @shadowmovenum, then resync the live moves.

    Shadow moves are packed to the front because pbUpdateShadowMoves uses
    @shadowmovenum as an index cutoff when deciding which originals to return.
    """
    packed = [m for m in shadow_moves if m][:4]
    attributes["@shadowmovenum"] = len(packed)
    attributes["@shadowmoves"] = (packed + [0, 0, 0, 0])[:4] + (list(originals) + [0, 0, 0, 0])[:4]
    update_shadow_moves(attributes)

def shadow_move_sets(attributes: dict):
    """(shadow_moves, originals) as two 4-long lists, or None when not stored."""
    stored = attributes.get("@shadowmoves")
    if not isinstance(stored, list) or len(stored) < 8:
        return None
    values = [m if isinstance(m, int) else 0 for m in stored[:8]]
    return values[:4], values[4:8]

def shadow_moves_for_species(species_id: int) -> list:
    """The Shadow moves makeShadow would grant (max 4, Shadow Rush as fallback)."""
    moves = SHADOW_MOVE_DATA.get(species_id) or []
    if not moves:
        return [SHADOW_RUSH_ID]
    return list(moves[:4])

def _move_slots(attributes: dict) -> list:
    moves = attributes.get("@moves")
    if not isinstance(moves, list):
        moves = []
        attributes["@moves"] = moves
    while len(moves) < 4:
        moves.append(RubyObject("PBMove", {"@id": 0, "@pp": 0, "@ppup": 0}))
    return moves

def _write_move_slot(slot, move_id: int):
    if not isinstance(slot, RubyObject):
        return
    slot.attributes["@id"]   = move_id
    slot.attributes["@pp"]   = MOVE_DATA.get(move_id, {}).get("pp", 0) if move_id else 0
    slot.attributes["@ppup"] = 0

def pokemon_move_ids(attributes: dict) -> list:
    ids = []
    for slot in _move_slots(attributes)[:4]:
        mid = slot.attributes.get("@id", 0) if isinstance(slot, RubyObject) else 0
        ids.append(mid if isinstance(mid, int) else 0)
    return ids

def _replace_moves(attributes: dict, wanted: list):
    """pbReplaceMoves: keep the wanted moves, clear anything else out."""
    wanted = (list(wanted) + [0, 0, 0, 0])[:4]
    slots  = _move_slots(attributes)
    for move in wanted:
        current = pokemon_move_ids(attributes)
        if move != 0 and move in current:
            continue  # already known — nothing to do
        for i in range(4):
            if (current[i] == 0 and move != 0) or (current[i] not in wanted):
                _write_move_slot(slots[i], move)
                break

def _compact_moves(attributes: dict):
    """Slide filled move slots to the front, keeping id/PP/PP-Ups together.

    pbReplaceMoves can leave an empty slot in front of a filled one when the move
    it wants is already in a later slot.  The game tolerates that, but it looks
    broken in the summary screen, and a packed list is what pbReplaceMoves would
    produce next time anyway, so tidy it here.
    """
    slots = _move_slots(attributes)
    filled = [(s.attributes.get("@id", 0), s.attributes.get("@pp", 0), s.attributes.get("@ppup", 0))
              for s in slots[:4] if isinstance(s, RubyObject) and s.attributes.get("@id", 0)]
    for i, slot in enumerate(slots[:4]):
        if not isinstance(slot, RubyObject):
            continue
        mid, pp, ppup = filled[i] if i < len(filled) else (0, 0, 0)
        slot.attributes["@id"]   = mid
        slot.attributes["@pp"]   = pp
        slot.attributes["@ppup"] = ppup

def update_shadow_moves(attributes: dict, allmoves: bool = False):
    """pbUpdateShadowMoves — resync @moves with the shadow/original move sets."""
    stored = attributes.get("@shadowmoves")
    if not isinstance(stored, list) or len(stored) < 8:
        return
    if not pokemon_is_shadow(attributes):
        _replace_moves(attributes, stored[4:8])
        _compact_moves(attributes)
        attributes.pop("@shadowmoves", None)
        attributes.pop("@shadowmovenum", None)
        return
    movenum = attributes.get("@shadowmovenum", 0)
    movenum = movenum if isinstance(movenum, int) else 0
    moves   = [m for m in stored[:4] if m]
    stage   = heart_stage(pokemon_heart_gauge(attributes))
    relearning = 3 if allmoves else SHADOW_RELEARN_BY_STAGE[min(stage, 5)]
    relearned  = 0
    for i in range(4):
        if i < movenum:
            continue
        if stored[4 + i] and relearned < relearning:
            moves.append(stored[4 + i])
            relearned += 1
    _replace_moves(attributes, moves)
    _compact_moves(attributes)

def make_shadow(attributes: dict):
    """makeShadow — full heart gauge, shadow moves in, originals stashed away."""
    species_id = attributes.get("@species", 0)
    shadow_moves = shadow_moves_for_species(species_id if isinstance(species_id, int) else 0)
    originals = pokemon_move_ids(attributes)

    attributes["@shadow"]        = True
    attributes["@heartgauge"]    = HEART_GAUGE_SIZE
    attributes["@savedexp"]      = 0
    attributes["@savedev"]       = [0] * 6
    attributes["@hypermode"]     = False
    attributes["@shadowmovenum"] = len(shadow_moves)
    attributes["@shadowmoves"]   = (shadow_moves + [0, 0, 0, 0])[:4] + originals
    update_shadow_moves(attributes)

def purify(attributes: dict) -> dict:
    """pbPurify — drop the shadow flag, give back moves, EVs and stashed EXP.

    Returns what was handed back so the caller can tell the user.  Stats are not
    recalculated here; the editor's stat fields stay under the user's control.
    """
    restored = {"exp": 0, "ev": [0] * 6}
    before = pokemon_move_ids(attributes)
    attributes["@shadow"]     = False
    attributes["@heartgauge"] = 0
    attributes["@hypermode"]  = False
    update_shadow_moves(attributes)

    saved_ev = attributes.get("@savedev")
    if isinstance(saved_ev, list):
        ev = attributes.get("@ev")
        ev = list(ev) if isinstance(ev, list) else [0] * 6
        while len(ev) < 6:
            ev.append(0)
        for i in range(6):
            gain = saved_ev[i] if i < len(saved_ev) and isinstance(saved_ev[i], int) else 0
            if gain:
                ev[i] += gain
                restored["ev"][i] = gain
        attributes["@ev"] = _sanitize_evs(ev)
    attributes.pop("@savedev", None)

    saved_exp = attributes.get("@savedexp")
    if isinstance(saved_exp, int) and saved_exp:
        exp = attributes.get("@exp", 0)
        attributes["@exp"] = (exp if isinstance(exp, int) else 0) + saved_exp
        restored["exp"] = saved_exp
    attributes.pop("@savedexp", None)

    restored["moves"] = [m for m in pokemon_move_ids(attributes) if m and m not in before]
    return restored

def set_heart_gauge(attributes: dict, value: int):
    """adjustHeart's clamping, then resync moves the way pbReadyToPurify does."""
    value = min(HEART_GAUGE_SIZE, max(0, int(value)))
    attributes["@heartgauge"] = value
    if value == 0:
        attributes["@hypermode"] = False
    update_shadow_moves(attributes)

def item_display_name(internet_id: int) -> str:
    return ITEM_NAMES.get(internet_id, f"Unknown (#{internet_id})")

def item_picker_id(source_id: int) -> int:
    """Convert a game's raw item constant to the encoded item-data key."""
    try:
        source_id = int(source_id)
    except (TypeError, ValueError):
        return 0
    return source_id * 2 + 1 if source_id > 0 else 0

def item_source_id(picker_id: int) -> int:
    """Convert an encoded item-data key back to the raw saved item constant."""
    try:
        picker_id = int(picker_id)
    except (TypeError, ValueError):
        return 0
    return (picker_id - 1) // 2 if picker_id > 0 else 0

def bag_add_button_text(quantity) -> str:
    value = str(quantity).strip()
    return f"Add {value}" if value else "Add"

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

        self._app_icon = resource_path("icon.ico")

        # Icon
        try:
            self.iconbitmap(self._app_icon)
        except Exception:
            pass

        self.style = ttk.Style()
        try:
            self.style.theme_use("vista")
        except tk.TclError:
            pass

        self.raw          = None
        self.positions    = []
        self.trainer      = None
        self.bag          = None
        self.bag_idx      = None
        self.player_idx   = None
        self.meta_idx     = None
        self.storage      = None
        self.storage_idx  = None
        self.storage_error = ""
        self.game_system  = None
        self.game_player  = None
        self.global_meta  = None
        self.play_time_frames = None
        self.save_path    = get_latest_save_file() or os.path.join(DEFAULT_SAVE_DIR, "Game.rxdata")
        self.trainer_id   = 0
        self.secret_id    = 0

        self.var_money  = tk.StringVar()
        self.var_bp     = tk.StringVar()
        self.var_sid    = tk.StringVar(value="—")
        self.var_trainer_name = tk.StringVar(value="-")
        self.var_trainer_public_id = tk.StringVar(value="-")
        self.var_trainer_full_id = tk.StringVar(value="-")
        self.var_trainer_type = tk.StringVar(value="-")
        self.var_trainer_language = tk.StringVar(value="-")
        self.var_pokedex_seen = tk.StringVar(value="-")
        self.var_pokedex_owned = tk.StringVar(value="-")
        self.var_shadow_caught = tk.StringVar(value="-")
        self.var_badge_count = tk.StringVar(value="-")
        self.var_party_count = tk.StringVar(value="-")
        self.var_pc_count = tk.StringVar(value="-")
        self.var_bag_item_count = tk.StringVar(value="-")
        self.var_save_count = tk.StringVar(value="-")
        self.var_play_time = tk.StringVar(value="-")
        self.var_step_count = tk.StringVar(value="-")
        self.var_visited_maps = tk.StringVar(value="-")
        self.var_coins = tk.StringVar(value="-")
        self.var_current_box = tk.StringVar(value="-")
        self.var_player_location = tk.StringVar(value="-")
        self.var_player_x = tk.StringVar()
        self.var_player_y = tk.StringVar()
        self.var_respawn = tk.StringVar(value="-")
        self.var_teleport = tk.StringVar(value="-")
        self._loaded_location = None      # (x, y) as loaded, to detect real edits
        # Two different things, and the game uses them for two different things:
        # pbStartOver revives you at @pokecenter*, while the Teleport move sends
        # you to @healingSpot.
        self._respawn_spot = None         # [map_id, x, y] from @pokecenter*
        self._teleport_spot = None        # [map_id, x, y] from @healingSpot
        self._loaded_respawn = None       # copies as loaded, to detect real edits
        self._loaded_teleport = None
        self._location_dirty = False      # only rewrite those streams when edited
        self.var_registered_items = tk.StringVar(value="-")
        self.badge_vars = [tk.BooleanVar() for _ in range(8)]
        self.pkmn_vars  = []
        self.bag_rows   = []
        self.box_vars   = {}
        self._box_tab_meta = {}
        self._box_render_order = []
        self._suspend_box_render = False
        self._scroll_canvases: set = set()
        self._pokemon_sprite_cache = {}
        self._species_choices = tuple(self._species_label(sid) for sid in sorted(PKMN_DATA))
        self._move_choices = tuple(f"{mid} — {data.get('name', 'Unknown')}" for mid, data in sorted(MOVE_DATA.items()))
        self._item_icon_cache = {}
        self._ball_icon_cache = {}
        self._info_buttons = []
        self._theme = "dark"
        self._palette = {}

        self._build_ui()
        self._apply_theme("dark")
        self.bind_all("<MouseWheel>", self._on_mousewheel)
        self.bind_all("<Shift-MouseWheel>", lambda e: self._on_mousewheel(e, horizontal=True))
        if os.path.exists(self.save_path):
            self._do_load(self.save_path)

    _AUTOCOMPLETE_LIMIT = 10

    def _make_search_combo(self, parent, variable, choices, on_select, width=28,
                           current_label=None):
        """Entry with its own autocomplete list: type a species ID or a name.

        Tk's native combobox dropdown takes a grab when it posts, so keystrokes
        after the first would go to its listbox instead of the entry - typing
        "char" left only the "c".  This drives a small borderless Toplevel
        instead, which never takes focus, so typing, arrowing and clicking all
        work together.
        """
        entry = ttk.Entry(parent, textvariable=variable, width=width)
        entry._all_choices = tuple(choices)
        state = {"popup": None, "list": None, "closing": None}

        def matches(query):
            query = query.strip().casefold()
            if not query:
                return []
            starts, contains = [], []
            for choice in entry._all_choices:
                folded = choice.casefold()
                if folded.startswith(query):
                    starts.append(choice)
                elif query in folded:
                    contains.append(choice)
                if len(starts) >= self._AUTOCOMPLETE_LIMIT:
                    break
            return (starts + contains)[:self._AUTOCOMPLETE_LIMIT]

        def close(_event=None):
            if state["closing"] is not None:
                try: entry.after_cancel(state["closing"])
                except tk.TclError: pass
                state["closing"] = None
            if state["popup"] is not None:
                try: state["popup"].destroy()
                except tk.TclError: pass
            state["popup"] = state["list"] = None

        def choose(_event=None):
            listbox = state["list"]
            if listbox is None:
                return
            selection = listbox.curselection()
            if not selection:
                return
            value = listbox.get(selection[0])
            close()
            variable.set(value)
            entry.icursor(tk.END)
            on_select(value)

        def show(found):
            if not found:
                close()
                return
            if state["popup"] is None:
                popup = tk.Toplevel(entry)
                popup.wm_overrideredirect(True)
                popup.wm_attributes("-topmost", True)
                listbox = tk.Listbox(popup, activestyle="dotbox", exportselection=False)
                listbox.pack(fill="both", expand=True)
                listbox.bind("<ButtonRelease-1>", choose)
                listbox.bind("<Motion>", lambda e: (listbox.selection_clear(0, tk.END),
                                                    listbox.selection_set(listbox.nearest(e.y))))
                state["popup"], state["list"] = popup, listbox
            listbox = state["list"]
            listbox.delete(0, tk.END)
            for item in found:
                listbox.insert(tk.END, item)
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(0)
            listbox.configure(height=len(found))
            state["popup"].wm_geometry(
                "%dx%d+%d+%d" % (max(entry.winfo_width(), 180), 18 * len(found) + 4,
                                 entry.winfo_rootx(),
                                 entry.winfo_rooty() + entry.winfo_height()))

        def move(step):
            listbox = state["list"]
            if listbox is None or listbox.size() == 0:
                return "break"
            current = listbox.curselection()
            index = (current[0] if current else 0) + step
            index = max(0, min(listbox.size() - 1, index))
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(index)
            listbox.see(index)
            return "break"

        def on_key(event):
            if event.keysym in ("Up", "Down", "Return", "KP_Enter", "Escape",
                                "Tab", "ISO_Left_Tab", "Left", "Right",
                                "Shift_L", "Shift_R", "Control_L", "Control_R"):
                return
            show(matches(variable.get()))

        def on_return(_event=None):
            if state["list"] is not None:
                choose()
            else:
                revert()
            return "break"

        def revert():
            """Only a pick from the list changes the species; typing never does."""
            if current_label is not None:
                variable.set(current_label())

        def on_focus_out(_event=None):
            # A click on the list pulls focus off the entry first, so give that
            # click a moment to land before tearing the list down.
            def finish():
                state["closing"] = None
                close()
                revert()
            state["closing"] = entry.after(150, finish)

        entry.bind("<KeyRelease>", on_key)
        entry.bind("<Down>", lambda e: move(1))
        entry.bind("<Up>", lambda e: move(-1))
        entry.bind("<Return>", on_return)
        entry.bind("<KP_Enter>", on_return)
        entry.bind("<Escape>", lambda e: (close(), revert()))
        entry.bind("<FocusOut>", on_focus_out)
        entry.bind("<Destroy>", close)
        return entry

    def _current_species_label(self, v) -> str:
        """The label for the species a slot actually holds, for reverting to."""
        try:
            species_id = int(v["species_id"].get() or 0)
        except (KeyError, ValueError):
            return ""
        return self._species_label(species_id) if species_id in PKMN_DATA else ""

    def _species_label(self, species_id: int) -> str:
        return f"{species_id} — {PKMN_DATA.get(species_id, {}).get('name', 'Unknown')}"

    def _species_from_text(self, value) -> int:
        return species_id_from_text(value)

    def _manual_species_changed(self, v):
        if v.get("_syncing"): return
        try: species_id = int(v["species_id"].get())
        except (ValueError, KeyError): return
        if species_id not in PKMN_DATA: return
        if "species_search" in v: v["species_search"].set(self._species_label(species_id))
        self._refresh_form_options(v)
        self._set_ability_value(v)
        self._schedule_recalculate(v, full_heal=True)

    def _select_species(self, v, value):
        species_id = self._species_from_text(value)
        if not species_id:
            return
        v['_syncing'] = True
        try:
            v['species_id'].set(str(species_id))
            v['species_search'].set(self._species_label(species_id))
        finally:
            v['_syncing'] = False
        self._refresh_form_options(v)
        self._set_ability_value(v)
        self._schedule_recalculate(v, full_heal=True)

    def _select_move_text(self, v, index: int, value):
        text = str(value or "").strip()
        match = re.match(r"^(\d+)", text)
        move_id = int(match.group(1)) if match else 0
        if not move_id:
            folded = text.casefold()
            move_id = next((mid for mid, data in MOVE_DATA.items()
                            if data.get("name", "").casefold() == folded), 0)
        if move_id in MOVE_DATA:
            self._update_move_vars(v, index, move_id)
            v[f"move{index}_search"].set(f"{move_id} — {MOVE_DATA[move_id].get('name', 'Unknown')}")

    def _schedule_recalculate(self, v, full_heal=False):
        if v.get('_syncing'):
            return
        v['_pending_full_heal'] = v.get('_pending_full_heal', False) or full_heal
        pending = v.pop('_recalc_after', None)
        if pending:
            try: self.after_cancel(pending)
            except tk.TclError: pass
        v['_recalc_after'] = self.after_idle(lambda vv=v: self._recalculate_stats(vv, vv.pop('_pending_full_heal', False)))

    def _sync_level_from_exp(self, v):
        if v.get('_syncing'): return
        try:
            species_id = int(v['species_id'].get() or 0)
            growth = PKMN_DATA.get(species_id, {}).get('growth', 'medium-fast')
            level = _level_for_exp(growth, int(v['exp'].get() or 0))
        except ValueError:
            return
        v['_syncing'] = True
        try: v['level'].set(str(level))
        finally: v['_syncing'] = False
        self._schedule_recalculate(v)

    def _sync_exp_from_level(self, v):
        if v.get('_syncing'): return
        try:
            species_id = int(v['species_id'].get() or 0)
            level = min(MAX_LEVEL, max(1, int(v['level'].get())))
            growth = PKMN_DATA.get(species_id, {}).get('growth', 'medium-fast')
        except ValueError:
            return
        v['_syncing'] = True
        try:
            v['level'].set(str(level))
            v['exp'].set(str(_exp_for_level(growth, level)))
        finally: v['_syncing'] = False
        self._schedule_recalculate(v, full_heal=True)

    def _recalculate_stats(self, v, full_heal=True):
        v.pop('_recalc_after', None)
        if v.get('_syncing'): return
        try:
            species_id = int(v['species_id'].get())
            level = int(v['level'].get())
            form_id = self._selected_form_id(v)
            nature = nature_index_from_value(v['nature_idx'].get())
            ivs = [int(v['iv_' + s.lower()].get() or 0) for s in STATS]
            evs = [int(v['ev_' + s.lower()].get() or 0) for s in STATS]
            stats = calculate_pokemon_stats(species_id, form_id, level, nature, ivs, evs)
        except (ValueError, KeyError):
            return
        old_max = int(v['totalhp'].get() or 0) if str(v['totalhp'].get() or '').isdigit() else 0
        old_hp = int(v['hp'].get() or 0) if str(v['hp'].get() or '').isdigit() else 0
        v['_syncing'] = True
        try:
            for key, value in zip(('totalhp','attack','defense','spatk','spdef','speed'), stats):
                v[key].set(str(value))
            if full_heal or old_hp >= old_max:
                v['hp'].set(str(stats[0]))
            else:
                v['hp'].set(str(min(stats[0], max(0, old_hp))))
            self._refresh_ev_total(v)
        finally: v['_syncing'] = False

    def _refresh_ev_total(self, v):
        """Update the EV total readout only - never the stats.

        Populating a slot holds "_syncing" so the recalculation traces cannot
        rewrite a Pokemon the user never touched, which also skipped this label
        and left it reading 0 after every load.
        """
        if 'ev_total' not in v:
            return
        try:
            total = sum(max(0, int(v['ev_' + stat.lower()].get() or 0)) for stat in STATS)
        except (KeyError, ValueError):
            return
        v['ev_total'].set(f"Total: {total} / 510" + ('  ⚠ over limit' if total > 510 else ''))

    def _clear_pokemon_editor_vars(self, v):
        # Clearing species_id triggers the form/gender/ability refresh traces,
        # which may update cached entries in this dictionary.  Iterate over a
        # snapshot so those callbacks cannot resize the active iterator.
        for val in list(v.values()):
            if isinstance(val, tk.BooleanVar):
                val.set(False)
            elif isinstance(val, tk.StringVar):
                val.set("")

    def _palette_for(self, mode: str) -> dict:
        if mode == "dark":
            return {
                "bg": "#0f172a",
                "panel": "#172033",
                "field": "#101827",
                "text": "#e5edf8",
                "muted": "#9fb0c7",
                "accent": "#60a5fa",
                "accent2": "#1d4ed8",
                "button": "#1e3a5f",
                "button_active": "#2563a6",
                "danger_button": "#7f1d1d",
                "danger_button_active": "#991b1b",
                "danger_text": "#fecaca",
                "border": "#355172",
                "select": "#1d4ed8",
                "select_text": "#ffffff",
                "error": "#f87171",
                "ok": "#93c5fd",
                "info_fill": "#172c47",
                "info_outline": "#5b7fa8",
                "info_text": "#93c5fd",
            }
        return {
            "bg": "#f0f0f0",
            "panel": "#f7f7f7",
            "field": "#ffffff",
            "text": "#111827",
            "muted": "#666666",
            "accent": "#1266d6",
            "accent2": "#0f5bbd",
            "button": "#f3f4f6",
            "button_active": "#e5e7eb",
            "danger_button": "#fee2e2",
            "danger_button_active": "#fecaca",
            "danger_text": "#991b1b",
            "border": "#8aa9c8",
            "select": "#2b77d1",
            "select_text": "#ffffff",
            "error": "#cc0000",
            "ok": "blue",
            "info_fill": "#f7fbff",
            "info_outline": "#8aa9c8",
            "info_text": "#1266d6",
        }

    def _apply_theme(self, mode: str):
        self._theme = mode
        p = self._palette_for(mode)
        self._palette = p
        try:
            self.style.theme_use("clam" if mode == "dark" else "vista")
        except tk.TclError:
            pass
        self.configure(bg=p["bg"])

        self.style.configure(".", background=p["bg"], foreground=p["text"])
        self.style.configure("TFrame", background=p["bg"])
        self.style.configure("TLabelframe", background=p["bg"], foreground=p["text"])
        self.style.configure("TLabelframe.Label", background=p["bg"], foreground=p["text"])
        self.style.configure("TLabel", background=p["bg"], foreground=p["text"])
        self.style.configure("TButton", background=p["button"], foreground=p["text"])
        self.style.map("TButton", background=[("active", p["button_active"])], foreground=[("active", p["text"])])
        self.style.configure(
            "Danger.TButton",
            background=p["danger_button"],
            foreground=p["danger_text"],
            bordercolor=p["danger_text"],
        )
        self.style.map(
            "Danger.TButton",
            background=[("active", p["danger_button_active"])],
            foreground=[("active", p["danger_text"])],
        )
        # Without explicit state maps, clam keeps its light default for the hover
        # ("active") background and the indicator, which washes out the label text
        # of any checkbutton that has one.
        for widget in ("TCheckbutton", "TRadiobutton"):
            self.style.configure(
                widget,
                background=p["bg"],
                foreground=p["text"],
                indicatorbackground=p["field"],
                indicatorforeground=p["text"],
                focuscolor=p["accent"],
            )
            self.style.map(
                widget,
                background=[("active", p["panel"]), ("disabled", p["bg"])],
                foreground=[("disabled", p["muted"]), ("active", p["text"])],
                indicatorbackground=[
                    ("disabled", p["panel"]),
                    ("selected", p["select"]),
                    ("active", p["field"]),
                    ("!selected", p["field"]),
                ],
                indicatorforeground=[("selected", p["select_text"]), ("!selected", p["text"])],
            )
        self.style.configure("TNotebook", background=p["bg"])
        self.style.configure("TNotebook.Tab", background=p["panel"], foreground=p["text"])
        self.style.map("TNotebook.Tab", background=[("selected", p["field"])], foreground=[("selected", p["text"])])
        self.style.configure("Treeview", background=p["field"], fieldbackground=p["field"], foreground=p["text"])
        self.style.map("Treeview", background=[("selected", p["select"])], foreground=[("selected", p["select_text"])])
        self.style.configure("Treeview.Heading", background=p["panel"], foreground=p["text"])
        self.style.configure("TEntry", fieldbackground=p["field"], foreground=p["text"])
        self.style.configure(
            "TSpinbox",
            fieldbackground=p["field"],
            foreground=p["text"],
            background=p["button"],
            arrowcolor=p["text"],
            bordercolor=p["border"],
            lightcolor=p["border"],
            darkcolor=p["border"],
            insertcolor=p["text"],
            selectbackground=p["select"],
            selectforeground=p["select_text"],
        )
        self.style.map(
            "TSpinbox",
            fieldbackground=[("disabled", p["panel"]), ("!disabled", p["field"])],
            foreground=[("disabled", p["muted"]), ("!disabled", p["text"])],
            background=[("active", p["button_active"]), ("disabled", p["panel"])],
            arrowcolor=[("disabled", p["muted"]), ("!disabled", p["text"])],
            selectbackground=[("!disabled", p["select"])],
            selectforeground=[("!disabled", p["select_text"])],
        )
        self.style.configure(
            "TCombobox",
            fieldbackground=p["field"],
            foreground=p["text"],
            background=p["button"],
            arrowcolor=p["text"],
            bordercolor=p["border"],
            lightcolor=p["border"],
            darkcolor=p["border"],
            insertcolor=p["text"],
            selectbackground=p["select"],
            selectforeground=p["select_text"],
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[
                ("readonly", p["field"]),
                ("disabled", p["panel"]),
                ("!disabled", p["field"]),
            ],
            foreground=[
                ("readonly", p["text"]),
                ("disabled", p["muted"]),
                ("!disabled", p["text"]),
            ],
            background=[
                ("active", p["button_active"]),
                ("readonly", p["button"]),
                ("disabled", p["panel"]),
            ],
            arrowcolor=[
                ("disabled", p["muted"]),
                ("active", p["text"]),
                ("readonly", p["text"]),
            ],
            selectbackground=[("readonly", p["field"]), ("!disabled", p["select"])],
            selectforeground=[("readonly", p["text"]), ("!disabled", p["select_text"])],
        )
        self.option_add("*TCombobox*Listbox.background", p["field"])
        self.option_add("*TCombobox*Listbox.foreground", p["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", p["select"])
        self.option_add("*TCombobox*Listbox.selectForeground", p["select_text"])

        for canvas in list(self._scroll_canvases):
            try:
                canvas.configure(bg=p["bg"])
            except tk.TclError:
                pass
        live_info_buttons = []
        for canvas in self._info_buttons:
            try:
                if canvas.winfo_exists():
                    self._draw_info_button(canvas)
                    live_info_buttons.append(canvas)
            except tk.TclError:
                pass
        self._info_buttons = live_info_buttons
        if hasattr(self, "status"):
            self.status.configure(foreground=p["muted"])

    def _set_theme(self, mode: str):
        self._apply_theme(mode)

    def _center_popup(self, win, size=None):
        win.update_idletasks()
        if size:
            # An explicitly requested geometry wins: winfo_width() is still the
            # content's requested size before the window is mapped, so reading it
            # here would silently discard the caller's chosen dimensions.
            w, h = size
        else:
            w = win.winfo_width()
            h = win.winfo_height()
            if w <= 1:
                w = win.winfo_reqwidth()
            if h <= 1:
                h = win.winfo_reqheight()
        self.update_idletasks()
        x = self.winfo_rootx() + max(0, (self.winfo_width() - w) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - h) // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")

    def _make_popup(self, title: str, geometry=None, resizable=(False, False), modal: bool = True):
        win = tk.Toplevel(self)
        win.title(title)
        if self._palette:
            win.configure(bg=self._palette["bg"])
        try:
            win.iconbitmap(self._app_icon)
        except Exception:
            pass
        win.transient(self)
        requested = None
        if geometry:
            win.geometry(geometry)
            match = re.match(r"^(\d+)x(\d+)", geometry)
            if match:
                requested = (int(match.group(1)), int(match.group(2)))
        if resizable is not None:
            win.resizable(*resizable)
        self._center_popup(win, requested)
        if modal:
            win.grab_set()
        return win

    def _on_mousewheel(self, e, horizontal: bool = False):
        w = self.winfo_containing(e.x_root, e.y_root)
        while w is not None:
            if w in self._scroll_canvases:
                amount = int(-1 * (e.delta / 120))
                if horizontal:
                    w.xview_scroll(amount, "units")
                else:
                    w.yview_scroll(amount, "units")
                return
            w = getattr(w, "master", None)

    def _make_scrollable(self, canvas: tk.Canvas):
        self._scroll_canvases.add(canvas)
        if self._palette:
            try:
                canvas.configure(bg=self._palette["bg"])
            except tk.TclError:
                pass

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
        abilities = []
        seen = set()
        for ability in data.get("abilities", []):
            key = ability.casefold()
            if key not in seen:
                abilities.append(ability)
                seen.add(key)
        hidden = data.get("hidden_ability", "")
        if hidden and hidden.casefold() not in seen:
            abilities.append(f"Hidden: {hidden}")
        return ", ".join(abilities) if abilities else "-"

    def _parse_form_id(self, value, default: int = 0) -> int:
        if isinstance(value, int):
            return value
        text = str(value or "").strip()
        if " - " in text:
            text = text.split(" - ", 1)[0].strip()
        try:
            return int(text)
        except ValueError:
            return default

    def _form_label(self, species_id: int, form_id: int) -> str:
        name = None
        for fid, form_name in FORM_DATA.get(species_id, []):
            if fid == form_id:
                name = form_name
                break
        if not name:
            name = "Default" if form_id == 0 else f"Form {form_id}"
        return f"{form_id} - {name}"

    def _form_choices(self, species_id: int, current_form: int = 0) -> list:
        forms = dict(FORM_DATA.get(species_id, []))
        forms.setdefault(0, "Default")
        if species_id in SEASONAL_FORM_SPECIES:
            seasonal_form = seasonal_pokemon_form()
            name = forms.get(seasonal_form, f"Form {seasonal_form}")
            return [f"{seasonal_form} - {name} (current season)"]
        forms.setdefault(current_form, "Default" if current_form == 0 else f"Form {current_form}")
        return [f"{fid} - {name}" for fid, name in sorted(forms.items())]

    def _set_form_value(self, v: dict, species_id: int, form_id: int):
        form_id = max(0, min(self._parse_form_id(form_id), 99))
        if species_id in SEASONAL_FORM_SPECIES:
            form_id = seasonal_pokemon_form()
        choices = self._form_choices(species_id, form_id)
        combo = v.get("form_combo")
        if combo is not None:
            combo.configure(values=choices)
        v["form"].set(choices[0] if species_id in SEASONAL_FORM_SPECIES
                      else self._form_label(species_id, form_id))

    def _refresh_form_options(self, v: dict):
        try:
            species_id = int(v.get("species_id").get() or 0)
        except (AttributeError, ValueError):
            species_id = 0
        current_form = self._parse_form_id(v.get("form").get() if v.get("form") else 0)
        self._set_form_value(v, species_id, current_form)
        self._set_gender_value(v)
        self._set_ability_value(v)
        if v.get("dex_sprite"):
            self._set_pokemon_dex_vars(v, species_id, current_form)
        self._refresh_form_sprite(v, species_id, current_form)

    def _refresh_form_sprite(self, v: dict, species_id: int, form_id: int):
        """Refresh a compact form sprite, used by lazily rendered PC slots."""
        label = v.get("form_sprite")
        if label is None:
            return
        img = self._load_pokemon_sprite(
            species_id, form_id, max_size=v.get("form_sprite_size", 72)
        )
        label.configure(image=img if img else "", text="" if img else "(no sprite)")
        label.image = img

    def _set_gender_value(self, v: dict, attributes: dict = None):
        gender_var = v.get("gender")
        if gender_var is None:
            return
        try:
            species_id = int(v.get("species_id").get() or 0)
        except (AttributeError, ValueError):
            species_id = 0
        choices = gender_choices_for_species(species_id)
        combo = v.get("gender_combo")
        if combo is not None:
            combo.configure(values=choices)
        value = pokemon_gender(attributes) if attributes is not None else gender_var.get()
        gender_var.set(value if value in choices else choices[0])

    def _set_ability_value(self, v: dict, slot: int = None):
        ability_var = v.get("ability_slot")
        if ability_var is None:
            return
        try:
            species_id = int(v.get("species_id").get() or 0)
        except (AttributeError, ValueError):
            species_id = 0
        choices = ability_choices_for_species(species_id)
        if slot is None:
            slot = ability_slot_from_value(species_id, ability_var.get())

        labels_by_slot = {choice_slot: label for choice_slot, label in choices}
        selected_label = labels_by_slot.get(slot)
        if selected_label is None:
            selected_label = choices[0][1]
        v["_ability_choices"] = {label: choice_slot for choice_slot, label in choices}
        combo = v.get("ability_combo")
        if combo is not None:
            combo.configure(values=[label for _slot, label in choices])
        ability_var.set(selected_label)

    def _selected_ability_slot(self, v: dict) -> int:
        value = v.get("ability_slot").get() if v.get("ability_slot") else ""
        mapped = v.get("_ability_choices", {}).get(value)
        if mapped is not None:
            return mapped
        try:
            species_id = int(v.get("species_id").get() or 0)
        except (AttributeError, ValueError):
            species_id = 0
        return ability_slot_from_value(species_id, value)

    def _selected_form_id(self, v: dict) -> int:
        return max(0, min(self._parse_form_id(v.get("form").get() if v.get("form") else 0), 99))

    def _identity_values(self, v: dict) -> dict:
        return {
            "nature": v["nature_idx"].get(),
            "shiny": bool(v["shiny"].get()),
            "ability": self._selected_ability_slot(v),
            "gender": v["gender"].get(),
        }

    def _remember_identity_values(self, v: dict):
        """Remember exactly what the identity controls showed after load/save."""
        v["_loaded_identity"] = self._identity_values(v)

    def _changed_identity_fields(self, v: dict) -> set:
        """Only explicit UI changes may create native identity override flags."""
        loaded = v.get("_loaded_identity")
        if not isinstance(loaded, dict):
            return {"nature", "shiny", "ability", "gender"}
        current = self._identity_values(v)
        return {field for field, value in current.items() if value != loaded.get(field)}

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

    def _make_pokemon_dex_panel(self, parent, species_id: int, form: int = 0, compact: bool = False,
                                ability_slot_var=None, pkmn=None, slot_vars=None):
        data = PKMN_DATA.get(species_id, {})
        frame = ttk.LabelFrame(parent, text="Pokedex", padding=4)
        sprite = ttk.Label(frame, anchor="center", width=12)
        sprite.grid(row=0, column=0, rowspan=5, sticky="n", padx=(0, 6))
        img = self._load_pokemon_sprite(species_id, form, max_size=72 if compact else 96)
        sprite.configure(image=img if img else "", text="" if img else "(no sprite)")
        sprite.image = img
        if slot_vars is not None:
            slot_vars["form_sprite"] = sprite
            slot_vars["form_sprite_size"] = 72 if compact else 96
        name = data.get("name", f"Species#{species_id}")
        lines = [
            f"#{species_id} {name}",
            self._pokemon_types_text(data),
            (data.get("kind", "") + " Pokemon").strip(),
            self._pokemon_measure_text(data),
        ]
        for row, text in enumerate(lines):
            ttk.Label(frame, text=text or "-", anchor="w", width=28 if compact else 34).grid(row=row, column=1, sticky="w")
        ability_row = len(lines)
        ttk.Label(frame, text=self._pokemon_abilities_text(data), anchor="w", width=28 if compact else 34,
                  wraplength=220 if compact else 280).grid(row=ability_row, column=1, sticky="w")
        info_btn = self._make_info_button(
            frame,
            lambda sid=species_id, av=ability_slot_var, pk=pkmn: self._show_ability_info_for(sid, av, pk)
        )
        info_btn.grid(row=ability_row, column=2, sticky="w", padx=(4, 0))
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

    def _refresh_held_item_display(self, v: dict):
        try:
            source_id = int(v["item"].get() or 0)
        except (KeyError, ValueError):
            source_id = 0
        picker_id = item_picker_id(source_id)
        name_var = v.get("item_name")
        if name_var is not None:
            name_var.set(item_display_name(picker_id) if picker_id else "None")
        label = v.get("item_icon")
        if label is not None:
            icon = self._load_item_icon(picker_id, max_size=v.get("item_icon_size", 28)) if picker_id else None
            label.configure(image=icon if icon else "", text="" if icon else "—")
            label.image = icon

    def _set_held_item_from_picker(self, v: dict, picker_id: int):
        v["item"].set(str(item_source_id(picker_id)))

    def _choose_held_item(self, v: dict):
        try:
            current = item_picker_id(int(v["item"].get() or 0))
        except (KeyError, ValueError):
            current = 0
        self._open_item_picker(
            current_id=current,
            on_select=lambda picker_id, vv=v: self._set_held_item_from_picker(vv, picker_id),
        )

    def _show_held_item_info(self, v: dict):
        try:
            picker_id = item_picker_id(int(v["item"].get() or 0))
        except (KeyError, ValueError):
            picker_id = 0
        if not picker_id:
            messagebox.showinfo("Held Item", "This Pokémon is not holding an item.", parent=self)
            return
        self._show_item_info(picker_id)

    def _make_held_item_control(self, parent, v: dict, row: int,
                                label_width: int = 14, compact: bool = False):
        ttk.Label(parent, text="Held Item:", width=label_width, anchor="e").grid(
            row=row, column=0, sticky="e", pady=1 if compact else 2
        )
        holder = ttk.Frame(parent)
        holder.grid(row=row, column=1, sticky="w", padx=2 if compact else 3,
                    pady=1 if compact else 2)
        v["item_name"] = tk.StringVar(value="None")
        v["item_icon"] = ttk.Label(holder, width=3, anchor="center")
        v["item_icon_size"] = 24 if compact else 28
        v["item_icon"].pack(side="left", padx=(0, 2))
        info = self._make_info_button(holder, lambda vv=v: self._show_held_item_info(vv))
        info.pack(side="left", padx=(0, 2))
        ttk.Label(
            holder, textvariable=v["item_name"], anchor="w",
            width=15 if compact else 19, relief="sunken",
        ).pack(side="left", padx=(0, 3))
        ttk.Button(
            holder, text="Change", width=7,
            command=lambda vv=v: self._choose_held_item(vv),
        ).pack(side="left", padx=(0, 2))
        ttk.Button(
            holder, text="Remove", width=7,
            command=lambda vv=v: vv["item"].set("0"),
        ).pack(side="left")
        v["item"].trace_add("write", lambda *_args, vv=v: self._refresh_held_item_display(vv))
        self._refresh_held_item_display(v)

    def _load_ball_icon(self, ball_id: int, max_size: int = 24):
        """Balls are items, so reuse the item icons already bundled with us."""
        item_id = BALL_ITEM_IDS.get(int(ball_id))
        return self._load_item_icon(item_id, max_size) if item_id else None

    def _make_ball_control(self, parent, v: dict, row: int,
                           label_width: int = 14, compact: bool = False):
        """Named/icon selector backed by the save's unchanged numeric @ballused value."""
        ttk.Label(parent, text="Ball:", width=label_width, anchor="e").grid(
            row=row, column=0, sticky="e", pady=1 if compact else 2
        )
        v["ball_choice"] = tk.StringVar()
        v["ball_icon_size"] = 20 if compact else 24
        # Icon and dropdown share one holder in column 1, the way the held-item
        # control does.  Gridding the combo in column 2 instead pushed it clear of
        # the (much wider) held-item row above, leaving a large gap and forcing an
        # extra column that stretched every row in the group.
        holder = ttk.Frame(parent)
        holder.grid(row=row, column=1, sticky="w", padx=2 if compact else 3,
                    pady=1 if compact else 2)
        v["ball_icon"] = ttk.Label(holder, width=3, anchor="center")
        v["ball_icon"].pack(side="left", padx=(0, 2))
        combo = ttk.Combobox(
            holder, textvariable=v["ball_choice"], values=BALL_CHOICES,
            width=18 if compact else 20, state="readonly",
        )
        combo.pack(side="left")
        def refresh(*_args):
            try:
                ball_id = int(v["ball"].get() or 0)
            except (KeyError, ValueError):
                ball_id = 0
            v["ball_choice"].set(f"{ball_id} — {BALL_NAMES.get(ball_id, 'Unknown ball')}")
            label = v.get("ball_icon")
            if label is not None:
                image = self._load_ball_icon(ball_id, v["ball_icon_size"])
                label.configure(image=image if image else "", text="" if image else "—")
                label.image = image
        def select(_event=None):
            match = re.match(r"^(\d+)", v["ball_choice"].get())
            if match:
                v["ball"].set(match.group(1))
        combo.bind("<<ComboboxSelected>>", select)
        v["ball"].trace_add("write", refresh)
        refresh()
    def _show_item_info(self, item_id: int):
        data = ITEM_DATA.get(item_id, {"name": item_display_name(item_id), "description": ""})
        win = self._make_popup(data.get("name", f"Item #{item_id}"), "460x330")

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

    def _show_ability_info(self, v):
        pkmn = v.get("_pkmn_obj")
        if not isinstance(pkmn, RubyObject):
            messagebox.showinfo("Abilities", "No Pokemon is loaded in this slot.", parent=self)
            return

        attrs = pkmn.attributes
        species_id = attrs.get("@species", 0)
        self._show_ability_info_for(species_id, v.get("ability_slot"), pkmn)

    def _show_ability_info_for(self, species_id: int, ability_slot_var=None, pkmn=None):
        species = PKMN_DATA.get(species_id, {})
        choices = ability_choices_for_species(species_id)

        if not species.get("abilities") and not species.get("hidden_ability"):
            messagebox.showinfo("Abilities", "No ability data is available for this Pokemon.", parent=self)
            return

        if ability_slot_var is not None:
            try:
                slot = ability_slot_from_value(species_id, ability_slot_var.get())
            except tk.TclError:
                slot = 0
        else:
            attrs = pkmn.attributes if isinstance(pkmn, RubyObject) else {}
            pid = attrs.get("@personalID", 0) or 0
            ability_flag = attrs.get("@abilityflag")
            slot = ability_flag if isinstance(ability_flag, int) else pid & 1

        labels_by_slot = {choice_slot: label for choice_slot, label in choices}
        current = labels_by_slot.get(slot, choices[0][1])
        name = species.get("name", f"Species #{species_id}")

        win = self._make_popup(f"{name} Abilities", "500x340")

        outer = ttk.Frame(win, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=f"{name} Abilities", font=("", 12, "bold")).pack(anchor="w")
        if current:
            ttk.Label(outer, text=f"Current: {current}", foreground="gray").pack(anchor="w", pady=(2, 10))
        else:
            ttk.Label(outer, text="Current ability could not be resolved.", foreground="gray").pack(anchor="w", pady=(2, 10))

        rows = []
        for choice_slot, label in choices:
            ability = label.removesuffix(" (Hidden)")
            slot_label = "Hidden" if choice_slot == 2 else "Normal"
            rows.append((slot_label, ability, choice_slot == slot))

        for row, (label, ability, is_current) in enumerate(rows):
            card = ttk.Frame(outer)
            card.pack(fill="x", pady=(0, 10))
            heading = ability + ("  (current)" if is_current else "")
            ttk.Label(card, text=label + ":", width=9, anchor="e").grid(row=0, column=0, sticky="ne", padx=(0, 8))
            ttk.Label(card, text=heading, font=("", 10, "bold")).grid(row=0, column=1, sticky="w")
            desc = ABILITY_BY_NAME.get(ability.lower(), {}).get("description", "") or "No description available."
            ttk.Label(card, text=desc, wraplength=360, justify="left").grid(row=1, column=1, sticky="w")

        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))

    def _draw_info_button(self, canvas):
        p = self._palette or self._palette_for(self._theme)
        canvas.configure(bg=p["bg"], highlightthickness=0, bd=0)
        canvas.delete("all")
        canvas.create_oval(2, 2, 20, 20, outline=p["info_outline"], fill=p["info_fill"])
        canvas.create_text(11, 11, text="i", fill=p["info_text"], font=("", 9, "bold"))

    def _make_info_button(self, parent, command):
        canvas = tk.Canvas(parent, width=22, height=22, highlightthickness=0, bd=0)
        self._draw_info_button(canvas)
        self._info_buttons.append(canvas)
        canvas.bind("<Button-1>", lambda _e: command())
        canvas.bind("<Enter>", lambda _e: canvas.configure(cursor="hand2"))
        return canvas

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        ttk.Button(top, text="Load Save",          command=self._ask_load).pack(side="left", padx=4)
        ttk.Button(top, text="Save (auto-backup)", command=self._do_save).pack(side="left", padx=4)
        ttk.Button(top, text="Pokemon Build Library", command=lambda: self._open_build_dialog(None)).pack(side="left", padx=4)
        self.status = ttk.Label(top, text="No file loaded", foreground="gray")
        self.status.pack(side="left", padx=10)
        ttk.Button(top, text="Dark", width=7, command=lambda: self._set_theme("dark")).pack(side="right", padx=4)
        ttk.Button(top, text="Light", width=7, command=lambda: self._set_theme("light")).pack(side="right", padx=4)

        ttk.Separator(self, orient="horizontal").pack(fill="x")

        nb = ttk.Notebook(self)
        self.nb = nb
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        nb.bind("<<NotebookTabChanged>>", lambda _event: self._on_main_tab_changed())

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
        for col in range(3):
            f.columnconfigure(col, weight=1)

        editor = ttk.LabelFrame(f, text="Trainer", padding=8)
        editor.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        identity = ttk.LabelFrame(f, text="Identity", padding=8)
        identity.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        progress = ttk.LabelFrame(f, text="Progress", padding=8)
        progress.grid(row=0, column=2, sticky="nsew", padx=4, pady=4)
        world = ttk.LabelFrame(f, text="Save / World", padding=8)
        world.grid(row=1, column=0, columnspan=3, sticky="ew", padx=4, pady=4)

        def value_row(parent, label, var, r, editable=False):
            ttk.Label(parent, text=label + ":", width=17, anchor="e").grid(row=r, column=0, sticky="e", pady=3, padx=4)
            if editable:
                ttk.Entry(parent, textvariable=var, width=18).grid(row=r, column=1, sticky="w", pady=3, padx=4)
            else:
                ttk.Label(parent, textvariable=var, width=22, anchor="w").grid(row=r, column=1, sticky="w", pady=3, padx=4)

        row = 0
        value_row(editor, "Money (max 999999)", self.var_money, row, editable=True); row += 1
        value_row(editor, "Battle Points", self.var_bp, row, editable=True); row += 1
        ttk.Label(editor, text="Badges:", width=17, anchor="e").grid(row=row, column=0, sticky="e", pady=3, padx=4)
        bf = ttk.Frame(editor)
        bf.grid(row=row, column=1, sticky="w")
        for i, v in enumerate(self.badge_vars):
            ttk.Checkbutton(bf, variable=v, text=f"#{i+1}").grid(row=i // 4, column=i % 4, padx=2, sticky="w")
        row += 1
        btns = ttk.Frame(editor)
        btns.grid(row=row, column=1, sticky="w", pady=(8, 0))
        ttk.Button(btns, text="All Badges", command=self._all_badges).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="Heal All Party", command=self._heal_all_party).pack(side="left")

        for r, (label, var) in enumerate([
            ("Name", self.var_trainer_name),
            ("Trainer ID", self.var_trainer_public_id),
            ("Secret ID", self.var_sid),
            ("Full ID", self.var_trainer_full_id),
            ("Trainer Type", self.var_trainer_type),
            ("Language", self.var_trainer_language),
        ]):
            value_row(identity, label, var, r)

        for r, (label, var) in enumerate([
            ("Badges", self.var_badge_count),
            ("Party", self.var_party_count),
            ("PC Pokemon", self.var_pc_count),
            ("Pokedex Seen", self.var_pokedex_seen),
            ("Pokedex Owned", self.var_pokedex_owned),
            ("Shadow Caught", self.var_shadow_caught),
            ("Bag Entries", self.var_bag_item_count),
        ]):
            value_row(progress, label, var, r)

        for c in range(4):
            world.columnconfigure(c, weight=1)
        for i, (label, var) in enumerate([
            ("Save Count", self.var_save_count),
            ("Play Time", self.var_play_time),
            ("Steps", self.var_step_count),
            ("Visited Maps", self.var_visited_maps),
            ("Coins", self.var_coins),
            ("Current PC Box", self.var_current_box),
            ("Registered Items", self.var_registered_items),
        ]):
            col = 0 if i < 4 else 2
            r = i if i < 4 else i - 4
            ttk.Label(world, text=label + ":", width=17, anchor="e").grid(row=r, column=col, sticky="e", pady=3, padx=4)
            ttk.Label(world, textvariable=var, width=26, anchor="w").grid(row=r, column=col + 1, sticky="w", pady=3, padx=4)

        # Player position: editable X/Y on the map the save was made on, plus the
        # respawn point, which is the only cross-map relocation that is safe.
        location = ttk.LabelFrame(world, text="Player Position", padding=6)
        location.grid(row=4, column=0, columnspan=4, sticky="ew", padx=4, pady=(8, 2))
        ttk.Label(location, text="Current map:", width=13, anchor="e").grid(row=0, column=0, sticky="e", pady=2)
        ttk.Label(location, textvariable=self.var_player_location, width=28,
                  anchor="w").grid(row=0, column=1, sticky="w", padx=(4, 12))
        ttk.Label(location, text="X:").grid(row=0, column=2, sticky="e")
        ttk.Entry(location, textvariable=self.var_player_x, width=6).grid(row=0, column=3, sticky="w", padx=(2, 8))
        ttk.Label(location, text="Y:").grid(row=0, column=4, sticky="e")
        ttk.Entry(location, textvariable=self.var_player_y, width=6).grid(row=0, column=5, sticky="w", padx=(2, 10))
        ttk.Button(location, text="Show Map",
                   command=self._open_map_viewer).grid(row=0, column=6, sticky="w")

        # Two separate destinations, which the game keeps separate too.
        ttk.Label(location, text="Respawn at:", width=13, anchor="e").grid(row=1, column=0, sticky="e", pady=2)
        ttk.Label(location, textvariable=self.var_respawn, width=28,
                  anchor="w").grid(row=1, column=1, sticky="w", padx=(4, 12))
        ttk.Label(location, text="where you reappear after whiting out",
                  foreground="gray").grid(row=1, column=2, columnspan=5, sticky="w")

        ttk.Label(location, text="Teleport to:", width=13, anchor="e").grid(row=2, column=0, sticky="e", pady=2)
        ttk.Label(location, textvariable=self.var_teleport, width=28,
                  anchor="w").grid(row=2, column=1, sticky="w", padx=(4, 12))
        ttk.Label(location, text="where the Teleport move sends you",
                  foreground="gray").grid(row=2, column=2, columnspan=5, sticky="w")

    def _current_map_id(self):
        gp = self.game_player.attributes if isinstance(self.game_player, RubyObject) else {}
        value = gp.get("@oldMap")
        return int(value) if isinstance(value, int) else None

    # Marker colours.  Four different things used to share one red box, which is
    # why every town you clicked looked like it was where you were standing.
    MARK_SELECT = "#ffd24d"      # the tile you have picked, and nothing else
    MARK_PLAYER = "#ff4d4d"      # where the save says you are
    MARK_PLAYER_DIM = "#8a8f98"  # the other half of the player blink
    MARK_RESPAWN = "#3fb950"     # @pokecenter*, where whiting out puts you
    MARK_TELEPORT = "#7cc4ff"    # @healingSpot, where the Teleport move puts you

    def _place_label(self, canvas, centre_x, top, bottom, text, colour, size, taken, tags):
        """Draw a marker's label clear of the labels already placed.

        Zoomed out, a tile is about ten pixels and a label three times that, so
        stacking by tile is not enough - a label two tiles up still lands on the
        marker below it.  Labels are laid out in priority order and each one is
        pushed further out until it stops overlapping.
        """
        height = size + 4
        half = max(9.0, len(text) * size * 0.34)
        x0, x1 = centre_x - half, centre_x + half

        def free(low, high):
            return not any(x0 < ox1 and ox0 < x1 and low < oy1 and oy0 < high
                           for ox0, ox1, oy0, oy1 in taken)

        for step in range(8):                       # upwards first
            y1 = top - 2 - step * height
            if y1 - height >= 0 and free(y1 - height, y1):
                taken.append((x0, x1, y1 - height, y1))
                return self._stroked_text(canvas, centre_x, y1, text, colour, "s",
                                          ("", int(size), "bold"), tags)
        for step in range(8):                       # then below, if that is full
            y0 = bottom + 2 + step * height
            if free(y0, y0 + height):
                taken.append((x0, x1, y0, y0 + height))
                return self._stroked_text(canvas, centre_x, y0, text, colour, "n",
                                          ("", int(size), "bold"), tags)
        return None

    @staticmethod
    def _stroked_text(canvas, x, y, text, colour, anchor, font, tags):
        """Canvas text with a dark outline, so it reads over any map.

        The outline copies deliberately do not carry the marker's own tag: the
        blink recolours everything tagged for the player, and eight red copies
        of the name one pixel apart is a red smear, not a label.
        """
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            canvas.create_text(x + dx, y + dy, text=text, fill="#0b0b0b",
                               anchor=anchor, font=font, tags=("mark",))
        return canvas.create_text(x, y, text=text, fill=colour, anchor=anchor,
                                  font=font, tags=tags)

    @staticmethod
    def _arrow_points(x0, y0, size, direction):
        """A triangle filling one tile, pointing the way you walk through it."""
        pad = max(1.0, size * 0.15)
        mid_x, mid_y = x0 + size / 2, y0 + size / 2
        if direction == "down":
            return [mid_x, y0 + size - pad, x0 + pad, y0 + pad, x0 + size - pad, y0 + pad]
        if direction == "left":
            return [x0 + pad, mid_y, x0 + size - pad, y0 + pad, x0 + size - pad, y0 + size - pad]
        if direction == "right":
            return [x0 + size - pad, mid_y, x0 + pad, y0 + pad, x0 + pad, y0 + size - pad]
        return [mid_x, y0 + pad, x0 + pad, y0 + size - pad, x0 + size - pad, y0 + size - pad]

    def _open_map_viewer(self):
        if not isinstance(self.game_player, RubyObject):
            messagebox.showerror("No save loaded", "Load a save file first.", parent=self)
            return

        current_map = self._current_map_id()
        player_name = (self.var_trainer_name.get() or "Player").strip()
        win = self._make_popup("Map Viewer", "1320x820", resizable=(True, True))
        # Maps are large and the point of opening one is usually to see where a
        # tile sits in the whole place, so start zoomed out.
        state = {"map_id": current_map, "zoom": 1 / 3, "tile": None, "image": None,
                 "offset": (0, 0), "region_points": {}, "region_index": 0,
                 # False so the first tick turns the player marker red, not grey.
                 "blink": False, "blink_job": None}

        def player_tile():
            try:
                return (int(self.var_player_x.get()), int(self.var_player_y.get()))
            except (TypeError, ValueError):
                return None

        def marks():
            """The three save-backed points, in draw order."""
            found = []
            if current_map is not None and player_tile() is not None:
                found.append(("player", self.MARK_PLAYER, player_name,
                              current_map, player_tile()))
            if self._respawn_spot:
                found.append(("respawn", self.MARK_RESPAWN, "Respawn",
                              int(self._respawn_spot[0]),
                              (int(self._respawn_spot[1]), int(self._respawn_spot[2]))))
            if self._teleport_spot:
                found.append(("teleport", self.MARK_TELEPORT, "Teleport",
                              int(self._teleport_spot[0]),
                              (int(self._teleport_spot[1]), int(self._teleport_spot[2]))))
            return found

        body = ttk.Frame(win, padding=8); body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1); body.rowconfigure(0, weight=1)

        picker = ttk.Notebook(body, width=500)
        picker.grid(row=0, column=0, sticky="nsw", padx=(0, 8))

        # ── region tab: the game's own town map, 16px cells ──────────────────
        region_tab = ttk.Frame(picker); picker.add(region_tab, text=" Region ")
        region_names = [r["name"] for r in TOWN_MAP_REGIONS] or ["(no town map data)"]
        region_var = tk.StringVar(value=region_names[0])
        ttk.Combobox(region_tab, textvariable=region_var, values=region_names, width=24,
                     state="readonly").pack(anchor="w", pady=(6, 4))
        region_canvas = tk.Canvas(region_tab, width=480, height=320, highlightthickness=0)
        region_canvas.pack(fill="both", expand=True)
        region_hint = ttk.Label(region_tab, foreground="gray", wraplength=470, justify="left",
                                text="Click a marked square. Only places the game lists on "
                                     "its town map appear here - use All Maps for the rest.")
        region_hint.pack(anchor="w", pady=(4, 6))

        # ── list tab: every map, searchable ──────────────────────────────────
        list_tab = ttk.Frame(picker); picker.add(list_tab, text=" All Maps ")
        search_var = tk.StringVar()
        show_unused = tk.BooleanVar(value=False)
        search_row = ttk.Frame(list_tab); search_row.pack(fill="x", pady=(6, 4))
        ttk.Label(search_row, text="Search:").pack(side="left")
        ttk.Entry(search_row, textvariable=search_var, width=22).pack(side="left", padx=4)
        ttk.Checkbutton(list_tab, text="Show unused maps", variable=show_unused,
                        takefocus=False,
                        command=lambda: refresh_list()).pack(anchor="w", pady=(0, 4))
        list_holder = ttk.Frame(list_tab); list_holder.pack(fill="both", expand=True)
        maps_tree = ttk.Treeview(list_holder, columns=("id", "name"), show="headings",
                                 selectmode="browse", height=20)
        maps_tree.heading("id", text="ID"); maps_tree.heading("name", text="Name")
        maps_tree.column("id", width=52, anchor="center", stretch=False)
        maps_tree.column("name", width=210, anchor="w", stretch=True)
        maps_tree.tag_configure("unused", foreground="gray")
        list_scroll = ttk.Scrollbar(list_holder, orient="vertical", command=maps_tree.yview)
        maps_tree.configure(yscrollcommand=list_scroll.set)
        maps_tree.pack(side="left", fill="both", expand=True); list_scroll.pack(side="right", fill="y")

        # ── map view ────────────────────────────────────────────────────────
        view = ttk.Frame(body); view.grid(row=0, column=1, sticky="nsew")
        view.rowconfigure(1, weight=1); view.columnconfigure(0, weight=1)

        header = ttk.Frame(view); header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        title_var = tk.StringVar(value="-")
        ttk.Label(header, textvariable=title_var, font=("", 11, "bold")).pack(side="left")
        ttk.Button(header, text="-", width=3,
                   command=lambda: set_zoom(state["zoom"] / 1.5)).pack(side="right")
        zoom_var = tk.StringVar(value="33%")
        ttk.Label(header, textvariable=zoom_var, width=6,
                  anchor="center").pack(side="right", padx=2)
        ttk.Button(header, text="+", width=3,
                   command=lambda: set_zoom(state["zoom"] * 1.5)).pack(side="right")

        canvas_holder = ttk.Frame(view); canvas_holder.grid(row=1, column=0, sticky="nsew")
        canvas_holder.rowconfigure(0, weight=1); canvas_holder.columnconfigure(0, weight=1)
        canvas = tk.Canvas(canvas_holder, background="#101010", highlightthickness=0)
        vbar = ttk.Scrollbar(canvas_holder, orient="vertical", command=canvas.yview)
        hbar = ttk.Scrollbar(canvas_holder, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        canvas.grid(row=0, column=0, sticky="nsew"); vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")

        footer = ttk.Frame(view); footer.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        status_var = tk.StringVar(value="Click a tile to choose a position.")
        ttk.Label(footer, textvariable=status_var, foreground="gray").pack(side="left")

        # Classic tk buttons, not ttk: in light mode the app uses the "vista"
        # ttk theme, whose native button element throws away any background you
        # give it, and matching each button to its marker is the whole point.
        def action_button(text, colour, command):
            button = tk.Button(footer, text=text, command=command, state="disabled",
                               bg="#4a4f57", activebackground=colour, fg="#101010",
                               activeforeground="#101010", relief="raised", bd=1,
                               disabledforeground="#8a8f98", padx=8, takefocus=0)
            button.pack(side="right", padx=3)
            button.marker_colour = colour
            return button

        def set_action(button, enabled):
            """A tk button keeps its colour when disabled, so change it here."""
            button.configure(state="normal" if enabled else "disabled",
                             bg=button.marker_colour if enabled else "#4a4f57")

        ttk.Button(footer, text="Close", command=win.destroy).pack(side="right", padx=(10, 0))
        teleport_button = action_button("Set Teleport Point", self.MARK_TELEPORT,
                                        lambda: apply_spot("teleport"))
        respawn_button = action_button("Set Respawn Point", self.MARK_RESPAWN,
                                       lambda: apply_spot("respawn"))
        move_button = action_button("Move Player Here", self.MARK_SELECT,
                                    lambda: apply_spot("player"))

        # ── region tab behaviour ────────────────────────────────────────────
        def refresh_region(*_args):
            region_canvas.delete("all")
            region = next((r for r in TOWN_MAP_REGIONS if r["name"] == region_var.get()), None)
            if region is None:
                return
            path = resource_path(os.path.join("game_resources", "Graphics",
                                              "Pictures", region["image"]))
            image = None
            if os.path.exists(path):
                try:
                    image = tk.PhotoImage(file=path)
                except tk.TclError:
                    image = None
            if image is not None:
                region_canvas.image = image
                region_canvas.create_image(0, 0, image=image, anchor="nw")
                region_canvas.configure(scrollregion=(0, 0, image.width(), image.height()))
            state["region_index"] = TOWN_MAP_REGIONS.index(region)
            state["region_points"] = {}
            # Outline every square that any map claims, not just the named
            # landmarks - that is what makes routes reachable.
            for cell in sorted(k for k in MAP_POSITIONS if k[0] == state["region_index"]):
                cx, cy = cell[1], cell[2]
                x0, y0 = cx * TOWNMAP_CELL, cy * TOWNMAP_CELL
                region_canvas.create_rectangle(
                    x0, y0, x0 + TOWNMAP_CELL, y0 + TOWNMAP_CELL,
                    outline="#3fb950", width=1)
            for point in region["points"]:
                cx, cy = point["cell"]
                x0, y0 = cx * TOWNMAP_CELL, cy * TOWNMAP_CELL
                if point["map_id"] is not None:
                    # Landmarks get a heavier outline and carry a landing tile.
                    region_canvas.create_rectangle(
                        x0, y0, x0 + TOWNMAP_CELL, y0 + TOWNMAP_CELL,
                        outline="#7cc4ff", width=2)
                    state["region_points"][(cx, cy)] = point
            draw_region_marks()

        def draw_region_marks():
            """Player, respawn and teleport on the town map.

            A map with no square of its own resolves to its parent's, and that
            is drawn as an arrow instead of a box: you are inside something on
            that square, not standing on it.  The arrow opens the map you are
            really in.
            """
            region_canvas.delete("mark")
            placed = []
            for index, (kind, colour, label, map_id, _tile) in enumerate(marks()):
                cell = town_cell_for_map(map_id)
                if cell is None or cell[0] != state["region_index"]:
                    continue
                placed.append((index, kind, colour, label, map_id, cell[1], cell[2], cell[4]))

            # All three points routinely land on one 16px square - a Pokemon
            # Center is the respawn, the town outside it the teleport - so the
            # labels stack and the player is drawn last, on top of the rest.
            slots, depth_of_cell = {}, {}
            for index, _kind, _colour, _label, _map_id, cx, cy, _depth in placed:
                slots[index] = depth_of_cell.get((cx, cy), 0)
                depth_of_cell[(cx, cy)] = slots[index] + 1
            # Shapes back to front, so the player ends up innermost and on top
            # while the markers it sits on still show as a ring around it.
            for index, kind, colour, label, map_id, cx, cy, depth in reversed(placed):
                slot = slots[index]
                inset = (depth_of_cell[(cx, cy)] - 1 - slot) * 2
                size = TOWNMAP_CELL - inset * 2
                x0, y0 = cx * TOWNMAP_CELL + inset, cy * TOWNMAP_CELL + inset
                tags = ("mark", f"mark_{kind}")
                if depth > 0:
                    # Only the topmost marker gets a dark rim: on a nested one it
                    # would swallow the couple of pixels the marker underneath
                    # has to show itself with.
                    item = region_canvas.create_polygon(
                        self._arrow_points(x0, y0, size, "up"), fill=colour,
                        outline="#101010" if slot == 0 else "",
                        width=1 if slot == 0 else 0, tags=tags)
                    region_canvas.tag_bind(item, "<Button-1>",
                                           lambda _e, m=map_id: open_marked_map(m))
                    region_canvas.tag_bind(item, "<Enter>",
                                           lambda _e: region_canvas.configure(cursor="hand2"))
                else:
                    region_canvas.create_rectangle(
                        x0 + 1, y0 + 1, x0 + size - 1, y0 + size - 1,
                        outline=colour, width=2, tags=tags)
            # Labels in priority order, so the player's name gets the spot
            # nearest its marker and the rest stack outwards from there.
            taken = []
            for _index, kind, colour, label, _map_id, cx, cy, _depth in placed:
                top = cy * TOWNMAP_CELL
                self._place_label(region_canvas, cx * TOWNMAP_CELL + TOWNMAP_CELL / 2,
                                  top, top + TOWNMAP_CELL, label, colour, 7, taken,
                                  ("mark", f"mark_{kind}"))

        def open_marked_map(map_id):
            """Follow a marker's arrow into the map it stands for."""
            show_map(map_id)
            status_var.set(f"Opened {map_display_name(map_id)}")
            return "break"

        def region_cell(event):
            return (int(region_canvas.canvasx(event.x) // TOWNMAP_CELL),
                    int(region_canvas.canvasy(event.y) // TOWNMAP_CELL))

        def cell_maps(cell):
            """Maps reachable from a town-map square, landmark first."""
            found = maps_at_town_cell(state.get("region_index", 0), cell[0], cell[1])
            point = state.get("region_points", {}).get(cell)
            if point and point["map_id"] is not None:
                found = [point["map_id"]] + [m for m in found if m != point["map_id"]]
            return found, point

        def on_region_motion(event):
            cell = region_cell(event)
            region_canvas.delete("hover")
            x0, y0 = cell[0] * TOWNMAP_CELL, cell[1] * TOWNMAP_CELL
            found, point = cell_maps(cell)
            region_canvas.create_rectangle(
                x0, y0, x0 + TOWNMAP_CELL, y0 + TOWNMAP_CELL,
                outline="#ffd24d" if found else "#8899aa", width=2, tags="hover")
            if region_canvas.find_withtag("mark"):
                region_canvas.tag_lower("hover", "mark")
            region_canvas.configure(cursor="hand2" if found else "")
            if found:
                label = point["name"] if point else map_display_name(found[0])
                if point and point["subtitle"]:
                    label += f" - {point['subtitle']}"
                extra = f"   ({len(found)} maps)" if len(found) > 1 else ""
                region_hint.configure(text=f"{label}{extra}")
            else:
                region_hint.configure(text="Nothing here. Use All Maps for anywhere "
                                           "the town map does not cover.")

        def on_region_leave(_event=None):
            region_canvas.delete("hover")
            region_canvas.configure(cursor="")

        def on_region_click(event):
            cell = region_cell(event)
            found, point = cell_maps(cell)
            if not found:
                return
            if len(found) == 1:
                open_cell_map(found[0], point)
                return
            menu = tk.Menu(win, tearoff=0)
            for map_id in found:
                menu.add_command(label=map_display_name(map_id),
                                 command=lambda m=map_id, p=point: open_cell_map(m, p))
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        def open_cell_map(map_id, point=None):
            show_map(map_id)
            if point and point["map_id"] == map_id and point["x"] is not None:
                select_tile(point["x"], point["y"])
            status_var.set(point["name"] if point else map_display_name(map_id))

        # ── list tab behaviour ──────────────────────────────────────────────
        def refresh_list(*_args):
            query = search_var.get().strip().casefold()
            include_unused = show_unused.get()
            maps_tree.delete(*maps_tree.get_children())
            for map_id in sorted(MAP_NAMES):
                unused = map_id in UNUSED_MAPS
                if unused and not include_unused:
                    continue
                name = MAP_NAMES[map_id]
                if query and query not in name.casefold() and query != str(map_id):
                    continue
                maps_tree.insert("", "end", iid=str(map_id),
                                 values=(map_id, name + ("   (unused)" if unused else "")),
                                 tags=("unused",) if unused else ())

        def on_list_select(_event=None):
            selection = maps_tree.selection()
            if selection:
                show_map(int(selection[0]))

        # ── map view behaviour ──────────────────────────────────────────────
        def zoom_steps(factor):
            """PhotoImage only scales by whole numbers, so zoom snaps to ratios."""
            if factor < 1:
                return 1, max(1, int(round(1 / factor)))
            return max(1, int(round(factor))), 1

        def set_zoom(value):
            state["zoom"] = max(0.2, min(4.0, value))
            up, down = zoom_steps(state["zoom"])
            zoom_var.set(f"{int(round(100 * up / down))}%")
            draw_map()

        def show_map(map_id):
            state["map_id"] = int(map_id)
            state["tile"] = None
            state["offset"] = map_image_offset(map_id)
            title_var.set(map_display_name(map_id)
                          + ("   (current map)" if map_id == current_map else ""))
            for button in (move_button, respawn_button, teleport_button):
                set_action(button, False)
            draw_map()

        def draw_map():
            canvas.delete("all")
            state["image"] = None
            path = map_image_path(state["map_id"])
            if path is None:
                reason = map_skip_reason(state["map_id"])
                canvas.create_text(
                    20, 20, anchor="nw", fill="#cccccc", width=560,
                    text=reason or ("No rendered image for this map.\n\n"
                                    "Run  python tools/render_maps.py  to generate the "
                                    "map images (needs game_resources/ and Pillow)."))
                return
            try:
                image = tk.PhotoImage(file=path)
            except tk.TclError:
                canvas.create_text(20, 20, anchor="nw", fill="#cccccc",
                                   text="That map image could not be loaded.")
                return
            up, down = zoom_steps(state["zoom"])
            if up > 1:
                image = image.zoom(up)
            if down > 1:
                image = image.subsample(down)
            state["image"] = image
            canvas.image = image
            canvas.create_image(0, 0, image=image, anchor="nw")
            canvas.configure(scrollregion=(0, 0, image.width(), image.height()))
            draw_map_marks()
            if state["tile"]:
                mark_tile(*state["tile"])

        def tile_pixels():
            """On-screen size of one 32px tile at the current zoom."""
            up, down = zoom_steps(state["zoom"])
            return 32 * up / down

        def draw_map_marks():
            """Player, respawn and teleport on the map being viewed.

            On the map itself they are boxes.  On a map that merely *contains*
            the marked one they become an arrow on the door that leads there,
            pointing the way you would walk through it, and clicking it follows
            the door.
            """
            canvas.delete("mark")
            size = tile_pixels()
            ox, oy = state["offset"]
            placed = []
            for kind, colour, label, map_id, tile in marks():
                spots = ([(tile[0], tile[1], None)] if map_id == state["map_id"]
                         else doors_to(state["map_id"], map_id))
                for tx, ty, direction in spots:
                    placed.append((len(placed), kind, colour, label, map_id, tx, ty, direction))

            slots, on_tile = {}, {}
            for index, _kind, _colour, _label, _map_id, tx, ty, _direction in placed:
                slots[index] = on_tile.get((tx, ty), 0)
                on_tile[(tx, ty)] = slots[index] + 1
            # Drawn back to front, so the blinking player marker is never buried
            # under the respawn box when they share a tile.
            for index, kind, colour, label, map_id, tx, ty, direction in reversed(placed):
                slot = slots[index]
                inset = (on_tile[(tx, ty)] - 1 - slot) * max(2.0, size * 0.12)
                left, top = (tx - ox) * size, (ty - oy) * size
                x0, y0, box = left + inset, top + inset, size - inset * 2
                tags = ("mark", f"mark_{kind}")
                if direction is None:
                    canvas.create_rectangle(x0, y0, x0 + box, y0 + box,
                                            outline=colour, width=3, tags=tags)
                else:
                    item = canvas.create_polygon(
                        self._arrow_points(x0, y0, box, direction), fill=colour,
                        outline="#101010" if slot == 0 else "",
                        width=1 if slot == 0 else 0, tags=tags)
                    canvas.tag_bind(item, "<Button-1>",
                                    lambda _e, m=map_id: open_marked_map(m))
                    canvas.tag_bind(item, "<Enter>",
                                    lambda _e: canvas.configure(cursor="hand2"))
                    canvas.tag_bind(item, "<Leave>",
                                    lambda _e: canvas.configure(cursor=""))
            taken = []
            for _index, kind, colour, label, _map_id, tx, ty, _direction in placed:
                left, top = (tx - ox) * size, (ty - oy) * size
                self._place_label(canvas, left + size / 2, top, top + size,
                                  label, colour, 8, taken, ("mark", f"mark_{kind}"))

        def blink():
            """Only the player marker blinks; it is the one you are looking for."""
            state["blink"] = not state["blink"]
            colour = self.MARK_PLAYER if state["blink"] else self.MARK_PLAYER_DIM
            for widget in (canvas, region_canvas):
                for item in widget.find_withtag("mark_player"):
                    kind = widget.type(item)
                    if kind == "polygon":
                        widget.itemconfigure(item, fill=colour)
                    elif kind == "text":
                        widget.itemconfigure(item, fill=colour)
                    else:
                        widget.itemconfigure(item, outline=colour)
            state["blink_job"] = win.after(600, blink)

        def mark_tile(tx, ty):
            """tx/ty are map tile coordinates; the image may start part-way in."""
            size = tile_pixels()
            ox, oy = state["offset"]
            tx, ty = tx - ox, ty - oy
            x0, y0 = tx * size, ty * size
            colour = self.MARK_SELECT
            canvas.create_rectangle(x0, y0, x0 + size, y0 + size,
                                    outline=colour, width=3, tags="marker")
            canvas.create_line(x0, y0, x0 + size, y0 + size, fill=colour, tags="marker")
            canvas.create_line(x0, y0 + size, x0 + size, y0, fill=colour, tags="marker")

        def select_tile(tx, ty):
            state["tile"] = (int(tx), int(ty))
            canvas.delete("marker")
            mark_tile(int(tx), int(ty))
            set_action(move_button, state["map_id"] == current_map)
            set_action(respawn_button, True)
            set_action(teleport_button, True)
            status_var.set(f"Selected tile  X {int(tx)}  Y {int(ty)}")

        def on_map_motion(event):
            if state["image"] is None:
                return
            size = tile_pixels()
            ox, oy = state["offset"]
            col = int(canvas.canvasx(event.x) // size)
            row = int(canvas.canvasy(event.y) // size)
            canvas.delete("hover")
            canvas.create_rectangle(col * size, row * size,
                                    (col + 1) * size, (row + 1) * size,
                                    outline="#ffd24d", width=2, tags="hover")
            status_var.set(f"X {col + ox}  Y {row + oy}"
                           + (f"   (selected X {state['tile'][0]} Y {state['tile'][1]})"
                              if state["tile"] else ""))

        def on_map_leave(_event=None):
            canvas.delete("hover")

        def on_canvas_click(event):
            if state["image"] is None:
                return
            size = tile_pixels()
            ox, oy = state["offset"]
            select_tile(int(canvas.canvasx(event.x) // size) + ox,
                        int(canvas.canvasy(event.y) // size) + oy)

        def apply_spot(kind):
            """Each button writes its own field; the dialog stays open."""
            if not state["tile"]:
                return
            tx, ty = state["tile"]
            map_id = int(state["map_id"])
            if kind == "player":
                if map_id != current_map:
                    return
                self.var_player_x.set(str(tx)); self.var_player_y.set(str(ty))
                self.status.config(
                    text=f"Player position set to X {tx} Y {ty}. Click Save to write.",
                    foreground="blue")
            elif kind == "respawn":
                self._respawn_spot = [map_id, tx, ty]
                self.var_respawn.set(self._spot_text(self._respawn_spot))
                self.status.config(
                    text=f"Respawn point set to {self._spot_text(self._respawn_spot)}. "
                         "Click Save to write.", foreground="blue")
            else:
                self._teleport_spot = [map_id, tx, ty]
                self.var_teleport.set(self._spot_text(self._teleport_spot))
                self.status.config(
                    text=f"Teleport point set to {self._spot_text(self._teleport_spot)}. "
                         "Click Save to write.", foreground="blue")
            status_var.set(f"{kind.capitalize()} set to X {tx} Y {ty} on "
                           f"{map_display_name(map_id)}.")
            draw_map_marks()
            draw_region_marks()

        def on_destroy(event):
            if event.widget is win and state["blink_job"] is not None:
                try:
                    win.after_cancel(state["blink_job"])
                except tk.TclError:
                    pass
                state["blink_job"] = None

        canvas.bind("<Button-1>", on_canvas_click)
        canvas.bind("<Motion>", on_map_motion)
        canvas.bind("<Leave>", on_map_leave)
        region_canvas.bind("<Button-1>", on_region_click)
        region_canvas.bind("<Motion>", on_region_motion)
        region_canvas.bind("<Leave>", on_region_leave)
        maps_tree.bind("<<TreeviewSelect>>", on_list_select)
        region_var.trace_add("write", refresh_region)
        search_var.trace_add("write", refresh_list)
        win.bind("<Destroy>", on_destroy)
        self._make_scrollable(canvas)

        set_zoom(state["zoom"])
        refresh_region(); refresh_list()
        if current_map is not None:
            show_map(current_map)
            tile = player_tile()
            if tile is not None:
                select_tile(*tile)
        blink()

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

    def _count_truthy(self, values) -> int:
        return sum(1 for value in values if value is True) if isinstance(values, list) else 0

    def _format_count(self, count: int, total: int = 0) -> str:
        return f"{count:,} / {total:,}" if total else f"{count:,}"

    def _format_play_time(self, frames) -> str:
        if not isinstance(frames, int) or frames < 0:
            return "-"
        seconds = frames // 60
        hours, rem = divmod(seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        return f"{hours:,}:{minutes:02d}:{seconds:02d}"

    def _party_count(self) -> int:
        if not self.trainer:
            return 0
        party = self.trainer.attributes.get("@party", [])
        return sum(1 for pkmn in party if isinstance(pkmn, RubyObject)) if isinstance(party, list) else 0

    def _pc_pokemon_count(self) -> int:
        if not isinstance(self.storage, RubyObject):
            return 0
        boxes = self.storage.attributes.get("@boxes", [])
        if not isinstance(boxes, list):
            return 0
        count = 0
        for box in boxes:
            if not isinstance(box, RubyObject):
                continue
            pokemon = box.attributes.get("@pokemon", [])
            if isinstance(pokemon, list):
                count += sum(1 for pkmn in pokemon if isinstance(pkmn, RubyObject))
        return count

    def _bag_entry_count(self) -> int:
        if not isinstance(self.bag, RubyObject):
            return 0
        pockets = self.bag.attributes.get("@pockets", [])
        if not isinstance(pockets, list):
            return 0
        count = 0
        for pocket in pockets:
            if isinstance(pocket, list):
                count += len(pocket)
        return count

    def _registered_items_text(self) -> str:
        if not isinstance(self.bag, RubyObject):
            return "-"
        ids = []
        for key in ("@registeredItem", "@registeredItem2", "@registeredItem3", "@registeredItem4", "@registeredItem5"):
            item_id = self.bag.attributes.get(key, 0)
            if isinstance(item_id, int) and item_id:
                encoded_id = item_id * 2 + 1
                ids.append(item_display_name(encoded_id))
        return ", ".join(ids) if ids else "-"

    # ── Party tab ────────────────────────────────────────────────────────────

    def _build_party_tab(self):
        self.party_nb = ttk.Notebook(self.tab_party)
        self.party_nb.pack(fill="both", expand=True)
        self.pkmn_vars = []
        for slot in range(6):
            frame = ttk.Frame(self.party_nb)
            self.party_nb.add(frame, text=f" Slot {slot+1} ")
            frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1)
            canvas = tk.Canvas(frame, highlightthickness=0)
            yscroll = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
            xscroll = ttk.Scrollbar(frame, orient="horizontal", command=canvas.xview)
            canvas.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
            canvas.grid(row=0, column=0, sticky="nsew")
            yscroll.grid(row=0, column=1, sticky="ns")
            xscroll.grid(row=1, column=0, sticky="ew")
            inner = ttk.Frame(canvas, padding=8)
            window = canvas.create_window((0, 0), window=inner, anchor="nw")
            inner.bind("<Configure>", lambda _e, c=canvas: c.configure(scrollregion=c.bbox("all")))
            canvas.bind("<Configure>", lambda e, c=canvas, w=window, f=inner:
                        c.itemconfigure(w, width=max(e.width, f.winfo_reqwidth())))
            self._make_scrollable(canvas)
            self.pkmn_vars.append(self._build_pkmn_slot(inner, slot))

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
            ("speed","Speed"),("level","Level (1–120)"),("exp","Experience"),
        ]):
            v[key] = tk.StringVar()
            ttk.Label(lf, text=lbl+":", width=14, anchor="e").grid(row=i, column=0, sticky="e", pady=2)
            if key == "species_id":
                species_choices = self._species_choices
                v["species_search"] = tk.StringVar()
                # The raw ID is never shown: it only changes when a species is
                # picked from the list, and the field reverts otherwise.
                combo = self._make_search_combo(
                    lf, v["species_search"], species_choices,
                    lambda value, vv=v: self._select_species(vv, value), 26,
                    current_label=lambda vv=v: self._current_species_label(vv))
                combo.grid(row=i, column=1, sticky="ew", pady=2, padx=3)
            elif key == "form":
                v["form_combo"] = ttk.Combobox(
                    lf, textvariable=v[key], values=["0 - Default"], width=18, state="readonly"
                )
                v["form_combo"].grid(row=i, column=1, sticky="w", pady=2, padx=3)
                v["form_combo"].bind("<<ComboboxSelected>>", lambda _event, vv=v: self._schedule_recalculate(vv, True))
            else:
                ttk.Entry(lf, textvariable=v[key], width=10).grid(row=i, column=1, sticky="w", pady=2, padx=3)
        v["species_id"].trace_add("write", lambda *_args, vv=v: self._manual_species_changed(vv))

        rf = ttk.LabelFrame(e, text="Extra", padding=6)
        rf.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        v["item"] = tk.StringVar()
        self._make_held_item_control(rf, v, row=0)
        for i, (key, lbl) in enumerate([
            ("happiness","Happiness"), ("status","Status (0=OK)"),
        ], start=1):
            v[key] = tk.StringVar()
            ttk.Label(rf, text=lbl+":", width=14, anchor="e").grid(row=i, column=0, sticky="e", pady=2)
            ttk.Entry(rf, textvariable=v[key], width=10).grid(row=i, column=1, sticky="w", pady=2, padx=3)
        v["ball"] = tk.StringVar()
        self._make_ball_control(rf, v, row=3)
        v["obtain_lv"] = tk.StringVar()
        ttk.Label(rf, text="Obtained Lv:", width=14, anchor="e").grid(row=4, column=0, sticky="e", pady=2)
        ttk.Entry(rf, textvariable=v["obtain_lv"], width=10).grid(row=4, column=1, sticky="w", pady=2, padx=3)

        r = 5
        v["nature_idx"] = tk.StringVar()
        ttk.Label(rf, text="Nature:", width=14, anchor="e").grid(row=r, column=0, sticky="e", pady=2)
        ttk.Combobox(rf, textvariable=v["nature_idx"], values=NATURE_CHOICES, width=24, state="readonly").grid(
            row=r, column=1, sticky="w", padx=3, pady=2); r += 1

        v["gender"] = tk.StringVar()
        ttk.Label(rf, text="Gender:", width=14, anchor="e").grid(row=r, column=0, sticky="e", pady=2)
        v["gender_combo"] = ttk.Combobox(
            rf, textvariable=v["gender"], values=GENDERS, width=10, state="readonly"
        )
        v["gender_combo"].grid(row=r, column=1, sticky="w", padx=3, pady=2); r += 1

        v["ability_slot"] = tk.StringVar()
        ttk.Label(rf, text="Ability:", width=14, anchor="e").grid(row=r, column=0, sticky="e", pady=2)
        v["ability_combo"] = ttk.Combobox(
            rf, textvariable=v["ability_slot"], values=[], width=20, state="readonly"
        )
        v["ability_combo"].grid(row=r, column=1, sticky="w", padx=3, pady=2); r += 1

        v["shiny"] = tk.BooleanVar()
        ttk.Label(rf, text="Shiny:", width=14, anchor="e").grid(row=r, column=0, sticky="e", pady=2)
        ttk.Checkbutton(rf, variable=v["shiny"]).grid(row=r, column=1, sticky="w", padx=3)

        bf = ttk.LabelFrame(e, text="Quick Actions", padding=6)
        bf.grid(row=0, column=2, sticky="n", padx=4, pady=4)
        ttk.Button(bf, text="Heal",       width=12, command=lambda vv=v: self._heal_slot(vv)).pack(pady=2)
        ttk.Button(bf, text="31 All IVs", width=12, command=lambda vv=v: self._max_ivs(vv)).pack(pady=2)
        ttk.Button(bf, text="Recalculate Stats", width=16, command=lambda vv=v: self._recalculate_stats(vv, True)).pack(pady=2)
        ttk.Button(bf, text="Zero EVs",   width=12, command=lambda vv=v: self._zero_evs(vv)).pack(pady=2)
        ttk.Button(bf, text="Restore PP", width=12, command=lambda vv=v: self._restore_pp(vv)).pack(pady=2)
        ttk.Button(bf, text="Build Library", width=12, command=lambda vv=v: self._open_build_dialog(vv)).pack(pady=2)
        ttk.Separator(bf, orient="horizontal").pack(fill="x", pady=4)
        v["shadow_status"] = tk.StringVar(value="Not Shadow")
        ttk.Button(bf, text="Shadow…", width=12,
                   command=lambda vv=v: self._open_shadow_dialog(vv)).pack(pady=2)
        ttk.Label(bf, textvariable=v["shadow_status"], width=14,
                  anchor="center", justify="center").pack(pady=(0, 2))

        manage = ttk.LabelFrame(e, text="Manage", padding=6)
        manage.grid(row=1, column=2, sticky="n", padx=4, pady=4)
        ttk.Button(
            manage, text="Move", width=12,
            command=lambda s=slot: self._move_party_pokemon(s),
        ).pack(pady=2)
        ttk.Button(
            manage, text="Delete", width=12, style="Danger.TButton",
            command=lambda s=slot: self._delete_party_pokemon(s),
        ).pack(pady=2)

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
            if key == "dex_abilities":
                v["ability_info_btn"] = self._make_info_button(df, lambda vv=v: self._show_ability_info(vv))
                v["ability_info_btn"].grid(row=row, column=2, sticky="w", padx=(4, 0), pady=1)
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

        evf = ttk.LabelFrame(e, text="EVs  (0–252 each)", padding=6)
        evf.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        for i, stat in enumerate(STATS):
            v["ev_"+stat.lower()] = tk.StringVar()
            ttk.Label(evf, text=stat, width=5).grid(row=0, column=i)
            ttk.Entry(evf, textvariable=v["ev_"+stat.lower()], width=4).grid(row=1, column=i)
        v["ev_total"] = tk.StringVar(value="Total: 0 / 510")
        ttk.Label(evf, textvariable=v["ev_total"]).grid(row=2, column=0, columnspan=6, sticky="w", pady=(4, 0))

        mf = ttk.LabelFrame(e, text="Moves", padding=6)
        mf.grid(row=2, column=0, columnspan=3, sticky="ew", padx=4, pady=4)
        for i in range(4):
            v[f"move{i}"]       = tk.StringVar(value="0")
            v[f"move{i}_name"]  = tk.StringVar(value="—")
            v[f"movepp{i}"]     = tk.StringVar(value="0")
            v[f"moveppup{i}"]   = tk.StringVar(value="0")
            v[f"move{i}_maxpp"] = tk.StringVar(value="/0")
            ttk.Label(mf, text=f"Move {i+1}:", anchor="e", width=8).grid(row=i, column=0, sticky="e", padx=(2,0), pady=2)
            v[f"move{i}_search"] = tk.StringVar(value="0 — None")
            ttk.Label(mf, textvariable=v[f"move{i}_search"], width=26,
                      anchor="w", relief="sunken").grid(row=i, column=1, sticky="ew", padx=2, pady=2)
            ttk.Button(mf, text="Search…", width=8,
                       command=lambda vv=v, ii=i: self._change_move(vv, ii)
                       ).grid(row=i, column=2, padx=(4,2), pady=2)
            ttk.Label(mf, text="PP:", anchor="e").grid(row=i, column=3, sticky="e", padx=(8,0))
            ttk.Entry(mf, textvariable=v[f"movepp{i}"], width=4).grid(row=i, column=4, padx=2)
            ttk.Label(mf, textvariable=v[f"move{i}_maxpp"], anchor="w", width=4).grid(row=i, column=5, sticky="w")
            ttk.Label(mf, text="PP Ups:").grid(row=i, column=6, padx=(6, 1))
            ttk.Spinbox(mf, from_=0, to=3, textvariable=v[f"moveppup{i}"], width=3).grid(row=i, column=7)
            v[f"moveppup{i}"].trace_add("write", lambda *_args, vv=v, ii=i: self._refresh_move_pp_display(vv, ii))
        ttk.Button(mf, text="Max all PP Ups", command=lambda vv=v: self._max_pp_ups(vv)).grid(row=4, column=1, sticky="w", padx=2, pady=(5, 1))
        ttk.Label(mf, text="Current PP / maximum PP; each move stores 0–3 PP Ups.", foreground="gray").grid(row=4, column=2, columnspan=6, sticky="w", padx=4)
        mf.columnconfigure(1, weight=1)

        v["level"].trace_add("write", lambda *_args, vv=v: self._sync_exp_from_level(vv))
        v["exp"].trace_add("write", lambda *_args, vv=v: self._sync_level_from_exp(vv))
        v["nature_idx"].trace_add("write", lambda *_args, vv=v: self._schedule_recalculate(vv))
        for stat in STATS:
            v["iv_" + stat.lower()].trace_add("write", lambda *_args, vv=v: self._schedule_recalculate(vv))
            v["ev_" + stat.lower()].trace_add("write", lambda *_args, vv=v: self._schedule_recalculate(vv))

        e.columnconfigure(0, weight=1)
        e.columnconfigure(1, weight=1)
        e.columnconfigure(3, weight=1)
        v["_pkmn_obj"] = None

        v["add_frame"] = ttk.Frame(parent, padding=12)
        add_btn = ttk.Button(v["add_frame"], text="+ Add Pokémon to this slot",
                             command=lambda s=slot: self._add_to_party_slot(s))
        add_btn.pack(anchor="center", padx=8, pady=8)
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

    def _refresh_move_pp_display(self, v, index: int):
        try:
            move_id = int(v[f"move{index}"].get() or 0)
            pp_ups = int(v[f"moveppup{index}"].get() or 0)
        except (ValueError, KeyError):
            return
        maximum = move_max_pp(move_id, pp_ups)
        v[f"move{index}_maxpp"].set(f"/{maximum}")

    def _max_pp_ups(self, v):
        for index in range(4):
            if f"moveppup{index}" not in v: continue
            v[f"moveppup{index}"].set("3")
            try: move_id = int(v[f"move{index}"].get() or 0)
            except (ValueError, KeyError): move_id = 0
            v[f"movepp{index}"].set(str(move_max_pp(move_id, 3)))
            self._refresh_move_pp_display(v, index)

    def _restore_pp(self, v):
        self._restore_pp_from_obj(v, None)

    def _restore_pp_from_obj(self, v, pkmn):
        for i in range(4):
            try:
                mid = int(v[f"move{i}"].get() or 0)
            except (ValueError, KeyError):
                mid = 0
            try: pp_ups = int(v.get(f"moveppup{i}").get() or 0)
            except (ValueError, AttributeError): pp_ups = 0
            max_pp = move_max_pp(mid, pp_ups)
            if max_pp:
                v[f"movepp{i}"].set(str(max_pp))


    def _parse_build_text(self, text: str) -> dict:
        lines = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        fields, move_names, in_moves = {}, [], False
        for line in lines:
            if line == "---":
                continue
            if line.casefold().startswith("moves:"):
                in_moves = True; continue
            if in_moves and line[:1] in ("-", "*", "•"):
                move_names.append(line[1:].strip()); continue
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip().casefold()] = value.strip(); in_moves = False
            elif in_moves:
                move_names.append(line)
        species = self._species_from_text(fields.get("species", ""))
        if not species:
            raise ValueError("Unknown or missing species")
        level = min(MAX_LEVEL, max(1, int(fields.get("level", 100))))
        nature_text = fields.get("nature", "Hardy").casefold()
        nature = next((i for i, name in enumerate(NATURES) if name.casefold() == nature_text), None)
        if nature is None:
            nature = nature_index_from_value(fields.get("nature", "Hardy"))
        ivs = [31] * 6
        if "ivs" in fields:
            parsed = [int(x) for x in re.findall(r"\d+", fields["ivs"])][:6]
            if len(parsed) != 6: raise ValueError("IVs must contain six numbers")
            ivs = [min(31, max(0, value)) for value in parsed]
        ev_map = {stat: 0 for stat in STATS}
        aliases = {"hp":"HP", "atk":"Atk", "def":"Def", "spa":"SpA", "spatk":"SpA",
                   "spd":"SpD", "spdef":"SpD", "spe":"Spe", "speed":"Spe"}
        for amount, stat in re.findall(r"(\d+)\s*([A-Za-z]+)", fields.get("evs", "")):
            key = aliases.get(stat.casefold())
            if key: ev_map[key] = min(252, max(0, int(amount)))
        evs = [ev_map[stat] for stat in STATS]
        moves = []
        for name in move_names[:4]:
            match = re.match(r"^(\d+)", name)
            move_id = int(match.group(1)) if match else next(
                (mid for mid, data in MOVE_DATA.items() if data.get("name", "").casefold() == name.casefold()), 0)
            if move_id not in MOVE_DATA: raise ValueError(f"Unknown move: {name}")
            moves.append((move_id, MOVE_DATA[move_id].get("pp", 0)))
        return {"fields": fields, "species": species, "level": level, "nature": nature,
                "ivs": ivs, "evs": evs, "moves": moves}

    def _validate_build_text(self, text: str) -> list:
        """(block, line, message) for everything wrong with the raw editor text.

        Syntax first, from validate_build_block; then _parse_build_text, which
        already raises on the semantic problems - an unknown species, move, item
        or ability, or IVs that are not six numbers - so they are not restated
        here.  A block with broken syntax is not parsed, because the parser
        would only report a confusing consequence of it.
        """
        blocks = split_build_blocks_with_lines(text)
        if not blocks:
            return [(1, 1, "There is no build text here")]
        problems = []
        for index, (block, first_line) in enumerate(blocks, start=1):
            found = validate_build_block(block, first_line)
            if not found:
                try:
                    self._parse_build_text(block)
                except ValueError as exc:
                    found = [(first_line, str(exc))]
                except Exception as exc:
                    found = [(first_line, f"{type(exc).__name__}: {exc}")]
            problems.extend((index, line, message) for line, message in found)
        return problems

    def _apply_build_text(self, v, text: str):
        if v is None: raise ValueError("Select an existing Pokémon before applying to the current slot")
        build = self._parse_build_text(text); fields = build["fields"]
        self._select_species(v, str(build["species"]))
        v["level"].set(str(build["level"]))
        v["nature_idx"].set(NATURE_CHOICES[build["nature"]])
        for stat, value in zip(STATS, build["ivs"]): v["iv_" + stat.lower()].set(str(value))
        for stat, value in zip(STATS, build["evs"]): v["ev_" + stat.lower()].set(str(value))
        if "happiness" in fields: v["happiness"].set(fields["happiness"])
        # _build_text_from_slot writes Nickname, so applying has to read it back
        # or a saved build quietly loses the name it was saved with.
        if fields.get("nickname", "").strip() and "nickname" in v:
            v["nickname"].set(fields["nickname"].strip())
        if "item" in fields:
            wanted = fields["item"].casefold()
            item_id = next((iid for iid, data in ITEM_DATA.items() if data.get("name", "").casefold() == wanted), 0)
            if not item_id: raise ValueError(f"Unknown item: {fields['item']}")
            self._set_held_item_from_picker(v, item_id)
        if "ability" in fields:
            wanted = fields["ability"].casefold()
            choice = next((label for _slot, label in ability_choices_for_species(build["species"])
                           if label.split(" (")[0].casefold() == wanted), None)
            if not choice: raise ValueError(f"Ability is not listed for this species: {fields['ability']}")
            v["ability_slot"].set(choice)
        for index in range(4):
            move_id = build["moves"][index][0] if index < len(build["moves"]) else 0
            self._update_move_vars(v, index, move_id)
        self._recalculate_stats(v, True)

    def _pokemon_from_build(self, text: str) -> RubyObject:
        build = self._parse_build_text(text); fields = build["fields"]
        pkmn = self._create_pokemon_obj(build["species"], nature_index=build["nature"],
                                        level=build["level"], moves=build["moves"], evs=build["evs"])
        a = pkmn.attributes
        a["@iv"] = _display_stats_to_game(build["ivs"])
        if fields.get("nickname", "").strip():
            a["@name"] = fields["nickname"].strip().encode("utf-8")
        if "happiness" in fields: a["@happiness"] = min(255, max(0, int(fields["happiness"])))
        if "item" in fields:
            wanted = fields["item"].casefold()
            picker_id = next((iid for iid, data in ITEM_DATA.items() if data.get("name", "").casefold() == wanted), 0)
            if not picker_id: raise ValueError(f"Unknown item: {fields['item']}")
            a["@item"] = item_source_id(picker_id)
        if "ability" in fields:
            wanted = fields["ability"].casefold()
            label = next((label for _slot, label in ability_choices_for_species(build["species"])
                          if label.split(" (")[0].casefold() == wanted), None)
            if not label: raise ValueError(f"Ability is not listed for this species: {fields['ability']}")
            a["@abilityflag"] = ability_slot_from_value(build["species"], label)
        stats = calculate_pokemon_stats(build["species"], pokemon_form(a), build["level"],
                                        build["nature"], build["ivs"], build["evs"])
        for key, value in zip(("@totalhp","@attack","@defense","@spatk","@spdef","@speed"), stats):
            a[key] = value
        a["@hp"] = stats[0]
        return pkmn

    def _pc_box_options(self):
        """(box index, box object, label) for every real PC box."""
        boxes = self.storage.attributes.get("@boxes", []) if isinstance(self.storage, RubyObject) else []
        options = []
        for box_idx, box in enumerate(boxes if isinstance(boxes, list) else []):
            if not isinstance(box, RubyObject):
                continue
            box_name = ds(box.attributes.get("@name", f"Box {box_idx + 1}"))
            options.append((box_idx, box, f"Box {box_idx + 1}: {box_name}"))
        return options

    @staticmethod
    def _empty_slots_in(box):
        """(list, index) pairs for every free slot in one box, in order."""
        pokemon = box.attributes.get("@pokemon", [])
        if not isinstance(pokemon, list):
            return []
        return [(pokemon, index) for index, value in enumerate(pokemon)
                if not isinstance(value, RubyObject)]

    def _ask_target_box(self, options, remaining, parent=None):
        """Ask which box to fill next.  Returns a box option, or None to cancel."""
        dlg = self._make_popup(f"Import {remaining} build(s)", "430x170")
        if parent is not None:
            dlg.transient(parent)
        ttk.Label(dlg, text=f"Which PC box should receive {remaining} Pokemon?",
                  font=("", 10, "bold"), padding=(0, 10, 0, 6)).pack()
        frame = ttk.Frame(dlg, padding=8); frame.pack(fill="x", padx=10)
        labels = [label for _idx, _box, label in options]
        free = {label: len(self._empty_slots_in(box)) for _idx, box, label in options}
        current = self.storage.attributes.get("@currentBox", 0)
        default = next((o for o in options if o[0] == current), options[0])
        box_var = tk.StringVar(value=default[2])
        ttk.Label(frame, text="Box:").pack(side="left")
        ttk.Combobox(frame, textvariable=box_var, values=labels, width=26,
                     state="readonly").pack(side="left", padx=(4, 8))
        free_var = tk.StringVar()
        ttk.Label(frame, textvariable=free_var, foreground="gray").pack(side="left")
        def refresh(*_a):
            free_var.set(f"{free.get(box_var.get(), 0)} free")
        box_var.trace_add("write", refresh); refresh()

        chosen = {}
        buttons = ttk.Frame(dlg, padding=10); buttons.pack(fill="x", side="bottom")
        def confirm():
            chosen["option"] = next((o for o in options if o[2] == box_var.get()), None)
            dlg.destroy()
        ttk.Button(buttons, text="Cancel", command=dlg.destroy).pack(side="right")
        ttk.Button(buttons, text="Use this box", command=confirm).pack(side="right", padx=4)
        dlg.wait_window()
        return chosen.get("option")

    def _ask_overflow(self, box_label, fits, remaining, parent=None):
        """Chosen box is too small: fill it, spread the rest automatically, or stop."""
        dlg = self._make_popup("Not enough room", "470x190")
        if parent is not None:
            dlg.transient(parent)
        ttk.Label(
            dlg, padding=(12, 12, 12, 4), justify="left", wraplength=440,
            text=(f"{box_label} has room for {fits} of {remaining} Pokemon.\n\n"
                  "Fill it and choose another box for the rest, let the editor place "
                  "them in the first free slots, or cancel the whole import."),
        ).pack(fill="x")
        answer = {}
        buttons = ttk.Frame(dlg, padding=10); buttons.pack(fill="x", side="bottom")
        def choose(value):
            answer["value"] = value; dlg.destroy()
        ttk.Button(buttons, text="Cancel", command=dlg.destroy).pack(side="right")
        ttk.Button(buttons, text="Auto choose", command=lambda: choose("auto")).pack(side="right", padx=4)
        ttk.Button(buttons, text="Fill this box", command=lambda: choose("fill")).pack(side="right")
        dlg.wait_window()
        return answer.get("value")

    def _plan_build_placements(self, count, parent=None):
        """Resolve where `count` Pokemon go before anything is written.

        Returns a list of (list, index) slots, or None when the user cancels.
        Nothing in the save is touched here, so cancelling costs nothing.
        """
        options = self._pc_box_options()
        if not options:
            raise ValueError("This save has no PC boxes")
        taken, placements = set(), []
        while len(placements) < count:
            remaining = count - len(placements)
            option = self._ask_target_box(options, remaining, parent=parent)
            if option is None:
                return None
            _box_idx, box, label = option
            free = [slot for slot in self._empty_slots_in(box)
                    if (id(slot[0]), slot[1]) not in taken]
            if len(free) >= remaining:
                placements.extend(free[:remaining])
                break
            if not free:
                messagebox.showwarning("Box is full", f"{label} has no free slots.", parent=parent)
                continue
            choice = self._ask_overflow(label, len(free), remaining, parent=parent)
            if choice is None:
                return None
            placements.extend(free)
            taken.update((id(slots), index) for slots, index in free)
            if choice == "auto":
                spare = []
                for _idx, other, _label in options:
                    for slot in self._empty_slots_in(other):
                        if (id(slot[0]), slot[1]) not in taken:
                            spare.append(slot)
                needed = count - len(placements)
                if len(spare) < needed:
                    raise ValueError(
                        f"Need {needed} more empty PC slots; only {len(spare)} are left")
                placements.extend(spare[:needed])
                break
            taken.update((id(slots), index) for slots, index in placements)
        return placements

    def _import_builds_to_pc(self, build_texts, parent=None):
        if not isinstance(self.storage, RubyObject):
            raise ValueError("This save has no PC storage")
        self._apply_party(); self._apply_boxes()

        total_free = sum(len(self._empty_slots_in(box))
                         for _idx, box, _label in self._pc_box_options())
        if total_free < len(build_texts):
            raise ValueError(
                f"Need {len(build_texts)} empty PC slots; only {total_free} are available")

        # Build every Pokemon and resolve every destination before writing, so a
        # cancel or a parse failure leaves the save exactly as it was.
        created = [self._pokemon_from_build(text) for text in build_texts]
        placements = self._plan_build_placements(len(created), parent=parent)
        if placements is None:
            return 0

        for pkmn, (slots, index) in zip(created, placements):
            slots[index] = pkmn
        self._populate_boxes(); self._fill_trainer()
        self.status.config(
            text=f"Imported {len(created)} builds into the PC. Click Save to write.",
            foreground="blue")
        return len(created)
    def _build_text_from_slot(self, v, trainer: str = "", description: str = "") -> str:
        """Serialise the Pokemon currently in an editor slot into a build block.

        The inverse of _apply_build_text, so a saved build round-trips back into
        the same slot values.
        """
        if v is None or not isinstance(v.get("_pkmn_obj"), RubyObject):
            raise ValueError("This slot has no Pokemon to save")
        try:
            species_id = int(v["species_id"].get())
        except (KeyError, ValueError):
            raise ValueError("This slot has no species set")
        if species_id not in PKMN_DATA:
            raise ValueError("This slot's species is not in the bundled data")

        lines = [f"Trainer: {trainer.strip()}"] if trainer.strip() else []
        lines.append(f"Species: {PKMN_DATA[species_id].get('name', species_id)}")
        if description.strip():
            lines.append(f"Description: {description.strip()}")
        nickname = v["nickname"].get().strip() if "nickname" in v else ""
        if nickname and nickname.casefold() != PKMN_DATA[species_id].get("name", "").casefold():
            lines.append(f"Nickname: {nickname}")
        lines.append(f"Level: {v['level'].get().strip() or '100'}")
        lines.append(f"Nature: {v['nature_idx'].get().split(' (')[0].strip() or 'Hardy'}")
        ability = v["ability_slot"].get().split(" (")[0].strip() if "ability_slot" in v else ""
        if ability:
            lines.append(f"Ability: {ability}")

        ivs = [v["iv_" + stat.lower()].get().strip() or "0" for stat in STATS]
        lines.append("IVs: " + "/".join(ivs))
        evs = []
        for stat in STATS:
            value = int(v["ev_" + stat.lower()].get().strip() or 0)
            if value:
                evs.append(f"{value} {stat}")
        lines.append("EVs: " + (" / ".join(evs) if evs else "0 HP"))

        lines.append("Moves:")
        for index in range(4):
            try:
                move_id = int(v[f"move{index}"].get() or 0)
            except (KeyError, ValueError):
                continue
            if move_id in MOVE_DATA:
                lines.append(f"- {MOVE_DATA[move_id]['name']}")

        try:
            item_id = item_picker_id(int(v["item"].get() or 0))
        except (KeyError, ValueError):
            item_id = 0
        item_name = ITEM_DATA.get(item_id, {}).get("name", "")
        if item_name:
            lines.append(f"Item: {item_name}")
        happiness = v["happiness"].get().strip() if "happiness" in v else ""
        lines.append(f"Happiness: {happiness or '0'}")
        return "\n".join(lines)

    def _ask_build_details(self, default_trainer: str, parent=None):
        """Ask for the Trainer and Description a saved build should carry."""
        dlg = self._make_popup("Save build to library", "440x210")
        if parent is not None:
            dlg.transient(parent)
        ttk.Label(dlg, text="Who owns this build, and how would you describe it?",
                  padding=(12, 12, 12, 6), wraplength=410, justify="left").pack(fill="x")
        form = ttk.Frame(dlg, padding=(12, 0)); form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        trainer_var = tk.StringVar(value=default_trainer)
        description_var = tk.StringVar()
        ttk.Label(form, text="Trainer:", width=11, anchor="e").grid(row=0, column=0, sticky="e", pady=3)
        ttk.Entry(form, textvariable=trainer_var).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ttk.Label(form, text="Description:", width=11, anchor="e").grid(row=1, column=0, sticky="e", pady=3)
        ttk.Entry(form, textvariable=description_var).grid(row=1, column=1, sticky="ew", padx=(6, 0))
        ttk.Label(dlg, text="Leave Trainer blank for a wild build.", foreground="gray",
                  padding=(12, 6)).pack(anchor="w")

        answer = {}
        buttons = ttk.Frame(dlg, padding=10); buttons.pack(fill="x", side="bottom")
        def confirm():
            answer["trainer"] = trainer_var.get()
            answer["description"] = description_var.get()
            dlg.destroy()
        ttk.Button(buttons, text="Cancel", command=dlg.destroy).pack(side="right")
        ttk.Button(buttons, text="Save", command=confirm).pack(side="right", padx=4)
        dlg.wait_window()
        return (answer.get("trainer"), answer.get("description")) if answer else (None, None)

    def _render_build_info(self, parent, build_text: str):
        """Rebuild the read-only Info tab for one build block."""
        for child in parent.winfo_children():
            child.destroy()
        summary = build_summary(build_text)
        species_id = summary["species_id"]
        if not species_id:
            ttk.Label(parent, text="This block names no species the game knows.",
                      foreground="gray").pack(anchor="w", padx=8, pady=8)
            return

        fields = _build_fields(build_text)
        ttk.Label(parent, text=build_title(build_text), font=("", 12, "bold")).pack(
            anchor="center", pady=(8, 2))
        ttk.Label(parent, text=f"{summary['tier']}  ·  {summary['style']}",
                  foreground="gray").pack(anchor="center")

        sprite = self._load_pokemon_sprite(species_id, 0, max_size=96)
        sprite_label = ttk.Label(parent, image=sprite if sprite else "",
                                 text="" if sprite else "(no sprite)", anchor="center")
        sprite_label.image = sprite
        sprite_label.pack(anchor="center", pady=4)
        if summary["description"]:
            ttk.Label(parent, text=summary["description"], foreground="gray",
                      wraplength=380, justify="center").pack(anchor="center", pady=(0, 6))

        grid = ttk.Frame(parent, padding=(10, 0))
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)
        row = 0
        for label, value in (
            ("Level", fields.get("level", "-")),
            ("Nature", fields.get("nature", "-")),
            ("Ability", fields.get("ability", "-")),
            ("Item", fields.get("item", "-")),
            ("Happiness", fields.get("happiness", "-")),
        ):
            ttk.Label(grid, text=f"{label}:", width=11, anchor="e").grid(row=row, column=0, sticky="e")
            ttk.Label(grid, text=value or "-", anchor="w").grid(row=row, column=1, sticky="w", padx=(6, 0))
            row += 1

        ivs, evs = _build_ivs_evs(fields)
        digits = re.sub(r"\D", "", fields.get("level", "")) or "100"
        level = min(MAX_LEVEL, max(1, int(digits)))
        nature_index = next((i for i, name in enumerate(NATURES)
                             if name.casefold() == fields.get("nature", "").casefold()), 0)
        stats = calculate_pokemon_stats(species_id, 0, level, nature_index, ivs, evs)

        table = ttk.Frame(parent, padding=(10, 8))
        table.pack(fill="x")
        for column, heading in enumerate(("", *STATS)):
            ttk.Label(table, text=heading, width=6, anchor="center",
                      font=("", 8, "bold")).grid(row=0, column=column)
        for line, values in (("IVs", ivs), ("EVs", evs), ("Stats", stats)):
            record = 1 + ("IVs", "EVs", "Stats").index(line)
            ttk.Label(table, text=line, width=6, anchor="e").grid(row=record, column=0, sticky="e")
            for column, value in enumerate(values, start=1):
                ttk.Label(table, text=str(value), width=6, anchor="center").grid(row=record, column=column)

        moves = ttk.LabelFrame(parent, text="Moves", padding=6)
        moves.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        move_ids = _build_move_ids(build_text)
        if not move_ids:
            ttk.Label(moves, text="No moves listed.", foreground="gray").pack(anchor="w")
        for move_id in move_ids:
            data = MOVE_DATA.get(move_id, {})
            power = data.get("power", 0)
            detail = f"{data.get('type', '?')} · {data.get('category', '?')}"
            detail += f" · {power} pow" if power else " · status"
            if data.get("name") in MOVE_UTILITY_VALUE:
                detail += " · utility"
            line = ttk.Frame(moves)
            line.pack(fill="x")
            ttk.Label(line, text=data.get("name", f"#{move_id}"), width=18, anchor="w").pack(side="left")
            ttk.Label(line, text=detail, foreground="gray", anchor="w").pack(side="left")

    def _open_build_dialog(self, v=None):
        win = self._make_popup("Pokemon Build Library", "1120x680", resizable=(True, True))
        body = ttk.Frame(win, padding=10); body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3, minsize=560); body.columnconfigure(1, weight=2, minsize=380)
        body.rowconfigure(2, weight=1)

        # Opened from a Pokemon's own button: offer that Pokemon as an unsaved
        # build sitting at the top of the list until it is added to the library.
        pending = {"text": None}
        if v is not None and isinstance(v.get("_pkmn_obj"), RubyObject):
            try:
                pending["text"] = self._build_text_from_slot(v)
            except ValueError:
                pending["text"] = None

        filters = ttk.Frame(body); filters.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(filters, text="Tier:").pack(side="left")
        tier_var = tk.StringVar(value="All")
        ttk.Combobox(filters, textvariable=tier_var, values=["All", *BUILD_TIERS], width=8,
                     state="readonly").pack(side="left", padx=(4, 14))
        ttk.Label(filters, text="Search:").pack(side="left")
        search_var = tk.StringVar(); ttk.Entry(filters, textvariable=search_var, width=30).pack(side="left", padx=4)
        count_var = tk.StringVar(); ttk.Label(filters, textvariable=count_var, foreground="gray").pack(side="left", padx=8)
        ttk.Label(body, text="Builds (Ctrl/Shift selects several; the Raw text tab holds "
                             "whatever you pick):").grid(row=1, column=0, sticky="w")

        list_frame = ttk.Frame(body); list_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 6), pady=4)
        list_frame.rowconfigure(0, weight=1); list_frame.columnconfigure(0, weight=1)
        columns = ("tier", "trainer", "species", "style", "description")
        library = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="extended")
        for name, width, anchor, stretch in (
            ("tier", 38, "center", False), ("trainer", 76, "w", False),
            ("species", 88, "w", True), ("style", 116, "w", False),
            ("description", 150, "w", True),
        ):
            library.column(name, width=width, minwidth=34, anchor=anchor, stretch=stretch)
        list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=library.yview)
        library.configure(yscrollcommand=list_scroll.set)
        library.grid(row=0, column=0, sticky="nsew"); list_scroll.grid(row=0, column=1, sticky="ns")

        # Right pane: Info first, the raw block behind it.
        tabs = ttk.Notebook(body); tabs.grid(row=2, column=1, sticky="nsew", pady=4)
        info_outer = ttk.Frame(tabs); raw_outer = ttk.Frame(tabs)
        tabs.add(info_outer, text=" Info "); tabs.add(raw_outer, text=" Raw text ")

        info_canvas = tk.Canvas(info_outer, highlightthickness=0, borderwidth=0, width=380)
        info_scroll = ttk.Scrollbar(info_outer, orient="vertical", command=info_canvas.yview)
        info_frame = ttk.Frame(info_canvas)
        info_frame.bind("<Configure>", lambda _e: info_canvas.configure(scrollregion=info_canvas.bbox("all")))
        info_window = info_canvas.create_window((0, 0), window=info_frame, anchor="nw")
        info_canvas.bind("<Configure>", lambda e: info_canvas.itemconfigure(info_window, width=e.width))
        info_canvas.configure(yscrollcommand=info_scroll.set)
        info_canvas.pack(side="left", fill="both", expand=True); info_scroll.pack(side="right", fill="y")

        # Buttons that must not run while the editor holds uncommitted edits.
        raw_gated = []

        # These two live inside the Raw tab, so they are visible exactly when the
        # editor is and need no tab-change plumbing.  The strip is packed before
        # the text box so its height is reserved rather than fought over.
        raw_buttons = ttk.Frame(raw_outer)
        raw_buttons.pack(side="bottom", fill="x", pady=(4, 2))
        apply_raw = ttk.Button(raw_buttons, text="Apply RAW Changes",
                               command=lambda: safe(apply_raw_changes))
        ttk.Button(raw_buttons, text="New Empty Build",
                   command=lambda: safe(new_empty_build)).pack(side="right")
        ttk.Label(raw_outer, foreground="gray", wraplength=340, justify="left",
                  text="Edits are checked and saved only when you apply them, and go to "
                       "your own build file. Separate several builds with a --- line.").pack(
                           side="bottom", fill="x", pady=(4, 2))

        editor = tk.Text(raw_outer, wrap="word", height=10, undo=True)
        raw_scroll = ttk.Scrollbar(raw_outer, orient="vertical", command=editor.yview)
        editor.configure(yscrollcommand=raw_scroll.set)
        editor.pack(side="left", fill="both", expand=True); raw_scroll.pack(side="right", fill="y")

        # Entry 0 is the unsaved Pokemon, when there is one; the rest mirror the
        # library.  Summaries are derived once per rebuild, not per redraw.
        entries, summaries, entry_ids = [], [], []
        def rebuild_entries():
            entries[:] = ([pending["text"]] if pending["text"] else []) + list(BUILD_LIBRARY)
            entry_ids[:] = ([None] if pending["text"] else []) + list(BUILD_IDS)
            summaries[:] = [build_summary(text) for text in entries]
            if pending["text"]:
                summaries[0] = dict(summaries[0], description="(unregistered - not in library)")
        rebuild_entries()

        # The ids of the blocks currently loaded into the editor, in order.  The
        # user never sees them; they are what lets an edited build be written
        # back over itself instead of appended as a near-duplicate.
        loaded = {"ids": [], "dirty": False}

        def current_text():
            return editor.get("1.0", "end").strip()

        def refresh_info(*_args):
            blocks = split_build_blocks(current_text())
            self._render_build_info(info_frame, blocks[0] if blocks else "")
            if len(blocks) > 1:
                ttk.Label(info_frame, foreground="gray",
                          text=f"Showing 1 of {len(blocks)} builds in the raw text.").pack(
                              anchor="w", padx=8, pady=(6, 0))

        def set_dirty(state):
            """Only an explicit Apply commits the raw text, so the rest of the
            dialog must not act on half-typed edits."""
            loaded["dirty"] = bool(state)
            editor.edit_modified(False)
            if state:
                apply_raw.pack(side="left", padx=(0, 4))
            else:
                apply_raw.pack_forget()
            for button in raw_gated:
                button.configure(state="disabled" if state else "normal")

        def load_into_editor(texts, ids):
            editor.delete("1.0", "end")
            editor.insert("1.0", "\n---\n".join(strip_build_id(text) for text in texts))
            loaded["ids"] = list(ids)
            set_dirty(False)
            refresh_info()

        def show_selected(_event=None):
            selected = library.selection()
            if selected:
                indexes = [int(iid) for iid in selected]
                load_into_editor([entries[i] for i in indexes],
                                 [entry_ids[i] for i in indexes])
            else:
                refresh_info()

        def new_empty_build():
            """Start a build from nothing: the field names, and nothing else."""
            library.selection_remove(*library.selection())
            editor.delete("1.0", "end")
            editor.insert("1.0", "\n".join(f"{label}:" for label in BUILD_KEY_LABELS.values()
                                           if label != "Tier"))
            loaded["ids"] = []
            set_dirty(True)
            tabs.select(raw_outer)
            editor.focus_set()

        def apply_raw_changes():
            """Validate the raw text, then write it to the user's library file."""
            problems = self._validate_build_text(current_text())
            if problems:
                messagebox.showerror(
                    "Build text is not valid",
                    "Nothing was saved. Fix these and apply again:\n\n"
                    + build_validation_report(problems), parent=win)
                return
            blocks = split_build_blocks(current_text())
            # The unsaved Pokemon at the top of the list has no id yet; applying
            # is what turns it into a real library entry.
            ids = [identifier or new_build_id() for identifier in loaded["ids"]]
            if len(blocks) > len(ids):
                # More builds than were loaded means the user added some, and
                # what to ask depends on whether they started from an entry.
                if ids:
                    question = ("You seem to have added multiple Pokemon builds inside an "
                                "already existing entry. Do you want to save them as "
                                "separate builds?")
                else:
                    question = ("Multiple Builds detected in the RAW text. Do you want to "
                                "import them to the library?")
                if len(blocks) > 1 and not messagebox.askokcancel("Multiple builds", question,
                                                                  parent=win):
                    return
                ids += [new_build_id() for _ in range(len(blocks) - len(ids))]
            path = save_user_builds(list(zip(ids, blocks)))
            pending["text"] = None
            rebuild_entries(); refresh_library()
            keep = [str(entries.index(text)) for text in BUILD_LIBRARY
                    if build_id(text) in ids and text in entries]
            loaded["ids"] = ids
            set_dirty(False)
            if keep:
                library.selection_set(keep); library.see(keep[0])
            self.status.config(text=f"Saved {len(blocks)} build(s) to your library.",
                               foreground="blue")
            messagebox.showinfo("Builds saved",
                                f"{len(blocks)} build(s) written to your library.\n{path}",
                                parent=win)

        tier_rank = {name: index for index, name in enumerate(BUILD_TIERS)}
        sort_state = {"col": "tier", "reverse": False}
        def set_sort(col):
            if sort_state["col"] == col: sort_state["reverse"] = not sort_state["reverse"]
            else: sort_state.update(col=col, reverse=False)
            refresh_library()

        def refresh_library(*_args):
            query, tier = search_var.get().casefold().strip(), tier_var.get()
            previous = set(library.selection()); rows = []
            for index, summary in enumerate(summaries):
                if tier != "All" and summary["tier"] != tier: continue
                haystack = " ".join((summary["trainer"], summary["species_name"],
                                     summary["style"], summary["description"],
                                     entries[index])).casefold()
                if query and query not in haystack: continue
                rows.append((index, summary))
            col = sort_state["col"]
            def key(row):
                summary = row[1]
                if col == "tier":
                    return (tier_rank.get(summary["tier"], 99),
                            summary["species_name"].casefold())
                return (str(summary[{"trainer": "trainer", "species": "species_name",
                                     "style": "style", "description": "description"}[col]]).casefold(),
                        summary["species_name"].casefold())
            rows.sort(key=key, reverse=sort_state["reverse"])
            if pending["text"]:
                rows.sort(key=lambda row: row[0] != 0)
            library.delete(*library.get_children())
            for heading, label in (("tier", "Tier"), ("trainer", "Trainer"),
                                   ("species", "Species"), ("style", "Style"),
                                   ("description", "Description")):
                indicator = (" ▼" if sort_state["reverse"] else " ▲") if heading == col else ""
                library.heading(heading, text=label + indicator,
                                command=lambda c=heading: set_sort(c))
            for index, summary in rows:
                library.insert("", "end", iid=str(index),
                               values=(summary["tier"], summary["trainer"],
                                       summary["species_name"], summary["style"],
                                       summary["description"]))
            count_var.set(f"{len(rows)} of {len(entries)} builds")
            restored = [iid for iid in previous if library.exists(iid)]
            if restored:
                library.selection_set(restored); library.see(restored[0]); show_selected()
            elif library.get_children():
                first = library.get_children()[0]
                library.selection_set(first); library.see(first); show_selected()
            else:
                editor.delete("1.0", "end"); refresh_info()

        library.bind("<<TreeviewSelect>>", show_selected)
        tier_var.trace_add("write", refresh_library); search_var.trace_add("write", refresh_library)
        # Editing the raw block is the source of truth; Info re-renders from it.
        tabs.bind("<<NotebookTabChanged>>", lambda _e: refresh_info())
        refresh_library()

        row = ttk.Frame(win, padding=10); row.pack(fill="x")
        def safe(action):
            try: action()
            except Exception as exc: messagebox.showerror("Build error", str(exc), parent=win)
        def apply_current():
            blocks = split_build_blocks(current_text())
            if not blocks: raise ValueError("There is no build text to apply")
            self._apply_build_text(v, blocks[0]); win.destroy()
        def import_to_pc():
            # The editor is the one source of truth: what you can see is what
            # gets created, whether you picked it from the table or typed it.
            blocks = split_build_blocks(current_text())
            if not blocks: raise ValueError("There is no build text to import")
            count = self._import_builds_to_pc(blocks, parent=win)
            if count:
                messagebox.showinfo("Builds imported",
                                    f"Created {count} Pokemon. Click Save to write the save file.",
                                    parent=win)
        def save_to_library():
            text = current_text()
            if not build_summary(text)["species_id"]:
                raise ValueError("This block names no species the game knows")
            default_trainer = ds(self.trainer.attributes.get("@name", b"")) if self.trainer else ""
            trainer, description = self._ask_build_details(default_trainer, parent=win)
            if trainer is None:
                return
            fields = _build_fields(text)
            kept = [line for line in text.splitlines()
                    if line.split(":")[0].strip().casefold() not in ("trainer", "description")]
            block = []
            if trainer.strip():
                block.append(f"Trainer: {trainer.strip()}")
            block.append(f"Species: {fields.get('species', '')}")
            if description.strip():
                block.append(f"Description: {description.strip()}")
            block += [line for line in kept
                      if line.split(":")[0].strip().casefold() != "species"]
            path = append_user_build("\n".join(block))
            pending["text"] = None
            rebuild_entries(); refresh_library()
            messagebox.showinfo("Saved to library",
                                f"Build added to your library.\n{path}", parent=win)

        ttk.Button(row, text="Close", command=win.destroy).pack(side="right")
        if pending["text"]:
            ttk.Button(row, text="Save to Library",
                       command=lambda: safe(save_to_library)).pack(side="left", padx=(0, 4))
        import_button = ttk.Button(row, text="Import to PC", command=lambda: safe(import_to_pc))
        import_button.pack(side="left", padx=4)
        raw_gated.append(import_button)
        if v is not None:
            current_button = ttk.Button(row, text="Apply to Current",
                                        command=lambda: safe(apply_current))
            current_button.pack(side="right", padx=4)
            raw_gated.append(current_button)

        # Everything downstream reads committed text, so nothing may run while
        # the editor holds edits that have not been through Apply.
        editor.bind("<<Modified>>", lambda _e: editor.edit_modified() and set_dirty(True))
        show_selected()

    def _sync_slot_vars_from_obj(self, v):
        """Re-read the fields the shadow dialog can rewrite behind the UI's back.

        The dialog edits the save object directly (moves, EVs, EXP), while
        _apply_party/_apply_boxes later write the UI vars back onto that object.
        Without this resync the stale vars would undo the shadow change on save.
        """
        pkmn = v.get("_pkmn_obj")
        if not isinstance(pkmn, RubyObject):
            return
        a = pkmn.attributes
        moves = a.get("@moves", [])
        for i in range(4):
            if f"move{i}" not in v:
                continue
            mid = pp = 0
            if isinstance(moves, list) and i < len(moves) and isinstance(moves[i], RubyObject):
                mid = moves[i].attributes.get("@id", 0) or 0
                pp  = moves[i].attributes.get("@pp", 0) or 0
                ppup = moves[i].attributes.get("@ppup", 0) or 0
            m = MOVE_DATA.get(mid, {})
            v[f"move{i}"].set(str(mid))
            v[f"move{i}_name"].set(m.get("name", "—") if mid else "—")
            v[f"movepp{i}"].set(str(pp))
            if f"moveppup{i}" in v:
                v[f"moveppup{i}"].set(str(ppup))
            v[f"move{i}_maxpp"].set(f"/{move_max_pp(mid, ppup)}" if mid else "/0")
        if "exp" in v:
            v["exp"].set(str(a.get("@exp", 0)))
        ev = _game_stats_to_display(a.get("@ev", []))
        for j, stat in enumerate(STATS):
            key = "ev_" + stat.lower()
            if key in v:
                v[key].set(str(ev[j]))

    def _open_shadow_move_chooser(self, parent, title: str, current_id: int, callback,
                                  shadow_only: bool = True, allow_none: bool = True):
        """Small move chooser used by the shadow dialog. callback(move_id), 0 = none."""
        win = self._make_popup(title, "600x460", resizable=(True, True))

        def close():
            win.destroy()
            try:
                parent.grab_set()  # hand modality back to the shadow dialog
            except tk.TclError:
                pass

        win.protocol("WM_DELETE_WINDOW", close)

        frow = ttk.Frame(win, padding=(10, 8, 10, 4))
        frow.pack(fill="x")
        ttk.Label(frow, text="Search:").pack(side="left")
        search_var = tk.StringVar()
        ent = ttk.Entry(frow, textvariable=search_var, width=22)
        ent.pack(side="left", padx=(2, 14))
        all_var = tk.BooleanVar(value=not shadow_only)
        ttk.Checkbutton(frow, text="Show all moves", variable=all_var).pack(side="left")

        tv_frame = ttk.Frame(win, padding=(10, 0, 10, 4))
        tv_frame.pack(fill="both", expand=True)
        cols = ("name", "type", "cat", "pwr", "acc", "pp")
        tree = ttk.Treeview(tv_frame, columns=cols, show="headings", height=14, selectmode="browse")
        for col, w, anch, text in [
            ("name", 170, "w", "Name"),
            ("type",  84, "center", "Type"),
            ("cat",   74, "center", "Category"),
            ("pwr",   52, "center", "Power"),
            ("acc",   58, "center", "Accuracy"),
            ("pp",    40, "center", "PP"),
        ]:
            tree.heading(col, text=text)
            tree.column(col, width=w, anchor=anch, stretch=False)
        vsb = ttk.Scrollbar(tv_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        desc_frame = ttk.LabelFrame(win, text="Description", padding=(6, 2))
        desc_frame.pack(fill="x", padx=10, pady=(0, 4))
        desc_lbl = ttk.Label(desc_frame, text="", wraplength=560, justify="left")
        desc_lbl.pack(fill="x")

        btn_row = ttk.Frame(win, padding=(10, 0, 10, 8))
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Select", command=lambda: confirm()).pack(side="right", padx=4)
        ttk.Button(btn_row, text="Cancel", command=close).pack(side="right")

        def refresh(*_):
            term = search_var.get().strip().lower()
            tree.delete(*tree.get_children())
            if allow_none:
                tree.insert("", "end", iid="0", values=("(none)", "—", "—", "—", "—", "—"))
            entries = MOVE_DATA.items() if all_var.get() else \
                [(mid, MOVE_DATA[mid]) for mid in SHADOW_MOVE_IDS]
            for mid, m in sorted(entries, key=lambda x: x[1].get("name", "").lower()):
                name = m.get("name", "")
                if term and term not in name.lower() and term not in m.get("description", "").lower():
                    continue
                tree.insert("", "end", iid=str(mid), values=(
                    name, m.get("type", ""), m.get("category", ""),
                    m.get("power", 0) or "—", m.get("accuracy", 0) or "—", m.get("pp", 0),
                ))
            if tree.exists(str(current_id)):
                tree.selection_set(str(current_id))
                tree.see(str(current_id))

        def on_select(_event=None):
            sel = tree.selection()
            if sel:
                desc_lbl.config(text=MOVE_DATA.get(int(sel[0]), {}).get("description", ""))

        def confirm(_event=None):
            sel = tree.selection()
            if not sel:
                return
            move_id = int(sel[0])
            close()
            callback(move_id)

        search_var.trace_add("write", refresh)
        all_var.trace_add("write", refresh)
        tree.bind("<<TreeviewSelect>>", on_select)
        tree.bind("<Double-1>", confirm)
        refresh()
        ent.focus_set()

    def _refresh_shadow_status(self, v):
        """Update the slot's shadow caption plus its tab / frame title marker."""
        pkmn = v.get("_pkmn_obj")
        a = pkmn.attributes if isinstance(pkmn, RubyObject) else None
        is_shadow = bool(a) and pokemon_is_shadow(a)

        if "shadow_status" in v:
            if a is None:
                v["shadow_status"].set("—")
            elif is_shadow:
                gauge = pokemon_heart_gauge(a)
                v["shadow_status"].set(f"Shadow ♥{gauge}\nstage {heart_stage(gauge)}")
            else:
                v["shadow_status"].set("Not Shadow")

        marker = "◆ " if is_shadow else ""
        title_frame = v.get("_title_frame")
        if title_frame is not None and v.get("_title_text"):
            title_frame.config(text=marker + v["_title_text"])
        tab_ref = v.get("_tab_ref")
        if tab_ref:
            notebook, index, text = tab_ref
            notebook.tab(index, text=f" {marker}{text} ")

    def _open_shadow_dialog(self, v):
        pkmn = v.get("_pkmn_obj")
        if not isinstance(pkmn, RubyObject):
            messagebox.showinfo("Shadow Pokémon", "This slot is empty.", parent=self)
            return
        a = pkmn.attributes
        species_id = a.get("@species", 0)
        species_id = species_id if isinstance(species_id, int) else 0
        name = ds(a.get("@name", b"")) or PKMN_DATA.get(species_id, {}).get("name", f"#{species_id}")

        win = self._make_popup(f"Shadow Pokemon - {name}", "560x620")
        win.title(f"Shadow Pokémon — {name}")

        head = ttk.Frame(win, padding=(12, 10, 12, 4)); head.pack(fill="x")
        state_var = tk.StringVar()
        ttk.Label(head, textvariable=state_var, font=("", 10, "bold")).pack(anchor="w")
        detail_var = tk.StringVar()
        ttk.Label(head, textvariable=detail_var, wraplength=420, justify="left").pack(anchor="w", pady=(4, 0))

        gauge_frame = ttk.LabelFrame(win, text="Heart Gauge", padding=8)
        gauge_frame.pack(fill="x", padx=12, pady=6)
        gauge_var = tk.StringVar(value=str(pokemon_heart_gauge(a)))
        stage_var = tk.StringVar()
        row = ttk.Frame(gauge_frame); row.pack(fill="x")
        ttk.Label(row, text=f"Gauge (0–{HEART_GAUGE_SIZE}):", width=18, anchor="e").pack(side="left")
        gauge_entry = ttk.Entry(row, textvariable=gauge_var, width=8)
        gauge_entry.pack(side="left", padx=4)
        ttk.Label(row, textvariable=stage_var).pack(side="left", padx=6)
        ttk.Label(gauge_frame,
                  text="The gauge counts down as you walk. At 0 the Pokémon can be\n"
                       "purified at the Relic Stone; lower stages hand back the\n"
                       "original moves one at a time.",
                  justify="left", foreground="gray").pack(anchor="w", pady=(6, 0))

        hyper_var = tk.BooleanVar(value=bool(a.get("@hypermode")))
        ttk.Checkbutton(gauge_frame, text="Hyper Mode", variable=hyper_var).pack(anchor="w", pady=(4, 0))

        moves_frame = ttk.LabelFrame(win, text="Move Sets", padding=8)
        moves_frame.pack(fill="both", expand=True, padx=12, pady=4)
        moves_var = tk.StringVar()
        ttk.Label(moves_frame, textvariable=moves_var, justify="left", wraplength=520).pack(anchor="w")

        grid = ttk.Frame(moves_frame)
        grid.pack(fill="x", pady=(6, 0))
        ttk.Label(grid, text="Shadow moves", font=("", 9, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Separator(grid, orient="vertical").grid(row=0, column=1, rowspan=6, sticky="ns", padx=10)
        ttk.Label(grid, text="Originals (returned on purify)", font=("", 9, "bold")).grid(row=0, column=2, sticky="w")
        shadow_btns, original_btns = [], []
        for i in range(4):
            sb = ttk.Button(grid, width=24)
            sb.grid(row=1 + i, column=0, sticky="w", pady=1)
            shadow_btns.append(sb)
            ob = ttk.Button(grid, width=24)
            ob.grid(row=1 + i, column=2, sticky="w", pady=1)
            original_btns.append(ob)
        copy_btn = ttk.Button(grid, text="Copy current moves")
        copy_btn.grid(row=5, column=2, sticky="w", pady=(4, 0))
        hint = ttk.Label(moves_frame, foreground="gray", wraplength=520, justify="left",
                         text="Edits here are what the game reloads whenever it resyncs shadow "
                              "moves (purification, gauge reaching 0, scents, daycare steps).")
        hint.pack(anchor="w", pady=(6, 0))

        btns = ttk.Frame(win, padding=(12, 4, 12, 10)); btns.pack(fill="x")
        make_btn   = ttk.Button(btns, text="Make Shadow")
        purify_btn = ttk.Button(btns, text="Purify")
        apply_btn  = ttk.Button(btns, text="Apply Gauge")
        make_btn.pack(side="left", padx=(0, 4))
        purify_btn.pack(side="left", padx=4)
        apply_btn.pack(side="left", padx=4)
        ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

        def move_names(ids):
            named = [MOVE_DATA.get(m, {}).get("name", f"#{m}") for m in ids if m]
            return ", ".join(named) if named else "—"

        def move_label(move_id):
            if not move_id:
                return "(none)"
            return MOVE_DATA.get(move_id, {}).get("name", f"#{move_id}")

        def choose_shadow(idx: int):
            sets = shadow_move_sets(a)
            if not sets:
                return
            shadow_set, original_set = sets

            def apply(move_id):
                new_set = list(shadow_set)
                new_set[idx] = move_id
                if not any(new_set):
                    messagebox.showinfo(
                        "Shadow moves",
                        "A Shadow Pokémon needs at least one Shadow move — with none "
                        "stored, a full heart gauge would leave it with no moves at all.",
                        parent=win,
                    )
                    return
                set_shadow_move_sets(a, new_set, original_set)
                refresh()

            self._open_shadow_move_chooser(
                win, f"Shadow move {idx + 1}", shadow_set[idx], apply, shadow_only=True)

        def choose_original(idx: int):
            sets = shadow_move_sets(a)
            if not sets:
                return
            shadow_set, original_set = sets

            def apply(move_id):
                new_set = list(original_set)
                new_set[idx] = move_id
                set_shadow_move_sets(a, shadow_set, new_set)
                refresh()

            self._open_shadow_move_chooser(
                win, f"Original move {idx + 1}", original_set[idx], apply, shadow_only=False)

        def copy_current():
            sets = shadow_move_sets(a)
            if not sets:
                return
            shadow_set, _ = sets
            current = pokemon_move_ids(a)
            overlap = [m for m in current if m and m in shadow_set]
            if overlap:
                if not messagebox.askyesno(
                    "Copy current moves",
                    f"{move_names(overlap)} {'is a Shadow move' if len(overlap) == 1 else 'are Shadow moves'} "
                    "and would be stored as an original, so purification would keep it.\n\nStore them anyway?",
                    parent=win,
                ):
                    return
            set_shadow_move_sets(a, shadow_set, current)
            refresh()

        def refresh(sync: bool = True):
            is_shadow = pokemon_is_shadow(a)
            gauge = pokemon_heart_gauge(a)
            state_var.set("Shadow Pokémon" if is_shadow else "Not a Shadow Pokémon")
            stage_var.set(f"stage {heart_stage(gauge)} of 5")
            gauge_var.set(str(gauge))
            hyper_var.set(bool(a.get("@hypermode")))
            sets = shadow_move_sets(a)
            lines = [f"Current moves: {move_names(pokemon_move_ids(a))}"]
            if not sets:
                lines.append(f"Would gain: {move_names(shadow_moves_for_species(species_id))}")
            moves_var.set("\n".join(lines))

            shadow_set, original_set = sets if sets else ([0] * 4, [0] * 4)
            for i in range(4):
                shadow_btns[i].configure(text=move_label(shadow_set[i]),
                                         command=lambda idx=i: choose_shadow(idx))
                original_btns[i].configure(text=move_label(original_set[i]),
                                           command=lambda idx=i: choose_original(idx))
                shadow_btns[i].state(["!disabled"] if sets else ["disabled"])
                original_btns[i].state(["!disabled"] if sets else ["disabled"])
            copy_btn.configure(command=copy_current)
            copy_btn.state(["!disabled"] if sets else ["disabled"])
            if is_shadow:
                saved_ev = a.get("@savedev") or [0] * 6
                saved_ev = [x if isinstance(x, int) else 0 for x in saved_ev]
                detail_var.set(
                    f"EXP held back: {a.get('@savedexp', 0) or 0}   "
                    f"EVs held back: {sum(saved_ev)}\n"
                    "While shadow, EXP and EVs are stored instead of applied, "
                    "and the summary screen hides nature and IVs above stage 3."
                )
            else:
                detail_var.set(
                    "Making this a Shadow Pokémon fills the heart gauge, swaps in its "
                    "Shadow moves and stores the current ones until purification."
                )
            make_btn.state(["disabled"] if is_shadow else ["!disabled"])
            purify_btn.state(["!disabled"] if is_shadow else ["disabled"])
            apply_btn.state(["!disabled"] if is_shadow else ["disabled"])
            gauge_entry.state(["!disabled"] if is_shadow else ["disabled"])
            self._refresh_shadow_status(v)
            # Only pull the slot's vars back from the object once this dialog has
            # actually rewritten it — otherwise merely opening the dialog would
            # discard move/EV/EXP edits the user has made but not saved yet.
            if sync:
                self._sync_slot_vars_from_obj(v)

        def do_make():
            make_shadow(a)
            refresh()

        def do_purify():
            restored = purify(a)
            refresh()
            bits = []
            if restored["moves"]:
                bits.append("Regained " + move_names(restored["moves"]) + ".")
            if restored["exp"]:
                bits.append(f"Regained {restored['exp']} Exp. Points.")
            if any(restored["ev"]):
                bits.append(f"Regained {sum(restored['ev'])} EVs.")
            bits.append("Stats are not recalculated — adjust them or level the Pokémon in game.")
            messagebox.showinfo(f"{name} was purified", "\n".join(bits), parent=win)

        def do_apply_gauge():
            try:
                value = int(gauge_var.get() or 0)
            except ValueError:
                messagebox.showerror("Heart Gauge", "Enter a whole number.", parent=win)
                return
            set_heart_gauge(a, value)
            a["@hypermode"] = bool(hyper_var.get()) and pokemon_heart_gauge(a) > 0
            refresh()

        make_btn.configure(command=do_make)
        purify_btn.configure(command=do_purify)
        apply_btn.configure(command=do_apply_gauge)
        refresh(sync=False)

    def _open_pkmn_picker(self, callback):
        win = self._make_popup("Select Pokemon", "700x600")
        win.title("Select Pokémon")
        self._center_popup(win)

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
        f.rowconfigure(2, weight=1)

        hint = "Items are grouped by bag pocket. Use Change to swap an item, or i for source details."
        ttk.Label(f, text=hint, foreground="gray", padding=(4, 4)).grid(
            row=0, column=0, columnspan=2, sticky="w")

        add_frame = ttk.LabelFrame(f, text="Add item", padding=(8, 5))
        add_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 4))
        self._add_item_id = tk.StringVar()
        self._add_qty = tk.StringVar(value="99")
        self._add_item_name = tk.StringVar(value="Choose an item...")
        self._add_button_text = tk.StringVar(value=bag_add_button_text(self._add_qty.get()))
        ttk.Label(
            add_frame, textvariable=self._add_item_name, width=28,
            anchor="w", relief="sunken",
        ).pack(side="left", padx=(0, 4))
        ttk.Entry(add_frame, textvariable=self._add_qty, width=6).pack(side="left", padx=(0, 4))
        ttk.Button(
            add_frame, text="Browse...",
            command=lambda: self._open_item_picker(self._add_item_id, self._add_item_name),
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            add_frame, textvariable=self._add_button_text,
            command=self._add_bag_item,
        ).pack(side="left")
        self._add_qty.trace_add(
            "write",
            lambda *_: self._add_button_text.set(bag_add_button_text(self._add_qty.get())),
        )

        canvas = tk.Canvas(f, highlightthickness=0)
        sb = ttk.Scrollbar(f, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.grid(row=2, column=0, sticky="nsew")
        sb.grid(row=2, column=1, sticky="ns")

        self.bag_inner = ttk.Frame(canvas)
        win = canvas.create_window((0, 0), window=self.bag_inner, anchor="nw")
        self.bag_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self._make_scrollable(canvas)
        self.bag_canvas = canvas

    def _populate_bag(self):
        for w in self.bag_inner.winfo_children():
            w.destroy()
        self.bag_rows = []
        if hasattr(self, "_add_item_id"):
            self._add_item_id.set("")
            self._add_item_name.set("Choose an item...")
            self._add_qty.set("99")

        if not isinstance(self.bag, RubyObject):
            ttk.Label(self.bag_inner, text="No bag data found.").pack(); return

        pockets = self.bag.attributes.get("@pockets", [])
        pocket_list = pockets if isinstance(pockets, list) else list(pockets.values())

        grid_row = 0
        for pi, pocket in enumerate(pocket_list):
            pname = POCKET_NAMES[pi] if pi < len(POCKET_NAMES) else f"Pocket {pi}"
            if not isinstance(pocket, list) or not pocket:
                continue
            header = ttk.Frame(self.bag_inner, padding=(4, 5, 4, 1))
            header.grid(row=grid_row, column=0, columnspan=5, sticky="ew")
            ttk.Label(header, text=pname, font=("", 10, "bold")).pack(side="left")
            ttk.Label(header, text=f"{len(pocket)} item slots", foreground="gray").pack(side="left", padx=6)
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
                icon_label.grid(row=grid_row, column=0, padx=(4, 1), pady=0)

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
                info_btn.grid(row=grid_row, column=1, padx=(0, 2), pady=0)

                ttk.Label(self.bag_inner, textvariable=name_var, anchor="w").grid(
                    row=grid_row, column=2, padx=(0, 2), pady=0, sticky="w")
                ttk.Entry(self.bag_inner, textvariable=qty_var, width=6).grid(
                    row=grid_row, column=3, padx=2, pady=0)
                ttk.Button(self.bag_inner, text="Change", width=7,
                           command=lambda iv=id_var, nv=name_var: self._open_item_picker(iv, nv)).grid(
                    row=grid_row, column=4, padx=(2, 4), pady=0)

                self.bag_rows.append((pi, ei, id_var, qty_var))
                grid_row += 1

    def _add_bag_item(self):
        if not isinstance(self.bag, RubyObject):
            messagebox.showerror("No bag loaded", "Load a save file with bag data first.", parent=self)
            return
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
        self.bag_canvas.yview_moveto(0.0)
        name = item_display_name(internet_id)
        pocket_name = POCKET_NAMES[pi] if pi < len(POCKET_NAMES) else "bag"
        self.status.config(text=f"Added: {name} x{qty} to {pocket_name} - click Save to write.",
                           foreground="blue")

    def _open_item_picker(self, id_var=None, name_var=None, current_id=None, on_select=None):
        dlg = self._make_popup("Item Browser", "920x600", resizable=(True, True))
        dlg.columnconfigure(0, weight=1)
        dlg.rowconfigure(1, weight=1)

        # ── filter row ──────────────────────────────────────────────────────
        top = ttk.Frame(dlg, padding=(8, 8, 8, 4))
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="Pocket:").pack(side="left")
        cat_var = tk.StringVar(value="All")
        ttk.Combobox(top, textvariable=cat_var, values=ITEM_CAT_LIST,
                     width=14, state="readonly").pack(side="left", padx=(4, 12))
        ttk.Label(top, text="Search:").pack(side="left")
        search_var = tk.StringVar()
        search_entry = ttk.Entry(top, textvariable=search_var, width=22)
        search_entry.pack(side="left", padx=4)
        count_lbl = ttk.Label(top, text="", foreground="gray")
        count_lbl.pack(side="right", padx=8)

        # ── treeview ────────────────────────────────────────────────────────
        tf = ttk.Frame(dlg)
        tf.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 4))
        tf.columnconfigure(0, weight=1)
        tf.rowconfigure(0, weight=1)

        style = ttk.Style()
        style.configure("ItemBrowser.Treeview", rowheight=32)

        cols = ("desc", "pocket", "price", "id")
        tree = ttk.Treeview(tf, columns=cols, show="tree headings",
                            selectmode="browse", style="ItemBrowser.Treeview")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        tree.column("#0",     width=185, minwidth=120, stretch=False, anchor="w")
        tree.column("desc",   width=340, minwidth=120, stretch=True,  anchor="w")
        tree.column("pocket", width=105, minwidth=80,  stretch=False, anchor="w")
        tree.column("price",  width=72,  minwidth=50,  stretch=False, anchor="e")
        tree.column("id",     width=58,  minwidth=48,  stretch=False, anchor="e")

        # ── sort state ──────────────────────────────────────────────────────
        sort_state  = {"col": "#0", "rev": False}
        _images: dict = {}
        refresh_state = {"token": 0}

        COL_LABELS = {
            "#0": "Name", "desc": "Description", "pocket": "Pocket",
            "price": "Price", "id": "ID",
        }

        def _apply_headings():
            for c, lbl in COL_LABELS.items():
                ind = (" ▲" if not sort_state["rev"] else " ▼") if c == sort_state["col"] else ""
                tree.heading(c, text=lbl + ind, command=lambda col=c: _sort(col))

        def _sort(col):
            if sort_state["col"] == col:
                sort_state["rev"] = not sort_state["rev"]
            else:
                sort_state["col"] = col
                sort_state["rev"] = False
            _refresh()

        def _refresh(*_, preselect=""):
            refresh_state["token"] += 1
            token = refresh_state["token"]
            cat = cat_var.get()
            q   = search_var.get().strip().lower()
            items = [d for d in ITEM_DATA.values()
                     if (cat == "All" or d.get("pocket") == cat)
                     and (not q or q in d["name"].lower()
                          or q in d.get("description", "").lower()
                          or q == str(d.get("source_id", ""))
                          or q == str(d.get("id", "")))]

            col, rev = sort_state["col"], sort_state["rev"]
            if col in ("#0", "desc"):
                items.sort(key=lambda d: d["name"].lower(), reverse=rev)
            elif col == "pocket":
                items.sort(key=lambda d: (d.get("pocket", ""), d["name"].lower()), reverse=rev)
            elif col == "price":
                items.sort(key=lambda d: (d.get("price", 0), d["name"].lower()), reverse=rev)
            elif col == "id":
                items.sort(key=lambda d: (d.get("source_id", 0), d["name"].lower()), reverse=rev)

            tree.delete(*tree.get_children())
            _images.clear()
            count_lbl.configure(text=f"Loading {len(items)} items...")
            _apply_headings()

            def _insert_batch(start=0):
                if token != refresh_state["token"] or not tree.winfo_exists():
                    return
                for d in items[start:start + 80]:
                    iid  = d["id"]
                    icon = self._load_item_icon(iid, max_size=24)
                    _images[iid] = icon
                    desc = d.get("description", "")
                    if len(desc) > 70:
                        desc = desc[:69] + "..."
                    price = d.get("price", 0)
                    tree.insert("", tk.END, iid=str(iid), text=" " + d["name"],
                                image=icon or "",
                                values=(desc, d.get("pocket", ""),
                                        f"₽{price:,}" if price else "—",
                                        d.get("source_id", 0)))
                next_start = start + 80
                count_lbl.configure(text=f"{min(next_start, len(items))}/{len(items)} items")
                if next_start < len(items):
                    dlg.after(10, lambda: _insert_batch(next_start))
                    return
                count_lbl.configure(text=f"{len(items)} items")
                if preselect and tree.exists(preselect):
                    tree.selection_set(preselect)
                    tree.see(preselect)

            _insert_batch()

        try:
            cur = str(int(current_id if current_id is not None else id_var.get()))
        except (AttributeError, ValueError, TypeError):
            cur = ""

        def _initial_refresh():
            _refresh(preselect=cur)

        search_var.trace_add("write", _refresh)
        cat_var.trace_add("write", _refresh)
        search_var.trace_add("write", _refresh)
        tree.insert("", tk.END, iid="_loading", text=" Loading items...")
        count_lbl.configure(text="Loading...")
        dlg.after(1, _initial_refresh)

        # ── buttons ─────────────────────────────────────────────────────────
        bf = ttk.Frame(dlg, padding=(8, 0, 8, 8))
        bf.grid(row=2, column=0, sticky="ew")

        def do_select(*_):
            sel = tree.selection()
            if not sel:
                return
            iid = int(sel[0])
            if id_var is not None:
                id_var.set(str(iid))
            if name_var is not None:
                name_var.set(ITEM_DATA.get(iid, {}).get("name", item_display_name(iid)))
            if on_select is not None:
                on_select(iid)
            dlg.destroy()

        tree.bind("<Double-Button-1>", do_select)
        tree.bind("<Return>",          do_select)
        dlg.bind("<Escape>",           lambda _: dlg.destroy())
        ttk.Button(bf, text="Select", width=10, command=do_select).pack(side="left", padx=4)
        ttk.Button(bf, text="Cancel", width=10, command=dlg.destroy).pack(side="left", padx=4)

        search_entry.focus_set()

    # ── PC Boxes tab ─────────────────────────────────────────────────────────

    def _build_boxes_tab(self):
        f = self.tab_boxes
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)
        self.boxes_nb = ttk.Notebook(f)
        self.boxes_nb.grid(row=0, column=0, sticky="nsew")
        self.boxes_nb.bind("<<NotebookTabChanged>>", lambda _event: self._render_selected_box_tab())

    def _on_main_tab_changed(self):
        if hasattr(self, "tab_boxes") and self.nb.select() == str(self.tab_boxes):
            self._render_selected_box_tab()

    def _show_boxes_message(self, message: str):
        """Replace the box tabs with one explaining why there is nothing to show.

        Without this the tab is simply empty, which looks like a broken build
        rather than a save the editor could not read.
        """
        holder = ttk.Frame(self.boxes_nb, padding=24)
        self.boxes_nb.add(holder, text=" PC Storage ")
        ttk.Label(holder, text=message, justify="left", wraplength=760).pack(anchor="w")

    def _populate_boxes(self):
        for tab in self.boxes_nb.tabs():
            self.boxes_nb.forget(tab)
        self.box_vars = {}
        self._box_tab_meta = {}
        self._box_render_order = []

        if not isinstance(self.storage, RubyObject):
            reason = getattr(self, "storage_error", "") or "the PokemonStorage stream was not found"
            self._show_boxes_message(
                "The PC storage in this save could not be read, so there are no boxes to edit.\n\n"
                f"Reason: {reason}\n\n"
                "Everything else in the save (Trainer, Party, Bag) is still editable, and saving "
                "leaves the PC storage bytes untouched.")
            return
        boxes = self.storage.attributes.get("@boxes", [])
        if not isinstance(boxes, list) or not any(isinstance(b, RubyObject) for b in boxes):
            self._show_boxes_message("This save has no PC boxes yet.")
            return

        for bi, box in enumerate(boxes):
            if not isinstance(box, RubyObject): continue
            box_name = ds(box.attributes.get("@name", f"Box {bi+1}"))

            outer = ttk.Frame(self.boxes_nb, padding=4)
            outer.columnconfigure(0, weight=1)
            outer.rowconfigure(0, weight=1)
            self.boxes_nb.add(outer, text=f" {box_name[:10]} ")
            self._box_tab_meta[str(outer)] = {"bi": bi, "box": box, "outer": outer, "rendered": False}

        current_box = self.storage.attributes.get("@currentBox", 0)
        tab_idx = self._box_tab_index_for_box(current_box)
        tabs = self.boxes_nb.tabs()
        if tabs:
            self._suspend_box_render = True
            self.boxes_nb.select(tabs[min(tab_idx, len(tabs) - 1)])
            self._suspend_box_render = False
            if hasattr(self, "nb") and self.nb.select() == str(self.tab_boxes):
                self._render_selected_box_tab()

    def _box_tab_index_for_box(self, box_idx: int) -> int:
        if not isinstance(self.storage, RubyObject):
            return 0
        boxes = self.storage.attributes.get("@boxes", [])
        if not isinstance(boxes, list):
            return 0
        try:
            box_idx = int(box_idx)
        except (TypeError, ValueError):
            return 0
        return sum(1 for j in range(max(0, box_idx)) if j < len(boxes) and isinstance(boxes[j], RubyObject))

    def _select_box_tab(self, box_idx: int):
        tabs = self.boxes_nb.tabs()
        if not tabs:
            return
        tab_idx = min(self._box_tab_index_for_box(box_idx), len(tabs) - 1)
        self.boxes_nb.select(tabs[tab_idx])
        self._render_selected_box_tab()

    def _render_selected_box_tab(self):
        if self._suspend_box_render:
            return
        selected = self.boxes_nb.select()
        if not selected:
            return
        meta = self._box_tab_meta.get(selected)
        if not meta:
            return
        if meta.get("rendered"):
            if selected in self._box_render_order:
                self._box_render_order.remove(selected)
            self._box_render_order.append(selected)
            return
        # Keep only two heavy box widget trees alive. Persist their UI values to
        # the in-memory Ruby objects before eviction, so resizing never has to
        # lay out hundreds of hidden searchable combos.
        if len(self._box_render_order) >= 2:
            self._apply_boxes()
            stale = self._box_render_order.pop(0)
            stale_meta = self._box_tab_meta.get(stale)
            if stale_meta:
                for child in stale_meta["outer"].winfo_children(): child.destroy()
                stale_meta["rendered"] = False
                self.box_vars.pop(stale_meta["bi"], None)
        self._render_box_tab(meta)
        self._box_render_order.append(selected)

    def _rerender_box(self, box_idx: int):
        tab_idx = self._box_tab_index_for_box(box_idx)
        tabs = self.boxes_nb.tabs()
        if tab_idx >= len(tabs):
            self._populate_boxes()
            return
        meta = self._box_tab_meta.get(tabs[tab_idx])
        if not meta:
            self._populate_boxes()
            return
        meta["rendered"] = False
        self.box_vars.pop(meta["bi"], None)
        self._render_box_tab(meta)
        self._select_box_tab(box_idx)

    def _render_box_tab(self, meta: dict):
        bi = meta["bi"]
        box = meta["box"]
        outer = meta["outer"]
        for child in outer.winfo_children():
            child.destroy()
        meta["rendered"] = True
        pokemon_list = box.attributes.get("@pokemon", [])

        canvas = tk.Canvas(outer, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        hsb = ttk.Scrollbar(outer, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=sb.set, xscrollcommand=hsb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        inner = ttk.Frame(canvas)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda _e, c=canvas: c.configure(scrollregion=c.bbox("all")))
        # Slot rows are wide; stretch them to the canvas when there is room and
        # let the horizontal scrollbar take over when there isn't, so the right
        # hand panels can never be clipped away.
        canvas.bind("<Configure>",
                    lambda e, c=canvas, w=win, f=inner: c.itemconfig(w, width=max(e.width, f.winfo_reqwidth())))
        self._make_scrollable(canvas)

        slot_vars = []
        for si, pkmn in enumerate(pokemon_list):
            if not isinstance(pkmn, RubyObject):
                ef = ttk.LabelFrame(inner, text=f"Slot {si}: Empty", padding=4)
                ef.pack(fill="x", pady=2, padx=2)
                ttk.Button(
                    ef,
                    text="+ Add Pokemon",
                    command=lambda b=bi, s=si, bx=box: self._add_to_box_slot(b, s, bx),
                ).pack(padx=4, pady=2)
                slot_vars.append(None)
                continue

            a = pkmn.attributes
            nick = ds(a.get("@name", b""))
            sp = a.get("@species", "?")
            pid = a.get("@personalID", 0) or 0

            label = f"Slot {si}: {nick or f'Species#{sp}'}  [#{sp}]"
            sf = ttk.LabelFrame(inner, text=("◆ " + label) if pokemon_is_shadow(a) else label, padding=4)
            sf.pack(fill="x", pady=2, padx=2)

            sv = {}
            # Held Item is the widest row in the slot, so it must not take part in
            # sizing anything.  It is a child of the slot frame positioned with
            # place() just under the Species-to-Ability column: placed widgets
            # contribute nothing to their master's requested size, so the column
            # keeps its own width and the control simply overlaps to the right.
            # The bottom padding on lp reserves the vertical room it needs.
            lp = ttk.Frame(sf); lp.pack(side="left", padx=4, anchor="n", pady=(0, 34))
            hp_ = ttk.Frame(sf)
            rp = ttk.Frame(sf); rp.pack(side="left", padx=4, anchor="n")
            ip = ttk.Frame(sf); ip.pack(side="left", padx=4, anchor="n")
            bp = ttk.Frame(sf); bp.pack(side="left", padx=4, fill="y")

            for i, (key, lbl, val) in enumerate([
                ("species_id", "Species ID", str(sp)),
                ("form", "Form ID", str(pokemon_form(a))),
                ("nickname", "Nickname", nick),
                ("hp", "HP", str(a.get("@hp", 0))),
                ("totalhp", "Max HP", str(a.get("@totalhp", 0))),
            ]):
                sv[key] = tk.StringVar(value=val)
                ttk.Label(lp, text=lbl + ":", width=12, anchor="e").grid(row=i, column=0, sticky="e", pady=1)
                if key == "species_id":
                    sv["species_search"] = tk.StringVar(value=self._species_label(int(sp)))
                    species_choices = self._species_choices
                    combo = self._make_search_combo(
                        lp, sv["species_search"], species_choices,
                        lambda value, vv=sv: self._select_species(vv, value), 24,
                        current_label=lambda vv=sv: self._current_species_label(vv))
                    combo.grid(row=i, column=1, sticky="w", pady=1, padx=2)
                elif key == "form":
                    sv["form_combo"] = ttk.Combobox(lp, textvariable=sv[key], values=["0 - Default"], width=18, state="readonly")
                    sv["form_combo"].grid(row=i, column=1, sticky="w", pady=1, padx=2)
                    sv["form_combo"].bind("<<ComboboxSelected>>", lambda _event, vv=sv: self._schedule_recalculate(vv, True))
                else:
                    ttk.Entry(lp, textvariable=sv[key], width=8).grid(row=i, column=1, sticky="w", pady=1, padx=2)
            self._set_form_value(sv, sp if isinstance(sp, int) else 0, pokemon_form(a))
            sv["species_id"].trace_add("write", lambda *_args, vv=sv: self._manual_species_changed(vv))

            sv["item"] = tk.StringVar(value=str(a.get("@item", 0)))
            self._make_held_item_control(hp_, sv, row=0, label_width=12, compact=True)
            # Anchored to lp's bottom-left, but owned by the slot frame, so it can
            # run past lp's right edge without widening it.
            hp_.place(in_=lp, relx=0.0, rely=1.0, y=6, anchor="nw")
            for i, (key, lbl, val) in enumerate([
                ("happiness", "Happiness", str(a.get("@happiness", 0))),
                ("status", "Status", str(a.get("@status", 0))),
                ("level", "Level", str(_level_for_exp(PKMN_DATA.get(int(sp), {}).get("growth", "medium-fast"), a.get("@exp", 0)))),
                ("exp", "Exp", str(a.get("@exp", 0))),
            ], start=0):
                sv[key] = tk.StringVar(value=val)
                ttk.Label(rp, text=lbl + ":", width=12, anchor="e").grid(row=i, column=0, sticky="e", pady=1)
                ttk.Entry(rp, textvariable=sv[key], width=8).grid(row=i, column=1, sticky="w", pady=1, padx=2)
            sv["ball"] = tk.StringVar(value=str(a.get("@ballused", 0)))
            self._make_ball_control(rp, sv, row=4, label_width=12, compact=True)
            sv["obtain_lv"] = tk.StringVar(value=str(a.get("@obtainLevel", 0)))
            ttk.Label(rp, text="Obtained Lv:", width=12, anchor="e").grid(row=5, column=0, sticky="e", pady=1)
            ttk.Entry(rp, textvariable=sv["obtain_lv"], width=8).grid(row=5, column=1, sticky="w", pady=1, padx=2)

            sv["nature_idx"] = tk.StringVar(value=NATURE_CHOICES[pokemon_nature(a)])
            sv["gender"] = tk.StringVar(value=pokemon_gender(a))
            sv["shiny"] = tk.BooleanVar(value=pokemon_is_shiny(a, self.trainer_id, self.secret_id))
            ability_flag = a.get("@abilityflag")
            selected_ability_slot = ability_flag if isinstance(ability_flag, int) else pid & 1
            # Identity fields continue the left column, under Max HP, instead of
            # claiming a column of their own.
            sv["ability_slot"] = tk.StringVar()
            ttk.Label(lp, text="Nature:", anchor="e", width=12).grid(row=5, column=0, sticky="e", pady=1)
            ttk.Combobox(lp, textvariable=sv["nature_idx"], values=NATURE_CHOICES, width=22,
                         state="readonly").grid(row=5, column=1, sticky="w", padx=2, pady=1)
            ttk.Label(lp, text="Gender:", anchor="e", width=12).grid(row=6, column=0, sticky="e", pady=1)
            sv["gender_combo"] = ttk.Combobox(
                lp, textvariable=sv["gender"], values=gender_choices_for_species(sp), width=9, state="readonly"
            )
            sv["gender_combo"].grid(row=6, column=1, sticky="w", padx=2, pady=1)
            ttk.Label(lp, text="Shiny:", anchor="e", width=12).grid(row=7, column=0, sticky="e", pady=1)
            ttk.Checkbutton(lp, variable=sv["shiny"]).grid(row=7, column=1, sticky="w", padx=2, pady=1)
            ttk.Label(lp, text="Ability:", anchor="e", width=12).grid(row=8, column=0, sticky="e", pady=1)
            sv["ability_combo"] = ttk.Combobox(
                lp, textvariable=sv["ability_slot"], values=[], width=18, state="readonly"
            )
            sv["ability_combo"].grid(row=8, column=1, sticky="w", padx=2, pady=1)
            self._set_ability_value(sv, selected_ability_slot)
            self._remember_identity_values(sv)

            iv = a.get("@iv", [])
            ev = a.get("@ev", [])
            display_iv = _game_stats_to_display(iv)
            display_ev = _game_stats_to_display(ev)
            ttk.Label(ip, text="IVs:", font=("", 8, "bold")).grid(row=0, column=0, columnspan=6)
            ttk.Label(ip, text="EVs:", font=("", 8, "bold")).grid(row=3, column=0, columnspan=6, pady=(4, 0))
            for j, stat in enumerate(STATS):
                key = stat.lower()
                sv["iv_" + key] = tk.StringVar(value=str(display_iv[j]))
                sv["ev_" + key] = tk.StringVar(value=str(display_ev[j]))
                ttk.Label(ip, text=stat, width=4).grid(row=1, column=j)
                ttk.Entry(ip, textvariable=sv["iv_" + key], width=3).grid(row=2, column=j)
                ttk.Label(ip, text=stat, width=4).grid(row=4, column=j)
                ttk.Entry(ip, textvariable=sv["ev_" + key], width=3).grid(row=5, column=j)

            # Battle stats — same fields the party tab exposes, kept compact.
            ttk.Label(ip, text="Stats:", font=("", 8, "bold")).grid(row=6, column=0, columnspan=6, pady=(4, 0))
            for j, (key, attr, lbl) in enumerate([
                ("attack", "@attack", "Atk"),
                ("defense", "@defense", "Def"),
                ("spatk", "@spatk", "SpA"),
                ("spdef", "@spdef", "SpD"),
                ("speed", "@speed", "Spe"),
            ]):
                sv[key] = tk.StringVar(value=str(a.get(attr, 0)))
                ttk.Label(ip, text=lbl, width=4).grid(row=7, column=j)
                ttk.Entry(ip, textvariable=sv[key], width=4).grid(row=8, column=j)

            sv["_pkmn_obj"] = pkmn
            sv["shadow_status"] = tk.StringVar()
            sv["_title_frame"] = sf
            sv["_title_text"] = label
            quick = ttk.LabelFrame(bp, text="Quick Actions", padding=4)
            quick.pack(fill="x", pady=(0, 4))
            ttk.Button(quick, text="31 All IVs", width=10, command=lambda vv=sv: self._max_ivs(vv)).pack(pady=2)
            ttk.Button(quick, text="Build Library", width=10, command=lambda vv=sv: self._open_build_dialog(vv)).pack(pady=2)
            ttk.Separator(quick, orient="horizontal").pack(fill="x", pady=4)
            ttk.Button(quick, text="Shadow…", width=10,
                       command=lambda vv=sv: self._open_shadow_dialog(vv)).pack(pady=2)
            ttk.Label(quick, textvariable=sv["shadow_status"], width=12,
                      anchor="center", justify="center").pack(pady=(0, 2))
            self._refresh_shadow_status(sv)
            manage = ttk.LabelFrame(bp, text="Manage", padding=4)
            manage.pack(fill="x")
            ttk.Button(manage, text="Move", width=10, command=lambda b=bi, s=si, bx=box, pk=pkmn: self._move_box_pokemon(b, s, bx, pk)).pack(pady=2)
            ttk.Button(manage, text="Delete", width=10, style="Danger.TButton",
                       command=lambda b=bi, s=si, bx=box: self._delete_box_pokemon(b, s, bx)).pack(pady=2)

            dp = self._make_pokemon_dex_panel(
                sf, sp if isinstance(sp, int) else 0, pokemon_form(a),
                compact=True, ability_slot_var=sv["ability_slot"], pkmn=pkmn,
                slot_vars=sv,
            )

            mp = ttk.LabelFrame(sf, text="Moves", padding=4)
            mp.pack(side="left", padx=4, fill="y")
            box_moves = a.get("@moves", [])
            for i in range(4):
                mid, bm = 0, {}
                sv[f"move{i}"] = tk.StringVar(value="0")
                sv[f"move{i}_name"] = tk.StringVar(value="-")
                sv[f"movepp{i}"] = tk.StringVar(value="0")
                sv[f"moveppup{i}"] = tk.StringVar(value="0")
                sv[f"move{i}_maxpp"] = tk.StringVar(value="/0")
                if isinstance(box_moves, list) and i < len(box_moves) and isinstance(box_moves[i], RubyObject):
                    mid = box_moves[i].attributes.get("@id", 0)
                    pp = box_moves[i].attributes.get("@pp", 0)
                    ppup = box_moves[i].attributes.get("@ppup", 0)
                    bm = MOVE_DATA.get(mid, {})
                    sv[f"move{i}"].set(str(mid))
                    sv[f"move{i}_name"].set(bm.get("name", "-") if mid else "-")
                    sv[f"movepp{i}"].set(str(pp))
                    sv[f"moveppup{i}"].set(str(ppup))
                    sv[f"move{i}_maxpp"].set(f"/{move_max_pp(mid, ppup)}" if mid else "/0")
                rf2 = ttk.Frame(mp)
                rf2.pack(fill="x", pady=1)
                ttk.Label(rf2, text=f"{i+1}:", width=2).pack(side="left")
                ttk.Label(rf2, textvariable=sv[f"move{i}_name"], width=14, relief="sunken", anchor="w").pack(side="left", padx=2)
                ttk.Button(rf2, text="Search…", width=7, command=lambda vv=sv, ii=i: self._change_move(vv, ii)).pack(side="left", padx=2)
                ttk.Label(rf2, text="PP:", width=3).pack(side="left")
                ttk.Entry(rf2, textvariable=sv[f"movepp{i}"], width=4).pack(side="left")
                ttk.Label(rf2, textvariable=sv[f"move{i}_maxpp"], width=4, anchor="w").pack(side="left")
                ttk.Label(rf2, text="Ups:", width=4).pack(side="left")
                ttk.Spinbox(rf2, from_=0, to=3, textvariable=sv[f"moveppup{i}"], width=3).pack(side="left")
                sv[f"moveppup{i}"].trace_add("write", lambda *_args, vv=sv, ii=i: self._refresh_move_pp_display(vv, ii))

            ttk.Button(mp, text="Max all PP Ups", command=lambda vv=sv: self._max_pp_ups(vv)).pack(anchor="w", pady=(4, 0))
            dp.pack(side="left", padx=4, fill="y")

            sv["level"].trace_add("write", lambda *_args, vv=sv: self._sync_exp_from_level(vv))
            sv["exp"].trace_add("write", lambda *_args, vv=sv: self._sync_level_from_exp(vv))
            sv["nature_idx"].trace_add("write", lambda *_args, vv=sv: self._schedule_recalculate(vv))
            for stat in STATS:
                sv["iv_" + stat.lower()].trace_add("write", lambda *_args, vv=sv: self._schedule_recalculate(vv))
                sv["ev_" + stat.lower()].trace_add("write", lambda *_args, vv=sv: self._schedule_recalculate(vv))
            slot_vars.append((si, sv))

        self.box_vars[bi] = (bi, box, slot_vars)

    # ── pokemon picker / add ─────────────────────────────────────────────────

    def _open_pokemon_picker(self, callback):
        dlg = self._make_popup("Pokemon Browser", "920x600", resizable=(True, True))
        dlg.title("Pokémon Browser")
        self._center_popup(dlg)
        dlg.columnconfigure(0, weight=1)
        dlg.rowconfigure(1, weight=1)

        # ── filter row ──────────────────────────────────────────────────────
        top = ttk.Frame(dlg, padding=(8, 8, 8, 4))
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="Search:").pack(side="left")
        search_var = tk.StringVar()
        search_entry = ttk.Entry(top, textvariable=search_var, width=16)
        search_entry.pack(side="left", padx=(4, 12))
        ttk.Label(top, text="Type:").pack(side="left")
        type_var = tk.StringVar(value="All")
        ttk.Combobox(top, textvariable=type_var, values=["All"] + POKEMON_TYPES,
                     width=10, state="readonly").pack(side="left", padx=(4, 8))
        ttk.Label(top, text="Stage:").pack(side="left")
        stage_var = tk.StringVar(value="All")
        ttk.Combobox(top, textvariable=stage_var, values=PKMN_STAGE_LIST,
                     width=6, state="readonly").pack(side="left", padx=(4, 8))
        ttk.Label(top, text="Rarity:").pack(side="left")
        rarity_var = tk.StringVar(value="All")
        ttk.Combobox(top, textvariable=rarity_var, values=PKMN_RARITY_LIST,
                     width=10, state="readonly").pack(side="left", padx=(4, 8))
        count_lbl = ttk.Label(top, text="", foreground="gray")
        count_lbl.pack(side="right", padx=8)

        # ── treeview ────────────────────────────────────────────────────────
        tf = ttk.Frame(dlg)
        tf.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 4))
        tf.columnconfigure(0, weight=1)
        tf.rowconfigure(0, weight=1)

        style = ttk.Style()
        style.configure("PkmnBrowser.Treeview", rowheight=32)

        cols = ("sid", "types", "stage", "rarity", "bst")
        tree = ttk.Treeview(tf, columns=cols, show="tree headings",
                            selectmode="browse", style="PkmnBrowser.Treeview")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        tree.column("#0",     width=170, minwidth=100, stretch=True,  anchor="w")
        tree.column("sid",    width=50,  minwidth=40,  stretch=False, anchor="e")
        tree.column("types",  width=112, minwidth=80,  stretch=False, anchor="w")
        tree.column("stage",  width=58,  minwidth=45,  stretch=False, anchor="center")
        tree.column("rarity", width=82,  minwidth=65,  stretch=False, anchor="w")
        tree.column("bst",    width=52,  minwidth=40,  stretch=False, anchor="e")

        # ── sort state ──────────────────────────────────────────────────────
        sort_state = {"col": "sid", "rev": False}
        _sprites: dict = {}
        refresh_state = {"token": 0}

        COL_LABELS = {"#0": "Name", "sid": "#", "types": "Type(s)",
                      "stage": "Stage", "rarity": "Rarity", "bst": "BST"}

        def _apply_headings():
            for c, lbl in COL_LABELS.items():
                ind = (" ▲" if not sort_state["rev"] else " ▼") if c == sort_state["col"] else ""
                tree.heading(c, text=lbl + ind, command=lambda col=c: _sort(col))

        def _sort(col):
            if sort_state["col"] == col:
                sort_state["rev"] = not sort_state["rev"]
            else:
                sort_state["col"] = col
                sort_state["rev"] = False
            _refresh()

        _STAGE_ORDER  = {"Baby": 0, "1": 1, "2": 2, "3": 3}
        _RARITY_ORDER = {"Common": 0, "Legendary": 1, "Mythical": 2}

        def _refresh(*_):
            refresh_state["token"] += 1
            token = refresh_state["token"]
            q      = search_var.get().strip().lower()
            typ    = type_var.get()
            stage  = stage_var.get()
            rarity = rarity_var.get()

            items = [(sid, d) for sid, d in PKMN_DATA.items()
                     if (not q or q in d["name"].lower() or q in str(sid))
                     and (typ    == "All" or typ    in (d["type1"], d["type2"]))
                     and (stage  == "All" or stage  == d["stage"])
                     and (rarity == "All" or rarity == d["rarity"])]

            col, rev = sort_state["col"], sort_state["rev"]
            if col == "#0":
                items.sort(key=lambda x: x[1]["name"].lower(), reverse=rev)
            elif col == "sid":
                items.sort(key=lambda x: x[0], reverse=rev)
            elif col == "types":
                items.sort(key=lambda x: (x[1]["type1"], x[1].get("type2", "")), reverse=rev)
            elif col == "stage":
                items.sort(key=lambda x: (_STAGE_ORDER.get(x[1]["stage"], 9), x[0]), reverse=rev)
            elif col == "rarity":
                items.sort(key=lambda x: (_RARITY_ORDER.get(x[1]["rarity"], 9), x[0]), reverse=rev)
            elif col == "bst":
                items.sort(key=lambda x: sum(x[1][s] for s in ("hp","atk","def","spa","spd","spe")),
                           reverse=rev)

            tree.delete(*tree.get_children())
            _sprites.clear()
            count_lbl.configure(text=f"Loading {len(items)} species...")
            _apply_headings()

            def _insert_batch(start=0):
                if token != refresh_state["token"] or not tree.winfo_exists():
                    return
                for sid, d in items[start:start + 80]:
                    sprite = self._load_pokemon_sprite(sid, 0, max_size=24)
                    _sprites[sid] = sprite
                    t2  = ("/" + d["type2"]) if d["type2"] else ""
                    bst = sum(d[s] for s in ("hp", "atk", "def", "spa", "spd", "spe"))
                    tree.insert("", tk.END, iid=str(sid), text=" " + d["name"],
                                image=sprite or "",
                                values=(sid, d["type1"] + t2, d["stage"], d["rarity"], bst))
                next_start = start + 80
                count_lbl.configure(text=f"{min(next_start, len(items))}/{len(items)} species")
                if next_start < len(items):
                    dlg.after(10, lambda: _insert_batch(next_start))
                else:
                    count_lbl.configure(text=f"{len(items)} species")

            _insert_batch()

        for v in (search_var, type_var, stage_var, rarity_var):
            v.trace_add("write", _refresh)
        tree.insert("", tk.END, iid="_loading", text=" Loading Pokemon...")
        count_lbl.configure(text="Loading...")
        dlg.after(1, _refresh)

        # ── buttons ─────────────────────────────────────────────────────────
        bf = ttk.Frame(dlg, padding=(8, 0, 8, 8))
        bf.grid(row=2, column=0, sticky="ew")

        manual_var = tk.StringVar()
        ttk.Label(bf, text="ID:").pack(side="left")
        ttk.Entry(bf, textvariable=manual_var, width=6).pack(side="left", padx=(4, 12))

        def do_select(*_):
            sel = tree.selection()
            if sel:
                sid = int(sel[0])
            else:
                try:
                    sid = int(manual_var.get())
                except ValueError:
                    messagebox.showerror("Input error",
                                         "Select a Pokémon or enter a species ID.", parent=dlg)
                    return
            dlg.destroy()
            callback(sid)

        tree.bind("<Double-Button-1>", do_select)
        tree.bind("<Return>",          do_select)
        dlg.bind("<Escape>",           lambda _: dlg.destroy())
        ttk.Button(bf, text="Select", width=9, command=do_select).pack(side="left", padx=4)
        ttk.Button(bf, text="Cancel", width=9, command=dlg.destroy).pack(side="left", padx=(0, 4))

        search_entry.focus_set()

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

    def _create_pokemon_obj(self, species_id: int, form_id: int = 0,
                            nature_index: int = 0, level: int = None,
                            moves: list = None, evs: list = None) -> RubyObject:
        d      = PKMN_DATA.get(species_id, {})
        stage  = d.get("stage",  "1")
        rarity = d.get("rarity", "Common")
        if level is None:
            level = _default_level(stage, rarity)

        hp_b, atk_b, def_b, spa_b, spd_b, spe_b = pokemon_base_stats(
            species_id, form_id
        )

        iv_hp  = min(31, hp_b  // 4)
        iv_atk = min(31, atk_b // 4)
        iv_def = min(31, def_b // 4)
        iv_spa = min(31, spa_b // 4)
        iv_spd = min(31, spd_b // 4)
        iv_spe = min(31, spe_b // 4)
        ev_hp, ev_atk, ev_def, ev_spa, ev_spd, ev_spe = _sanitize_evs(evs or [0, 0, 0, 0, 0, 0])

        total_hp = (2 * hp_b + iv_hp + ev_hp // 4)  * level // 100 + level + 10
        def calc(b, iv, ev, game_stat_index):
            raw = (2 * b + iv + ev // 4) * level // 100 + 5
            return raw * _nature_stat_multiplier(nature_index, game_stat_index) // 100

        name_str = d.get("name", f"#{species_id}")
        growth   = d.get("growth", "medium-fast")
        exp      = _exp_for_level(growth, level)
        nature_index = max(0, min(24, int(nature_index)))
        pid      = find_pid(nature_index, False, self.trainer_id, self.secret_id)

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
        a["@attack"]       = calc(atk_b, iv_atk, ev_atk, 0)
        a["@defense"]      = calc(def_b, iv_def, ev_def, 1)
        a["@spatk"]        = calc(spa_b, iv_spa, ev_spa, 3)
        a["@spdef"]        = calc(spd_b, iv_spd, ev_spd, 4)
        a["@speed"]        = calc(spe_b, iv_spe, ev_spe, 2)
        a["@exp"]          = exp
        a["@item"]         = 0
        a["@happiness"]    = 70
        a["@status"]       = 0
        a["@statusCount"]  = 0
        a["@ballused"]     = 0
        a["@obtainLevel"]  = level
        a["@obtainMode"]   = 0
        a["@obtainMap"]    = 0
        a["@obtainText"]   = None
        a["@timeReceived"] = int(time.time())
        a["@iv"]           = _display_stats_to_game(
            [iv_hp, iv_atk, iv_def, iv_spa, iv_spd, iv_spe]
        )
        a["@ev"]           = _display_stats_to_game(
            [ev_hp, ev_atk, ev_def, ev_spa, ev_spd, ev_spe]
        )
        a["@form"]         = 0
        a["@abilityflag"]  = 0
        a["@natureflag"]   = nature_index
        a["@genderflag"]   = None
        a["@shinyflag"]    = False
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

        apply_pokemon_form(a, form_id)

        return pkmn

    def _open_move_picker(self, species_id: int, callback):
        """Creation setup popup. callback(form, nature, level, selected moves)."""
        d       = PKMN_DATA.get(species_id, {})
        name    = d.get("name", f"#{species_id}")
        def_lv  = _default_level(d.get("stage", "1"), d.get("rarity", "Common"))

        win = self._make_popup(f"Create {name}", "900x570")

        # ── Form, Nature, and level row ──────────────────────────────────────
        top = ttk.Frame(win, padding=(10, 8, 10, 4))
        top.pack(fill="x")
        form_choices = self._form_choices(species_id, 0)
        form_var = tk.StringVar(value=form_choices[0])
        initial_form = self._parse_form_id(form_choices[0])
        nature_var = tk.StringVar(value=NATURE_CHOICES[0])
        level_var = tk.IntVar(value=def_lv)
        sprite = ttk.Label(top, width=8, anchor="center")
        sprite.pack(side="left", padx=(0, 10))
        initial_image = self._load_pokemon_sprite(species_id, initial_form, max_size=56)
        sprite.configure(image=initial_image if initial_image else "", text="" if initial_image else "(no sprite)")
        sprite.image = initial_image

        ttk.Label(top, text="Form:").pack(side="left")
        form_combo = ttk.Combobox(
            top, textvariable=form_var, values=form_choices, width=22, state="readonly"
        )
        form_combo.pack(side="left", padx=(4, 12))
        ttk.Label(top, text="Nature:").pack(side="left")
        ttk.Combobox(
            top, textvariable=nature_var, values=NATURE_CHOICES, width=24, state="readonly"
        ).pack(side="left", padx=(4, 12))
        ttk.Label(top, text="Level:").pack(side="left")
        ttk.Spinbox(top, from_=1, to=MAX_LEVEL, textvariable=level_var, width=5).pack(side="left", padx=4)
        ttk.Label(top, text="(double-click a move to add it)", foreground="gray").pack(side="left", padx=8)

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
        ttk.Button(right, text="YOU DECIDE", command=lambda: _auto()).pack(fill="x", padx=2)

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

        def _current_form():
            return self._parse_form_id(form_var.get())

        def _current_learnset():
            form_id = _current_form()
            result = pokemon_learnset(species_id, form_id)
            existing = {move_id for _level, move_id in result}
            required = required_form_moves(species_id, form_id)
            return [(1, move_id) for move_id in sorted(required - existing)] + result

        def _refresh_tree(*_):
            try:
                lvl = max(1, min(MAX_LEVEL, int(level_var.get())))
            except (ValueError, tk.TclError):
                return
            tree.delete(*tree.get_children())
            seen = set()
            for learn_lv, mid in _current_learnset():
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
                if selected[idx][0] in required_form_moves(species_id, _current_form()):
                    win.bell()
                    return
                selected.pop(idx)
                _refresh_slots()

        def _auto():
            try:
                lvl = max(1, min(MAX_LEVEL, int(level_var.get())))
            except (ValueError, tk.TclError):
                lvl = def_lv
            result = recommended_creation_move_ids(_current_learnset(), lvl)
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
                lvl = max(1, min(MAX_LEVEL, int(level_var.get())))
            except (ValueError, tk.TclError):
                lvl = def_lv
            form_id = _current_form()
            required = required_form_moves(species_id, form_id)
            selected_ids = {move_id for move_id, _pp in selected}
            if not required.issubset(selected_ids):
                names = ", ".join(MOVE_DATA.get(mid, {}).get("name", f"#{mid}") for mid in required)
                messagebox.showerror(
                    "Required form move",
                    f"This form requires {names}. Add it before continuing.",
                    parent=win,
                )
                return
            try:
                nature_index = nature_index_from_value(nature_var.get())
            except ValueError:
                nature_index = 0
            win.destroy()
            callback(form_id, nature_index, lvl, list(selected))

        def _on_form_changed(*_):
            form_id = _current_form()
            image = self._load_pokemon_sprite(species_id, form_id, max_size=56)
            sprite.configure(image=image if image else "", text="" if image else "(no sprite)")
            sprite.image = image
            selected.clear()
            _refresh_tree()
            _refresh_slots()

        level_var.trace_add("write", _refresh_tree)
        form_var.trace_add("write", _on_form_changed)
        tree.bind("<<TreeviewSelect>>", _on_select)
        tree.bind("<Double-1>", _on_double)

        _refresh_tree()

    # ── move browser (change existing move) ──────────────────────────────────

    def _open_ev_picker(self, species_id: int, level: int, callback):
        """EV selection popup. callback([hp, atk, def, spa, spd, spe]) on confirm."""
        d = PKMN_DATA.get(species_id, {})
        name = d.get("name", f"#{species_id}")
        level = max(1, min(MAX_LEVEL, int(level)))

        win = self._make_popup(f"Choose EVs - {name}", "720x350")

        ttk.Label(win, text=f"EV spread for {name}", font=("", 10, "bold"),
                  padding=(10, 10, 10, 4)).pack(anchor="w")

        body = ttk.Frame(win, padding=(10, 0, 10, 8))
        body.pack(fill="both", expand=True)

        left = ttk.LabelFrame(body, text="Preset", padding=6)
        left.pack(side="left", fill="y", padx=(0, 8))

        preset_var = tk.StringVar(value="Fresh / zero EVs")
        for preset in EV_PRESETS:
            ttk.Radiobutton(left, text=preset, value=preset, variable=preset_var).pack(anchor="w", pady=2)

        training = ttk.LabelFrame(body, text="Training", padding=6)
        training.pack(side="left", fill="y", padx=(0, 8))
        training_var = tk.StringVar(value="Adapted")
        for choice in EV_TRAINING_LEVELS:
            ttk.Radiobutton(
                training, text=choice, value=choice, variable=training_var
            ).pack(anchor="w", pady=2)
        ttk.Label(
            training,
            text=f"Adapted uses level {level}\n({level}% of the preset).",
            foreground="gray",
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        right = ttk.LabelFrame(body, text="Values", padding=8)
        right.pack(side="left", fill="both", expand=True)

        ev_vars = []
        syncing_preset = {"active": False}

        def _raw_values():
            values = []
            for var in ev_vars:
                try:
                    values.append(int(var.get() or 0))
                except ValueError:
                    values.append(0)
            return values

        def _validate_ev_edit(index, proposed):
            if syncing_preset["active"]:
                return True
            if not _valid_ev_edit(_raw_values(), index, proposed):
                win.bell()
                return False
            return True

        for i, stat in enumerate(STATS):
            ttk.Label(right, text=stat, width=5).grid(row=0, column=i, padx=2)
            var = tk.StringVar(value="0")
            validate = (win.register(
                lambda proposed, index=i: _validate_ev_edit(index, proposed)
            ), "%P")
            ttk.Entry(
                right, textvariable=var, width=5,
                validate="key", validatecommand=validate,
            ).grid(row=1, column=i, padx=2, pady=2)
            ev_vars.append(var)

        total_var = tk.StringVar(value="Total: 0 / 510")
        total_lbl = ttk.Label(right, textvariable=total_var)
        total_lbl.grid(row=2, column=0, columnspan=6, sticky="w", pady=(8, 0))
        ttk.Label(right, text="Each stat is clamped to 0-252. Total must be 510 or less.",
                  foreground="gray", wraplength=290).grid(row=3, column=0, columnspan=6, sticky="w", pady=(8, 0))

        btn_row = ttk.Frame(win, padding=(10, 0, 10, 10))
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Confirm", command=lambda: _confirm()).pack(side="right", padx=4)
        ttk.Button(btn_row, text="Cancel", command=win.destroy).pack(side="right")

        def _refresh_total(*_):
            values = _raw_values()
            total = sum(values)
            ok = total <= 510 and all(0 <= v <= 252 for v in values)
            total_var.set(f"Total: {total} / 510")
            total_lbl.configure(foreground=(self._palette.get("text", "black") if ok else self._palette.get("error", "red")))

        def _apply_preset(*_):
            preset = preset_var.get()
            if preset == "Custom":
                return
            multiplier = EV_TRAINING_LEVELS.get(training_var.get())
            if multiplier is None:
                multiplier = level / 100.0
            values = _scale_ev_preset(EV_PRESETS[preset], multiplier)
            syncing_preset["active"] = True
            for var, val in zip(ev_vars, values):
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
        training_var.trace_add("write", _apply_preset)
        for var in ev_vars:
            var.trace_add("write", _mark_custom)
        _apply_preset()

    def _update_move_vars(self, v: dict, move_idx: int, move_id: int):
        m = MOVE_DATA.get(move_id, {})
        v[f"move{move_idx}"].set(str(move_id))
        v[f"move{move_idx}_name"].set(m.get("name", "—") if move_id else "—")
        if f"moveppup{move_idx}" in v: v[f"moveppup{move_idx}"].set("0")
        v[f"move{move_idx}_maxpp"].set(f"/{move_max_pp(move_id, 0)}" if move_id else "/0")
        if move_id:
            v[f"movepp{move_idx}"].set(str(m.get("pp", 0)))

    def _change_move(self, v: dict, move_idx: int):
        try:
            sid = int(v["species_id"].get() or 0)
        except (ValueError, KeyError):
            sid = 0
        self._open_move_browser(sid, lambda mid: self._update_move_vars(v, move_idx, mid), self._selected_form_id(v))

    def _open_move_browser(self, species_id: int, callback, form_id: int = 0):
        """Browse moves, coloured by how the species can actually get them.

        Level-up legality comes from learnset_data.txt; TM, HM and tutor
        legality from teachable_data.txt, generated from the game's own
        Data/tm.dat.  Anything in neither is illegal, and still selectable -
        the editor advises, it does not block.
        """
        learnset_ids = {mid for _, mid in pokemon_learnset(species_id, form_id)}
        teachable_ids = pokemon_teachable(species_id) - learnset_ids

        def kind_of(move_id):
            if move_id in learnset_ids:
                return "levelup"
            if move_id in teachable_ids:
                return "teachable"
            return "illegal"

        win = self._make_popup("Move Browser", "790x560", resizable=(True, True))

        frow = ttk.Frame(win, padding=(10, 8, 10, 0)); frow.pack(fill="x")
        search_var = tk.StringVar()
        ttk.Label(frow, text="Search:").pack(side="left")
        entry = ttk.Entry(frow, textvariable=search_var, width=28)
        entry.pack(side="left", padx=(2, 12))

        # Filter toggles sit on their own row under the search box, each label
        # tinted like the rows it controls.
        trow = ttk.Frame(win, padding=(10, 4, 10, 4)); trow.pack(fill="x")
        ttk.Label(trow, text="Toggle move filters:").pack(side="left", padx=(0, 8))
        show_levelup = tk.BooleanVar(value=True)
        show_teachable = tk.BooleanVar(value=True)
        show_illegal = tk.BooleanVar(value=True)
        for kind, text, var in (
            ("levelup", "Level-up", show_levelup),
            ("teachable", "Teachable", show_teachable),
            ("illegal", "Illegal", show_illegal),
        ):
            holder = ttk.Frame(trow); holder.pack(side="left", padx=(0, 14))
            # takefocus=False keeps ttk from painting its focus ring on click.
            check = ttk.Checkbutton(holder, variable=var, takefocus=False)
            check.pack(side="left")
            tk.Label(holder, text=text, fg=MOVE_KIND_COLOURS[kind], bd=0, padx=0,
                     highlightthickness=0,
                     bg=self._palette["bg"] if self._palette else None).pack(side="left")

        tv_frame = ttk.Frame(win, padding=(10, 0, 10, 4)); tv_frame.pack(fill="both", expand=True)
        cols = ("name", "type", "cat", "pwr", "acc", "pp", "compat")
        tree = ttk.Treeview(tv_frame, columns=cols, show="headings", height=16, selectmode="browse")
        column_info = {
            "name": (145, "w", "Name"), "type": (78, "center", "Type"),
            "cat": (72, "center", "Category"), "pwr": (48, "center", "Power"),
            "acc": (52, "center", "Accuracy"), "pp": (36, "center", "PP"),
            "compat": (120, "center", "Legality"),
        }
        for col, (width, anchor, _label) in column_info.items():
            tree.column(col, width=width, anchor=anchor, stretch=False)
        vsb = ttk.Scrollbar(tv_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True); vsb.pack(side="left", fill="y")
        for kind, colour in MOVE_KIND_COLOURS.items():
            tree.tag_configure(kind, foreground=colour)

        desc_frame = ttk.LabelFrame(win, text="Description", padding=(6, 2)); desc_frame.pack(fill="x", padx=10, pady=(0, 4))
        desc_lbl = ttk.Label(desc_frame, text="", wraplength=760, justify="left"); desc_lbl.pack(fill="x")
        btn_row = ttk.Frame(win, padding=(10, 0, 10, 8)); btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Select", command=lambda: confirm()).pack(side="right", padx=4)
        ttk.Button(btn_row, text="Cancel", command=win.destroy).pack(side="right")
        count_var = tk.StringVar()
        ttk.Label(btn_row, textvariable=count_var, foreground="gray").pack(side="left")
        sort_state = {"col": "name", "reverse": False}

        _KIND_ORDER = {"levelup": 0, "teachable": 1, "illegal": 2}

        def sort_value(entry_pair, col):
            mid, move = entry_pair
            values = {
                "name": move.get("name", "").casefold(), "type": move.get("type", "").casefold(),
                "cat": move.get("category", "").casefold(), "pwr": move.get("power", 0),
                "acc": move.get("accuracy", 0), "pp": move.get("pp", 0),
                "compat": _KIND_ORDER[kind_of(mid)],
            }
            return (values[col], move.get("name", "").casefold())

        def apply_headings():
            for col, (_width, _anchor, label) in column_info.items():
                indicator = (" ▼" if sort_state["reverse"] else " ▲") if col == sort_state["col"] else ""
                tree.heading(col, text=label + indicator, command=lambda c=col: set_sort(c))

        def set_sort(col):
            if sort_state["col"] == col: sort_state["reverse"] = not sort_state["reverse"]
            else: sort_state.update(col=col, reverse=False)
            refresh()

        def refresh(*_):
            query = search_var.get().strip().casefold()
            wanted = {
                "levelup": show_levelup.get(),
                "teachable": show_teachable.get(),
                "illegal": show_illegal.get(),
            }
            entries = [
                (mid, move) for mid, move in MOVE_DATA.items()
                if (not query or query in move.get("name", "").casefold() or query == str(mid))
                and wanted[kind_of(mid)]
            ]
            entries.sort(key=lambda pair: sort_value(pair, sort_state["col"]), reverse=sort_state["reverse"])
            tree.delete(*tree.get_children()); apply_headings()
            for mid, move in entries:
                kind = kind_of(mid)
                power, accuracy = move.get("power", 0), move.get("accuracy", 0)
                tree.insert("", "end", iid=str(mid), values=(
                    move.get("name", f"#{mid}"), move.get("type", ""), move.get("category", ""),
                    power if power > 0 else "—", accuracy if accuracy > 0 else "—", move.get("pp", 0),
                    MOVE_KIND_LABELS[kind],
                ), tags=(kind,))
            count_var.set(f"{len(entries)} of {len(MOVE_DATA)} moves")

        def on_select(_event=None):
            selection = tree.selection()
            if selection: desc_lbl.config(text=MOVE_DATA.get(int(selection[0]), {}).get("description", ""))

        def confirm():
            selection = tree.selection()
            if not selection: return
            move_id = int(selection[0]); win.destroy(); callback(move_id)

        for filter_var in (search_var, show_levelup, show_teachable, show_illegal):
            filter_var.trace_add("write", refresh)
        tree.bind("<<TreeviewSelect>>", on_select); tree.bind("<Double-1>", lambda _event: confirm())
        refresh(); entry.focus_set()
    def _add_to_party_slot(self, slot: int):
        if not self.trainer:
            messagebox.showerror("No save loaded", "Load a save file first."); return
        def on_pick(sid):
            def on_moves(form_id, nature_index, level, moves):
                def on_evs(evs):
                    party = self.trainer.attributes.setdefault("@party", [])
                    while len(party) <= slot:
                        party.append(None)
                    party[slot] = self._create_pokemon_obj(
                        sid, form_id=form_id, nature_index=nature_index,
                        level=level, moves=moves, evs=evs,
                    )
                    self._fill_party()
                    name = PKMN_DATA.get(sid, {}).get("name", f"#{sid}")
                    self.status.config(
                        text=f"Added {name} to party slot {slot+1}. Click Save to write.",
                        foreground="blue")
                self._open_ev_picker(sid, level, on_evs)
            self._open_move_picker(sid, on_moves)
        self._open_pokemon_picker(on_pick)

    def _delete_party_pokemon(self, slot: int):
        if not self.trainer:
            return
        # Preserve unsaved edits in every party tab before the list is compacted
        # and the UI is rebuilt around the new slot positions.
        self._apply_party()
        party = self.trainer.attributes.get("@party", [])
        if not isinstance(party, list) or slot >= len(party) or not isinstance(party[slot], RubyObject):
            return
        pkmn = party[slot]
        a = pkmn.attributes
        nick = ds(a.get("@name", b"")) or f"Species#{a.get('@species', '?')}"
        if not messagebox.askyesno(
            "Delete Pokémon",
            f"Permanently delete {nick} from the party?\nThis cannot be undone.",
            icon="warning",
            parent=self,
        ):
            return
        party.pop(slot)
        self._fill_party()
        self.status.config(
            text=f"Deleted {nick} from the party. Click Save to write.",
            foreground="blue",
        )

    def _move_party_pokemon(self, slot: int):
        if not self.trainer or not isinstance(self.storage, RubyObject):
            return
        # Moving rebuilds the party tabs; write their current UI values to the
        # in-memory objects first so unrelated pending edits are not discarded.
        self._apply_party()
        self._apply_boxes()
        party = self.trainer.attributes.get("@party", [])
        if not isinstance(party, list) or slot >= len(party) or not isinstance(party[slot], RubyObject):
            return
        pkmn = party[slot]
        a = pkmn.attributes
        nick = ds(a.get("@name", b"")) or f"Species#{a.get('@species', '?')}"
        boxes = self.storage.attributes.get("@boxes", [])
        if not isinstance(boxes, list):
            return

        box_options = []
        for box_idx, box in enumerate(boxes):
            if not isinstance(box, RubyObject):
                continue
            box_name = ds(box.attributes.get("@name", f"Box {box_idx + 1}"))
            box_options.append((box_idx, box, f"Box {box_idx + 1}: {box_name}"))
        if not box_options:
            messagebox.showerror("No PC boxes", "This save has no available PC boxes.", parent=self)
            return

        dlg = self._make_popup(f"Move {nick}", "470x190")
        ttk.Label(
            dlg, text=f"Send {nick} to a PC box", font=("", 10, "bold"),
            padding=(0, 8, 0, 6),
        ).pack()
        destination = ttk.LabelFrame(dlg, text="Destination", padding=8)
        destination.pack(fill="x", padx=10, pady=(0, 8))

        labels = [label for _box_idx, _box, label in box_options]
        current_box = self.storage.attributes.get("@currentBox", 0)
        default_option = next(
            (option for option in box_options if option[0] == current_box),
            box_options[0],
        )
        box_var = tk.StringVar(value=default_option[2])
        slot_var = tk.StringVar()
        ttk.Label(destination, text="Box:").pack(side="left")
        ttk.Combobox(
            destination, textvariable=box_var, values=labels,
            width=22, state="readonly",
        ).pack(side="left", padx=(2, 10))
        ttk.Label(destination, text="Slot:").pack(side="left")
        slot_combo = ttk.Combobox(
            destination, textvariable=slot_var, width=22, state="readonly",
        )
        slot_combo.pack(side="left", padx=(2, 0))

        def selected_box_option():
            selected_label = box_var.get()
            return next(
                (option for option in box_options if option[2] == selected_label),
                box_options[0],
            )

        def refresh_slots(*_):
            _box_idx, box, _label = selected_box_option()
            pokemon_list = box.attributes.get("@pokemon", [])
            if not isinstance(pokemon_list, list):
                pokemon_list = []
            slot_labels = []
            for box_slot in range(max(len(pokemon_list), 30)):
                if box_slot < len(pokemon_list) and isinstance(pokemon_list[box_slot], RubyObject):
                    occupant = pokemon_list[box_slot].attributes
                    occupant_name = ds(occupant.get("@name", b"")) or f"Species#{occupant.get('@species', '?')}"
                    slot_labels.append(f"Slot {box_slot}: {occupant_name}")
                else:
                    slot_labels.append(f"Slot {box_slot}: (empty)")
            slot_combo["values"] = slot_labels
            slot_var.set(slot_labels[0] if slot_labels else "")

        def send_to_box():
            if slot_var.get() not in list(slot_combo["values"]):
                return
            dest_box_idx, dest_box, _label = selected_box_option()
            dest_slot = list(slot_combo["values"]).index(slot_var.get())
            dest_list = dest_box.attributes.get("@pokemon", [])
            if not isinstance(dest_list, list):
                dest_list = []
                dest_box.attributes["@pokemon"] = dest_list
            occupant = dest_list[dest_slot] if dest_slot < len(dest_list) else None
            occupant_name = ""
            if isinstance(occupant, RubyObject):
                occupant_attrs = occupant.attributes
                occupant_name = ds(occupant_attrs.get("@name", b"")) or f"Species#{occupant_attrs.get('@species', '?')}"
                if not messagebox.askyesno(
                    "Swap Pokémon",
                    f"Box {dest_box_idx + 1} Slot {dest_slot} has {occupant_name}.\n"
                    f"Swap it with {nick}?",
                    parent=dlg,
                ):
                    return

            move_party_pokemon_to_box(party, slot, dest_list, dest_slot)
            self.storage.attributes["@currentBox"] = dest_box_idx
            dlg.destroy()
            self._fill_party()
            self._rerender_box(dest_box_idx)
            self._select_box_tab(dest_box_idx)
            action = (
                f"Swapped {nick} with {occupant_name} in Box {dest_box_idx + 1} Slot {dest_slot}."
                if occupant_name else
                f"Moved {nick} to Box {dest_box_idx + 1} Slot {dest_slot}."
            )
            self.status.config(text=action + " Click Save to write.", foreground="blue")

        box_var.trace_add("write", refresh_slots)
        refresh_slots()
        button_row = ttk.Frame(dlg)
        button_row.pack(pady=(0, 8))
        ttk.Button(button_row, text="Send", command=send_to_box).pack(side="left", padx=4)
        ttk.Button(button_row, text="Cancel", command=dlg.destroy).pack(side="left", padx=4)

    def _delete_box_pokemon(self, bi: int, si: int, box: RubyObject):
        # Rerendering this box must not discard pending edits in any rendered
        # PC slot.
        self._apply_boxes()
        if "@pokemon" not in box.attributes:
            return
        pokemon_list = box.attributes["@pokemon"]
        if si >= len(pokemon_list) or not isinstance(pokemon_list[si], RubyObject):
            return
        a    = pokemon_list[si].attributes
        nick = ds(a.get("@name", b"")) or f"Species#{a.get('@species', '?')}"
        if not messagebox.askyesno("Delete Pokémon",
                f"Permanently delete {nick}?\nThis cannot be undone.",
                icon="warning", parent=self):
            return
        pokemon_list[si] = None
        self._rerender_box(bi)
        self.status.config(
            text=f"Deleted {nick} from Box {bi+1} Slot {si+1}. Click Save to write.",
            foreground="blue")

    def _move_box_pokemon(self, bi: int, si: int, box: RubyObject, pkmn: RubyObject):
        # A move can rebuild both Party and Box editors, so preserve their
        # current in-memory edits before opening the destination dialog.
        self._apply_party()
        self._apply_boxes()
        a    = pkmn.attributes
        nick = ds(a.get("@name", b"")) or f"Species#{a.get('@species', '?')}"

        if not isinstance(self.storage, RubyObject): return
        boxes  = self.storage.attributes.get("@boxes", [])
        party  = self.trainer.attributes.get("@party", [])

        dlg = self._make_popup(f"Move {nick}", "420x300")

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
            self._rerender_box(bi)
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
            self._rerender_box(bi)
            if dest_bi != bi:
                self._rerender_box(dest_bi)
            self._select_box_tab(dest_bi)
            self.status.config(
                text=f"Moved {nick} to Box {dest_bi+1} Slot {dest_si}. Click Save to write.",
                foreground="blue")

    def _add_to_box_slot(self, box_idx: int, slot_idx: int, box: RubyObject):
        if not self.trainer:
            messagebox.showerror("No save loaded", "Load a save file first."); return
        def on_pick(sid):
            def on_moves(form_id, nature_index, level, moves):
                def on_evs(evs):
                    pokemon_list = box.attributes.get("@pokemon", [])
                    while len(pokemon_list) <= slot_idx:
                        pokemon_list.append(None)
                    pokemon_list[slot_idx] = self._create_pokemon_obj(
                        sid, form_id=form_id, nature_index=nature_index,
                        level=level, moves=moves, evs=evs,
                    )
                    box.attributes["@pokemon"] = pokemon_list
                    # Point the PC to this box so it opens here directly, avoiding
                    # pbSwitchBoxToRight which can crash on nil slots in previously-empty boxes.
                    if isinstance(self.storage, RubyObject):
                        self.storage.attributes["@currentBox"] = box_idx
                    self._rerender_box(box_idx)
                    name = PKMN_DATA.get(sid, {}).get("name", f"#{sid}")
                    self.status.config(
                        text=f"Added {name} to box {box_idx+1}. PC will open at this box. Click Save to write.",
                        foreground="blue")
                self._open_ev_picker(sid, level, on_evs)
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
            with open(path, "rb") as fd:
                raw = fd.read()
        except Exception as e:
            messagebox.showerror("Load error", str(e)); return

        positions = split_streams(raw)
        if not positions:
            messagebox.showerror("Error", "No Marshal streams found."); return

        trainer = bag = storage = game_system = game_player = global_meta = None
        bag_idx = storage_idx = player_idx = meta_idx = None
        play_time_frames = None
        stream_errors = []
        for idx, start in enumerate(positions):
            end = positions[idx+1] if idx+1 < len(positions) else len(raw)
            try:
                obj = loads(raw[start:end])
            except Exception as e:
                # Game_Map never reads back (rubymarshal cannot resolve its object
                # cycles); keep the reason so a missing PokemonStorage can be
                # explained instead of showing an empty PC Boxes tab.
                stream_errors.append(f"stream {idx} @ {start}: {type(e).__name__}: {e}")
                continue
            if isinstance(obj, int) and play_time_frames is None:
                play_time_frames = obj
                continue
            if not isinstance(obj, RubyObject): continue
            cn = obj.ruby_class_name
            if cn == "PokeBattle_Trainer" and trainer is None:
                trainer = obj
            elif cn == "PokemonBag":
                bag = obj; bag_idx = idx
            elif cn == "PokemonStorage":
                storage = obj; storage_idx = idx
            elif cn == "Game_System":
                game_system = obj
            elif cn == "Game_Player":
                game_player = obj; player_idx = idx
            elif cn == "PokemonGlobalMetadata":
                global_meta = obj; meta_idx = idx

        if trainer is None:
            messagebox.showerror("Error", "PokeBattle_Trainer not found."); return

        self.raw         = raw
        self.positions   = positions
        self.trainer     = trainer
        self.bag         = bag;     self.bag_idx     = bag_idx
        self.storage     = storage; self.storage_idx = storage_idx
        self.player_idx  = player_idx
        self.meta_idx    = meta_idx
        self.storage_error = "" if storage is not None else (
            "; ".join(stream_errors) if stream_errors else "no PokemonStorage stream in this file")
        self.game_system = game_system
        self.game_player = game_player
        self.global_meta = global_meta
        self.play_time_frames = play_time_frames
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
        full_id = ta.get("@id", 0) or 0
        public_id = full_id & 0xFFFF
        secret_id = full_id >> 16
        seen = self._count_truthy(ta.get("@seen", []))
        owned = self._count_truthy(ta.get("@owned", []))
        shadow = self._count_truthy(ta.get("@shadowcaught", []))
        total_species = max(0, len(PKMN_DATA))
        badges = ta.get("@badges", [])

        self.var_trainer_name.set(ds(ta.get("@name", b"")) or "-")
        self.var_trainer_public_id.set(str(public_id))
        self.var_trainer_full_id.set(str(full_id))
        self.var_trainer_type.set(str(ta.get("@trainertype", "-")))
        self.var_trainer_language.set(str(ta.get("@language", "-")))
        self.var_sid.set(str(self.secret_id))
        for i, bv in enumerate(self.badge_vars):
            bv.set(badges[i] if isinstance(badges, list) and i < len(badges) else False)
        self.var_badge_count.set(self._format_count(self._count_truthy(badges), len(badges) if isinstance(badges, list) else 0))
        self.var_party_count.set(self._format_count(self._party_count(), 6))
        self.var_pc_count.set(self._format_count(self._pc_pokemon_count()))
        self.var_pokedex_seen.set(self._format_count(seen, total_species))
        self.var_pokedex_owned.set(self._format_count(owned, total_species))
        self.var_shadow_caught.set(self._format_count(shadow, total_species))
        self.var_bag_item_count.set(self._format_count(self._bag_entry_count()))

        gs = self.game_system.attributes if isinstance(self.game_system, RubyObject) else {}
        gm = self.global_meta.attributes if isinstance(self.global_meta, RubyObject) else {}
        gp = self.game_player.attributes if isinstance(self.game_player, RubyObject) else {}
        self.var_save_count.set(str(gs.get("@save_count", "-")))
        self.var_play_time.set(self._format_play_time(self.play_time_frames))
        self.var_step_count.set(self._format_count(gm.get("@stepcount", 0)) if isinstance(gm.get("@stepcount", 0), int) else "-")
        visited = self._count_truthy(gm.get("@visitedMaps", []))
        total_maps = len(gm.get("@visitedMaps", [])) - 1 if isinstance(gm.get("@visitedMaps", []), list) else 0
        self.var_visited_maps.set(self._format_count(visited, total_maps))
        self.var_coins.set(self._format_count(gm.get("@coins", 0)) if isinstance(gm.get("@coins", 0), int) else "-")
        current_box = self.storage.attributes.get("@currentBox", None) if isinstance(self.storage, RubyObject) else None
        self.var_current_box.set(f"Box {current_box + 1}" if isinstance(current_box, int) else "-")
        if gp:
            self.var_player_location.set(map_display_name(gp.get("@oldMap", "?")))
            x, y = gp.get("@x", 0), gp.get("@y", 0)
            self.var_player_x.set(str(x))
            self.var_player_y.set(str(y))
            self._loaded_location = (str(x), str(y))
        else:
            self.var_player_location.set("-")
            self.var_player_x.set(""); self.var_player_y.set("")
            self._loaded_location = None

        self._location_dirty = False
        # Kernel.pbStartOver revives you at @pokecenter*; @healingSpot is only
        # where the Teleport move takes you.  They are usually different maps.
        healing = gm.get("@healingSpot")
        self._teleport_spot = list(healing) if isinstance(healing, list) and len(healing) == 3 else None
        centre = [gm.get("@pokecenterMapId"), gm.get("@pokecenterX"), gm.get("@pokecenterY")]
        if all(isinstance(value, int) for value in centre):
            self._respawn_spot = centre
        else:
            self._respawn_spot = list(self._teleport_spot) if self._teleport_spot else None
        self._loaded_respawn = list(self._respawn_spot) if self._respawn_spot else None
        self._loaded_teleport = list(self._teleport_spot) if self._teleport_spot else None
        self.var_respawn.set(self._spot_text(self._respawn_spot))
        self.var_teleport.set(self._spot_text(self._teleport_spot))
        self.var_registered_items.set(self._registered_items_text())

    @staticmethod
    def _spot_text(spot) -> str:
        if not spot:
            return "-"
        return f"{map_display_name(spot[0])}  X {spot[1]}  Y {spot[2]}"


    def _fill_pkmn_slot(self, v, pkmn, label_prefix="", tab_parent=None, tab_idx=None, title_frame=None):
        # Populating these vars fires the nature/IV/EV write traces, which would
        # schedule a stat recalculation and rewrite (and full-heal) a Pokemon the
        # user never touched.  Loading a save must stay a no-op, so suppress the
        # traces here and drop anything already queued for this slot.
        v["_syncing"] = True
        pending = v.pop("_recalc_after", None)
        if pending:
            try: self.after_cancel(pending)
            except tk.TclError: pass
        try:
            self._fill_pkmn_slot_inner(v, pkmn, label_prefix, tab_parent, tab_idx, title_frame)
        finally:
            v["_syncing"] = False
        self._refresh_ev_total(v)

    def _fill_pkmn_slot_inner(self, v, pkmn, label_prefix="", tab_parent=None, tab_idx=None, title_frame=None):
        if isinstance(pkmn, RubyObject):
            a   = pkmn.attributes
            pid = a.get("@personalID", 0) or 0
            v["_pkmn_obj"] = pkmn
            for key, attr in [
                ("species_id","@species"),("hp","@hp"),
                ("totalhp","@totalhp"),("attack","@attack"),("defense","@defense"),
                ("spatk","@spatk"),("spdef","@spdef"),("speed","@speed"),
                ("exp","@exp"),("item","@item"),("happiness","@happiness"),
                ("status","@status"),("ball","@ballused"),("obtain_lv","@obtainLevel"),
            ]:
                v[key].set(str(a.get(attr, 0)))
            self._set_form_value(v, a.get("@species", 0), pokemon_form(a))
            v["species_search"].set(self._species_label(int(a.get("@species", 0))))
            growth = PKMN_DATA.get(int(a.get("@species", 0)), {}).get("growth", "medium-fast")
            v["level"].set(str(_level_for_exp(growth, a.get("@exp", 0))))
            v["nickname"].set(ds(a.get("@name", b"")))
            v["nature_idx"].set(NATURE_CHOICES[pokemon_nature(a)])
            self._set_gender_value(v, a)
            v["shiny"].set(pokemon_is_shiny(a, self.trainer_id, self.secret_id))
            ab = a.get("@abilityflag", None)
            self._set_ability_value(v, ab if isinstance(ab, int) else pid & 1)
            self._remember_identity_values(v)
            iv = a.get("@iv", [])
            ev = a.get("@ev", [])
            display_iv = _game_stats_to_display(iv)
            display_ev = _game_stats_to_display(ev)
            for j, stat in enumerate(STATS):
                key = stat.lower()
                v[f"iv_{key}"].set(str(display_iv[j]))
                v[f"ev_{key}"].set(str(display_ev[j]))
            moves = a.get("@moves", [])
            for i in range(4):
                if isinstance(moves, list) and i < len(moves) and isinstance(moves[i], RubyObject):
                    mid = moves[i].attributes.get("@id", 0); pp = moves[i].attributes.get("@pp", 0); ppup = moves[i].attributes.get("@ppup", 0)
                    m = MOVE_DATA.get(mid, {})
                    v[f"move{i}"].set(str(mid)); v[f"move{i}_name"].set(m.get("name", "—") if mid else "—")
                    if f"move{i}_search" in v: v[f"move{i}_search"].set(f"{mid} — {m.get('name', 'Unknown')}" if mid else "0 — None")
                    v[f"movepp{i}"].set(str(pp))
                    if f"moveppup{i}" in v: v[f"moveppup{i}"].set(str(ppup))
                    v[f"move{i}_maxpp"].set(f"/{move_max_pp(mid, ppup)}" if mid else "/0")
                else:
                    v[f"move{i}"].set("0"); v[f"move{i}_name"].set("—")
                    if f"move{i}_search" in v: v[f"move{i}_search"].set("0 — None")
                    v[f"movepp{i}"].set("0"); v[f"move{i}_maxpp"].set("/0")
                    if f"moveppup{i}" in v: v[f"moveppup{i}"].set("0")

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
            self._clear_pokemon_editor_vars(v)
            v["editor_frame"].pack_forget()
            v["add_frame"].pack(expand=True, fill="both")
            if tab_parent and tab_idx is not None:
                tab_parent.tab(tab_idx, text=f" {label_prefix} (empty)")
            if title_frame:
                title_frame.config(text=f"{label_prefix} (empty)")

    def _fill_party(self):
        party = self.trainer.attributes.get("@party", [])
        for slot, v in enumerate(self.pkmn_vars):
            # See _fill_pkmn_slot: writing these vars fires the recalculation
            # traces, which would rewrite the stats of an untouched save.
            v["_syncing"] = True
            pending = v.pop("_recalc_after", None)
            if pending:
                try: self.after_cancel(pending)
                except tk.TclError: pass
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
                self._set_form_value(v, a.get("@species", 0), pokemon_form(a))
                v["species_search"].set(self._species_label(int(a.get("@species", 0))))
                growth = PKMN_DATA.get(int(a.get("@species", 0)), {}).get("growth", "medium-fast")
                v["level"].set(str(_level_for_exp(growth, a.get("@exp", 0))))
                v["nickname"].set(ds(a.get("@name", b"")))
                v["nature_idx"].set(NATURE_CHOICES[pokemon_nature(a)])
                self._set_gender_value(v, a)
                v["shiny"].set(pokemon_is_shiny(a, self.trainer_id, self.secret_id))
                ab = a.get("@abilityflag", None)
                self._set_ability_value(v, ab if isinstance(ab, int) else pid & 1)
                self._remember_identity_values(v)
                iv = a.get("@iv", [])
                ev = a.get("@ev", [])
                display_iv = _game_stats_to_display(iv)
                display_ev = _game_stats_to_display(ev)
                for j, stat in enumerate(STATS):
                    key = stat.lower()
                    v[f"iv_{key}"].set(str(display_iv[j]))
                    v[f"ev_{key}"].set(str(display_ev[j]))
                moves = a.get("@moves", [])
                for i in range(4):
                    if isinstance(moves, list) and i < len(moves) and isinstance(moves[i], RubyObject):
                        mid = moves[i].attributes.get("@id", 0); pp = moves[i].attributes.get("@pp", 0); ppup = moves[i].attributes.get("@ppup", 0)
                        m = MOVE_DATA.get(mid, {})
                        v[f"move{i}"].set(str(mid)); v[f"move{i}_name"].set(m.get("name", "—") if mid else "—")
                        if f"move{i}_search" in v: v[f"move{i}_search"].set(f"{mid} — {m.get('name', 'Unknown')}" if mid else "0 — None")
                        v[f"movepp{i}"].set(str(pp))
                        if f"moveppup{i}" in v: v[f"moveppup{i}"].set(str(ppup))
                        v[f"move{i}_maxpp"].set(f"/{move_max_pp(mid, ppup)}" if mid else "/0")
                    else:
                        v[f"move{i}"].set("0"); v[f"move{i}_name"].set("—")
                        if f"move{i}_search" in v: v[f"move{i}_search"].set("0 — None")
                        v[f"movepp{i}"].set("0"); v[f"move{i}_maxpp"].set("/0")
                        if f"moveppup{i}" in v: v[f"moveppup{i}"].set("0")
                sp    = a.get("@species", slot+1)
                form  = pokemon_form(a)
                self._set_pokemon_dex_vars(v, sp, form if isinstance(form, int) else 0)
                nick  = ds(a.get("@name", b""))
                label = (nick or f"Species#{sp}") + f" [#{sp}]"
                v["_tab_ref"] = (self.party_nb, slot, label[:16])
                self._refresh_shadow_status(v)
                v["editor_frame"].pack(fill="both", expand=True)
                v["add_btn"].pack_forget()
            else:
                v["_pkmn_obj"] = None
                v["_tab_ref"] = None
                self.party_nb.tab(slot, text=f" Slot {slot+1} (empty)")
                self._clear_pokemon_editor_vars(v)
                self._refresh_shadow_status(v)
                if v.get("dex_sprite"):
                    v["dex_sprite"].configure(image="", text="")
                    v["dex_sprite"].image = None
                v["editor_frame"].pack_forget()
                v["add_frame"].pack(fill="both", expand=True)
            v["_syncing"] = False
            self._refresh_ev_total(v)

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
        self._apply_player_location()

    def _apply_player_location(self):
        """Write X/Y and the respawn point, but only when they actually changed.

        Writing unconditionally would break the byte-identical round trip that
        SaveRoundTripTests guards.
        """
        gp = self.game_player.attributes if isinstance(self.game_player, RubyObject) else None
        if gp is not None and self._loaded_location is not None:
            current = (self.var_player_x.get().strip(), self.var_player_y.get().strip())
            if current != self._loaded_location:
                try:
                    x, y = max(0, int(current[0])), max(0, int(current[1]))
                except ValueError:
                    raise ValueError("Player X and Y must be whole numbers")
                gp["@x"], gp["@y"] = x, y
                # real_* are the pixel position the sprite is drawn at; leaving
                # them stale renders the player offset from their own tile.
                gp["@real_x"], gp["@real_y"] = x * 128, y * 128
                if "@oldX" in gp: gp["@oldX"] = x
                if "@oldY" in gp: gp["@oldY"] = y
                self._loaded_location = (str(x), str(y))
                self._location_dirty = True

        meta = self.global_meta.attributes if isinstance(self.global_meta, RubyObject) else None
        if meta is None:
            return

        # The two destinations are written independently: overwriting one with
        # the other is what made the editor report the wrong respawn point.
        if self._respawn_spot is not None and self._respawn_spot != self._loaded_respawn:
            meta["@pokecenterMapId"] = int(self._respawn_spot[0])
            meta["@pokecenterX"] = int(self._respawn_spot[1])
            meta["@pokecenterY"] = int(self._respawn_spot[2])
            self._loaded_respawn = list(self._respawn_spot)
            self._location_dirty = True

        if self._teleport_spot is not None and self._teleport_spot != self._loaded_teleport:
            stored = meta.get("@healingSpot")
            if isinstance(stored, list) and len(stored) == 3:
                # Written in place: the list object is shared with the stream.
                stored[0], stored[1], stored[2] = (int(value) for value in self._teleport_spot)
            else:
                meta["@healingSpot"] = [int(value) for value in self._teleport_spot]
            self._loaded_teleport = list(self._teleport_spot)
            self._location_dirty = True

    def _apply_party(self):
        party = self.trainer.attributes.get("@party", [])
        for slot, v in enumerate(self.pkmn_vars):
            if slot >= len(party) or not isinstance(party[slot], RubyObject): continue
            a = party[slot].attributes
            def gi(key, default=0, vv=v):
                try: return int(vv[key].get() or default)
                except: return default

            for key, attr in [
                ("species_id","@species"),("hp","@hp"),("totalhp","@totalhp"),
                ("attack","@attack"),("defense","@defense"),("spatk","@spatk"),
                ("spdef","@spdef"),("speed","@speed"),("exp","@exp"),
                ("item","@item"),("happiness","@happiness"),("status","@status"),
                ("ball","@ballused"),("obtain_lv","@obtainLevel"),
            ]:
                value = gi(key)
                if value != a.get(attr, 0):
                    a[attr] = value

            current_iv = a.get("@iv", [])
            current_ev = a.get("@ev", [])
            display_iv = [min(31, max(0, gi(f"iv_{stat.lower()}"))) for stat in STATS]
            display_ev = [min(252, max(0, gi(f"ev_{stat.lower()}"))) for stat in STATS]
            if display_iv != _game_stats_to_display(current_iv):
                a["@iv"] = _display_stats_to_game(display_iv)
            if display_ev != _game_stats_to_display(current_ev):
                a["@ev"] = _display_stats_to_game(display_ev)
            nat_name = v["nature_idx"].get()
            nat_i    = nature_index_from_value(nat_name, pokemon_nature(a))
            shiny    = bool(v["shiny"].get())
            ab       = self._selected_ability_slot(v)
            apply_pokemon_identity(
                a, nat_i, shiny, ab, v["gender"].get(), self._changed_identity_fields(v)
            )

            moves = a.get("@moves", [])
            for i in range(4):
                if isinstance(moves, list) and i < len(moves) and isinstance(moves[i], RubyObject):
                    move_id = gi(f"move{i}")
                    move_pp = gi(f"movepp{i}")
                    move_ppup = min(3, max(0, gi(f"moveppup{i}")))
                    if move_id != moves[i].attributes.get("@id", 0):
                        moves[i].attributes["@id"] = move_id
                    if move_pp != moves[i].attributes.get("@pp", 0):
                        moves[i].attributes["@pp"] = move_pp
                    if move_ppup != moves[i].attributes.get("@ppup", 0):
                        moves[i].attributes["@ppup"] = move_ppup

            # Moves and ability are form prerequisites for Keldeo and Arceus,
            # so resolve the requested form only after applying those fields.
            form = self._selected_form_id(v)
            if form != pokemon_form(a):
                apply_pokemon_form(a, form)
                v["item"].set(str(a.get("@item", 0)))

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
        for bi, box, slot_vars in self.box_vars.values():
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
                    ("attack","@attack"),("defense","@defense"),("spatk","@spatk"),
                    ("spdef","@spdef"),("speed","@speed"),
                    ("ball","@ballused"),("obtain_lv","@obtainLevel"),
                ]:
                    value = gi(key)
                    if value != a.get(attr, 0):
                        a[attr] = value

                nick = sv["nickname"].get()
                if nick and nick != ds(a.get("@name", b"")):
                    a["@name"] = nick.encode("utf-8")

                nat_name = sv["nature_idx"].get()
                nat_i    = nature_index_from_value(nat_name, pokemon_nature(a))
                shiny    = bool(sv["shiny"].get())
                ab       = self._selected_ability_slot(sv)
                apply_pokemon_identity(
                    a, nat_i, shiny, ab, sv["gender"].get(), self._changed_identity_fields(sv)
                )

                current_iv = a.get("@iv", [])
                current_ev = a.get("@ev", [])
                display_iv = [min(31, max(0, gi("iv_" + stat.lower()))) for stat in STATS]
                display_ev = [min(252, max(0, gi("ev_" + stat.lower()))) for stat in STATS]
                if display_iv != _game_stats_to_display(current_iv):
                    a["@iv"] = _display_stats_to_game(display_iv)
                if display_ev != _game_stats_to_display(current_ev):
                    a["@ev"] = _display_stats_to_game(display_ev)

                moves = a.get("@moves", [])
                for i in range(4):
                    if isinstance(moves, list) and i < len(moves) and isinstance(moves[i], RubyObject):
                        move_id = gi(f"move{i}")
                        move_pp = gi(f"movepp{i}")
                        move_ppup = min(3, max(0, gi(f"moveppup{i}")))
                        if move_id != moves[i].attributes.get("@id", 0):
                            moves[i].attributes["@id"] = move_id
                        if move_pp != moves[i].attributes.get("@pp", 0):
                            moves[i].attributes["@pp"] = move_pp
                        if move_ppup != moves[i].attributes.get("@ppup", 0):
                            moves[i].attributes["@ppup"] = move_ppup

                form = self._selected_form_id(sv)
                if form != pokemon_form(a):
                    apply_pokemon_form(a, form)
                    sv["item"].set(str(a.get("@item", 0)))

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

        # Player position lives in Game_Player and the respawn point in
        # PokemonGlobalMetadata, so those streams have to be rewritten too -
        # editing the parsed objects alone would be silently discarded.
        player_bytes = meta_bytes = None
        if self._location_dirty and self.game_player is not None and self.player_idx is not None:
            try:    player_bytes = writes(self.game_player, cls=Ruby18Writer)
            except Exception as e:
                messagebox.showerror("Serialization error", f"Player: {e}"); return
        if self._location_dirty and self.global_meta is not None and self.meta_idx is not None:
            try:    meta_bytes = writes(self.global_meta, cls=Ruby18Writer)
            except Exception as e:
                messagebox.showerror("Serialization error", f"Global metadata: {e}"); return

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
        for index, payload in ((self.player_idx, player_bytes), (self.meta_idx, meta_bytes)):
            if index is not None and payload:
                start = positions[index]
                end = positions[index+1] if index+1 < len(positions) else len(raw)
                replacements.append((start, end, payload))

        replacements.sort(key=lambda x: x[0])
        result = b""; cursor = 0
        for start, end, nb in replacements:
            result += raw[cursor:start] + nb
            cursor = end
        result += raw[cursor:]

        # Validate every stream we are replacing before touching the user's file.
        try:
            loads(trainer_bytes)
            if bag_bytes is not None: loads(bag_bytes)
            if storage_bytes is not None: loads(storage_bytes)
            if player_bytes is not None: loads(player_bytes)
            if meta_bytes is not None: loads(meta_bytes)
            verified_positions = split_streams(result)
            if not verified_positions or verified_positions[0] != 0:
                raise ValueError("result is not a valid concatenated Ruby Marshal save")
        except Exception as e:
            messagebox.showerror("Validation error", f"The proposed save was not written:\n{e}")
            return

        bak = timestamped_backup_path(self.save_path)
        while os.path.exists(bak):
            bak = timestamped_backup_path(self.save_path)
        try:
            shutil.copy2(self.save_path, bak)
        except Exception as e:
            messagebox.showerror("Backup error", f"Save cancelled; backup could not be created:\n{e}")
            return

        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(prefix=".insurgence-save-", suffix=".tmp",
                                             dir=os.path.dirname(os.path.abspath(self.save_path)))
            with os.fdopen(fd, "wb") as f:
                f.write(result)
                f.flush()
                os.fsync(f.fileno())
            with open(temp_path, "rb") as f:
                if f.read() != result:
                    raise IOError("temporary-file verification failed")
            os.replace(temp_path, self.save_path)
            temp_path = None
        except Exception as e:
            messagebox.showerror("Write error", f"Original save was not replaced:\n{e}\nBackup: {bak}")
            return
        finally:
            if temp_path and os.path.exists(temp_path):
                try: os.unlink(temp_path)
                except OSError: pass

        # Future saves must compare against the file and identity selections we
        # just wrote.  This also makes changing a nature back after one save work
        # correctly, without ever treating a mere load as an identity edit.
        self.raw = result
        self.positions = split_streams(result)
        self._location_dirty = False
        for v in self.pkmn_vars:
            if isinstance(v.get("_pkmn_obj"), RubyObject):
                self._remember_identity_values(v)
        for _bi, _box, slot_vars in self.box_vars.values():
            for item in slot_vars:
                if item is not None:
                    self._remember_identity_values(item[1])

        self.status.config(
            text=f"Saved!  ({len(result):,} bytes)  Backup → {os.path.basename(bak)}",
            foreground="green")
        messagebox.showinfo("Saved", f"Save written.\nBackup: {bak}")


if __name__ == "__main__":
    app = Editor()
    app.mainloop()
