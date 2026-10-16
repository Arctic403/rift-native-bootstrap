#!/usr/bin/env python3
"""G4-C offline ARM32 PIE ELF verifier. Does NOT launch the binary."""
# SPDX-License-Identifier: MIT
import hashlib
import json
import os
import re
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out/g4c"
ELF = OUT / "lib/armeabi-v7a/libriftg4c_exec.so"
SOURCE = ROOT / "native/riftg4c-exec.c"
NDK = Path(os.environ["ANDROID_NDK_HOME"]).resolve()
TOOLS = NDK / "toolchains/llvm/prebuilt/linux-x86_64/bin"
READELF = TOOLS / "llvm-readelf"
CLANG = TOOLS / "clang"
MARKER = b"RIFT_G4C_EXEC_OK\n"


def require(ok, msg):
    if not ok:
        raise SystemExit("G4-C VERIFY FAILED: " + msg)


def readelf(*args):
    return subprocess.check_output([str(READELF), *args, str(ELF)], text=True)


require(ELF.is_file(), "ELF artifact is missing")
raw = ELF.read_bytes()
require(1024 <= len(raw) < 1024 * 1024, "unexpected ELF size")
require(raw[:4] == b"\x7fELF", "ELF magic missing")
require(raw[4] == 1 and raw[5] == 1, "not little-endian ELF32")
elf_type, elf_machine = struct.unpack_from("<HH", raw, 16)
elf_entry = struct.unpack_from("<I", raw, 24)[0]
require(elf_type == 3, "expected ET_DYN position-independent executable")
require(elf_machine == 40, "expected ARM machine architecture")
require(elf_entry != 0, "no executable entry point")
require(MARKER in raw, "fixed marker is absent")

revision = (NDK / "source.properties").read_text(encoding="utf-8")
require("Pkg.Revision = 27.2.12479018" in revision, "wrong NDK revision")
header = readelf("--file-header")
programs = readelf("--program-headers")
dynamic = readelf("--dynamic-table")
require(re.search(r"Class:\s+ELF32\b", header), "readelf disagrees on ELF32")
require(re.search(r"Machine:\s+ARM\b", header), "readelf disagrees on machine")
require("INTERP" in programs and "/system/bin/linker" in programs,
        "Android ARM32 dynamic program interpreter missing")
require("GNU_STACK" in programs, "GNU stack segment missing")
require("TEXTREL" not in dynamic, "text relocations not allowed")
needed = re.findall(r"\(NEEDED\).*?Shared library:\s*\[([^\]]+)\]", dynamic)
require("libc.so" in needed, "bionic libc dependency missing")
require(set(needed) <= {"libc.so", "libdl.so", "libm.so"},
        "unexpected shared libraries: " + str(needed))

digest = hashlib.sha256(raw).hexdigest()
source_sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
clang_line = subprocess.check_output([str(CLANG), "--version"], text=True).splitlines()[0]
info = {
    "schema": "rift-native-bootstrap-g4c-arm32-exec/1",
    "purpose": "Fixed-output Android ARM32 process launch probe ONLY",
    "device_execution_proven": False,
    "android_abi": "armeabi-v7a",
    "android_target": "armv7a-linux-androideabi26",
    "ndk_revision": "27.2.12479018",
    "clang_version": clang_line,
    "build_source_sha256": source_sha,
    "artifact": "lib/armeabi-v7a/libriftg4c_exec.so",
    "artifact_sha256": digest,
    "artifact_size": len(raw),
    "elf_class": "ELF32",
    "elf_machine": "ARM",
    "elf_type": "ET_DYN (PIE executable)",
    "elf_entry": hex(elf_entry),
    "program_interpreter": "/system/bin/linker",
    "needed": needed,
    "stdout_expected": MARKER.decode("ascii"),
    "exit_code_expected": 0,
    "git_sha": os.environ.get("GITHUB_SHA", "unknown"),
}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "SHA256SUMS.txt").write_text(
    f"{digest}  lib/armeabi-v7a/libriftg4c_exec.so\n", encoding="utf-8"
)
(OUT / "build-info.json").write_text(
    json.dumps(info, indent=2) + "\n", encoding="utf-8"
)
(OUT / "ELF_REPORT.txt").write_text(
    "\n".join([header, programs, dynamic]), encoding="utf-8"
)
print(json.dumps(info, indent=2))
print("PASS G4-C: static Android ARM32 PIE executable verification; NOT device-executed")
