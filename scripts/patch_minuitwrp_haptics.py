#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_minuitwrp_haptics.py -- Whiteink haptics patch v3

Rewrites upstream ``bootable/recovery/minuitwrp/events.cpp::vibrate()`` for the
realme GT Neo5 / GT3 (RMXTARO, AW8697 X-axis linear resonant actuator).

What the user actually reported
-------------------------------
After r12 the device DID vibrate, but weakly, still like a rotor motor, and
pulling OrangeFox's vibration sliders to 300 changed nothing.

Investigation of twres/pages/settings.xml:
    tw_button_vibrate   min=0 max=300
    tw_keyboard_vibrate min=0 max=300
    tw_action_vibrate   min=0 max=500
These are MILLISECONDS (durations), not amplitudes. On an X-axis LRA, longer
does NOT mean stronger - a 300 ms constant-amplitude on() is exactly the
rotor-like buzz we want to remove.

v1 (r12) threw timeout_ms away entirely: it returned as soon as perform()
reported isOk() (ignoring played_ms), and its fallback was a hard-coded 20 ms
on(). That is why "300" made no difference.
v2 (r13, cancelled) would have honoured timeout_ms on the on() path - i.e. a
300 ms buzz, even more rotor-like. Wrong direction.

What v3 does
------------
  * Treats timeout_ms as a STRENGTH INTENT, not a duration:
        <= 0        -> no vibration (respects the slider's off position)
        1 .. 99     -> level 1 (MEDIUM / 0.8 amplitude)
        >= 100      -> level 2 (STRONG / 1.0 amplitude / HEAVY_CLICK)
  * Drives a SHORT, crisp pulse (20 / 30 / 40 ms by level), never 300 ms.
  * Tries RichTap waveforms first, stepping down on failure:
        level 2 -> HEAVY_CLICK + STRONG -> CLICK + MEDIUM -> CLICK + LIGHT
        level 1 -> CLICK + MEDIUM       -> CLICK + LIGHT
        level 0 -> CLICK + LIGHT
    A waveform counts as successful only when isOk() && played_ms > 0.
  * If no waveform is available: setAmplitude(level amplitude) followed by a
    short on(drive_ms). High amplitude + short duration is the correct way to
    drive an LRA without a waveform library.
  * HAL unavailable / both AIDL calls failed -> sysfs LED / timed_output
    fallback using the SHORT duration, so vibration is never silently lost.
  * Synchronous off() before each event replaces upstream's detached per-tap
    thread; caches the IVibrator proxy (mutex + 500 ms retry); 35 ms throttle.
  * Writes mode changes to /tmp/fox_haptics.log for field diagnosis.
  * /tmp/fox_haptics_force_on forces the amplitude+on() path, no rebuild.

Safety
------
  * Function-level replacement (brace-matched), not a blind sed.
  * Exact match-count / post-condition assertions: an ineffective patch exits
    1 and fails CI instead of wasting ~2 h.
  * Idempotent: running twice is a no-op.
  * Non-AIDL branches (HIDL 1.2, Samsung, sysfs) preserved verbatim.

Usage
-----
    python3 patch_minuitwrp_haptics.py <path/to/events.cpp> [--check]
"""

import argparse
import sys

MARKER = "// Whiteink haptics patch v3"
SIGNATURE = "int vibrate(int timeout_ms)"

NEW_FUNCTION = r'''int vibrate(int timeout_ms)
{
    // === Whiteink haptics patch v3 ===
    // OrangeFox's vibration sliders (0-300 / 0-500) are MILLISECONDS, not
    // amplitude. On an X-axis LRA, longer != stronger: a 300 ms on() is a
    // rotor-like buzz. Treat the value as a strength intent and always drive
    // a short, crisp pulse. v1 discarded timeout_ms entirely (fixed 20 ms or
    // a fixed CLICK), v2 would have produced a 300 ms buzz - both wrong.
    if (timeout_ms > 10000) timeout_ms = 1000;
    char tout[6];
    sprintf(tout, "%i", timeout_ms);

#ifdef USE_QTI_HAPTICS
    android::sp<android::hardware::vibrator::V1_2::IVibrator> vib = android::hardware::vibrator::V1_2::IVibrator::getService();
    if (vib != nullptr) {
        vib->on((uint32_t)timeout_ms);
    }
#elif defined(USE_QTI_AIDL_HAPTICS)
    typedef ::aidl::android::hardware::vibrator::Effect Effect;
    typedef ::aidl::android::hardware::vibrator::EffectStrength EffectStrength;

    static std::chrono::steady_clock::time_point sLastBuzz;
    static std::mutex sVibMutex;
    static std::shared_ptr<IVibrator> sVib;
    static std::chrono::steady_clock::time_point sLastProbe;
    static int sLastMode = -1;

    if (timeout_ms <= 0) return 0;  // slider at 0 means vibration disabled
    const int level = timeout_ms >= 100 ? 2 : (timeout_ms >= 1 ? 1 : 0);
    const float amplitude = level == 2 ? 1.0f : (level == 1 ? 0.8f : 0.55f);
    const int drive_ms = 20 + level * 10;  // 20 / 30 / 40 ms, never 300
    char dstr[8];
    sprintf(dstr, "%i", drive_ms);

    const auto now = std::chrono::steady_clock::now();
    // Gesture navigation can emit events faster than an LRA can reproduce.
    if (now - sLastBuzz < std::chrono::milliseconds(35)) return 0;
    sLastBuzz = now;

    // Runtime kill switch, no rebuild needed:
    //   adb shell touch /tmp/fox_haptics_force_on -> amplitude + short on()
    //   adb shell rm    /tmp/fox_haptics_force_on -> back to auto waveform
    const bool force_on = (access("/tmp/fox_haptics_force_on", F_OK) == 0);

    // realme.vibrator starts only after vendor modules load; retry at most
    // every 500 ms, then keep the proxy instead of a per-tap binder lookup.
    {
        std::lock_guard<std::mutex> lock(sVibMutex);
        if (sVib == nullptr) {
            if (now - sLastProbe < std::chrono::milliseconds(500)) return 0;
            sLastProbe = now;
            sVib = IVibrator::fromBinder(
                ndk::SpAIBinder(AServiceManager_getService(kVibratorInstance.c_str())));
        }
    }

    int mode = 0;
    int used_level = level;
    int32_t played_ms = 0;
    if (sVib != nullptr) {
        // Return the HAL to idle first. Upstream FIX_OFF did this from a
        // detached worker after a timed wait; doing it synchronously removes
        // the per-tap thread without losing the off() state handling.
        sVib->off();

        if (!force_on) {
            static const Effect kEffects[3] = {
                Effect::CLICK, Effect::CLICK, Effect::HEAVY_CLICK };
            static const EffectStrength kStrengths[3] = {
                EffectStrength::LIGHT, EffectStrength::MEDIUM, EffectStrength::STRONG };
            // Heavier settings try heavier waveforms, then step down.
            for (int s = level; s >= 0; --s) {
                int32_t played = 0;
                const auto status = sVib->perform(
                    kEffects[s], kStrengths[s], nullptr, &played);
                // isOk() alone is NOT enough: vendor HALs can return OK with a
                // zero duration when the waveform file cannot be found.
                if (status.isOk() && played > 0) {
                    mode = 1;
                    used_level = s;
                    played_ms = played;
                    break;
                }
            }
        }
        if (mode == 0) {
            // No usable waveform: high amplitude + SHORT on(). Never feed
            // timeout_ms to on() - that would buzz like a rotor for 300 ms.
            sVib->setAmplitude(amplitude);
            if (sVib->on((uint32_t)drive_ms, nullptr).isOk()) {
                mode = 2;
            }
        }
    }
    if (mode == 0) {
        // HAL unavailable or both AIDL calls failed: sysfs fallback using the
        // SHORT duration so vibration is never silently lost.
        if (std::ifstream(LEDS_HAPTICS_ACTIVATE_FILE).good()) {
            write_to_file(LEDS_HAPTICS_DURATION_FILE, dstr);
            write_to_file(LEDS_HAPTICS_ACTIVATE_FILE, "1");
        } else {
            write_to_file(VIBRATOR_TIMEOUT_FILE, dstr);
        }
        mode = 3;
    }

    // Log only on mode changes: /tmp is tmpfs and this stays cheap.
    // mode 1 = waveform, 2 = amplitude+on(), 3 = sysfs.
    if (mode != sLastMode) {
        sLastMode = mode;
        FILE* f = fopen("/tmp/fox_haptics.log", "a");
        if (f != nullptr) {
            fprintf(f, "mode=%d level=%d used=%d amp=%.2f drive_ms=%d "
                    "timeout_ms=%d played_ms=%d force_on=%d\n",
                    mode, level, used_level, amplitude, drive_ms,
                    timeout_ms, played_ms, force_on ? 1 : 0);
            fclose(f);
        }
    }
#elif defined(USE_SAMSUNG_HAPTICS)
    /* Newer Samsung devices have duration file only
     0 in VIBRATOR_TIMEOUT_FILE means no vibration
     Anything else is the vibration running for X milliseconds */
    if (std::ifstream(VIBRATOR_TIMEOUT_FILE).good()) {
        write_to_file(VIBRATOR_TIMEOUT_FILE, tout);
    }
#else
    if (std::ifstream(LEDS_HAPTICS_ACTIVATE_FILE).good()) {
        write_to_file(LEDS_HAPTICS_DURATION_FILE, tout);
        write_to_file(LEDS_HAPTICS_ACTIVATE_FILE, "1");
    } else
        write_to_file(VIBRATOR_TIMEOUT_FILE, tout);
#endif
    return 0;
}'''

THREAD_BLOCK = """#ifdef USE_QTI_AIDL_HAPTICS_FIX_OFF
#include <thread>
#endif
"""

ATOMIC_BLOCK = """#ifdef USE_QTI_AIDL_HAPTICS_FIX_OFF
static std::atomic_int vib_on_count = 0;
#endif
"""

STD_HEADERS = """#include <chrono>
#include <mutex>  """ + MARKER + "\n"


class PatchError(Exception):
    pass


def find_function_span(text):
    """Return (start, end) covering `int vibrate(int timeout_ms) { ... }`."""
    hits = text.count(SIGNATURE)
    if hits != 1:
        raise PatchError("expected exactly 1 %r, found %d" % (SIGNATURE, hits))
    start = text.index(SIGNATURE)
    brace = text.find("{", start)
    if brace < 0:
        raise PatchError("opening brace not found after vibrate()")
    depth = 0
    i = brace
    while i < len(text):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1
    raise PatchError("unbalanced braces in vibrate()")


def apply(text):
    """Return (new_text, changed, notes). Raises PatchError on any mismatch."""
    notes = []
    if MARKER in text:
        if text.count("int vibrate(int timeout_ms)") != 1:
            raise PatchError("already patched but vibrate() signature count != 1")
        for token in ("Effect::HEAVY_CLICK", "setAmplitude(", "const int level =",
                      "played > 0", "fox_haptics_force_on",
                      "#include <chrono>", "#include <mutex>"):
            if token not in text:
                raise PatchError("already patched but missing %r" % token)
        notes.append("SKIP already patched (idempotent)")
        return text, False, notes

    # --- 1. locate and validate the upstream function -----------------------
    start, end = find_function_span(text)
    old = text[start:end]
    for token in ("USE_QTI_AIDL_HAPTICS", "AServiceManager_getService"):
        if token not in old:
            raise PatchError("vibrate() is not the expected AIDL implementation "
                             "(missing %r)" % token)
    if old.count("{") != old.count("}"):
        raise PatchError("brace imbalance inside vibrate()")
    notes.append("PASS located upstream AIDL vibrate() (%d bytes)" % len(old))
    notes.append("  upstream branches: HIDL=%s Samsung=%s sysfs=%s" % (
        "USE_QTI_HAPTICS" in old, "USE_SAMSUNG_HAPTICS" in old,
        "LEDS_HAPTICS_ACTIVATE_FILE" in old))

    # --- 2. inject <chrono> / <mutex> once ---------------------------------
    anchor = None
    for cand in ("#include <fstream>\n", "#include <string.h>\n",
                 "#include <stdio.h>\n"):
        if text.count(cand) == 1:
            anchor = cand
            break
    if anchor is None:
        raise PatchError("no unique include anchor for <chrono>/<mutex>")
    text = text.replace(anchor, anchor + STD_HEADERS, 1)
    notes.append("PASS injected <chrono> + <mutex> after %s" % anchor.strip())

    # --- 3. drop FIX_OFF thread/atomic scaffolding -------------------------
    for label, block in (("<thread> include", THREAD_BLOCK),
                         ("vib_on_count state", ATOMIC_BLOCK)):
        n = text.count(block)
        if n == 1:
            text = text.replace(block, "", 1)
            notes.append("PASS removed FIX_OFF %s" % label)
        elif n == 0:
            notes.append("SKIP FIX_OFF %s not present" % label)
        else:
            raise PatchError("FIX_OFF %s block found %d times" % (label, n))

    # --- 4. replace the function -------------------------------------------
    start, end = find_function_span(text)
    text = text[:start] + NEW_FUNCTION + text[end:]
    notes.append("PASS replaced vibrate() with v3 strength-mapping version")

    # --- 5. post-conditions -------------------------------------------------
    s2, e2 = find_function_span(text)
    new_fn = text[s2:e2]
    required = ("perform(", "Effect::CLICK", "Effect::HEAVY_CLICK",
                "EffectStrength::STRONG", "setAmplitude(",
                "std::lock_guard<std::mutex>", "kVibratorInstance",
                "USE_QTI_HAPTICS", "USE_SAMSUNG_HAPTICS", "return 0;",
                "const int level = timeout_ms >= 100 ? 2",
                "const int drive_ms = 20 + level * 10",
                "status.isOk() && played > 0",
                "sVib->on((uint32_t)drive_ms, nullptr).isOk()",
                "sVib->off()", "LEDS_HAPTICS_ACTIVATE_FILE",
                "/tmp/fox_haptics.log", "/tmp/fox_haptics_force_on")
    for token in required:
        if token not in new_fn:
            raise PatchError("patched vibrate() missing %r" % token)
    forbidden = ("std::thread(", "usleep(", "vib_on_count", "detach()",
                 "sVib->on(20, nullptr)",
                 "sVib->on((uint32_t)timeout_ms, nullptr)")
    for token in forbidden:
        if token in new_fn:
            raise PatchError("patched vibrate() still contains %r" % token)
    if new_fn.count("{") != new_fn.count("}"):
        raise PatchError("brace imbalance in patched vibrate()")
    if "#include <chrono>" not in text or "#include <mutex>" not in text:
        raise PatchError("standard headers missing after patch")
    notes.append("PASS post-conditions: strength mapping, short pulse, "
                 "waveform ladder, no thread")

    return text, True, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("events_cpp", help="path to upstream minuitwrp/events.cpp")
    ap.add_argument("--check", action="store_true",
                    help="report only, do not write the file")
    args = ap.parse_args()

    path = args.events_cpp
    with open(path, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    newline = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")

    try:
        patched, changed, notes = apply(text)
        again, changed2, _ = apply(patched)
        if changed2 or again != patched:
            raise PatchError("patch is not idempotent")
        notes.append("PASS idempotent (second apply is a no-op)")
    except PatchError as e:
        print("ERROR: %s" % e)
        return 1

    for n in notes:
        print(n)
    print("events.cpp haptics patch: %s" % ("APPLIED" if changed else "already present"))
    print("ALL CHECKS PASS")

    if changed and not args.check:
        out = patched.replace("\n", newline)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(out)
        print("wrote %s" % path)
    elif changed:
        print("--check: file not modified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
