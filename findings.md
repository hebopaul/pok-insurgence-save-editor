# Pokemon Insurgence — Save File Findings
*Game.rxdata | 204799 bytes | 11 Marshal streams*

---

## 1. Money & Trainer
| Field | Value |
|---|---|
| Trainer Name | Jesus |
| Trainer ID | 4097980967 |
| **Money** | **$999,999** |
| Battle Points | 0 |
| Badges | 0/8 |
| Pokedex | True |
| Pokegear | True |

### Editing Money
- Object: `PokeBattle_Trainer` (first stream, offset 0)
- Attribute: `@money`
- Type: plain integer — **no obfuscation**
- Hard cap in game code: **999,999**
- Edit with: `python edit_save.py money <amount>`

## 2. Party Pokemon

### Slot 1 — Haunter [Species#93 #93]
| Stat | Value |
|---|---|
| HP | 59 / 59 |
| Attack | 36 |
| Defense | 27 |
| Sp.Atk | 71 |
| Sp.Def | 38 |
| Speed | 62 |
| Nature | Gentle |
| Held Item | None (ID:0) |
| OT | Jesus |
| Obtained Lv | 5 |
| Happiness | 154 |
| Status | 0 (0=healthy) |
| Ball | 11 |
| Moves | Move#184 (PP:8) / Move#183 (PP:1) / Move#178 (PP:0) / Move#379 (PP:4) |
| IVs | HP:1 / Atk:18 / Def:9 / SpA:31 / SpD:25 / Spe:6 |
| EVs | HP:3 / Atk:10 / Def:9 / SpA:4 / SpD:4 / Spe:5 |

### Slot 2 — Crip [Species#728 #728]
| Stat | Value |
|---|---|
| HP | 75 / 81 |
| Attack | 51 |
| Defense | 51 |
| Sp.Atk | 54 |
| Sp.Def | 53 |
| Speed | 48 |
| Nature | Jolly |
| Held Item | None (ID:0) |
| OT | [<PBMove>, <PBMove>, <PBMove>, <PBMove>] |
| Obtained Lv | 7 |
| Happiness | 164 |
| Status | 0 (0=healthy) |
| Ball | 0 |
| Moves | Move#642 (PP:6) / Move#217 (PP:9) / Move#460 (PP:17) / Move#479 (PP:18) |
| IVs | HP:17 / Atk:30 / Def:28 / SpA:11 / SpD:24 / Spe:0 |
| EVs | HP:9 / Atk:10 / Def:8 / SpA:10 / SpD:9 / Spe:4 |

### Slot 3 — Pikachu [Species#25 #25]
| Stat | Value |
|---|---|
| HP | 36 / 36 |
| Attack | 24 |
| Defense | 19 |
| Sp.Atk | 23 |
| Sp.Def | 19 |
| Speed | 30 |
| Nature | Serious |
| Held Item | None (ID:0) |
| OT | [<PBMove>, <PBMove>, <PBMove>, <PBMove>] |
| Obtained Lv | 5 |
| Happiness | 127 |
| Status | 0 (0=healthy) |
| Ball | 0 |
| Moves | Move#310 (PP:28) / Move#79 (PP:29) / Move#80 (PP:9) / Move#687 (PP:20) |
| IVs | HP:16 / Atk:31 / Def:20 / SpA:4 / SpD:29 / Spe:3 |
| EVs | HP:1 / Atk:0 / Def:0 / SpA:0 / SpD:0 / Spe:0 |

### Slot 4 — Onix [Species#95 #95]
| Stat | Value |
|---|---|
| HP | 32 / 42 |
| Attack | 26 |
| Defense | 54 |
| Sp.Atk | 16 |
| Sp.Def | 20 |
| Speed | 29 |
| Nature | Lonely |
| Held Item | None (ID:0) |
| OT | [<PBMove>, <PBMove>, <PBMove>, <PBMove>] |
| Obtained Lv | 9 |
| Happiness | 117 |
| Status | 3 (0=healthy) |
| Ball | 11 |
| Moves | Move#370 (PP:30) / Move#316 (PP:20) / Move#508 (PP:13) / Move#507 (PP:14) |
| IVs | HP:30 / Atk:30 / Def:24 / SpA:13 / SpD:13 / Spe:9 |
| EVs | HP:4 / Atk:0 / Def:0 / SpA:1 / SpD:1 / Spe:0 |

### Slot 5 — Cubone [Species#104 #104]
| Stat | Value |
|---|---|
| HP | 0 / 45 |
| Attack | 26 |
| Defense | 38 |
| Sp.Atk | 25 |
| Sp.Def | 25 |
| Speed | 15 |
| Nature | Quiet |
| Held Item | None (ID:0) |
| OT | [<PBMove>, <PBMove>, <PBMove>, <PBMove>] |
| Obtained Lv | 9 |
| Happiness | 115 |
| Status | 0 (0=healthy) |
| Ball | 0 |
| Moves | Move#368 (PP:40) / Move#364 (PP:30) / Move#227 (PP:19) / Move#290 (PP:14) |
| IVs | HP:7 / Atk:28 / Def:9 / SpA:5 / SpD:31 / Spe:18 |
| EVs | HP:2 / Atk:1 / Def:0 / SpA:1 / SpD:0 / Spe:1 |

