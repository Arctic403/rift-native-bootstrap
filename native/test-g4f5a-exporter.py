#!/usr/bin/env python3
"""Fixture-only regression tests for G4-F5A deterministic ZIP exporter.

Mocks official NDK/LLVM inputs; cannot establish provenance of a real archive.
Real CI still uses exact official NDK revision and SHA-pinned LLVM tarball.
"""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
from unittest.mock import patch
import zipfile


def write(root, rel, payload):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(payload)


def member(tar, name, content):
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mode = 0o644
    tar.addfile(info, io.BytesIO(content))


def main():
    source = Path(__file__).with_name("package-android-arm32-sysroot-g4f5.py")
    spec = importlib.util.spec_from_file_location("g4f5a_exporter", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="g4f5a-fixture-") as tmp:
        root = Path(tmp)
        ndk = root/"ndk"
        (ndk/"source.properties").parent.mkdir(parents=True)
        (ndk/"source.properties").write_text(
            "Pkg.Desc = Android NDK\nPkg.Revision = 27.2.12479018\n")
        base = ndk/"toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr"
        for name in ("stdio.h", "stdlib.h", "stdint.h", "string.h"):
            write(base/"include", name, ("/* " + name + " */\n").encode())
        lib = base/"lib/arm-linux-androideabi/28"
        for name in ("crtbegin_dynamic.o", "crtend_android.o", "libc.so",
                     "libdl.so", "libm.so"):
            write(lib, name, ("fixture:" + name).encode())
        tarpath = root/"llvm-project-21.1.8.src.tar.xz"
        with tarfile.open(tarpath, "w:xz") as tar:
            prefix = "llvm-project-21.1.8.src"
            member(tar, prefix+"/llvm/LICENSE.TXT", b"test LLVM license")
            for name in ["stdarg.h", "stddef.h"] + [
                    "header-%02d.h" % i for i in range(21)]:
                member(tar, prefix+"/clang/lib/Headers/"+name,
                       ("/* fake " + name + " */\n").encode())
        true_sha = hashlib.sha256(tarpath.read_bytes()).hexdigest()
        output = root/"out"
        with patch.object(module, "LLVM_SHA", true_sha):
            with patch.object(sys, "argv", [
                str(source), "--ndk", str(ndk), "--llvm-archive",
                str(tarpath), "--output", str(output)
            ]):
                module.main()
        receipt = json.loads((output/"G4F5A-TRANSFER-RECEIPT.json").read_text())
        packed = output / receipt["zip"]
        assert packed.exists()
        assert not (output/"stage").exists()
        assert hashlib.sha256(packed.read_bytes()).hexdigest() == receipt["zipSha256"]
        with zipfile.ZipFile(packed) as z:
            names = z.namelist()
            assert len(names) == len(set(names)) == receipt["entries"]
            for name in ("sysroot/usr/include/stdio.h",
                         "sysroot/usr/lib/arm-linux-androideabi/28/crtbegin_dynamic.o",
                         "clang-resource/include/stdarg.h",
                         "clang-resource/include/stddef.h",
                         "LICENSES/LLVM-LICENSE.txt", "SHA256SUMS.txt"):
                assert name in names, name

        # Negative test: rejecting a wrong upstream LLVM tar hash.
        with patch.object(module, "LLVM_SHA", "0"*64):
            with patch.object(sys, "argv", [
                str(source), "--ndk", str(ndk), "--llvm-archive",
                str(tarpath), "--output", str(root/"wrong-sha")
            ]):
                try:
                    module.main()
                    raise AssertionError("untrusted LLVM tar was accepted")
                except RuntimeError as err:
                    assert "digest mismatch" in str(err)

        # Negative test: detect missing target-specific CRT startup object.
        (lib/"crtbegin_dynamic.o").unlink()
        with patch.object(module, "LLVM_SHA", true_sha):
            with patch.object(sys, "argv", [
                str(source), "--ndk", str(ndk), "--llvm-archive",
                str(tarpath), "--output", str(root/"no-crt")
            ]):
                try:
                    module.main()
                    raise AssertionError("missing Android CRT was accepted")
                except RuntimeError as err:
                    assert "crtbegin_dynamic.o" in str(err)
    print("PASS G4-F5A: deterministic ZIP roundtrip + checksum/CRT fail-closed fixtures")


if __name__ == "__main__":
    main()
