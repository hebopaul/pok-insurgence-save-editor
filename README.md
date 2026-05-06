# Pokémon Insurgence Save Editor

A desktop GUI for editing `Game.rxdata` save files from [Pokémon Insurgence](https://pokemon-insurgence.com/), made with the help of coding AI agents.

---

## Download

Grab the latest `.exe` from the [Releases](https://github.com/hebopaul/pok-insurgence-save-editor/releases) page — no installation required.

---

## Features

- **Trainer** — edit money, Battle Points, and badges
- **Party** — edit all six party slots:
  - Species, nickname, level, stats, experience
  - IVs and EVs with one-click Max / Zero buttons
  - Nature (dropdown), ability slot, shiny toggle
  - Moves and PP with one-click Restore
  - Held item and status — Heal button for instant full restore
- **Bag** — view all pockets with real item names, edit quantities, add new items via a searchable picker (filter by category and name)
- **PC Boxes** — edit every boxed Pokémon with the same controls as party slots
- Auto-backup on every save (`Game.rxdata.bak`)

---

## Usage

Double-click `Pokemon Insurgence Save Editor.exe` to launch.

The editor auto-loads `Game.rxdata` from the default Insurgence save location on startup. You can also click **Load Save** to open any `.rxdata` file manually.

When you're done editing, click **Save (auto-backup)** — your original file is backed up as `Game.rxdata.bak` before any changes are written.

---

## Item IDs

Item IDs in the Bag tab use the standard values found on community wikis and cheat-engine tables (the raw stored value, `id * 2 + 1`). The bundled `item_ids.txt` maps all 806 item IDs to their names.

---

## Notes

- Save files are Ruby Marshal 4.8 streams — no encryption, no checksum.
- Changing a Pokémon's nature or shiny status recalculates its PID. This also affects gender in some species.
- Level and stat fields are written directly; the game recalculates derived values on next load.

---

## Running from source

Requires Python 3.8+ and [rubymarshal](https://pypi.org/project/rubymarshal/):

```bash
pip install rubymarshal
python save_editor.py
```

---

## Disclaimer

This tool is fan-made and unaffiliated with the Pokémon Insurgence development team. Use at your own risk and keep backups.
