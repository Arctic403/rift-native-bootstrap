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

## Repository contents

- `native/riftprobe.c`: fixed JNI method returning `RFP1`.
- `native/build-arm32-probe.sh`: Android NDK cross-compilation script.
- `native/verify-arm32-probe.py`: read-only ELF/JNI/dependency verifier and build receipts.
- `.github/workflows/build-arm32-probe.yml`: manually triggered one-job workflow.

The GitHub Actions checkout and upload-artifact steps are pinned to reviewed v4 immutable commit SHAs, and the compiler version is fixed by the official NDK r27c package revision. Keep the generated receipts; the hosted runner and its installed SDK components are still external build inputs.
