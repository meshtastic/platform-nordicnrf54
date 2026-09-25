# Copyright 2014-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os

from SCons.Script import DefaultEnvironment

env = DefaultEnvironment()
platform = env.PioPlatform()
board = env.BoardConfig()

FRAMEWORK_DIR = platform.get_package_dir("framework-arduinoadafruitnrf54")
assert os.path.isdir(FRAMEWORK_DIR)

# Framework version - Arduino IDE injects this at build time from
# platform.txt as ARDUINO_BSP_VERSION; PIO has no platform.txt so read
# it from the framework's package.json.
_pkg_json = os.path.join(FRAMEWORK_DIR, "package.json")
try:
    with open(_pkg_json) as _f:
        FRAMEWORK_VERSION = json.load(_f).get("version", "0.0.0")
except (OSError, ValueError):
    FRAMEWORK_VERSION = "0.0.0"

mcu = board.get("build.mcu", "")
variant = board.get("build.variant", "")
sd_name = board.get("build.softdevice.sd_name", "s145")
sd_flags = board.get("build.softdevice.sd_flags", "-DS145")
sd_version = board.get("build.softdevice.sd_version", "10.0.1")
# sdk-nrf-bm ships s145 per SoC family (nrf54l, nrf54lm, ...): one API header
# set for the family, one hex per SoC in it. sd_family picks the header set and
# the hex directory, sd_soc the hex itself. build.mcu names the real part
# (nrf54lm20a) and does not match either, so both are declared per board.
sd_family = board.get("build.softdevice.sd_family", "nrf54l")
sd_soc = board.get("build.softdevice.sd_soc", mcu)
ldscript = board.get("build.arduino.ldscript", "")

env.Append(
    ASFLAGS=["-x", "assembler-with-cpp"],

    CFLAGS=["-std=gnu11"],

    CCFLAGS=[
        "-Os",
        "-ffunction-sections",
        "-fdata-sections",
        "-Wall",
        "-mthumb",
        "-mcpu=%s" % board.get("build.cpu"),
        "-mfpu=fpv5-sp-d16",
        "-mfloat-abi=hard",
        "-nostdlib",
        "-include", os.path.join(
            FRAMEWORK_DIR, "cores", "nRF5", "nordic", "nrf54l_compat.h"),
    ],

    CXXFLAGS=[
        "-std=gnu++17",
        "-fno-rtti",
        "-fno-exceptions",
    ],

    CPPDEFINES=[
        ("F_CPU", "$BOARD_F_CPU"),
        # int, not str: the LDF chain+ scanner evaluates "ARDUINO >= 100" in library headers
        ("ARDUINO", 10813),
        "ARDUINO_ARCH_NRF54",
        # Bluefruit54Lib's BLEDis bakes this into the BLE Device Info
        # Service as Firmware Revision. Arduino IDE injects it from
        # platform.txt; PIO reads the framework package.json instead.
        ("ARDUINO_BSP_VERSION", '\\"%s\\"' % FRAMEWORK_VERSION),
        "NRF54L_SERIES",
        "NRF_APPLICATION",
        "__STARTUP_CLEAR_BSS",
        "SOFTDEVICE_PRESENT",
        ("FLOAT_ABI_HARD", 1),
        sd_flags.replace("-D", ""),
    ],

    CPPPATH=[
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "nordic"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "nordic", "nrfx"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "nordic", "nrfx", "mdk"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "nordic", "nrfx", "hal"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "nordic", "nrfx", "haly"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "nordic", "nrfx", "drivers", "include"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "nordic", "nrfx", "soc", "irqs"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "nordic", "nrfx", "helpers"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "nordic", "nrfx", "lib"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "nordic", "nrfx", "bsp", "stable"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "nordic", "nrfx", "bsp", "stable", "mdk"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "nordic", "nrfx", "bsp", "stable", "soc"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "nordic", "CMSIS", "Include"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "nordic", "softdevice",
                     "%s_%s_%s_API" % (sd_name, sd_family, sd_version), "include"),
        # FreeRTOS path is Source/, not source/ — case matters on Linux.
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "freertos", "Source", "include"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "freertos", "config"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "freertos", "portable", "GCC", "nrf54l"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "freertos", "portable", "CMSIS", "nrf54l"),
        # Bluefruit52Lib pulls in nRF54Crypto.h cross-library; expose the
        # path globally so it resolves regardless of PIO LDF mode.
        os.path.join(FRAMEWORK_DIR, "libraries", "nRF54Crypto", "src"),
        # SEGGER SystemView source is shipped verbatim and is walked by the
        # framework BuildLibrary; the Config/*.c files include "SEGGER_SYSVIEW.h"
        # unconditionally even though sketches only pull SysView in via
        # #if CFG_SYSVIEW. Expose the SEGGER + Config dirs so the templates
        # compile; --gc-sections drops the symbols when CFG_SYSVIEW isn't set.
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "sysview"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "sysview", "SEGGER"),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "sysview", "Config"),
        os.path.join(FRAMEWORK_DIR, "variants", variant),
    ],

    LINKFLAGS=[
        "-Os",
        "-Wl,--gc-sections,--relax",
        "-mthumb",
        "-mcpu=%s" % board.get("build.cpu"),
        "-mfpu=fpv5-sp-d16",
        "-mfloat-abi=hard",
        "--specs=nano.specs",
        "--specs=nosys.specs",
        # FreeRTOS heap_3 wraps malloc/free so pvPortMalloc/vPortFree can
        # delegate to newlib's allocator before the scheduler has started.
        # The wrappers call __real_malloc/__real_free which only exist when
        # the linker is told to rename the originals.
        "-Wl,--wrap=malloc",
        "-Wl,--wrap=free",
    ],

    LIBPATH=[
        os.path.join(FRAMEWORK_DIR, "variants", variant),
        os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "linker"),
    ],

    LIBS=["m", "stdc++"],

    LIBSOURCE_DIRS=[
        os.path.join(FRAMEWORK_DIR, "libraries"),
    ],
)

