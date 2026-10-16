#!/usr/bin/env python3
"""Offline G4-B validation for an ARM32 Android JNI library (no code execution)."""
# SPDX-License-Identifier: MIT
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / 'out/lib/armeabi-v7a/libriftprobe.so'
NDK = Path(os.environ['ANDROID_NDK_HOME']).resolve()
TOOLCHAIN = NDK / 'toolchains/llvm/prebuilt/linux-x86_64'
READELF = TOOLCHAIN / 'bin/llvm-readelf'
CLANG = TOOLCHAIN / 'bin/clang'
SYMBOL = 'Java_com_rift_nativebuildprovider_NativeBuildProbe_nativeAnswer'


def inspect(*args):
    return subprocess.check_output([str(READELF), *args, str(ARTIFACT)], text=True)


def require(ok, message):
    if not ok:
        raise SystemExit('VERIFY FAIL: ' + message)


require(ARTIFACT.is_file(), 'ARM32 ELF missing')
require(0 < ARTIFACT.stat().st_size < 1024 * 1024, 'unexpected ELF size')
header = inspect('--file-header')
dynamic = inspect('--dynamic-table')
symbols = inspect('--wide', '--dyn-syms')
require(re.search(r'Class:\s+ELF32\b', header), 'not ELF32')
require(re.search(r'Machine:\s+ARM\b', header), 'not ARM ELF')
require(re.search(r'Type:\s+DYN\b', header), 'not shared-object ELF')
require(re.search(r'Data:\s+2.s complement, little endian', header), 'not little endian')
require(SYMBOL in symbols, 'expected JNI export not in dynamic symbol table')
require(re.search(r'\bGLOBAL\b.*\bDEFAULT\b.*' + re.escape(SYMBOL), symbols),
        'JNI function not default-visible global')
needed = re.findall(r'\(NEEDED\).*?Shared library:\s*\[([^\]]+)\]', dynamic)
allowed = {'libc.so', 'libm.so', 'libdl.so', 'liblog.so'}
require(set(needed) <= allowed, f'unexpected runtime dependencies: {needed}')
require('libriftprobe.so' in dynamic, 'ELF SONAME missing')

file_hash = hashlib.sha256(ARTIFACT.read_bytes()).hexdigest()
source_hash = hashlib.sha256((ROOT / 'native/riftprobe.c').read_bytes()).hexdigest()
ndk_props = (NDK / 'source.properties').read_text(encoding='utf-8')
require('Pkg.Revision = 27.2.12479018' in ndk_props, 'wrong Android NDK revision')
clang_line = subprocess.check_output([str(CLANG), '--version'], text=True).splitlines()[0]
info = {
    'schema': 'rift-native-bootstrap-arm32-probe/1',
    'abi': 'armeabi-v7a',
    'android_elf_target': 'armv7a-linux-androideabi26',
    'android_api_min': 26,
    'ndk_revision': '27.2.12479018',
    'clang_version': clang_line,
    'source_sha256': source_hash,
    'artifact': 'lib/armeabi-v7a/libriftprobe.so',
    'artifact_size': ARTIFACT.stat().st_size,
    'artifact_sha256': file_hash,
    'elf_type': 'ELF32/ARM/DYN',
    'jni_export': SYMBOL,
    'needed': needed,
    'git_sha': os.environ.get('GITHUB_SHA', 'local-uncommitted'),
    'native_execution_proven': False,
}
( ROOT / 'out/SHA256SUMS.txt').write_text(f'{file_hash}  lib/armeabi-v7a/libriftprobe.so\n')
( ROOT / 'out/build-info.json').write_text(json.dumps(info, indent=2) + '\n')
( ROOT / 'out/ELF_REPORT.txt').write_text('\n'.join([header, dynamic, symbols]))
print(json.dumps(info, indent=2))
print('PASS: static ARM32 ELF/JNI verification (device load NOT YET TESTED)')
