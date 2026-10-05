# Agent guide for this repo

## What this repo is

The PlatformIO **development platform** for the Nordic nRF54L series
(nRF54L05 / nRF54L10 / nRF54L15) — Cortex-M33 with RRAM, targeting an
Adafruit-style Arduino core on the **s145 SoftDevice v9.0.0**.

This repo holds no firmware source. It is the orchestration layer:
`platform.json` declares the package set, `builder/` drives the build
and upload, `boards/` defines the five board variants, `examples/`
holds runnable sketches (also the CI test matrix).

Out-of-tree platform: consumers install it directly from the repo URL,
not from the PlatformIO Registry.

## Companion repos

| Repo | Role | PIO package |
|---|---|---|
| [`meshtastic/nRF54_Arduino`](https://github.com/meshtastic/nRF54_Arduino) | Arduino core / framework source, s145 SoftDevice headers + hex | `framework-arduinoadafruitnrf54` |
| [`meshtastic/nRF54_Bootloader`](https://github.com/meshtastic/nRF54_Bootloader) | DFU bootloader source + per-board hex | `framework-arduinoadafruitnrf54-bootloader` |

Both are referenced as git URLs pinned to release tags (`#vX.Y.Z`) in
`platform.json` and are **public** — PIO clones them with no
authentication. A framework or bootloader fix reaches consumers only
after a new tag there and a pin bump here; bump the platform version in
the same commit so PlatformIO refreshes its cached copy.

Renovate (`renovate.json`, regex manager) watches both repos' tags and
opens PRs bumping the pins in `platform.json`. It does not touch the
platform `version`; bump that in the Renovate PR before merging.

## Project conventions

### Commit messages

- **Never add `Co-Authored-By: Claude` (or any AI attribution) trailers.**
- Imperative subject, terse but specific. Reference SHAs of related
  prior commits where helpful.
- Multi-paragraph body for non-trivial changes: state the symptom, the
  root cause, and what the fix does. CI build-log excerpts make good
  citations.

### Where a change belongs (cross-repo routing)

The platform <-> framework boundary follows one rule everywhere:

| Change touches | Goes in |
|---|---|
| Compiler invocation: `-mcpu`, `-mfpu`, include paths (`CPPPATH`), `CPPDEFINES`, force-includes, what `BuildLibrary` walks | **here** — `builder/frameworks/arduino/adafruit.py` |
| Board metadata: chip, MCU define, link script name, flash/RAM sizes, SD FWID, bootloader settings address, upload tooling | **here** — `boards/<variant>.json` |
| Toolchain / tool package versions | **here** — `platform.json` |
| Upload / merge / DFU-package logic, upload targets | **here** — `builder/main.py` |
| Example sketches, CI matrix | **here** — `examples/`, `.github/workflows/` |
| C/C++ source, headers, linker scripts, `nrfx_config.h`, variants, bundled-library `library.properties` | framework repo |
| Bootloader source, linker scripts, board defs, per-board hex | bootloader repo |

**Rule of thumb:** if it changes *how the compiler is invoked*, it's
here. If it changes *what gets compiled*, it's framework- or
bootloader-side.

## Architectural fixed points (don't accidentally break these)

### Build script chain

`platform.json` points the `arduino` framework at
`builder/frameworks/arduino/adafruit.py` — the framework build script
(CCFLAGS, CPPPATH, LINKFLAGS, the `BuildLibrary` calls). `builder/main.py` owns post-build: ELF→hex,
SoftDevice merge, DFU packaging, and the `upload` / `softdevice` /
`bootloader` targets.

### `adafruit.py` force-includes `nrf54l_compat.h`

`adafruit.py` adds `-include cores/nRF5/nordic/nrf54l_compat.h` to
CCFLAGS. That header (in the framework repo) aliases nRF52 peripheral
names to nRF54L equivalents so most Adafruit core code compiles
unmodified. Don't remove the force-include.

### `BuildLibrary` must walk both cores/ and variants/

`adafruit.py` calls `env.BuildLibrary` on `cores/nRF5` **and**
`variants/<variant>` — the variant tree contributes `g_ADigitalPinMap`
and per-board IRQ handlers. It also puts `cores/nRF5/sysview/{,SEGGER,Config}`
on CPPPATH because the SEGGER SystemView template `.c` files are walked
unconditionally even though sketches only opt in via `#if CFG_SYSVIEW`.
LINKFLAGS include `-Wl,--wrap=malloc,--wrap=free` for FreeRTOS heap_3.

### GCC 12 cortex-m33: plain `-mcpu`, no `+dsp`

`platform.json` pins `toolchain-gccarmnoneeabi ~1.120301.0` (GCC 12.3).
On that toolchain `cortex-m33` enables DSP by default and **rejects**
the `+dsp` suffix (`'cortex-m33' does not support feature 'dsp'`; only
negative suffixes `+nofp`/`+nodsp` are accepted). Use bare
`-mcpu=cortex-m33` in `adafruit.py`.

### Two hex files, two locations, resolved by `adafruit.py`

- **SoftDevice hex** — from the framework package:
  `{FRAMEWORK_DIR}/bootloader/s145/9.0.0/s145_nrf54l<chip>_9.0.0_softdevice.hex`
  → `env["SOFTDEVICEHEX"]`
- **Bootloader hex** — from the bootloader package:
  `{BOOTLOADER_DIR}/release/<variant>_bootloader.hex`
  → `env["DFUBOOTHEX"]`

`main.py` merges both into `firmware.hex` after the build
(`MERGEBOOTHEX`), so one file boots a blank chip; `userfirmware.hex` stays
the plain application image for DFU packages (`--dev-type 0x0054`). The
bootloader repo's master is source-only — hex files only exist on its
release tags, under `release/`.

### Variant name is a three-repo lockstep contract

`build.variant` in `boards/<v>.json` must equal:
- the directory name in the framework's `variants/<v>/`
- the directory name in the bootloader's `src/boards/<v>/`
- the filename stem of `release/<v>_bootloader.hex` on the bootloader release tag

Renaming a board means renaming all of these together.

### `examples/` is the integration test

`.github/workflows/examples.yml` builds `examples/arduino-blink`,
`arduino-ble-led`, `arduino-ble-uart` — this is the end-to-end test for
the whole platform + framework + bootloader stack. The workflow accepts
`workflow_dispatch`, so you can re-trigger it (e.g. after a framework
push) without a dummy commit here. The two BLE examples set
`lib_ldf_mode = deep+` because Bluefruit54Lib pulls `nRF54Crypto` via a
conditional include that PIO LDF's default `chain` mode skips.

## What's in the tree (orientation)

```
platform.json     - package set: framework, bootloader, toolchain, upload tools
platform.py       - PlatformIO platform class (board/upload tool wiring)
builder/
  frameworks/
    arduino/adafruit.py  - the framework build: CCFLAGS, CPPPATH,
                           force-include, BuildLibrary(cores + variant),
                           SoftDevice + bootloader hex resolution
    _bare.py         - bare-metal (no-framework) build
  main.py           - post-build: ELF->hex, SoftDevice + bootloader merge,
                      DFU packaging, upload (jlink / nrfjprog / nrfutil / pyocd),
                      softdevice / bootloader targets
boards/             - five board JSONs (nrf54l{15,10,05}dk, xiao_nrf54l15(_sense))
examples/           - arduino-blink, arduino-ble-led, arduino-ble-uart
                      (also the CI matrix)
.github/workflows/examples.yml  - integration build of all three examples
```
