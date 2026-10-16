#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# G4-D: source-verified Android ARM32 Ninja bootstrap. HOST BUILD ONLY.
set -euo pipefail
: "${ANDROID_NDK_HOME:?Set ANDROID_NDK_HOME to official NDK r27c}"
NDK="$(realpath "$ANDROID_NDK_HOME")"
grep -Fx 'Pkg.Revision = 27.2.12479018' "$NDK/source.properties"
test -x "$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/clang++"
test -f "$NDK/build/cmake/android.toolchain.cmake"

# Debian's 1.13.2 upstream source tar, whose SHA-256 is published in
# the Debian archive's signed ninja-build_1.13.2-1 source acceptance.
# No Termux prebuilt binary or com.termux-specific code is imported.
VERSION=1.13.2
SHA256=974d6b2f4eeefa25625d34da3cb36bdcebe7fbce40f4c16ac0835fd1c0cbae17
URL="https://deb.debian.org/debian/pool/main/n/ninja-build/ninja-build_${VERSION}.orig.tar.gz"
CACHE="out/g4d/cache"
WORK="out/g4d/work"
mkdir -p "$CACHE" "$WORK"
SOURCE_ARCHIVE="$CACHE/ninja-build_${VERSION}.orig.tar.gz"
curl -fL --retry 3 --proto '=https' --tlsv1.2 "$URL" -o "$SOURCE_ARCHIVE"
printf '%s  %s\n' "$SHA256" "$SOURCE_ARCHIVE" | sha256sum -c -

# Defensive archive layout: no absolute paths, traversals, links/devices.
python3 native/check-ninja-source-archive.py "$SOURCE_ARCHIVE"
mkdir -p "$WORK/source"
tar -xzf "$SOURCE_ARCHIVE" -C "$WORK/source" --strip-components=1
test -f "$WORK/source/CMakeLists.txt"
test -f "$WORK/source/COPYING"
cp "$WORK/source/COPYING" "out/g4d/NINJA-LICENSE.txt"

# Android API 28 is intentional: first try platform posix_spawn instead
# of bundling Termux's libandroid-spawn; actual Ninja job spawning is
# UNTESTED and will be qualified separately after --version.
cmake -S "$WORK/source" -B "$WORK/target" -G "Unix Makefiles" \
  -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=armeabi-v7a \
  -DANDROID_PLATFORM=android-28 \
  -DANDROID_STL=c++_static \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY \
  -DBUILD_TESTING=OFF \
  -DNINJA_BUILD_TESTING=OFF \
  -DCMAKE_CXX_FLAGS="-fPIE" \
  -DCMAKE_EXE_LINKER_FLAGS="-pie -Wl,-z,relro,-z,now"
cmake --build "$WORK/target" --target ninja --parallel 2
BINARY="$WORK/target/ninja"
test -f "$BINARY"
OUT="out/g4d/lib/armeabi-v7a/libriftninja.so"
mkdir -p "$(dirname "$OUT")"
cp "$BINARY" "$OUT"
"$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip" --strip-unneeded "$OUT"

# Critical: this is not runnable on the x86-64 CI machine. Verification
# checks binary and provenance WITHOUT executing any Android ELF.
python3 native/verify-arm32-ninja.py
