"""Prepare game_resources/ so the editor can be built and run from source.

Point this at your own Pokemon Insurgence installation.  It finds Game.rgssad,
decrypts it, and writes everything into game_resources/ in this project, laid
out exactly the way "Pokemon Insurgence Save Editor.spec" and the data
generators expect:

    game_resources/Data/                 .dat / .rxdata game data
    game_resources/Graphics/Battlers/    Pokemon sprites
    game_resources/Graphics/Icons/       item and ball icons

Usage:

    python setup_resources.py "G:\\Games\\Insurgence"
    python setup_resources.py "G:\\Games\\Insurgence" --force
    python setup_resources.py --check

The game's assets are not redistributed with this project, which is why this
step exists: extract them from a copy you already own.
"""
import argparse
import fnmatch
import os
import shutil
import struct
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(PROJECT_DIR, "game_resources")
ARCHIVE_NAME = "Game.rgssad"
MAGIC = b"RGSSAD\x00\x01"
GLOBAL_KEY = 0xDEADCAFE

# What the .spec bundles and the generators read.  Checked after extracting so a
# partial or wrong-version archive fails loudly instead of at build time.
REQUIRED_DIRS = [
    os.path.join("Data"),
    os.path.join("Graphics", "Battlers"),
    os.path.join("Graphics", "Icons"),
]
REQUIRED_FILES = [
    os.path.join("Data", "Scripts.rxdata"),
    os.path.join("Data", "tm.dat"),
    os.path.join("Data", "eggEmerald.dat"),
    os.path.join("Data", "trainers.dat"),
    os.path.join("Data", "attacksRS.dat"),
]


# ── RGSSAD v1 ────────────────────────────────────────────────────────────────
# Every read advances one running key; the key for a file's payload is the
# global key as it stands *after* the length field, not the length itself.

def update_key(key):
    return (key * 7 + 3) & 0xFFFFFFFF


def read_uint32_enc(handle, key):
    raw = handle.read(4)
    if len(raw) < 4:
        return None, key
    return struct.unpack("<I", raw)[0] ^ key, update_key(key)


def read_name_enc(handle, key, length):
    name = bytearray()
    for _ in range(length):
        byte = handle.read(1)
        if not byte:
            break
        name.append(byte[0] ^ (key & 0xFF))
        key = update_key(key)
    # RPG Maker stores paths with backslashes.
    return name.decode("utf-8", errors="replace").replace("\\", "/"), key


def decrypt_file_data(raw, file_key):
    out = bytearray()
    key = file_key
    key_bytes = struct.pack("<I", key)
    for index, byte in enumerate(raw):
        out.append(byte ^ key_bytes[index % 4])
        if index % 4 == 3:
            key = update_key(key)
            key_bytes = struct.pack("<I", key)
    return bytes(out)


# ── graphics ─────────────────────────────────────────────────────────────────
# Game.rgssad holds only Data/.  Graphics sit loose in the install, and only a
# slice of them is worth bundling: the editor draws Pokemon from Battlers, and
# from Icons it reads item icons (also used for capture balls) and the bag
# pocket tabs.  The other ~2,550 icons are party sprites it never shows, which
# would add roughly 17 MB to the executable for nothing.
GRAPHICS_SETS = [
    (os.path.join("Graphics", "Battlers"), ["*.png"]),
    (os.path.join("Graphics", "Icons"), ["item*.png", "bagPocket*.png"]),
    # Map viewer: the two region maps the town-map screen uses, and the trainer
    # sprites used to mark the player's position.  Characters is 41 MB in full;
    # the trchar slice is 1.7 MB.
    (os.path.join("Graphics", "Pictures"), ["mapRegion*.png"]),
    (os.path.join("Graphics", "Characters"), ["trchar*.png"]),
    # Needed only by tools/render_maps.py, but small enough to always copy.
    (os.path.join("Graphics", "Tilesets"), ["*.png"]),
    (os.path.join("Graphics", "Autotiles"), ["*.png"]),
]


def copy_graphics(game_root, force=False):
    copied = skipped = 0
    for relative, patterns in GRAPHICS_SETS:
        source = os.path.join(game_root, relative)
        if not os.path.isdir(source):
            print(f"  WARNING: {source} not found, skipping.")
            continue
        target_dir = os.path.join(OUT_DIR, relative)
        os.makedirs(target_dir, exist_ok=True)
        for name in os.listdir(source):
            if not any(fnmatch.fnmatch(name, pattern) for pattern in patterns):
                continue
            source_file = os.path.join(source, name)
            if not os.path.isfile(source_file):
                continue
            target_file = os.path.join(target_dir, name)
            if os.path.exists(target_file) and not force:
                skipped += 1
                continue
            shutil.copy2(source_file, target_file)
            copied += 1
            if copied and copied % 1000 == 0:
                print(f"  {copied} images copied...")
    return copied, skipped


