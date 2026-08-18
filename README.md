# Pokemon Insurgence Save Editor

A small Windows desktop GUI for editing `Game.rxdata` save files from [Pokemon Insurgence](https://pokemon-insurgence.com/).

## Download

Grab the latest `.exe` from the [Releases](https://github.com/hebopaul/pok-insurgence-save-editor/releases) page. No installation is required.

## Features

- Edit trainer money, Battle Points, and badges.
- Edit all six party slots, including species, nickname, level, experience, stats, IVs, EVs, nature, gender, ability slot, shiny flag, held item, status, moves, and PP.
- Add Pokemon to empty party or PC slots with Pokemon, move, and EV pickers.
- Browse PC boxes, edit boxed Pokemon (same fields as the party tab), move Pokemon between boxes and party slots, or delete boxed Pokemon.
- Turn any Pokemon into a Shadow Pokemon, set its heart gauge, choose its Shadow moves and the moves it gets back on purification, or purify it, from either the party tab or the PC boxes.
- Manage the bag by pocket, with searchable item selection, quantities, item icons, and item details.
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
