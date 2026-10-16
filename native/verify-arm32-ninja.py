#!/usr/bin/env python3
"""G4-D ELF32 ARM Ninja verifier. Never launch ARM ELF in CI."""
# SPDX-License-Identifier: MIT
import hashlib
import json
import os
import re
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out/g4d"
ELF = OUT / "lib/armeabi-v7a/libriftninja.so"
SOURCE = OUT / "cache/ninja-build_1.13.2.orig.tar.gz"
LICENSE = OUT / "NINJA-LICENSE.txt"
NDK = Path(os.environ["ANDROID_NDK_HOME"]).resolve()
TOOLS = NDK / "toolchains/llvm/prebuilt/linux-x86_64/bin"
READELF = TOOLS / "llvm-readelf"
EXPECTED_SOURCE_HASH = "974d6b2f4eeefa25625d34da3cb36bdcebe7fbce40f4c16ac0835fd1c0cbae17"


def require(ok, reason):
    if not ok:
        raise SystemExit("NINJA G4-D VERIFY FAIL: " + reason)


def elf_report(*args):
    return subprocess.check_output([str(READELF), *args, str(ELF)], text=True)


require(ELF.is_file(), "ARM32 Ninja ELF missing")
require(SOURCE.is_file(), "pinned Ninja source archive missing")
require(LICENSE.is_file() and LICENSE.stat().st_size > 100, "Ninja license missing")
source_sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
require(source_sha == EXPECTED_SOURCE_HASH, "wrong upstream source SHA-256")

data = ELF.read_bytes()
require(4000 < len(data) < 4_000_000, "unexpected Ninja binary size")
require(data[:4] == b"\x7fELF" and data[4] == 1 and data[5] == 1,
        "not little-endian ELF32")
etype, machine = struct.unpack_from("<HH", data, 16)
entry = struct.unpack_from("<I", data, 24)[0]
require(etype == 3 and machine == 40 and entry != 0,
        "expected executable ELF32 ARM ET_DYN PIE with nonzero entry")
header = elf_report("--file-header")
programs = elf_report("--program-headers")
dynamic = elf_report("--dynamic-table")
require(re.search(r"Class:\s+ELF32\b", header), "readelf ELF32 mismatch")
require(re.search(r"Machine:\s+ARM\b", header), "readelf ARM mismatch")
require("INTERP" in programs and "/system/bin/linker" in programs,
        "Android ARM32 dynamic linker absent")
require("GNU_STACK" in programs, "GNU_STACK segment absent")
require("TEXTREL" not in dynamic, "ELF has forbidden text relocations")
require("FLAGS_1" in dynamic and "PIE" in dynamic, "PIE linker flag absent")

needed = re.findall(r"\(NEEDED\).*?Shared library:\s*\[([^\]]+)\]", dynamic)
allowed = {"libc.so", "libm.so", "libdl.so", "liblog.so"}
require("libc.so" in needed, "Android bionic libc dependency missing")
require(set(needed) <= allowed,
        "extra runtime dependencies require independent packaging review: " + str(needed))
ndk_meta = (NDK / "source.properties").read_text(encoding="utf-8")
require("Pkg.Revision = 27.2.12479018" in ndk_meta, "unexpected NDK revision")

binary_sha = hashlib.sha256(data).hexdigest()
compiler = str(TOOLS / "clang++")
clang_version = subprocess.check_output([compiler, "--version"], text=True).splitlines()[0]
cmake_version = subprocess.check_output(["cmake", "--version"], text=True).splitlines()[0]
receipt = {
    "schema": "rift-native-bootstrap-g4d-ninja/1",
    "device_execution_proven": False,
    "ninja_source_version": "1.13.2",
    "ninja_source_url": "https://deb.debian.org/debian/pool/main/n/ninja-build/ninja-build_1.13.2.orig.tar.gz",
    "ninja_source_sha256": source_sha,
    "ninja_license": "Apache-2.0; see NINJA-LICENSE.txt",
    "ndk_revision": "27.2.12479018",
    "clang_version": clang_version,
    "cmake_version": cmake_version,
    "android_abi": "armeabi-v7a",
    "android_target_api": 28,
    "android_elf": "ELF32 ARM ET_DYN PIE",
    "android_interpreter": "/system/bin/linker",
    "artifact": "lib/armeabi-v7a/libriftninja.so",
    "artifact_size": len(data),
    "artifact_sha256": binary_sha,
    "elf_entry": hex(entry),
    "elf_needed": needed,
    "first_allowed_device_test": ["--version"],
    "native_build_jobs_authorized": False,
    "git_sha": os.environ.get("GITHUB_SHA", "unknown"),
}
(OUT / "SHA256SUMS.txt").write_text(
    binary_sha + "  lib/armeabi-v7a/libriftninja.so\n", encoding="utf-8"
)
(OUT / "build-info.json").write_text(
    json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
)
(OUT / "ELF_REPORT.txt").write_text(
    "\n".join([header, programs, dynamic]), encoding="utf-8"
)
print(json.dumps(receipt, indent=2))
print("PASS: ARM32 Ninja ELF & source verified. Device execution NOT YET PROVEN.")
