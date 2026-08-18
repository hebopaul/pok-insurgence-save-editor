# Pokemon Insurgence Save Editor

A small Windows desktop GUI for editing `Game.rxdata` save files from [Pokemon Insurgence](https://pokemon-insurgence.com/).

## Download

Grab the latest `.exe` from the [Releases](https://github.com/hebopaul/pok-insurgence-save-editor/releases) page. No installation is required.

## Features

- Edit trainer money, Battle Points, and badges.
- Edit all six party slots, including species, nickname, level, experience, stats, IVs, EVs, nature, gender, ability slot, shiny flag, held items through the visual item picker, status, moves, and PP; move party members to PC boxes or delete them from the dedicated Manage panel.
- Add Pokemon to empty party or PC slots with form, Nature, level-up move, and EV-training pickers; choose moves manually from empty slots or use the rules-based recommendation, with form-specific stats and learnsets applied automatically.
- Browse PC boxes, edit boxed Pokemon (same fields as the party tab), move Pokemon between boxes and party slots, or delete boxed Pokemon from the warning-styled Manage panel.
- Turn any Pokemon into a Shadow Pokemon, set its heart gauge, choose its Shadow moves and the moves it gets back on purification, or purify it, from either the party tab or the PC boxes.
- Manage the bag by pocket, with searchable item selection, visible game IDs, quantities, item icons, and item details.
- View Pokemon sprite/type/ability details and move descriptions while editing.
- Heal Pokemon, restore PP, max IVs, zero EVs, and set all badges with one-click actions.
- Create a `.bak` backup before every save.

## Usage

Double-click `Pokemon Insurgence Save Editor.exe` to launch it.

On startup, the editor loads the newest `.rxdata` save from:

```text
%USERPROFILE%\Saved Games\Pokemon Insurgence
```

Use **Load Save** to open another `.rxdata` file. Use **Save (auto-backup)** to write changes back to the selected file.

## Building

Run `.\build.ps1` to rebuild only the executable without reading the version history or creating a ZIP. Use `.\build.ps1 -o` to rebuild and overwrite the current version's ZIP without changing the history, `.\build.ps1 -v` for a small increase (`0.3.2` → `0.3.3`), or `.\build.ps1 -V` for a major increase (`0.3.2` → `0.4.0`). Version increases are recorded in `version_history.txt`.

## Running from Source

Requires Python 3.8+ and `rubymarshal`:

```bash
pip install rubymarshal
python save_editor.py
```

The source checkout includes the generated data files needed by the editor. The bundled release executable also includes extracted game sprites and item icons; those assets are not required for save editing, but may be absent when running directly from source.

## Notes

- Save files are Ruby Marshal streams.
- Nature, gender, ability, and shiny edits use Insurgence's native override fields, preserving the Pokemon's PID and its other PID-derived traits.
- Level and stat fields are written directly; the game may recalculate some derived values after loading.

## Disclaimer

This is a fan-made tool and is not affiliated with the Pokemon Insurgence development team. Keep backups before editing saves.
