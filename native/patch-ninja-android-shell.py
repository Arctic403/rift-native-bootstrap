#!/usr/bin/env python3
"""Strict, minimal Android shell-path patch for pinned Ninja 1.13.2 source.

Only substitutes the two exact upstream /bin/sh C++ string literals with
Android's /system/bin/sh. Fail closed on source drift. No prebuilt binaries
or Termux files are copied.
"""
# SPDX-License-Identifier: MIT
import hashlib
import json
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: patch-ninja-android-shell.py SRC/SUBPROCESS-POSIX.CC REPORT.JSON")
source = Path(sys.argv[1])
report = Path(sys.argv[2])
before = source.read_bytes()
needle = b'"/bin/sh"'
replacement = b'"/system/bin/sh"'
if before.count(needle) != 2 or replacement in before:
    raise SystemExit("Refusing patch: unexpected Ninja 1.13.2 POSIX shell launcher layout")
# Change *only* the shell executable path used by the subprocess launcher.
after = before.replace(needle, replacement)
if after.count(replacement) != 2 or needle in after:
    raise SystemExit("Refusing patch: unexpected post-patch launcher source")
source.write_bytes(after)
receipt = {
    "schema": "rift-native-bootstrap-ninja-android-shell-patch/1",
    "patch_scope": "two exact /bin/sh literals in src/subprocess-posix.cc only",
    "literal_replacements": 2,
    "android_shell": "/system/bin/sh",
    "source_before_sha256": hashlib.sha256(before).hexdigest(),
    "source_after_sha256": hashlib.sha256(after).hexdigest(),
    "upstream_source_version": "1.13.2",
    "changed_binary_build_proven": False,
}
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print("PASS: exactly two Ninja 1.13.2 shell launcher literals patched for Android")
