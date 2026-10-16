/*
 * G4-B read-only ARM32 JNI load proof for the independent Native Build Provider.
 * SPDX-License-Identifier: MIT
 *
 * No subprocess, file access, filesystem mutation or user-provided commands.
 * Compile as an Android armeabi-v7a ELF shared library via a trusted Android NDK.
 */
#include <jni.h>

JNIEXPORT jint JNICALL
Java_com_rift_nativebuildprovider_NativeBuildProbe_nativeAnswer(
    JNIEnv *env, jobject receiver) {
    (void)env;
    (void)receiver;
    return (jint)0x52465031; /* ASCII "RFP1": fixed ABI/JNI success marker */
}
