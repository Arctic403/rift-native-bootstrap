#!/usr/bin/env python3
"""G4-F5A: package a bounded, provenance-checked ARM32 Android NDK subset.

Runs on a trusted CI Linux host. Does not build or execute an Android binary.
Inputs: official NDK r27c and SHA-pinned LLVM 21.1.8 source archive.
Outputs: deterministic ZIP + SHA-256 for a later, manual RiftOS import.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tarfile
import zipfile

NDK_REV = "27.2.12479018"
LLVM_VERSION = "21.1.8"
LLVM_SHA = "4633a23617fa31a3ea51242586ea7fb1da7140e426bd62fc164261fe036aa142"
TARGET = "arm-linux-androideabi"
API = "28"
MAX_MEMBER = 16 * 1024 * 1024
MAX_TOTAL = 160 * 1024 * 1024
MAX_ZIP = 80 * 1024 * 1024
MAX_FILES = 6000
STAMP = (2026, 1, 1, 0, 0, 0)


def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def require(cond, why):
    if not cond:
        raise RuntimeError(why)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ndk", required=True, type=Path)
    ap.add_argument("--llvm-archive", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    ndk = args.ndk.resolve(strict=True)
    archive = args.llvm_archive.resolve(strict=True)
    props = (ndk / "source.properties").read_text()
    require("Pkg.Revision = " + NDK_REV in props.splitlines(),
            "Official NDK r27c revision mismatch")
    require(sha(archive) == LLVM_SHA, "LLVM 21.1.8 release archive digest mismatch")
    host = ndk / "toolchains/llvm/prebuilt/linux-x86_64"
    sysroot = host / "sysroot"
    include = sysroot / "usr/include"
    api_lib = sysroot / "usr/lib" / TARGET / API
    require(include.is_dir() and api_lib.is_dir(), "NDK ARM32 API-28 sysroot missing")
    for name in ("stdio.h", "stdlib.h", "stdint.h", "string.h"):
        require((include / name).is_file(), "missing required C header " + name)
    for name in ("crtbegin_dynamic.o", "crtend_android.o", "libc.so",
                 "libdl.so", "libm.so"):
        require((api_lib / name).is_file(), "missing ARM32 API-28 link input " + name)

    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    stage = out / "stage"
    require(not stage.exists(), "G4-F5A stage already exists; refuse overwrite")
    stage.mkdir()
    total = 0
    copied = 0

    def add(blob, relative):
        nonlocal total, copied
        relative = PurePosixPath(relative)
        require(not relative.is_absolute() and
                all(x not in (".", "..", "") for x in relative.parts),
                "unsafe staged resource path")
        require(len(blob) <= MAX_MEMBER, "overlarge staged member: " + str(relative))
        total += len(blob)
        copied += 1
        require(total <= MAX_TOTAL and copied <= MAX_FILES,
                "bounded resource budget exceeded")
        destination = stage.joinpath(*relative.parts)
        require(not destination.exists(), "duplicate staged resource")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(blob)

    def collect(ndk_dir, prefix):
        require(ndk_dir.resolve().is_relative_to(ndk), "NDK path outside official root")
        for item in sorted(ndk_dir.rglob("*")):
            if item.is_dir():
                continue
            require(item.is_file(), "NDK source is not a regular file")
            resolved = item.resolve(strict=True)
            require(resolved.is_relative_to(ndk),
                    "NDK symlink resolves outside NDK directory")
            require(item.stat().st_size <= MAX_MEMBER, "NDK member too large")
            relative = item.relative_to(ndk_dir)
            add(item.read_bytes(), PurePosixPath(prefix, *relative.parts))

    # C/POSIX/Android headers, per-target headers, and precisely API 28 link
    # inputs. Avoid other API levels, host tools and large C++ runtime archives.
    collect(include, "sysroot/usr/include")
    collect(api_lib, "sysroot/usr/lib/" + TARGET + "/" + API)

    # Clang 21 builtins include <stdarg.h>, <stddef.h> etc. These must match
    # the LLVM compiler revision, not the NDK's host Clang 18 resource dir.
    resource_count = 0
    llvm_license = None
    with tarfile.open(archive, mode="r|xz") as stream:
        for member in stream:
            name = PurePosixPath(member.name)
            parts = name.parts
            if len(parts) < 2 or parts[0] in ("", ".", ".."):
                continue
            if parts[-2:] == ("llvm", "LICENSE.TXT") and member.isfile():
                require(member.size <= MAX_MEMBER, "LLVM license oversized")
                llvm_license = stream.extractfile(member).read()
                continue
            try:
                pos = next(i for i in range(len(parts)-3)
                           if parts[i:i+3] == ("clang", "lib", "Headers"))
            except StopIteration:
                continue
            path_parts = parts[pos+3:]
            if not path_parts or member.isdir():
                continue
            require(member.isfile(), "symlink/link in Clang resource headers")
            require(all(t not in ("", ".", "..") for t in path_parts),
                    "unsafe Clang resource entry")
            require(member.size <= MAX_MEMBER, "Clang header exceeds member limit")
            content = stream.extractfile(member)
            require(content is not None, "Clang header read failure")
            data = content.read(MAX_MEMBER + 1)
            require(len(data) == member.size, "Clang resource length mismatch")
            add(data, PurePosixPath("clang-resource/include", *path_parts))
            resource_count += 1
    require(resource_count >= 20 and llvm_license is not None,
            "matching Clang 21 resource directory/license unavailable")
    for name in ("stdarg.h", "stddef.h"):
        require((stage / "clang-resource/include" / name).is_file(),
                "Clang 21 builtin header missing: " + name)

    # Preserve upstream legal/version metadata in the distribution artifact.
    add(llvm_license, "LICENSES/LLVM-LICENSE.txt")
    add((ndk / "source.properties").read_bytes(), "NDK-source.properties")
    for name in ("NOTICE", "LICENSE"):
        entry = ndk / name
        if entry.is_file() and entry.stat().st_size <= MAX_MEMBER:
            add(entry.read_bytes(), "LICENSES/NDK-" + name + ".txt")
    metadata = {
        "schema": "rift-native-bootstrap-g4f5a-ndk-sysroot/1",
        "source": "official Android NDK r27c plus original LLVM 21.1.8 Clang resource headers",
        "ndkRevision": NDK_REV,
        "llvmVersion": LLVM_VERSION,
        "llvmSourceSha256": LLVM_SHA,
        "abi": "armeabi-v7a",
        "target": "armv7a-linux-androideabi28",
        "api": int(API),
        "resourceHeaderFiles": resource_count,
        "nativeCodeExecution": False,
        "androidDeviceVerified": False,
        "totalUncompressedBytes": total,
        "inputStagedFileCount": copied,
        "note": "Not a complete NDK or validated mobile Clang runtime",
    }
    add((json.dumps(metadata, sort_keys=True, indent=2) + "\n").encode(),
        "build-info.json")

    entries = sorted(f for f in stage.rglob("*") if f.is_file())
    sums = "\n".join(sha(p) + "  " + p.relative_to(stage).as_posix()
                     for p in entries) + "\n"
    add(sums.encode(), "SHA256SUMS.txt")
    entries = sorted(f for f in stage.rglob("*") if f.is_file())
    destination = out / "riftndk-sysroot-arm32-api28-r27c-llvm21.zip"
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9, allowZip64=False) as zipout:
        for file in entries:
            name = file.relative_to(stage).as_posix()
            info = zipfile.ZipInfo(name, STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            with file.open("rb") as source, zipout.open(info, "w",
                                                         force_zip64=False) as target:
                shutil.copyfileobj(source, target, length=1024*1024)
    require(destination.stat().st_size <= MAX_ZIP,
            "ZIP exceeds 80 MiB proof-transfer cap")
    with zipfile.ZipFile(destination) as z:
        names = z.namelist()
        require(len(names) == len(set(names)) and
                len(names) == len(entries), "ZIP archive inventory mismatch")
        for member in z.infolist():
            require(not member.is_dir() and
                    PurePosixPath(member.filename).parts[0] != "..",
                    "ZIP archive entry unsafe")
            require(member.file_size <= MAX_MEMBER, "ZIP entry oversized")
            require(hashlib.sha256(z.read(member.filename)).hexdigest() ==
                    sha(stage / member.filename), "ZIP roundtrip checksum mismatch")

    receipt = {
        "schema": "rift-native-bootstrap-g4f5a-transfer-receipt/1",
        "zip": destination.name,
        "zipSha256": sha(destination),
        "zipBytes": destination.stat().st_size,
        "entries": len(entries),
        "resourceHeaders": resource_count,
        "ndkRevision": NDK_REV,
        "llvmVersion": LLVM_VERSION,
        "deviceProof": False,
    }
    (out / "G4F5A-TRANSFER-RECEIPT.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    shutil.rmtree(stage)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
