#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# One-time, host-only cross-compile. Do not execute the Android ELF on the host.
set -euo pipefail

: "${ANDROID_NDK_HOME:?ANDROID_NDK_HOME must point to the pinned official Android NDK}"
NDK="$(realpath "$ANDROID_NDK_HOME")"
TOOLCHAIN="$NDK/toolchains/llvm/prebuilt/linux-x86_64"
CLANG="$TOOLCHAIN/bin/clang"
READELF="$TOOLCHAIN/bin/llvm-readelf"

[[ -x "$CLANG" && -x "$READELF" ]] || {
  echo "Missing verified Android NDK Clang/llvm-readelf" >&2; exit 1;
}
[[ -f "$TOOLCHAIN/sysroot/usr/include/jni.h" ]] || {
  echo "Missing official NDK jni.h" >&2; exit 1;
}
[[ -f native/riftprobe.c ]] || {
  echo "Run from the repository root" >&2; exit 1;
}

OUT="out/lib/armeabi-v7a/libriftprobe.so"
mkdir -p "$(dirname "$OUT")"
"$CLANG" \
  --target=armv7a-linux-androideabi26 \
  --sysroot="$TOOLCHAIN/sysroot" \
  -std=c11 -O2 -Wall -Wextra -Werror \
  -fPIC -fvisibility=hidden -shared \
  -Wl,-z,relro -Wl,-z,now -Wl,--no-undefined \
  -Wl,-soname,libriftprobe.so \
  -o "$OUT" native/riftprobe.c

# Informational compiler and artifact details; the verifier enforces the ELF ABI.
"$CLANG" --version | head -n 1
"$READELF" -h "$OUT"
sha256sum "$OUT"
