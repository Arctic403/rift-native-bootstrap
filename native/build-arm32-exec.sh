#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# G4-C: fixed-function, standalone Android ARM32 PIE executable.
# This script CROSS-COMPILES only and never launches an Android executable.
set -euo pipefail

: "${ANDROID_NDK_HOME:?ANDROID_NDK_HOME must identify an official pinned Android NDK}"
NDK="$(realpath "$ANDROID_NDK_HOME")"
TOOLS="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin"
CLANG="$TOOLS/clang"
READELF="$TOOLS/llvm-readelf"
[[ -x "$CLANG" && -x "$READELF" ]] || {
  echo "Required NDK clang/readelf not installed" >&2; exit 1;
}
grep -Fx 'Pkg.Revision = 27.2.12479018' "$NDK/source.properties"
[[ -f native/riftg4c-exec.c ]] || { echo "Run in repository root" >&2; exit 1; }

# Android PackageManager native-lib extraction recognizes lib*.so entries.
# This file is actually an executable PIE, not a shared JNI library.
OUT=out/g4c/lib/armeabi-v7a/libriftg4c_exec.so
mkdir -p "$(dirname "$OUT")"
"$CLANG" \
  --target=armv7a-linux-androideabi26 \
  --sysroot="$NDK/toolchains/llvm/prebuilt/linux-x86_64/sysroot" \
  -std=c11 -O2 -Wall -Wextra -Werror \
  -fPIE -pie -Wl,-z,relro -Wl,-z,now -Wl,--no-undefined \
  -o "$OUT" native/riftg4c-exec.c

"$READELF" -h "$OUT"
"$READELF" -l "$OUT"
sha256sum "$OUT"
echo "Only ABI inspection and hashes were performed; device execution is pending."
