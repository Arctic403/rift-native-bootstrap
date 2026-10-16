#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
# G4-F1 experimental: host TableGen -> ARM32 Android Clang/LLD.
# Do not execute target binaries on the Linux host or modify device components.
set -euo pipefail
: "${ANDROID_NDK_HOME:?Use verified Android NDK r27c for cross-compilation}"
NDK="$(realpath "$ANDROID_NDK_HOME")"
grep -Fx 'Pkg.Revision = 27.2.12479018' "$NDK/source.properties"
test -x "$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/clang++"
test -f "$NDK/build/cmake/android.toolchain.cmake"

LLVM_VERSION="21.1.8"
LLVM_SHA="4633a23617fa31a3ea51242586ea7fb1da7140e426bd62fc164261fe036aa142"
LLVM_URL="https://github.com/llvm/llvm-project/releases/download/llvmorg-${LLVM_VERSION}/llvm-project-${LLVM_VERSION}.src.tar.xz"

ROOT="out/g4f"
CACHE="$ROOT/cache"
SOURCE="$ROOT/source"
HOST="$ROOT/host"
ANDROID="$ROOT/android"
mkdir -p "$CACHE" "$SOURCE"
ARCHIVE="$CACHE/llvm-project-${LLVM_VERSION}.src.tar.xz"

# Trust pinned original source only; never download arbitrary CI dependencies.
curl -fL --retry 3 --proto '=https' --tlsv1.2 "$LLVM_URL" -o "$ARCHIVE"
printf '%s  %s\n' "$LLVM_SHA" "$ARCHIVE" | sha256sum -c -
# Reject obvious tar traversal and symlink/hardlink extraction surprises.
python3 native/preflight-llvm-source-tar.py "$ARCHIVE"
tar --no-same-owner --no-same-permissions -xJf "$ARCHIVE" \
  -C "$SOURCE" --strip-components=1
test -f "$SOURCE/llvm/CMakeLists.txt"
test -f "$SOURCE/llvm/LICENSE.TXT"
test -f "$SOURCE/clang/CMakeLists.txt"
test -f "$SOURCE/lld/CMakeLists.txt"

# LLVM cross builds require tools executing on the build machine.
# Never try to run an Android ARM32 TableGen executable on x86-64.
cmake -S "$SOURCE/llvm" -B "$HOST" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DLLVM_ENABLE_PROJECTS=clang \
  -DLLVM_TARGETS_TO_BUILD=ARM \
  -DLLVM_INCLUDE_TESTS=OFF -DLLVM_INCLUDE_EXAMPLES=OFF \
  -DLLVM_INCLUDE_BENCHMARKS=OFF -DLLVM_ENABLE_ASSERTIONS=OFF \
  -DLLVM_ENABLE_ZLIB=OFF -DLLVM_ENABLE_ZSTD=OFF \
  -DLLVM_ENABLE_TERMINFO=OFF -DLLVM_ENABLE_LIBXML2=OFF \
  -DLLVM_ENABLE_LIBEDIT=OFF
cmake --build "$HOST" --target llvm-tblgen clang-tblgen --parallel 2
test -x "$HOST/bin/llvm-tblgen"
test -x "$HOST/bin/clang-tblgen"

# This compiler must RUN on the phone, not the CI machine.
# Target Android 28 for the Android 13, 32-bit user device.
cmake -S "$SOURCE/llvm" -B "$ANDROID" -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=armeabi-v7a -DANDROID_PLATFORM=android-28 \
  -DANDROID_STL=c++_static \
  -DCMAKE_BUILD_TYPE=MinSizeRel \
  -DCMAKE_INSTALL_PREFIX="$PWD/$ROOT/install-do-not-execute" \
  -DLLVM_HOST_TRIPLE=armv7a-linux-androideabi28 \
  -DLLVM_DEFAULT_TARGET_TRIPLE=armv7a-linux-androideabi28 \
  -DLLVM_NATIVE_TOOL_DIR="$PWD/$HOST/bin" \
  -DLLVM_ENABLE_PROJECTS="clang;lld" \
  -DLLVM_TARGETS_TO_BUILD=ARM \
  -DLLVM_INCLUDE_TESTS=OFF -DLLVM_INCLUDE_EXAMPLES=OFF \
  -DLLVM_INCLUDE_BENCHMARKS=OFF -DLLVM_ENABLE_ASSERTIONS=OFF \
  -DLLVM_ENABLE_ZLIB=OFF -DLLVM_ENABLE_ZSTD=OFF \
  -DLLVM_ENABLE_TERMINFO=OFF -DLLVM_ENABLE_LIBXML2=OFF \
  -DLLVM_ENABLE_LIBEDIT=OFF -DLLVM_ENABLE_FFI=OFF \
  -DLLVM_BUILD_LLVM_DYLIB=OFF -DLLVM_LINK_LLVM_DYLIB=OFF \
  -DCLANG_INCLUDE_TESTS=OFF \
  -DCMAKE_CXX_FLAGS="-fvisibility=hidden -ffunction-sections -fdata-sections" \
  -DCMAKE_EXE_LINKER_FLAGS="-Wl,-z,relro,-z,now -Wl,--gc-sections"
cmake --build "$ANDROID" --target clang lld --parallel 2

CLANG="$ANDROID/bin/clang"
LLD="$ANDROID/bin/lld"
test -f "$CLANG"
test -f "$LLD"
LIBS="$ROOT/lib/armeabi-v7a"
mkdir -p "$LIBS"
cp "$CLANG" "$LIBS/libriftclang.so"
cp "$LLD" "$LIBS/libriftlld.so"
STRIP="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip"
"$STRIP" --strip-unneeded "$LIBS/libriftclang.so"
"$STRIP" --strip-unneeded "$LIBS/libriftlld.so"
cp "$SOURCE/llvm/LICENSE.TXT" "$ROOT/LLVM-LICENSE.txt"
# The source release license applies to all components; retain NOTICE if present.
if test -f "$SOURCE/llvm/NOTICE.txt"; then
  cp "$SOURCE/llvm/NOTICE.txt" "$ROOT/LLVM-NOTICE.txt"
fi
python3 native/verify-arm32-clang-lld.py
