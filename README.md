# Rift Native Bootstrap

A **standalone, manually triggered** GitHub Actions project for building RiftOS's first Android **ARM32 (`armeabi-v7a`)** JNI test library. This bootstrap is unrelated to the RiftOS Core, Shell, Recovery or APK-signing process.

## Run the one-time build

1. Commit `native/` and `.github/workflows/build-arm32-probe.yml` to this repository's default branch.
2. On GitHub, open **Actions → Build Android ARM32 JNI probe → Run workflow**.
3. After the job succeeds, download the `riftprobe-armeabi-v7a-ndk-r27c` artifact from its run page.
4. Check `SHA256SUMS.txt`, `build-info.json`, `ELF_REPORT.txt` and the actual `lib/armeabi-v7a/libriftprobe.so`.
5. **Do not install or claim a working ARM32 native probe yet.** The SHA-256 must first be copied into the Native Build Provider's `NativeBuildProbe.kt` and `rift-hosted.json`, and the signed APK must be built and tested on the ARM32 phone.

## What it does and does not do

The workflow runs on GitHub's `ubuntu-24.04` **x86-64** hosted runner, installs exactly **Android NDK r27c (`27.2.12479018`)**, cross-compiles a harmless fixed-function JNI C library targeting **`armv7a-linux-androideabi26`**, then statically verifies its `ELF32/ARM/DYN` format, JNI symbol, allowed dynamic dependencies, and SHA-256. It publishes the library and machine-readable receipts for manual transfer back to RiftOS.

It **does not execute Android ELF code** on the x86-64 CI runner, include the whole Termux toolchain, compile Rift++, sign an APK, alter a repository outside this bootstrap, modify Android permissions or open native build execution. The provider APK still must prove the library loads on-device.

The JNI test source is self-contained and MIT-licensed. No Termux source files, patches or prebuilt packages are included at this stage.

## G4-C — standalone ARM32 executable delivery (not yet device-proven)

GitHub Actions now also offers **Build Android ARM32 executable probe** as a separate, manual workflow. This does NOT modify the proven JNI workflow.

1. Run **Actions → Build Android ARM32 executable probe → Run workflow** on the default branch.
2. After success, download the artifact `riftg4c-exec-armeabi-v7a-ndk-r27c`.
3. Check `out/g4c/SHA256SUMS.txt`, `out/g4c/build-info.json`, `out/g4c/ELF_REPORT.txt` and `out/g4c/lib/armeabi-v7a/libriftg4c_exec.so` (the workflow artifact may present the files without their `out/g4c/` prefix).
4. For the RiftOS MCP/RiftGit handoff used in this project, you may commit the downloaded artifact ZIP to **this bootstrap repository only**, and report that it is ready. It will then be pulled and SHA-checked before any provider changes.

The file is a **fixed-output Android ARM32 PIE executable**, despite its `lib*.so` filename, which is necessary for the installer’s `lib/armeabi-v7a/` extraction convention. It is **not a JNI library** and should never be loaded by `System.loadLibrary`. When later packaged into the Native Build Provider, a separately reviewed, exact-path, SHA-pinned, time-bounded launch test will check output `RIFT_G4C_EXEC_OK` and exit code 0; there will be no arbitrary command, argument input, shell or general native runner.

The CI workflow verifies **ELF32 ARM, ET_DYN PIE, executable entry point, Android interpreter `/system/bin/linker`, fixed marker, `DT_NEEDED` library dependencies, NDK r27c revision and SHA-256**. It does not run the ELF on Ubuntu and does not prove that the Android app will be allowed to execute it. The provider’s targetSdk 35 stays unchanged. Do not install, execute or enable compiler operations until the separate device proof is validated.

## G4-D — ARM32 Ninja compiler-toolchain bootstrap (CI only)

Run the isolated **Build Android ARM32 Ninja G4-D** workflow manually on the repository's default branch. It downloads **Ninja 1.13.2 source** from the Debian source archive, checks the published SHA-256 `974d6b2f4eeefa25625d34da3cb36bdcebe7fbce40f4c16ac0835fd1c0cbae17` **before extraction**, and cross-builds with Android NDK r27c for **`armeabi-v7a`, Android API 28**. The source archive is used as a pinned upstream source snapshot, not a prebuilt Termux package.

We are intentionally trying API 28 to avoid Termux's historic **libandroid-spawn** dependency for older Android API targets. This is **experimental**; CI will fail if linker/runtime dependencies aren't compatible. The NDK's **static C++ runtime** is requested; the verifier refuses unreviewed dynamic dependencies.

If successful, download the `riftninja-armeabi-v7a-ndk-r27c` artifact containing:
- `lib/armeabi-v7a/libriftninja.so` — actually an **ELF32 ARM PIE executable**, named as a `lib*.so` only for Android package manager extraction.
- `SHA256SUMS.txt`, `build-info.json`, `ELF_REPORT.txt`, and `NINJA-LICENSE.txt` — reproducibility/provenance and redistribution receipts.

**Do not launch the compiled Ninja binary on the CI host and do not install it yet.** When you upload the artifact ZIP to this repository, the RiftOS MCP will pull it with RiftGit, verify hashes and architecture, and prepare a distinct Native Build Provider candidate with a **single fixed `--version` test**, not a general native build runner.