### Slot 6 — Phanpy [Species#231 #231]
| Stat | Value |
|---|---|
| HP | 0 / 44 |
| Attack | 23 |
| Defense | 22 |
| Sp.Atk | 14 |
| Sp.Def | 16 |
| Speed | 17 |
| Nature | Naive |
| Held Item | None (ID:0) |
| OT | [<PBMove>, <PBMove>, <PBMove>, <PBMove>] |
| Obtained Lv | 12 |
| Happiness | 71 |
| Status | 0 (0=healthy) |
| Ball | 0 |
| Moves | Move#368 (PP:38) / Move#357 (PP:38) / Move#330 (PP:15) / Move#510 (PP:17) |
| IVs | HP:8 / Atk:31 / Def:27 / SpA:15 / SpD:3 / Spe:31 |
| EVs | HP:0 / Atk:0 / Def:0 / SpA:0 / SpD:0 / Spe:0 |

### Editing Party Pokemon
- Object: `PokeBattle_Trainer` → `@party[0..5]` → `PokeBattle_Pokemon`
- Key attributes:
  - `@hp` / `@totalhp` — current / max HP
  - `@attack`, `@defense`, `@spatk`, `@spdef`, `@speed` — battle stats
  - `@iv` — array [HP,Atk,Def,SpA,SpD,Spe], each 0–31
  - `@ev` — array [HP,Atk,Def,SpA,SpD,Spe], each 0–252 (total ≤ 510)
  - `@item` — held item ID
  - `@happiness` — 0–255
  - `@status` — 0=OK, 1=Sleep, 2=Poison, 3=Burn, 4=Freeze, 5=Paralysis
  - `@exp` — experience points
  - `@moves` — array of PBMove: `@id`=move ID, `@pp`=current PP
- Edit with: `python edit_save.py pokemon <slot> <attr> <value>`

## 3. Inventory (Bag)

### Medicine
| Item ID | Name | Quantity |
|---|---|---|
| 1 | Item#1 | 112 |
| 93 | Item#93 | 1 |
| 12 | Item#12 | 1 |
| 7 | Item#7 | 1 |

### Poke Balls
| Item ID | Name | Quantity |
|---|---|---|
| 217 | Item#217 | 109 |
| 227 | Item#227 | 2 |
| 223 | Item#223 | 2 |
| 224 | Item#224 | 131 |
| 218 | Item#218 | 2 |
| 263 | Item#263 | 130 |

### TMs & HMs
| Item ID | Name | Quantity |
|---|---|---|
| 267 | Item#267 | 136 |
| 276 | Item#276 | 1 |
| 266 | Item#266 | 1 |

### Berries
| Item ID | Name | Quantity |
|---|---|---|
| 314 | Item#314 | 1 |
| 659 | Item#659 | 1 |

### Key Items
| Item ID | Name | Quantity |
|---|---|---|
| 724 | Item#724 | 1 |
| 770 | Item#770 | 1 |
| 725 | Item#725 | 1 |
| 726 | Item#726 | 1 |

### Pocket 8
| Item ID | Name | Quantity |
|---|---|---|
| 707 | Item#707 | 1 |
| 504 | Item#504 | 1 |

### Editing Inventory
- Object: `PokemonBag` (stream at ~offset 199219)
- Attribute: `@pockets` — list of pockets
- Each pocket entry: `[item_id, quantity]`
- Edit with: `python edit_save.py item <item_id> <qty>`
- Max quantity per item: **999** (display limit)
- To add a new item: append `[id, qty]` to the correct pocket array

## 4. PC Storage Boxes

### Box 1
| Slot | Species | Nickname | HP | Lv | Nature |
|---|---|---|---|---|---|
| 0 | Species#299 | Nosepass | 24/24 | 9 | Lonely |
| 1 | Species#187 | Hoppip | 27/27 | 10 | Lax |
| 2 | Species#299 | Nosepass | 23/23 | 8 | Careful |
| 3 | Species#41 | Zubat | 28/28 | 9 | Lonely |
| 4 | Species#50 | Diglett | 18/18 | 7 | Calm |
| 5 | Species#504 | Patrat | 20/20 | 3 | Adamant |
| 6 | Species#74 | Geodude | 27/27 | 9 | Adamant |
| 7 | Species#12 | Butterfree | 33/33 | 4 | Lax |
| 8 | Species#222 | Corsola | 44/44 | 15 | Serious |
| 9 | Species#120 | Staryu | 33/33 | 14 | Lonely |

### Editing PC Storage
- Object: `PokemonStorage` → `@boxes[n]` → `@pokemon[slot]`
- Same attributes as party Pokemon apply

---

## 5. Technical Reference

### File Structure
| Stream # | Byte Offset | Object Class |
|---|---|---|
| 0 | 0 | `PokeBattle_Trainer` |
| 1 | 13405 | `int` |
| 2 | 13412 | `Game_System` |
| 3 | 14489 | `PokemonSystem` |
| 4 | 15361 | `int` |
| 5 | 15366 | `Game_Switches` |
| 6 | 16099 | `Game_Variables` |
| 7 | 196818 | `PokemonGlobalMetadata` |
| 8 | 199086 | `PokemonMapMetadata` |
| 9 | 199219 | `PokemonBag` |
| 10 | 199571 | `PokemonStorage` |

### Marshal Format Notes
- Magic: `04 08` (Ruby Marshal 4.8)
- No encryption, no checksum — edits are safe if Marshal is valid
- Integers: Ruby fixnum encoding (see edit_save.py for encoder)
- Strings: length-prefixed UTF-8 bytes
- Object references (tag `@`) — editing shifts object indices; use full reserialise

### Quick Edit Commands (edit_save.py)
```bash
python edit_save.py money 999999
python edit_save.py bp 9999            # Battle Points
python edit_save.py pokemon 0 iv 31    # Max IVs on slot 0
python edit_save.py pokemon 0 ev 0     # Zero EVs on slot 0
python edit_save.py pokemon 0 hp max   # Heal slot 0
python edit_save.py item 527 99        # 99x Rare Candy (ID 527)
python edit_save.py item 17 99         # 99x Master Ball (ID 17)
```