mcu_define = board.get("build.mcu_define", mcu.upper().replace("-", "_") + "_XXAA")
env.Append(CPPDEFINES=[mcu_define])

board_define = board.get("build.arduino_define", "")
if board_define:
    env.Append(CPPDEFINES=[board_define])

if ldscript:
    # Variants may override the chip script; the framework's linker dir holds the defaults.
    ld_path = os.path.join(FRAMEWORK_DIR, "variants", variant, ldscript)
    if not os.path.isfile(ld_path):
        ld_path = os.path.join(FRAMEWORK_DIR, "cores", "nRF5", "linker", ldscript)
    env.Replace(LDSCRIPT_PATH=ld_path)

sd_hex_path = os.path.join(
    FRAMEWORK_DIR, "bootloader", sd_name, sd_version, sd_family,
    "%s_%s_%s_softdevice.hex" % (sd_name, sd_soc, sd_version))

if os.path.isfile(sd_hex_path):
    env.Append(SOFTDEVICEHEX=sd_hex_path)

BOOTLOADER_DIR = platform.get_package_dir(
    "framework-arduinoadafruitnrf54-bootloader")
if BOOTLOADER_DIR:
    # Bootloader hex binaries live under release/ on release tags
    # (filenames carry the variant prefix). The bootloader repo's master
    # is source-only and doesn't carry hex. Note: bin/ would have been
    # the natural name but it's in the bootloader repo's .gitignore for
    # local-build output, so release/ is used instead.
    boot_hex_path = os.path.join(
        BOOTLOADER_DIR, "release", "%s_bootloader.hex" % variant)
    if os.path.isfile(boot_hex_path):
        env.Append(DFUBOOTHEX=boot_hex_path)

libs = []

libs.append(env.BuildLibrary(
    os.path.join("$BUILD_DIR", "FrameworkArduino"),
    os.path.join(FRAMEWORK_DIR, "cores", "nRF5")
))

# Variants contribute g_ADigitalPinMap + per-board IRQ handlers + (when
# the chip's vector table demands it) split-bank GPIOTE handlers.
# Without this BuildLibrary call those symbols are missing at link time.
libs.append(env.BuildLibrary(
    os.path.join("$BUILD_DIR", "FrameworkArduinoVariant"),
    os.path.join(FRAMEWORK_DIR, "variants", variant)
))

env.Prepend(LIBS=libs)
