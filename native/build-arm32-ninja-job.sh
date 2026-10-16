#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# G4-E: build Android ARM32 Ninja with a narrow /system/bin/sh patch.
# Host-side cross-compile ONLY. Do not execute ARM ELF on the CI host.
set -euo pipefail

# Rebuild upstream, checksum-verified Ninja through the proven G4-D lane.
bash native/build-arm32-ninja.sh

ROOT="out/g4d/work"
PATCH_RECEIPT="out/g4e/PATCH_REPORT.json"
python3 native/patch-ninja-android-shell.py \
  "$ROOT/source/src/subprocess-posix.cc" "$PATCH_RECEIPT"
# A changed .cc must recompile: no reuse of unpatched ninja output.
cmake --build "$ROOT/target" --target ninja --clean-first --parallel 2
test -f "$ROOT/target/ninja"

DEST="out/g4e/lib/armeabi-v7a/libriftninja_job.so"
mkdir -p "$(dirname "$DEST")"
cp "$ROOT/target/ninja" "$DEST"
"$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip" \
  --strip-unneeded "$DEST"

python3 native/verify-arm32-ninja-job.py
