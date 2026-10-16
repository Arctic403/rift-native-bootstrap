#!/usr/bin/env python3
"""Inspect a pinned upstream Ninja source tar before extraction."""
# SPDX-License-Identifier: MIT
import sys
import tarfile
from pathlib import PurePosixPath

if len(sys.argv) != 2:
    raise SystemExit("usage: check-ninja-source-archive.py PINNED_TAR_GZ")

with tarfile.open(sys.argv[1], "r:gz") as archive:
    members = archive.getmembers()
    if not 30 <= len(members) <= 400:
        raise SystemExit("unexpected Ninja source entry count")
    total = 0
    roots = set()
    has_cmake = False
    has_license = False
    for entry in members:
        name = entry.name
        path = PurePosixPath(name)
        if name.startswith("/") or ".." in path.parts or "\\" in name:
            raise SystemExit("unsafe upstream source entry: " + name)
        if not (entry.isfile() or entry.isdir()):
            raise SystemExit("upstream source includes unsupported symlink/device: " + name)
        if entry.size > 3_000_000:
            raise SystemExit("source entry too large: " + name)
        total += entry.size
        if total > 12_000_000:
            raise SystemExit("source archive exceeds size limit")
        if len(path.parts) < 2:
            if not entry.isdir():
                raise SystemExit("file has no archive root folder: " + name)
            continue
        roots.add(path.parts[0])
        relative = "/".join(path.parts[1:])
        has_cmake |= relative == "CMakeLists.txt"
        has_license |= relative == "COPYING"
    if len(roots) != 1 or not has_cmake or not has_license:
        raise SystemExit("unexpected upstream Ninja source layout")
print("PASS: pinned Ninja source tar archive extraction preflight")
