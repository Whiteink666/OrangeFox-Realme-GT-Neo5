#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_minuitwrp_haptics.py -- Whiteink haptics patch v4

Rewrites upstream ``bootable/recovery/minuitwrp/events.cpp::vibrate()`` for the
realme GT Neo5 / GT3 (RMXTARO, AW8697 X-axis linear resonant actuator).

History
-------
v1 (r12): cached HAL + perform(CLICK). Threw timeout_ms away entirely -> the
          slider did nothing and 300 felt like a weak 20 ms buzz.
v2 (r13): restored on(timeout_ms), cancelled - would have buzzed for 300 ms.
v3 (r14): strength mapping with 2 levels (1-99 / >=100), RichTap waveform
          ladder, /odm/etc waveform dual-insurance. THE LINEAR MOTOR NOW WORKS.

v4: user feedback "调到 300 震动有点小，现在震动应该是适合 100 左右，或者是 50"
    -> r14's maximum (300) is about right for a *mid* slider value; the top end
    must be stronger and the curve steeper.

What v4 does
------------
  * THREE levels instead of two, with thresholds pulled DOWN:
        <= 0        -> off
        1 .. 49     -> level 1 (light)
        50 .. 149   -> level 2 (= exactly r14's former "300" feel)
        >= 150      -> level 3 (new, strongest)
  * Always calls setAmplitude() BEFORE the waveform. v3 only set amplitude in
    the on() fallback, so the waveform path inherited whatever default
    amplitude the vendor HAL had - the most likely reason 300 felt small.
  * Level 3 never degrades to a weak CLICK+LIGHT waveform: if HEAVY_CLICK is
    unavailable it goes straight to full amplitude + a 60 ms on() pulse.
  * Optional double pulse for level 3 via /tmp/fox_haptics_double (off by
    default, so no behaviour change unless explicitly enabled).
  * Runtime gain: /tmp/fox_haptics_gain holds an integer -3..3 that shifts the
    level. Lets the user dial strength with adb WITHOUT another ~2 h rebuild.
    Read at most once every 2 s so the input thread stays cheap.
  * Keeps everything that made r14 work: cached IVibrator proxy (mutex + 500 ms
    retry), synchronous off(), 35 ms throttle, no threads, sysfs fallback,
    /tmp/fox_haptics.log, /tmp/fox_haptics_force_on.

Safety
------
  * Function-level brace-matched replacement, not blind sed.
  * Exact match-count / post-condition assertions: an ineffective patch exits
    1 and fails CI instead of wasting ~2 h.
  * Idempotent; non-AIDL branches (HIDL 1.2, Samsung, sysfs) preserved.

Usage
-----
    python3 patch_minuitwrp_haptics.py <path/to/events.cpp> [--check]
"""

import argparse
import sys

MARKER = "// Whiteink haptics patch v4"
SIGNATURE = "int vibrate(int timeout_ms)"

NEW_FUNCTION = r'''int vibrate(int timeout_ms)
{
    // === Whiteink haptics patch v4 ===
    // OrangeFox's vibration sliders (0-300 / 0-500) are MILLISECONDS, not
    // amplitude. Treat the value as a strength intent. v3 had only 2 levels
    // and never called setAmplitude() on the waveform path, which made even
    // the 300 setting feel weak. v4 uses 3 levels with thresholds pulled down.
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
    static std::chrono::steady_clock::time_point sLastGainRead;
    static int sGain = 0;
    static int sLastMode = -1;

    if (timeout_ms <= 0) return 0;  // slider at 0 means vibration disabled
    const auto now = std::chrono::steady_clock::now();

    // /tmp/fox_haptics_gain: integer -3..3, shifts the strength level.
    //   adb shell "echo 1 > /tmp/fox_haptics_gain"   -> one step stronger
    //   adb shell "echo -1 > /tmp/fox_haptics_gain"  -> one step softer
    //   adb shell "echo 3 > /tmp/fox_haptics_gain"   -> force max regardless of slider
    // Cached for 2 s so a file read never lands on the input hot path.
    if (now - sLastGainRead > std::chrono::seconds(2)) {
        sLastGainRead = now;
        int g = 0;
        std::ifstream gf("/tmp/fox_haptics_gain");
        if (gf.good() && (gf >> g)) {
            if (g > 3) g = 3;
            if (g < -3) g = -3;
            sGain = g;
        } else {
            sGain = 0;
        }
    }

    // r14 used 100 as the only threshold. v4 pulls it down so 50 / 100 already
    // get the strength that used to require 300, and 300 gets a new top level.
    int level = timeout_ms >= 150 ? 3 : (timeout_ms >= 50 ? 2 : 1);
    level += sGain;
    if (level < 0) level = 0;
    if (level > 3) level = 3;
    if (level == 0) return 0;

    static const float kAmp[4]   = { 0.0f, 0.70f, 0.90f, 1.00f };
    static const int   kDrive[4] = {    0,     20,     40,     60 };
    const float amplitude = kAmp[level];
    const int drive_ms = kDrive[level];   // 20 / 40 / 60 ms, never 300
    char dstr[8];
    sprintf(dstr, "%i", drive_ms);

    // Gesture navigation can emit events faster than an LRA can reproduce.
    if (now - sLastBuzz < std::chrono::milliseconds(35)) return 0;
    sLastBuzz = now;

    const bool force_on = (access("/tmp/fox_haptics_force_on", F_OK) == 0);
    const bool double_pulse = (access("/tmp/fox_haptics_double", F_OK) == 0);

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
        // v4: set the amplitude BEFORE the waveform too. v3 only did this in
        // the on() fallback, so waveform playback used the HAL default.
        sVib->setAmplitude(amplitude);

        if (!force_on) {
            static const Effect kEffects[4] = {
                Effect::CLICK, Effect::CLICK,
                Effect::HEAVY_CLICK, Effect::HEAVY_CLICK };
            static const EffectStrength kStrengths[4] = {
                EffectStrength::LIGHT, EffectStrength::MEDIUM,
                EffectStrength::STRONG, EffectStrength::STRONG };
            // Level 1/2 step down through the ladder. Level 3 deliberately
            // does NOT step down, so the top end never becomes a weak tick.
            const int floor_s = (level == 3) ? 3 : 1;
            for (int s = level; s >= floor_s; --s) {
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
            // Optional extra pulse at the top level, off unless requested.
            if (mode == 1 && level == 3 && double_pulse) {
                int32_t extra = 0;
                sVib->perform(Effect::HEAVY_CLICK, EffectStrength::STRONG,
                              nullptr, &extra);
                played_ms += extra;
            }
        }
        if (mode == 0) {
            // No usable waveform: full amplitude + a SHORT on(). Never feed
            // timeout_ms to on() - that would buzz like a rotor for 300 ms.
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
            fprintf(f, "mode=%d level=%d used=%d gain=%d amp=%.2f drive_ms=%d "
                    "timeout_ms=%d played_ms=%d force_on=%d\n",
                    mode, level, used_level, sGain, amplitude, drive_ms,
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
        for token in ("Effect::HEAVY_CLICK", "setAmplitude(", "const int drive_ms",
                      "fox_haptics_gain", "played > 0", "fox_haptics_force_on",
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
    notes.append("PASS replaced vibrate() with v4 three-level strength mapping")

    # --- 5. post-conditions -------------------------------------------------
    s2, e2 = find_function_span(text)
    new_fn = text[s2:e2]
    required = ("perform(", "Effect::CLICK", "Effect::HEAVY_CLICK",
                "EffectStrength::STRONG", "setAmplitude(amplitude)",
                "std::lock_guard<std::mutex>", "kVibratorInstance",
                "USE_QTI_HAPTICS", "USE_SAMSUNG_HAPTICS", "return 0;",
                "timeout_ms >= 150 ? 3 : (timeout_ms >= 50 ? 2 : 1)",
                "static const int   kDrive[4] = {    0,     20,     40,     60 };",
                "status.isOk() && played > 0",
                "sVib->on((uint32_t)drive_ms, nullptr).isOk()",
                "sVib->off()", "LEDS_HAPTICS_ACTIVATE_FILE",
                "/tmp/fox_haptics.log", "/tmp/fox_haptics_force_on",
                "/tmp/fox_haptics_gain", "/tmp/fox_haptics_double",
                "const int floor_s = (level == 3) ? 3 : 1;")
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
    notes.append("PASS post-conditions: 3 levels, gain file, amplitude before "
                 "waveform, no thread")

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