**Limit of proof:** Ninja's `--version` does not prove subprocess/job spawning. A separate approved, deterministic local build test and permissions/source confinement review must happen before allowing any real Ninja builds. Clang, LLD, CMake and sysroot are not installed by G4-D.

Sources: [upstream Ninja release](https://github.com/ninja-build/ninja/releases/tag/v1.13.2), [Debian Ninja source SHA-256 announcement](https://tracker.debian.org/news/1691166/accepted-ninja-build-1132-1-source-into-unstable/), and [Termux native-build architecture guide](https://github.com/termux/termux-packages/wiki/Building-packages).

## G4-E — Android Ninja fixed-job compatibility rebuild

The earlier Ninja 1.13.2 **`--version` passed on the ARM32 phone**, but that does not test job spawning. Upstream Ninja uses a POSIX shell at `/bin/sh` while Android exposes `/system/bin/sh`. A separate, manually triggered CI workflow **Build Android ARM32 Ninja job-spawn candidate** now rebuilds the identical pinned Ninja 1.13.2 source, replacing only the **two exact shell path literals** after a strict source-layout check. The patched source and ELF are SHA-verified independently; all other application and toolchain code stays unchanged.

To run:
1. Open `Actions → Build Android ARM32 Ninja job-spawn candidate` and run it manually on `main`.
2. After CI passes, download **`riftninja-job-armeabi-v7a-ndk-r27c`**.
3. Retain `SHA256SUMS.txt`, `build-info.json`, `PATCH_REPORT.json`, `ELF_REPORT.txt`, `NINJA-LICENSE.txt` and `lib/armeabi-v7a/libriftninja_job.so`.
4. Upload that ZIP to this bootstrap repo. RiftGit will pull it, verify the new hash and provenance, then prepare an independent Provider v0.6 fixed copy-job test.

**No user-supplied manifest or commands are permitted for the device test.** The planned test runs one fixed Ninja rule that copies a known constant text file into a second private temporary file, checks the output and cleans up. The current provider v0.5, general native runner, compiler operations, Core, Shell and Recovery stay unchanged until a new APK is manually built and approved. This rebuilt Ninja is not a completed toolchain or evidence that arbitrary Ninja jobs are safe.

## G4-F1 — Android-native ARM32 Clang + LLD bootstrap (experimental)

**This is a different, much larger build than Ninja.** The goal is to cross-compile actual **ARM32 Android executables** for LLVM Clang and LLD on a GitHub Ubuntu runner. We specifically do *not* copy host Linux x86-64 NDK `clang` onto the phone. The bootstrap runs two builds of the pinned LLVM **21.1.8** source: host `llvm-tblgen`/`clang-tblgen`, followed by Android `armeabi-v7a` Clang and LLD using official NDK **r27c** and an ARM-only backend.

- Run **Actions → Build Android ARM32 Clang LLD G4-F1 → Run workflow** on `main` when instructed.
- Source: upstream `llvm-project-21.1.8.src.tar.xz`, SHA-256 `4633a23617fa31a3ea51242586ea7fb1da7140e426bd62fc164261fe036aa142`. The checksum matches the published Termux libllvm source recipe, but **no Termux binaries** are copied.
- The GitHub runner must have at least **8 GiB free** before starting; the single build is capped at 150 minutes, uses only two parallel compiler jobs, and fails on missing outputs or unexpected ABI/dependencies.
- Build artifact `riftclang-lld-armeabi-v7a-llvm21-ndk-r27c` contains (if successful) **`libriftclang.so` and `libriftlld.so`**—Android ARM32 PIE executables named as `lib*.so` for potential APK installer extraction—plus SHA-256, ELF, provenance, and LLVM license reports. **No Android ELF is executed on the GitHub runner.**
- LLVM/Clang licensing is **Apache-2.0 WITH LLVM-exception**, with the upstream license file included.
- Important: the first successful CI run would **only prove that the binaries were compiled and statically verified**. Their usability on-device, the Clang builtin resource headers, sysroot/CRT layout, correct linker resolution, compiler memory use, signing, and running `hello.c` will each need further tests. General native builds, the installed Native Build Provider v0.6, RiftOS Core/Shell and Recovery remain unchanged.
- The LLVM artifact may be too large to upload as a normal GitHub repository file. **Check the size and CI receipts before trying the prior RiftGit ZIP handoff.** We will agree on a supported transfer route before moving the actual toolchain to the phone.

## Repository contents

- `native/riftprobe.c`: fixed JNI method returning `RFP1`.
- `native/build-arm32-probe.sh`: Android NDK cross-compilation script.
- `native/verify-arm32-probe.py`: read-only ELF/JNI/dependency verifier and build receipts.
- `.github/workflows/build-arm32-probe.yml`: manually triggered one-job workflow.
- `native/riftg4c-exec.c`: fixed `RIFT_G4C_EXEC_OK` output executable, no user input.
- `native/build-arm32-exec.sh`: host-side Android ARM32 PIE executable cross-compile.
- `native/verify-arm32-exec.py`: static ELF interpreter/ABI/marker/dependency/receipt check.
- `.github/workflows/build-arm32-exec.yml`: independently triggered G4-C executable build workflow.

The GitHub Actions checkout and upload-artifact steps are pinned to reviewed v4 immutable commit SHAs, and the compiler version is fixed by the official NDK r27c package revision. Keep the generated receipts; the hosted runner and its installed SDK components are still external build inputs.
