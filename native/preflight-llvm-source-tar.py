#!/usr/bin/env python3
"""Fail-closed archive layout validator for SHA-pinned LLVM project sources."""
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
import posixpath
import sys
import tarfile
from pathlib import PurePosixPath

if len(sys.argv) != 2:
    raise SystemExit("usage: preflight-llvm-source-tar.py VERIFIED_LLVM_TAR_XZ")
root_name = "llvm-project-21.1.8.src"
count = 0
size = 0
wanted = {
    f"{root_name}/llvm/CMakeLists.txt",
    f"{root_name}/clang/CMakeLists.txt",
    f"{root_name}/lld/CMakeLists.txt",
    f"{root_name}/llvm/LICENSE.TXT",
}
found = set()

with tarfile.open(sys.argv[1], "r:xz") as archive:
    for member in archive:
        count += 1
        if count > 180000:
            raise SystemExit("LLVM source archive entry count exceeds limit")
        name = member.name
        norm = PurePosixPath(name)
        if (name.startswith("/") or name.startswith("-") or "\\" in name
                or ".." in norm.parts
                or not (name == root_name or name.startswith(root_name + "/"))):
            raise SystemExit("unsafe LLVM archive path: " + name)
        if member.isfile():
            if member.size > 80_000_000:
                raise SystemExit("unexpectedly large LLVM source file: " + name)
            size += member.size
            if size > 1_800_000_000:
                raise SystemExit("LLVM source exceeds 1.8GB uncompressed bound")
        elif member.issym():
            if posixpath.isabs(member.linkname):
                raise SystemExit("absolute symlink in LLVM source: " + name)
            target = posixpath.normpath(
                posixpath.join(posixpath.dirname(name), member.linkname)
            )
            if target != root_name and not target.startswith(root_name + "/"):
                raise SystemExit("symlink escapes LLVM source root: " + name)
        elif member.islnk():
            target = posixpath.normpath(member.linkname)
            if target != root_name and not target.startswith(root_name + "/"):
                raise SystemExit("hardlink escapes LLVM source root: " + name)
        elif not member.isdir():
            raise SystemExit("special file in LLVM source tar: " + name)
        if name in wanted and member.isfile():
            found.add(name)

if found != wanted:
    raise SystemExit("LLVM source archive missing expected LLVM/Clang/LLD or license")
if count < 10000:
    raise SystemExit("LLVM source release suspiciously small")
print(f"PASS: LLVM release archive layout safe: {count} members, {size} file bytes")
