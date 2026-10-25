"""Build an English test disc: copy the stock image and apply every patch.

Usage: python apply_all.py <stock.bin> <target.bin> [<mode-select images dir>]
  <target.bin> is overwritten with a copy of <stock.bin> first; pair it with
  a .cue naming it (MODE2/2352, one track). Each patch reads only the stock
  image, so the order matters only where two patches write the same file:
  none do (patch_images.py leaves the files patch_siken.py writes).
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATCHES = [
    ["patch_newopt.py"], ["patch_exe_strings.py"], ["patch_mgtit.py"], ["patch_overlay.py", "kanri"],
    ["patch_menu_biz.py"], ["patch_pause.py"], ["patch_training.py"], ["patch_siken.py"],
    ["patch_images.py"], ["patch_labels.py"], ["patch_testmj.py"],
]


def main(stock, target, menu_images=None):
    shutil.copyfile(stock, target)
    for cmd in PATCHES:
        script, args = cmd[0], cmd[1:]
        extra = [menu_images] if script == "patch_menu_biz.py" and menu_images else []
        print("==", script, *args, flush=True)
        subprocess.run([sys.executable, os.path.join(HERE, script), *args, stock, target, *extra],
                       check=True)


if __name__ == "__main__":
    main(*sys.argv[1:4])
