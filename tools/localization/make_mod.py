"""Package the English translation as a local mod (disc overlays) for testing.

Compares the stock image with a patched one (from apply_all.py) sector by
sector and writes a feature-style package (format 6) whose [[overlay]]
entries replace the changed sector runs (target disc_raw), guarded by the
stock image digest. The runtime then plays the stock BIN/CUE with the
translation on top, without changing it.

The payload files hold game data: write the package only under the build
output (for example <exe-dir>/mods/installed), never in the repository.

Usage: python make_mod.py <stock.bin> <patched.bin> <mods-installed-dir> [version]
"""
import hashlib
import os
import sys

PACKAGE = "nsn2.english"
SECTOR = 2352
GAME_ID = "SLPS-02120"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main(stock, patched, root, version="0.1.0"):
    out = os.path.join(root, PACKAGE, version)
    os.makedirs(os.path.join(out, "assets"), exist_ok=True)
    disc_digest = hashlib.sha256()
    runs, current = [], None
    with open(stock, "rb") as a, open(patched, "rb") as b:
        lba = 0
        while True:
            sa, sb = a.read(SECTOR), b.read(SECTOR)
            if not sa:
                break
            disc_digest.update(sa)
            if sa != sb:
                if current and current[0] + len(current[1]) // SECTOR == lba:
                    current[1].extend(sb)
                    current[2].extend(sa)
                else:
                    current = [lba, bytearray(sb), bytearray(sa)]
                    runs.append(current)
            lba += 1
    lines = [
        "format_version = 6",
        'id = "%s"' % PACKAGE,
        'version = "%s"' % version,
        'name = "English Translation"',
        'author = "Tolotra"',
        'description = "Menus, pause menus, Training and Exam Drills in English. Built from your own disc."',
        'resolver = "declarative"',
        "",
        "[[target]]",
        'game_id = "%s"' % GAME_ID,
        'disc_sha256 = "%s"' % disc_digest.hexdigest(),
        "",
        "[[feature]]",
        'id = "english"',
        'name = "English translation"',
        'description = "Replaces the translated files of the disc."',
        'group = "Localization"',
        "default_enabled = true",
    ]
    for lba, new, old in runs:
        name = "assets/lba%06d.bin" % lba
        with open(os.path.join(out, name), "wb") as fh:
            fh.write(new)
        lines += ["", "[[overlay]]", 'feature = "english"', 'target = "disc_raw"',
                  "offset = %d" % (lba * SECTOR), 'file = "%s"' % name,
                  'sha256 = "%s"' % sha256(new), 'expected_sha256 = "%s"' % sha256(old)]
    with open(os.path.join(out, "manifest.toml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    total = sum(len(n) for _, n, _ in runs)
    print("%s %s: %d overlays, %d sectors (%.1f MB) -> %s" % (
        PACKAGE, version, len(runs), total // SECTOR, total / 1e6, out))


if __name__ == "__main__":
    main(*sys.argv[1:5])
