# Shiritsu Justice Gakuen: Nekketsu Seishun Nikki 2

<!-- retcomm-readme-metrics -->
[![GitHub downloads (all assets, all releases)](https://img.shields.io/github/downloads/tolotratlt/rival-schools-nekketsu-seishun-nikki-2-recomp/total)](https://github.com/tolotratlt/rival-schools-nekketsu-seishun-nikki-2-recomp/releases)
[![GitHub downloads (latest release)](https://img.shields.io/github/downloads/tolotratlt/rival-schools-nekketsu-seishun-nikki-2-recomp/latest/total)](https://github.com/tolotratlt/rival-schools-nekketsu-seishun-nikki-2-recomp/releases/latest)
[![GitHub release](https://img.shields.io/github/v/release/tolotratlt/rival-schools-nekketsu-seishun-nikki-2-recomp)](https://github.com/tolotratlt/rival-schools-nekketsu-seishun-nikki-2-recomp/releases/latest)
<!-- /retcomm-readme-metrics -->

Static recompilation of **Shiritsu Justice Gakuen: Nekketsu Seishun Nikki 2**
(Capcom, 1999, Japan only — the PlayStation sequel to *Rival Schools: United by
Fate*) built on [psxrecomp](https://github.com/mstan/psxrecomp) and
[recomp-ui](https://github.com/RetroPortingToolKit/recomp-ui).

This is an owned-input kit. You supply your own SLPS-02120 disc image and your
own SCPH-1001 BIOS dump; Generate turns them into C code and compiles the game
on your machine. This repository contains no game disc, no extracted game
executable, no retail BIOS, no generated game code, and no saved game.

| | |
|---|---|
| Region | Japan (NTSC-J) |
| Disc serial | SLPS-02120 |
| Discs | 1 |
| Boot executable | `SLPS_021.20` |
| Supported dump | `Shiritsu Justice Gakuen - Nekketsu Seishun Nikki 2 (Japan).cue` + `.bin`, single data track, 663216960 bytes, MD5 `a7149a13c6992a20732d4ed2fd7e7611` |
| BIOS | SCPH-1001 (USA), 524288 bytes, SHA-256 `71af94d1e47a68c11e8fdb9f8368040601514a42a5a399cda48c7d3bff1e99d3` |

The supported-dump digests are those of the dump this kit was probed from. They
have not been cross-checked against the Redump database. The game runs on the
USA SCPH-1001 BIOS; no Japanese BIOS profile is needed or shipped.

## Related kits

The two USA *Rival Schools: United by Fate* discs have their own kits:
[Arcade Disc](https://github.com/alexbeavs-ps1-ports/rival-schools-recomp) and
[Evolution Disc](https://github.com/alexbeavs-ps1-ports/rival-schools-evolution-recomp).
This kit uses the same pinned framework and launcher versions.

## Setup

1. Download the Windows setup ZIP (`rival-schools-sjgnsn-<version>-windows-x64.zip`) from
   [Releases](https://github.com/tolotratlt/rival-schools-nekketsu-seishun-nikki-2-recomp/releases)
   and extract it into a writable folder.
2. Install Python 3 if it is not already installed.
3. Start `Shiritsu_Justice_Gakuen__Nekketsu_Seishun_Nikki_2.exe`.
4. In the setup wizard select your disc image (the `.cue`) and your SCPH-1001
   BIOS file.
5. Run **Generate & rebuild** and wait for the game to start. The first run
   generates and compiles the game and takes several minutes.
6. Optional, English translation: quit the game and run
   `Install-English-Translation.cmd`. It builds an English mod from your own
   disc image (about a minute, Python 3 required; Pillow is installed into a
   private `.localization-venv` folder if missing). Start the game again:
   **English Translation** is listed and enabled in the launcher's Mods tab.
   Disable it there to play in Japanese.

The wizard uses CMake and Ninja from `PATH` when they are present, otherwise it
downloads the portable build tools (cmake-clang-v1). Keep the `.cue` and the
`.bin` it references together. The ZIP contains no game data: no disc image,
no game executable, no BIOS, and no generated game code.

## Building from source

To build without the setup ZIP:

1. Clone with submodules:
   `git clone --recursive <this repository>`
   (or `git submodule update --init --recursive` in an existing clone).
2. Put your dump in `disc/` with the exact names
   `Shiritsu Justice Gakuen - Nekketsu Seishun Nikki 2 (Japan).cue` / `.bin`,
   and your BIOS at `bios/SCPH1001.BIN`. Both folders are gitignored.
3. On Windows, open an **MSYS2 MINGW64** shell with these packages installed:
   `mingw-w64-x86_64-toolchain mingw-w64-x86_64-cmake mingw-w64-x86_64-ninja
   mingw-w64-x86_64-SDL2 mingw-w64-x86_64-pkgconf mingw-w64-x86_64-vulkan-headers
   mingw-w64-x86_64-shaderc mingw-w64-x86_64-python`.
4. Generate the game and BIOS C code:

   ```bash
   python psxrecomp/psxrecomp_cli.py generate --project-root . --config game.toml \
     --disc "disc/Shiritsu Justice Gakuen - Nekketsu Seishun Nikki 2 (Japan).cue" \
     --bios bios/SCPH1001.BIN --bios-stem SCPH1001 \
     --gen-marker SLPS_021.20_dispatch.c
   ```

5. Configure and build with the MSYS2 compiler:

   ```bash
   export VULKAN_SDK=/mingw64
   cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release \
     -DCMAKE_C_COMPILER=/mingw64/bin/gcc.exe -DCMAKE_CXX_COMPILER=/mingw64/bin/g++.exe \
     -DPSXRECOMP_REQUIRE_GAME_C=ON -DPSX_SETUP_WIZARD=ON \
     -DGLSLC_EXE=/mingw64/bin/glslc.exe
   cmake --build build-release --target psx-runtime
   ```

6. Run `build-release/Shiritsu_Justice_Gakuen__Nekketsu_Seishun_Nikki_2.exe`.

Name the compiler explicitly as above. If a portable `cmake-clang-v1` pack is
present in the shared toolchain cache, `psxrecomp_cli.py rebuild` may pick it
up and mix its libc++ headers with the MSYS2 Vulkan include path, which fails
to compile.

Linux and macOS should work with the same steps and native packages
(CMake, Ninja, Python 3, a C/C++ compiler, SDL, Vulkan headers, glslc), but
have not been tried.

## Status

Version 0.2.0, early bring-up.

- Windows: generated, compiled with MSYS2 GCC, and reported running by the
  maintainer on the first test (October 24, 2026). The 0.1.0 setup ZIP was
  extracted into a clean folder, generated and compiled with its own tools,
  and the resulting game was reported running.
- Linux and macOS: no package is published; not tested.
- Full-game completion, every mode, audio fidelity, and multiplayer are not
  claimed. Seeds are the first-pass boot-executable scan (1267 functions);
  code loaded later from the disc runs through the framework's runtime paths.
- English translation (optional mod built from your disc): MODE SELECT,
  Options and Key Config, Records, EDIT Entry, the Youth Diary 2 title menu,
  the battle and Training pause menus, Training, and Exam Drills '99 with
  Basics Review (menus, report cards, teacher instructions, task prompts).
  Story dialogue, the character select screen, Extras and the shop, Gorin
  Fest, and the battle banners stay in Japanese.
- MODE SELECT has an **Exit** entry below Options that quits the game.
- The Vulkan renderer is offered in the launcher. OpenGL stays the default.

## Diagnostic mode

If the game crashes, freezes, or misbehaves, build the diagnostic variant from
the same generated sources (no regeneration needed):

```bash
cmake -S . -B build-diagnostic -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=/mingw64/bin/gcc.exe -DCMAKE_CXX_COMPILER=/mingw64/bin/g++.exe \
  -DPSXRECOMP_REQUIRE_GAME_C=ON -DPSX_DEBUG_TOOLS=ON \
  -DGLSLC_EXE=/mingw64/bin/glslc.exe
cmake --build build-diagnostic --target psx-runtime
```

Run the exe in `build-diagnostic/`, reproduce the problem, quit, and attach the
report files it leaves next to the exe (`psx_crash.txt`,
`psx_last_run_report.json`, `psx_freeze_heartbeat.json`,
`psx_freeze_dump_*.json`) to a GitHub issue with a short description of what
you did. These files never contain saves, BIOS, or disc images. Details:
`psxrecomp/docs/DIAGNOSTIC_MODE.md`.

## Packaging a release (maintainers)

Always package from a **fresh clone**. A working tree where Generate has run
holds generated BIOS and game C, and a setup host configured there links the
recompiled BIOS into the executable. In an MSYS2 MINGW64 shell with `zip`
installed:

```bash
git clone --recursive https://github.com/tolotratlt/rival-schools-nekketsu-seishun-nikki-2-recomp.git rel
cd rel
bash psxrecomp/tools/ci/build_emitters.sh --framework psxrecomp --build-dir build-recompiler
export VULKAN_SDK=/mingw64
cmake -S . -B build-ci -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=/mingw64/bin/gcc.exe -DCMAKE_CXX_COMPILER=/mingw64/bin/g++.exe \
  -DCMAKE_DISABLE_FIND_PACKAGE_Freetype=ON \
  -DPSXRECOMP_FORCE_SETUP_HOST=ON -DPSXRECOMP_ALLOW_NO_BIOS=ON -DPSX_SETUP_WIZARD=ON \
  -DPSX_GAME_VERSION="$(cat VERSION)" -DGLSLC_EXE=/mingw64/bin/glslc.exe
cmake --build build-ci --target psx-runtime
RELEASE_VERSION="$(cat VERSION)" PSXRECOMP_RUNTIME_BIN_DIR=/mingw64/bin EXCLUDE_DEV_MODS=1 \
  bash scripts/package_setup_release.sh build-ci windows-x64 build-recompiler
```

The configure output must say `BIOS backends linked: (none)`. Before
publishing, remove third-party game images the framework docs carry:

```bash
zip -d dist/rival-schools-sjgnsn-*-windows-x64.zip 'psxrecomp/docs/assets/games/*' \
  'psxrecomp/docs/assets/widescreen/*' 'recomp-ui/assets/consoles/genesis/img/boxart_*'
```

## Legal

You must own the original game. Disc images under `disc/`, the boot executable
extracted there, BIOS dumps under `bios/`, and everything under `generated/`
are gitignored and must never be committed or redistributed. Retail BIOS dumps
are not redistributed and OpenBIOS is not shipped: this kit is retail-BIOS-only,
so Generate needs your own legally dumped SCPH-1001 image.

Default app icon: `assets/psxrecomp.ico` (and `.png` / `.svg`) — Retro-themed
controller mark from `psxrecomp/assets/`. Windows builds embed it via
`APP_ICON`.

Box art is not shipped in this kit or its repository.

The framework (`psxrecomp`) is licensed for noncommercial use only. Nothing
built from this kit may be sold or used commercially.

## About this project

This project was developed with AI assistance. AI assists with code,
documentation, and investigation; the maintainer tests the game and makes
release decisions. Validation claims describe only the tests actually
performed.

## Credits and licenses

Framework: [psxrecomp](https://github.com/mstan/psxrecomp), built from the
pinned fork commit named by the `psxrecomp` submodule. Launcher:
[recomp-ui](https://github.com/RetroPortingToolKit/recomp-ui), pinned by the
`recomp-ui` submodule. Kit layout follows the Rival Schools kits by Alexbeav.
This kit's own files are under [LICENSE](LICENSE); third-party notices are in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and the framework and
launcher licenses remain in their source directories. The original game and
its trademarks belong to their respective owners.

<!-- retcomm-readme-raid -->
---

<p align="center">
  <sub><b>R.A.I.D. — Retro AI Development</b> · a Discord for AI-assisted retro reverse-engineering, decomp &amp; recomp</sub>
</p>

<p align="center">
  <a href="https://discord.gg/Ad9BwSzctP"><img src=".github/raid-discord.png" alt="Join the Retro AI Development (R.A.I.D.) Discord" width="200"></a>
</p>
<!-- /retcomm-readme-raid -->
