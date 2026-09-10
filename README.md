# Pokemon Insurgence Save Editor

A small Windows desktop GUI for editing `Game.rxdata` save files from [Pokemon Insurgence](https://pokemon-insurgence.com/).

## Download

Grab the latest `.exe` from the [Releases](https://github.com/hebopaul/pok-insurgence-save-editor/releases) page. No installation is required.

## Features

- Edit trainer money, Battle Points, and badges.
- Edit all six party slots: species, nickname, level, experience, stats, IVs, EVs, nature,
  gender, ability, shiny flag, held item, capture ball, status, moves, PP and PP Ups; move
  party members to PC boxes or delete them from the dedicated Manage panel.
- Level and experience stay in sync across all six growth curves (levels 1-120), and stats
  recalculate automatically from base stats, level, nature, IVs and EVs.
- Find a species by typing its name or its ID - the field suggests matches as you type.
- Move browser colour-codes every move for the selected Pokemon: **green** for moves it
  learns by levelling up, **blue** for moves it can be taught by TM, HM, tutor or breeding,
  **red** for the rest. Each category has its own filter toggle. Illegal moves are flagged,
  never blocked.
- Add Pokemon to empty party or PC slots with form, nature, move and EV-training pickers,
  with form-specific stats and learnsets applied automatically.
- Browse PC boxes and edit boxed Pokemon with the same fields as the party tab; move
  Pokemon between boxes and party slots, or delete them from the warning-styled Manage panel.
- **Pokemon Build Library**: 141 ready-made builds drawn from the game's own trainer data
  and from canon Gen I-VI teams, each with an owning trainer, a computed power tier and a
  play-style tag. Apply one to the Pokemon you are editing, batch-import several into PC
  boxes of your choosing, write or paste your own, or save a Pokemon straight from a slot.
  The **Raw text** tab is a real editor over your own build file: what it holds is exactly
  what **Import to PC** creates.
- Turn any Pokemon into a Shadow Pokemon, set its heart gauge, choose its Shadow moves and
  the moves it gets back on purification, or purify it, from either tab.
- Edit where the player stands. The **Show Map** button opens a viewer with the game's own
  region map and a searchable list of every map. Your position, your respawn point and your
  Teleport destination are each drawn in their own colour and labelled - the blinking red
  marker is you - and each has its own button. When a marker sits *inside* somewhere, on the
  Pokemon Center you are standing in rather than the town around it, it becomes an arrow on
  the door that leads there, pointing the way you would walk through it; click the arrow to
  follow it. Position can be changed anywhere on the map the save was made on, and any other
  map can be set as a respawn or Teleport point.
- Manage the bag by pocket, with searchable item selection, visible game IDs, quantities,
  item icons, and item details.
- View Pokemon sprite/type/ability details and move descriptions while editing.
- Heal Pokemon, restore PP, max IVs, zero EVs, and set all badges with one-click actions.
- Every save writes a uniquely timestamped backup beside the file, validates the rewritten
  data before touching your save, and replaces it atomically.

## Usage

Double-click `Pokemon Insurgence Save Editor.exe` to launch it.

On startup, the editor loads the newest `.rxdata` save from:

```text
%USERPROFILE%\Saved Games\Pokemon Insurgence
```

Use **Load Save** to open another `.rxdata` file. Use **Save (auto-backup)** to write changes
back to the selected file; each save leaves a timestamped `.bak` next to it.

**Pokemon Build Library** opens the build browser. Opening it from a Pokemon's own **Build
Library** button also offers that Pokemon as an unsaved build you can add to the library.
Builds you save go to `%APPDATA%\PokemonInsurgenceSaveEditor\pokemon_builds.user.txt`, so
they survive rebuilding or reinstalling the editor.

## Building

Run `python setup_resources.py "<your Insurgence folder>"` first — the executable bundles the
sprites and icons it produces. See [Game Resources](#game-resources).

Run `.\build.ps1` to rebuild only the executable without reading the version history or creating a ZIP. Use `.\build.ps1 -o` to rebuild and overwrite the current version's ZIP without changing the history, `.\build.ps1 -v` for a small increase (`0.3.2` → `0.3.3`), or `.\build.ps1 -V` for a major increase (`0.3.2` → `0.4.0`). Version increases are recorded in `version_history.txt`.

## Running from Source

Requires Python 3.8+ and `rubymarshal`:

```bash
pip install rubymarshal
python save_editor.py
```

The checkout includes every generated data file the editor needs, so it runs and edits saves
straight away. Pokemon sprites and item icons are **not** included - they belong to the game,
not to this project - so those panels stay blank until you supply them yourself (see below).

## Game Resources

Sprites, icons and the raw game data are extracted from your own Pokemon Insurgence
installation. Point `setup_resources.py` at the folder the game is installed in:

```bash
python setup_resources.py "G:\Games\Insurgence"
```

It finds `Game.rgssad`, decrypts the `Data/` files out of it, copies the sprites and item
icons it needs from the installation's `Graphics/` folder, and writes everything to
`game_resources/` in the layout the build expects. It takes a few seconds and is safe to
re-run: existing files are left alone unless you pass `--force`.

```bash
python setup_resources.py --check                     # report what is present
python setup_resources.py "G:\Games\Insurgence" --force   # overwrite everything
```

`game_resources/` is git-ignored and never redistributed. You need it to build the
executable, or to regenerate the bundled data files, but not merely to edit saves.

### Map data and images

The viewer needs one generated data file, which is committed and already in the checkout.
Regenerate it only if the game updates:

```bash
python tools/gen_map_index.py        # writes map_meta.txt
```

It records each map's parent, every door and the direction you walk through it, and which maps
are unused leftovers. Reading it back costs nothing at startup; deriving the same facts from the
832 `Map###.rxdata` files takes the better part of a minute.

The viewer also draws pre-rendered PNGs, so generate them once after extracting resources:

```bash
python tools/render_maps.py          # every map (about a minute, ~157 MB in map_images/)
python tools/render_maps.py 812      # just one map
```

This needs Pillow (`pip install pillow`); the editor itself does not, because it only loads
the finished images. `map_images/` is git-ignored and not bundled in the executable - at full
size the game's 833 maps come to roughly 3.3 gigapixels. Without it the viewer still opens
and simply says which command to run.

## Notes

- Save files are Ruby Marshal streams.
- Nature, gender, ability, and shiny edits use Insurgence's native override fields, preserving the Pokemon's PID and its other PID-derived traits.
- Level and stat fields are written directly; the game may recalculate some derived values after loading.
- The player's map cannot be changed. The save stores the whole map - tiles, events and all -
  and the game loads it verbatim rather than rebuilding it, so only the X/Y position within
  that map is safe to edit. Use the respawn point to relocate across maps.
- The save keeps two separate destinations, and so does the editor. **Respawn at** is
  `@pokecenterMapId`, where `Kernel.pbStartOver` revives you after whiting out; **Teleport to**
  is `@healingSpot`, where the Teleport move sends you. They are usually different maps.
- Insurgence still ships the whole Pokemon Essentials sample project - a second Route 1,
  Lerucean Town, Cedolan Dept. and so on. Those maps are unreachable, and the tilesets they
  were drawn with have either been repurposed or were never shipped, so they render as
  scrambled tiles or not at all. The viewer hides them behind **Show unused maps**, and says
  which of the two reasons applies when you open one.
- Move legality is read from the game's own data: level-up learnsets, the TM/HM/tutor
  compatibility table, and the egg-move table. Event-exclusive moves cannot be verified and
  show as illegal.
- Loading a save and saving it again without editing anything produces a byte-identical file.

## Disclaimer

This is a fan-made tool and is not affiliated with the Pokemon Insurgence development team. Keep backups before editing saves.
