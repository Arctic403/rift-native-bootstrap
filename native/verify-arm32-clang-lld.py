#!/usr/bin/env python3
"""G4-F1 static verification: Android ARM32 Clang + LLD bootstrap, no ELF runs."""
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
import hashlib
import json
import os
import re
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out/g4f"
NDK = Path(os.environ["ANDROID_NDK_HOME"]).resolve()
READELF = NDK / "toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf"
LLVM_SHA = "4633a23617fa31a3ea51242586ea7fb1da7140e426bd62fc164261fe036aa142"
ARCHIVE = OUT / "cache/llvm-project-21.1.8.src.tar.xz"
LICENSE = OUT / "LLVM-LICENSE.txt"
ARTIFACTS = {
    "clang": OUT / "lib/armeabi-v7a/libriftclang.so",
    "lld": OUT / "lib/armeabi-v7a/libriftlld.so",
}
ALLOWED_NEEDED = {"libc.so", "libm.so", "libdl.so", "liblog.so"}
results = {}
full_reports = []


def check(value, reason):
    if not value:
        raise SystemExit("G4-F1 VERIFY FAIL: " + reason)


check(ARCHIVE.is_file(), "pinned LLVM source missing")
check(hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == LLVM_SHA,
      "pinned source SHA-256 does not match")
check(LICENSE.is_file() and LICENSE.stat().st_size > 100,
      "LLVM Apache-2.0 WITH LLVM-exception license missing")
check("Pkg.Revision = 27.2.12479018" in
      (NDK / "source.properties").read_text(encoding="utf-8"),
      "cross compiler NDK revision changed")

for name, binary in ARTIFACTS.items():
    check(binary.is_file(), f"missing Android ARM32 {name} binary")
    # Hash in streaming mode; large compiler files should not be buffered twice.
    digest = hashlib.sha256()
    with binary.open("rb") as source:
        first = source.read(64)
        check(first[:4] == b"\x7fELF" and first[4] == 1 and first[5] == 1,
              f"{name} must be ELF32 little endian")
        typ, machine = struct.unpack_from("<HH", first, 16)
        entry = struct.unpack_from("<I", first, 24)[0]
        check(typ == 3 and machine == 40 and entry != 0,
              f"{name} must be Android ARM PIE with an entry point")
        digest.update(first)
        for part in iter(lambda: source.read(1 << 20), b""):
            digest.update(part)
    check(100_000 <= binary.stat().st_size <= 200_000_000,
          f"{name} file size outside reviewed bounds")
    def readelf(*args):
        return subprocess.check_output(
            [str(READELF), *args, str(binary)], text=True
        )
    header = readelf("--file-header")
    program = readelf("--program-headers")
    dynamic = readelf("--dynamic-table")
    check(re.search(r"Class:\s+ELF32\b", header) is not None,
          f"{name} ELF32 mismatch")
    check(re.search(r"Machine:\s+ARM\b", header) is not None,
          f"{name} ARM mismatch")
    check("/system/bin/linker" in program and "INTERP" in program,
          f"{name} Android program interpreter missing")
    check("GNU_STACK" in program and "TEXTREL" not in dynamic,
          f"{name} unexpected stack/relocation properties")
    check("FLAGS_1" in dynamic and "PIE" in dynamic,
          f"{name} PIE linker flag not set")
    deps = re.findall(
        r"\(NEEDED\).*?Shared library:\s*\[([^\]]+)\]", dynamic
    )
    check("libc.so" in deps and set(deps) <= ALLOWED_NEEDED,
          f"{name} requires unreviewed libraries: {deps}")
    results[name] = {
        "apk_native_entry": "lib/armeabi-v7a/" + binary.name,
        "sha256": digest.hexdigest(),
        "bytes": binary.stat().st_size,
        "elf": "ELF32 ARM ET_DYN PIE",
        "android_linker": "/system/bin/linker",
        "needed": deps,
        "device_execution_proven": False,
    }
    full_reports.append(f"===== {name} =====\n{header}\n{program}\n{dynamic}")

check(results["clang"]["sha256"] != results["lld"]["sha256"],
      "compiler/linker artifacts unexpectedly identical")
ndk_compiler = NDK / "toolchains/llvm/prebuilt/linux-x86_64/bin/clang"
version = subprocess.check_output(
    [str(ndk_compiler), "--version"], text=True
).splitlines()[0]
info = {
    "schema": "rift-native-bootstrap-g4f-arm32-clang-lld/1",
    "llvm_upstream_version": "21.1.8",
    "llvm_source_sha256": LLVM_SHA,
    "llvm_license": "Apache-2.0 WITH LLVM-exception; see LLVM-LICENSE.txt",
    "android_ndk_revision": "27.2.12479018",
    "ndk_host_compiler_version": version,
    "android_abi": "armeabi-v7a",
    "android_target_api": 28,
    "host_tablegen_used": True,
    "arm_backend_only": True,
    "android_build_has_been_executed": False,
    "clang_runtime_resource_headers_included": False,
    "full_android_sysroot_included": False,
    "llvm_binaries": results,
    "device_hello_c_compilation_proven": False,
    "native_provider_unchanged": True,
    "git_sha": os.environ.get("GITHUB_SHA", "unknown"),
}
(OUT / "build-info.json").write_text(
    json.dumps(info, indent=2) + "\n", encoding="utf-8"
)
(OUT / "SHA256SUMS.txt").write_text(
    "".join(f'{item["sha256"]}  {item["apk_native_entry"]}\n'
            for item in results.values()), encoding="utf-8"
)
(OUT / "ELF_REPORT.txt").write_text(
    "\n".join(full_reports), encoding="utf-8"
)
print(json.dumps(info, indent=2))
print("PASS: pinned LLVM Clang/LLD ARM32 ELF static checks only")
print("NO claim of Android execution or hello.c compilation")