# ── locating and extracting ──────────────────────────────────────────────────

def find_archive(game_dir):
    """Game.rgssad usually sits in a '... Core' subfolder, so search for it."""
    direct = os.path.join(game_dir, ARCHIVE_NAME)
    if os.path.isfile(direct):
        return direct
    matches = []
    for root, _dirs, files in os.walk(game_dir):
        if ARCHIVE_NAME in files:
            matches.append(os.path.join(root, ARCHIVE_NAME))
    if not matches:
        return None
    matches.sort(key=len)
    return matches[0]


def safe_output_path(name):
    """Refuse archive entries that would escape game_resources/."""
    target = os.path.normpath(os.path.join(OUT_DIR, name))
    if os.path.commonpath([os.path.normpath(OUT_DIR), target]) != os.path.normpath(OUT_DIR):
        raise ValueError(f"archive entry escapes the output directory: {name!r}")
    return target


def extract(archive_path, force=False):
    with open(archive_path, "rb") as handle:
        if handle.read(8) != MAGIC:
            print(f"ERROR: {archive_path} is not an RGSSAD v1 archive.")
            return 0, 0

        key = GLOBAL_KEY
        written = skipped = 0
        while True:
            name_len, key = read_uint32_enc(handle, key)
            if name_len is None:
                break
            name, key = read_name_enc(handle, key, name_len)
            data_len, key = read_uint32_enc(handle, key)
            if data_len is None:
                break

            file_key = key
            raw = handle.read(data_len)
            if len(raw) < data_len:
                print(f"  WARNING: truncated data for {name}, stopping.")
                break

            target = safe_output_path(name)
            if os.path.exists(target) and not force:
                skipped += 1
                continue

            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as out:
                out.write(decrypt_file_data(raw, file_key))
            written += 1
            if written and written % 200 == 0:
                print(f"  {written} files written...")
    return written, skipped


# ── verification ─────────────────────────────────────────────────────────────

def check():
    """Report whether game_resources/ has what the build and generators need."""
    problems = []
    if not os.path.isdir(OUT_DIR):
        print(f"MISSING: {OUT_DIR}")
        return False

    for relative in REQUIRED_DIRS:
        path = os.path.join(OUT_DIR, relative)
        count = len(os.listdir(path)) if os.path.isdir(path) else 0
        status = "ok" if count else "EMPTY"
        print(f"  {status:>7}  {relative:<24} {count} files")
        if not count:
            problems.append(relative)

    for relative in REQUIRED_FILES:
        path = os.path.join(OUT_DIR, relative)
        exists = os.path.isfile(path)
        print(f"  {'ok' if exists else 'MISSING':>7}  {relative}")
        if not exists:
            problems.append(relative)

    if problems:
        print("\nIncomplete. Re-run with your game folder, adding --force to overwrite.")
        return False
    print("\ngame_resources/ is complete: the editor can be built and run from source.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Extract Pokemon Insurgence resources into this project.")
    parser.add_argument("game_dir", nargs="?",
                        help=r'Insurgence install folder, e.g. "G:\Games\Insurgence"')
    parser.add_argument("--force", action="store_true",
                        help="overwrite files that already exist")
    parser.add_argument("--check", action="store_true",
                        help="only report what game_resources/ currently has")
    args = parser.parse_args()

    if args.check and not args.game_dir:
        return 0 if check() else 1

    if not args.game_dir:
        parser.print_help()
        print("\nERROR: give the folder your Pokemon Insurgence install lives in.")
        return 2

    if not os.path.isdir(args.game_dir):
        print(f"ERROR: not a folder: {args.game_dir}")
        return 2

    archive = find_archive(args.game_dir)
    if not archive:
        print(f"ERROR: no {ARCHIVE_NAME} found under {args.game_dir}")
        return 2

    game_root = os.path.dirname(archive)
    print(f"Archive : {archive}")
    print(f"Output  : {OUT_DIR}")
    os.makedirs(OUT_DIR, exist_ok=True)

    print("\nExtracting Data from the archive...")
    written, skipped = extract(archive, force=args.force)
    print(f"  {written} files written, {skipped} already present.")

    print("\nCopying Graphics from the installation...")
    copied, graphics_skipped = copy_graphics(game_root, force=args.force)
    print(f"  {copied} images copied, {graphics_skipped} already present.")

    if skipped or graphics_skipped:
        print("  (re-run with --force to overwrite what is already there)")
    print()
    return 0 if check() else 1


if __name__ == "__main__":
    sys.exit(main())
