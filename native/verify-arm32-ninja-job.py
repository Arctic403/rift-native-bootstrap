#!/usr/bin/env python3
"""Static verifier: Android-patched Ninja ARM32 PIE, no host execution."""
# SPDX-License-Identifier: MIT
import hashlib
import json
import os
import re
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out/g4e"
ELF = OUT / "lib/armeabi-v7a/libriftninja_job.so"
PATCH = OUT / "PATCH_REPORT.json"
SOURCE = ROOT / "out/g4d/cache/ninja-build_1.13.2.orig.tar.gz"
LICENSE = ROOT / "out/g4d/NINJA-LICENSE.txt"
BASE = ROOT / "out/g4d/lib/armeabi-v7a/libriftninja.so"
PATCHED_SOURCE = ROOT / "out/g4d/work/source/src/subprocess-posix.cc"
NDK = Path(os.environ["ANDROID_NDK_HOME"]).resolve()
TOOLS = NDK / "toolchains/llvm/prebuilt/linux-x86_64/bin"
READELF = TOOLS / "llvm-readelf"
EXPECTED_SOURCE_SHA = "974d6b2f4eeefa25625d34da3cb36bdcebe7fbce40f4c16ac0835fd1c0cbae17"


def need(ok, message):
    if not ok:
        raise SystemExit("G4-E NINJA VERIFY FAIL: " + message)


def report(*args):
    return subprocess.check_output([str(READELF), *args, str(ELF)], text=True)


need(ELF.is_file() and BASE.is_file(), "patched or baseline Ninja ELF missing")
need(PATCH.is_file() and LICENSE.is_file(), "patch receipt or upstream license missing")
need(hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED_SOURCE_SHA,
     "upstream Ninja source checksum mismatch")
patch = json.loads(PATCH.read_text(encoding="utf-8"))
need(patch["literal_replacements"] == 2 and patch["android_shell"] == "/system/bin/sh",
     "shell patch receipt mismatch")
patched_bytes = PATCHED_SOURCE.read_bytes()
need(hashlib.sha256(patched_bytes).hexdigest() == patch["source_after_sha256"],
     "patched Ninja source checksum mismatch")
need(patched_bytes.count(b'"/system/bin/sh"') == 2
     and b'"/bin/sh"' not in patched_bytes,
     "Android shell launcher source is not precisely patched")
raw = ELF.read_bytes()
need(5000 < len(raw) < 4_000_000, "unexpected Ninja executable size")
need(raw[:4] == b"\x7fELF" and raw[4] == 1 and raw[5] == 1,
     "patched Ninja not ELF32 little endian")
etype, machine = struct.unpack_from("<HH", raw, 16)
entry = struct.unpack_from("<I", raw, 24)[0]
need(etype == 3 and machine == 40 and entry != 0,
     "patched Ninja not Android ARM32 PIE")
need(b"/system/bin/sh\x00" in raw, "patched Ninja binary lacks Android shell literal")
need(b"/bin/sh\x00" not in raw.replace(b"/system/bin/sh\x00", b""), "unexpected legacy shell literal outside Android path")
baseline_sha = hashlib.sha256(BASE.read_bytes()).hexdigest()
binary_sha = hashlib.sha256(raw).hexdigest()
need(binary_sha != baseline_sha, "patched Ninja binary is identical to baseline")

header = report("--file-header")
programs = report("--program-headers")
dynamic = report("--dynamic-table")
need("INTERP" in programs and "/system/bin/linker" in programs,
     "Android ARM32 linker missing")
need("GNU_STACK" in programs and "TEXTREL" not in dynamic,
     "ELF stack or relocation requirements failed")
need("FLAGS_1" in dynamic and "PIE" in dynamic, "PIE ELF flag missing")
needed = re.findall(r"\(NEEDED\).*?Shared library:\s*\[([^\]]+)\]", dynamic)
need("libc.so" in needed and set(needed) <= {"libc.so","libm.so","libdl.so","liblog.so"},
     "unreviewed runtime dependency: " + str(needed))
need("Pkg.Revision = 27.2.12479018" in (NDK / "source.properties").read_text(),
     "NDK r27c revision differs")

receipt = {
    "schema": "rift-native-bootstrap-g4e-ninja-job/1",
    "ninja_version": "1.13.2",
    "upstream_source_sha256": EXPECTED_SOURCE_SHA,
    "source_patch": patch,
    "android_abi": "armeabi-v7a",
    "android_api_target": 28,
    "ndk_revision": "27.2.12479018",
    "artifact": "lib/armeabi-v7a/libriftninja_job.so",
    "artifact_sha256": binary_sha,
    "artifact_size": len(raw),
    "baseline_unpatched_ninja_sha256": baseline_sha,
    "elf": "ELF32 ARM ET_DYN PIE",
    "interpreter": "/system/bin/linker",
    "needed": needed,
    "version_probe_not_a_job_proof": True,
    "device_job_execution_proven": False,
    "general_native_runner_enabled": False,
    "git_sha": os.environ.get("GITHUB_SHA", "unknown"),
}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "SHA256SUMS.txt").write_text(
    binary_sha + "  lib/armeabi-v7a/libriftninja_job.so\n", encoding="utf-8"
)
(OUT / "build-info.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
(OUT / "ELF_REPORT.txt").write_text(
    "\n".join([header, programs, dynamic]), encoding="utf-8"
)
(OUT / "NINJA-LICENSE.txt").write_bytes(LICENSE.read_bytes())
print(json.dumps(receipt, indent=2))
print("PASS: SHA-pinned Android-patched Ninja ELF verified, device spawning NOT tested.")
