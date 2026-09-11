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
  follow it. **Move Player Here** works on any map, not just the one the save was made on;
  the viewer will not silently drop you inside a wall, and the respawn and Teleport points
  can be set anywhere too.
- Manage the bag by pocket, with searchable item selection, visible game IDs, quantities,
  item icons, and item details.
- View Pokemon sprite/type/ability details and move descriptions while editing.
- Heal Pokemon, restore PP, max IVs, zero EVs, and set all badges with one-click actions.
- Every save writes a uniquely timestamped backup, validates the rewritten data before
  touching your save, and replaces it atomically.
- Take named checkpoints with **Backup Save File**, and go back to any of them from
  **Restore Save File** - restoring copies the backup over your save and backs up whatever it
  replaces first, so nothing is ever lost in either direction.

## Usage

Double-click `Pokemon Insurgence Save Editor.exe` to launch it.

On startup, the editor loads the newest `.rxdata` save from:

```text
%USERPROFILE%\Saved Games\Pokemon Insurgence
```

Use **Load Save** to open another `.rxdata` file, and **Save** to write changes back to it.

### Backups

Backups live in a `Save Editor Backups` folder beside your saves, and carry their date and name
in the filename - there is no separate index to lose.

- Every **Save** quietly keeps a copy first. These are trimmed to the newest 10 per save file,
  so they cannot pile up forever.
- **Backup Save File** takes a checkpoint you name yourself ("before Elite Four"). Named
  backups are never trimmed. Leave the name blank and it is filed under its date instead.
  The name goes into a filename, so the characters Windows forbids are refused as you type.
- **Restore Save File** lists every backup with its name, which save it came from, and when it
  was taken. Restoring asks first, then copies the backup over that save - the backup stays in
  the list, and the save being replaced is backed up before it is overwritten.

Backups from older versions of the editor, left loose beside the save, are moved into the
folder the first time a backup is taken.

**Pokemon Build Library** opens the build browser. Opening it from a Pokemon's own **Build
Library** button also offers that Pokemon as an unsaved build you can add to the library.
Builds you save go to `%APPDATA%\PokemonInsurgenceSaveEditor\pokemon_builds.user.txt`, so
they survive rebuilding or reinstalling the editor.

Picking rows in the table loads them into the **Raw text** tab, several at a time, separated by
a line containing `---`. That text is the single source of truth: **Import to PC** creates what
you can see there, and nothing else acts on it.

Typing in it changes nothing on its own. An **Apply RAW Changes** button appears while there are
uncommitted edits, and until you press it **Import to PC** and **Apply to Current** stay
disabled. Applying checks the text first and refuses to save anything if it does not hold up,
naming the block and line of every problem — an unknown field, a line that is not `Key: value`,
a move bullet outside a `Moves:` list, five moves, EVs over 510. `Trainer` and `Description` may
be blank or missing; `Species` may not.

**New Empty Build** clears the editor and the selection and lays out the field names for you to
fill in. If you apply text holding more than one build, the editor notices and asks before
splitting it into separate library entries.

Editing one of the built-in builds **overrides** it rather than duplicating it: every build
carries a hidden id, and your version is written to your own file under the same id, so the list
shows one row, not two. `gen_resources/pokemon_builds.txt` is never written to. To keep both,
copy the text into **New Empty Build** instead, which earns a new id.

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

The checkout includes every generated data file the editor needs, in `gen_resources/`, so it
runs and edits saves straight away. That folder holds only derived data - species, moves, items,
abilities, learnsets, forms, the build library and the map index - all rebuilt from the game's
own files by the generator scripts, never edited by hand. Pokemon sprites and item icons are
**not** included - they belong to the game, not to this project - so those panels stay blank
until you supply them yourself (see below).

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
python tools/gen_map_index.py        # writes gen_resources/map_meta.txt
```

It records each map's parent, every door and the direction you walk through it, which maps are
unused leftovers, and one bit per tile saying whether the player could stand there. Reading it
back costs nothing at startup; deriving the same facts from the 832 `Map###.rxdata` files takes
the better part of a minute.

The viewer also draws pre-rendered PNGs, so generate them once after extracting resources:

```bash
python tools/render_maps.py          # every map (a few minutes, ~16 MB in map_images/)
python tools/render_maps.py 812      # just one map
python tools/render_maps.py --force  # re-render maps that already exist
```

This needs Pillow (`pip install pillow`); the editor itself does not, because it only loads the
finished images. Maps are written at 10 px per tile - roughly a third of the game's own 32 px
art - on a 256-colour palette, which is what makes the whole set 16 MB rather than 150 MB and
small enough to bundle into the executable. The viewer opens at that scale one-for-one and can
zoom in from there. `map_images/` is git-ignored, so a checkout renders its own; without it the
viewer still opens and says which command to run.

## Notes

- Save files are Ruby Marshal streams.
- Nature, gender, ability, and shiny edits use Insurgence's native override fields, preserving the Pokemon's PID and its other PID-derived traits.
- Level and stat fields are written directly; the game may recalculate some derived values after loading.
- Moving the player to another map works by asking the game to rebuild it. The save stores the
  whole map - tiles, events and all - and `PokemonLoad` normally uses it verbatim, so changing
  the map id alone would load the new map's name over the old map's tiles. It also sets
  `$PokemonGlobal.safesave`, which is the flag that makes the game re-run
  `$MapFactory.setup($game_map.map_id)` on load and build the destination from
  `Data/Map###.rxdata` instead. The same load then runs the handlers a Fly or a warp would,
  so encounters, weather, music and any following Pokemon all catch up by themselves.
- Because arriving inside a wall can leave you unable to walk out, the editor checks the
  destination tile against the game's own passability rules and asks before allowing one that
  nothing can stand on. It also clears the surf/dive state and any bridge you were standing on,
  which is what the game does on an ordinary transfer.
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
