"""Build the English translation mod on the player's machine, from their disc.

The setup kit ships no game data: this script reads the player's own stock
disc image, applies every translation patch to a temporary copy, and writes
the result as a local mod (disc-sector overlays guarded by the stock image
digest) where the game runtime looks for installed mods. The temporary copy
is deleted afterwards. Pillow is needed for the text rendering; when it is
missing it is installed into a private virtual environment beside the kit.

Usage (from the kit folder, or through Install-English-Translation.cmd):
  python tools/localization/build_english_mod.py [--disc <.cue|.bin>] [--out <mods/installed dir>]

Without --disc the disc chosen in the launcher (build-release/settings.toml)
is used. Without --out the mod goes to build-release/mods/installed.
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.abspath(os.path.join(HERE, "..", ".."))
STOCK_SHA256 = "62dbc6ca47ec8d9dfbb5797f35d4e720d63e00b5a8e0edd080b149c3ff4f1823"
VENV = os.path.join(KIT, ".localization-venv")


def ensure_pillow():
    """Re-run this script inside a private venv when Pillow is missing."""
    try:
        import PIL  # noqa: F401
        return
    except ImportError:
        pass
    if os.environ.get("NSN2_LOCALIZATION_VENV"):
        sys.exit("Pillow could not be installed in %s" % VENV)
    py = os.path.join(VENV, "Scripts" if os.name == "nt" else "bin",
                      "python.exe" if os.name == "nt" else "python")
    if not os.path.exists(py):
        print("Creating a private Python environment for the translation tools...", flush=True)
        subprocess.run([sys.executable, "-m", "venv", VENV], check=True)
    print("Installing Pillow into it...", flush=True)
    subprocess.run([py, "-m", "pip", "install", "--quiet", "pillow"], check=True)
    env = dict(os.environ, NSN2_LOCALIZATION_VENV="1")
    sys.exit(subprocess.run([py, os.path.abspath(__file__)] + sys.argv[1:], env=env).returncode)


def disc_from_settings():
    for path in (os.path.join(KIT, "build-release", "settings.toml"), os.path.join(KIT, "settings.toml")):
        if os.path.exists(path):
            text = open(path, encoding="utf-8").read()
            m = re.search(r'^\[disc\]\s*\npath\s*=\s*"([^"]+)"', text, re.M)
            if m:
                return m.group(1)
    return None


def bin_from(disc):
    if disc.lower().endswith(".cue"):
        m = re.search(r'FILE\s+"([^"]+)"', open(disc, encoding="utf-8", errors="replace").read())
        if not m:
            sys.exit("no FILE line in %s" % disc)
        return os.path.join(os.path.dirname(disc), m.group(1))
    return disc


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--disc", help="stock .cue or .bin (default: the launcher's disc)")
    parser.add_argument("--out", help="mods/installed folder (default: build-release/mods/installed)")
    args = parser.parse_args()
    ensure_pillow()

    disc = args.disc or disc_from_settings()
    if not disc:
        sys.exit("No disc given and none found in build-release/settings.toml: pass --disc <your .cue>.")
    stock = bin_from(disc)
    if not os.path.exists(stock):
        sys.exit("Disc image not found: %s" % stock)
    print("Checking %s ..." % stock, flush=True)
    if sha256_file(stock) != STOCK_SHA256:
        sys.exit("This is not the supported stock dump of SLPS-02120 (SHA-256 mismatch).")
    out = args.out or os.path.join(KIT, "build-release", "mods", "installed")
    version = open(os.path.join(KIT, "VERSION"), encoding="utf-8").read().strip()

    sys.path.insert(0, HERE)
    import nsn2lz  # noqa: E402
    import apply_all  # noqa: E402
    import make_mod  # noqa: E402
    from patch_newopt import iso_files  # noqa: E402
    from patch_pause import read_file  # noqa: E402

    work = tempfile.mkdtemp(prefix="nsn2-english-")
    try:
        with open(stock, "rb") as f:
            files, sector = iso_files(f)
            _, _, menu = read_file(f, files, sector, "/DAT2/MENU.BIZ")
        menu_dec = os.path.join(work, "MENU_BIZ.dec")
        with open(menu_dec, "wb") as fh:
            fh.write(nsn2lz.decompress(bytes(menu))[0])
        images = os.path.join(work, "mode_select")
        print("Drawing the MODE SELECT textures...", flush=True)
        subprocess.run([sys.executable, os.path.join(HERE, "prepare_mode_select_images.py"),
                        "--source", menu_dec, "--out", images], check=True, stdout=subprocess.DEVNULL)
        patched = os.path.join(work, "english.bin")
        print("Applying the translation patches (about a minute)...", flush=True)
        apply_all.main(stock, patched, images)
        make_mod.main(stock, patched, out, version)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("Done. Start the game: 'English Translation' is listed and enabled in the launcher's Mods tab.")


if __name__ == "__main__":
    main()
