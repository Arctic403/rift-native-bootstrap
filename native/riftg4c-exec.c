/*
 * G4-C installer-packaged ARM32 PIE ELF launch proof.
 * SPDX-License-Identifier: MIT
 *
 * Exact fixed output only. No arguments, project files, network, shell,
 * subprocesses, dynamic loading, or command interpretation.
 *
 * This is an executable (ET_DYN PIE), NOT a JNI shared library.
 * The .so filename is ONLY for Android PackageManager's ABI-specific
 * native-library extraction path. It must NOT be System.loadLibrary'd.
 */
#include <unistd.h>

int main(void) {
    static const char marker[] = "RIFT_G4C_EXEC_OK\n";
    const ssize_t written = write(STDOUT_FILENO, marker, sizeof(marker) - 1U);
    return written == (ssize_t)(sizeof(marker) - 1U) ? 0 : 4;
}
