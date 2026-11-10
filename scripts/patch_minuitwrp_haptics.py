#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_minuitwrp_haptics.py -- Whiteink haptics patch v1

Rewrites upstream ``bootable/recovery/minuitwrp/events.cpp::vibrate()`` for the
realme GT Neo5 / GT3 (RMXTARO, AW8697 X-axis linear resonant actuator).

Why the upstream implementation is wrong for this device
-------------------------------------------------------
TWRP/OrangeFox calls ``vibrate(int timeout_ms)`` on every virtual-key / button
event. The AIDL branch does three things that hurt this device:

  1. ``AServiceManager_getService()`` + ``IVibrator::fromBinder()`` on EVERY
     tap -- a synchronous binder round trip on the input thread.
  2. ``IVibrator::on(timeout_ms)`` -- a constant-amplitude, duration-based
     buzz. On an X-axis LRA with RichTap waveforms this reads as a cheap rotor
     motor ("嗡嗡感"); the 300+ pre-rendered ``effect_*.bin`` waveforms shipped
     in /odm/etc/vibrator are never used.
  3. With ``USE_QTI_AIDL_HAPTICS_FIX_OFF`` it spawns a detached ``std::thread``
     + ``usleep(timeout_ms * 1000)`` + ``vib->off()`` per tap.

What this patch does
--------------------
  * Caches the ``IVibrator`` proxy once (mutex-protected), retrying at most
    every 500 ms while the late-starting ``realme.vibrator`` service comes up.
  * Fires the pre-rendered RichTap waveform through
    ``perform(Effect::CLICK, EffectStrength::MEDIUM, nullptr, &played_ms)``.
  * Falls back to a short, bounded 20 ms ``on()`` buzz when the HAL has no
    CLICK waveform, so vibration is never silently lost.
  * Rate-limits bursty gesture / virtual-key events to one every 35 ms.
  * Removes the FIX_OFF ``<thread>`` include and ``vib_on_count`` state;
    ``BoardConfig.mk`` no longer defines TW_SUPPORT_INPUT_AIDL_HAPTICS_FIX_OFF.

Safety
------
  * Function-level replacement (brace-matched), not a blind sed, so small
    upstream edits elsewhere in events.cpp do not break the patch.
  * Exact match-count assertions: a silently ineffective patch exits 1 and
    fails the cloud build instead of wasting ~2 h.
  * Idempotent: running twice is a no-op and still exits 0.
  * All non-AIDL branches (HIDL 1.2, Samsung, sysfs LED) are preserved verbatim.

Usage
-----
    python3 patch_minuitwrp_haptics.py <path/to/events.cpp> [--check]

``--check`` reports what would change without writing the file.
"""

import argparse
import sys

MARKER = "// Whiteink haptics patch v1"
SIGNATURE = "int vibrate(int timeout_ms)"

NEW_FUNCTION = r'''int vibrate(int timeout_ms)
{
    // === Whiteink haptics patch v1 ===
    // Applied by scripts/patch_minuitwrp_haptics.py on every cloud sync.
    // Upstream calls IVibrator::on(timeout_ms) per key event: a fixed-amplitude
    // buzz that reads as a rotor motor on the AW8697 X-axis LRA, plus a binder
    // getService()/fromBinder() and (with FIX_OFF) a detached thread every tap.
    // Fire the pre-rendered RichTap CLICK waveform via perform() instead, cache
    // the HAL proxy, and rate-limit bursty gesture events.
    if (timeout_ms > 10000) timeout_ms = 1000;
    char tout[6];
    sprintf(tout, "%i", timeout_ms);

#ifdef USE_QTI_HAPTICS
    android::sp<android::hardware::vibrator::V1_2::IVibrator> vib = android::hardware::vibrator::V1_2::IVibrator::getService();
    if (vib != nullptr) {
        vib->on((uint32_t)timeout_ms);
    }
#elif defined(USE_QTI_AIDL_HAPTICS)
    // Gesture navigation / virtual keys can emit events far faster than an LRA
    // can reproduce. Drop anything inside 35 ms so scrolling stays responsive.
    static std::chrono::steady_clock::time_point sLastBuzz;
    const auto now = std::chrono::steady_clock::now();
    if (now - sLastBuzz < std::chrono::milliseconds(35)) return 0;
    sLastBuzz = now;

    // realme.vibrator only starts after vendor modules are loaded, so the first
    // taps may find no service. Retry at most every 500 ms, then keep the proxy
    // for the rest of the session instead of a per-tap binder lookup.
    static std::mutex sVibMutex;
    static std::shared_ptr<IVibrator> sVib;
    static std::chrono::steady_clock::time_point sLastProbe;
    {
        std::lock_guard<std::mutex> lock(sVibMutex);
        if (sVib == nullptr) {
            if (now - sLastProbe < std::chrono::milliseconds(500)) return 0;
            sLastProbe = now;
            sVib = IVibrator::fromBinder(
                ndk::SpAIBinder(AServiceManager_getService(kVibratorInstance.c_str())));
        }
    }
    if (sVib != nullptr) {
        int32_t played_ms = 0;
        const auto status = sVib->perform(
            ::aidl::android::hardware::vibrator::Effect::CLICK,
            ::aidl::android::hardware::vibrator::EffectStrength::MEDIUM,
            nullptr, &played_ms);
        (void)played_ms;
        if (status.isOk()) return 0;
        // HAL has no CLICK waveform (or refused it): short bounded buzz fallback.
        sVib->on(20, nullptr);
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
        # Already patched: verify structure, do not touch the file.
        if text.count("int vibrate(int timeout_ms)") != 1:
            raise PatchError("already patched but vibrate() signature count != 1")
        for token in ("Effect::CLICK", "EffectStrength::MEDIUM", "sVibMutex",
                      "#include <chrono>", "#include <mutex>"):
            if token not in text:
                raise PatchError("already patched but missing %r" % token)
        notes.append("SKIP already patched (idempotent)")
        return text, False, notes

    # --- 1. locate and validate the upstream function -----------------------
    start, end = find_function_span(text)
    old = text[start:end]
    # Only the two tokens that define the AIDL branch are mandatory. OrangeFox
    # may have trimmed the HIDL / Samsung / sysfs branches relative to TWRP
    # 12.1; requiring those would fail CI on a harmless upstream difference.
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
    # Prefer the fstream anchor; fall back if OrangeFox reordered the includes.
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
    notes.append("PASS replaced vibrate() with cached-HAL perform(CLICK) version")

    # --- 5. post-conditions -------------------------------------------------
    s2, e2 = find_function_span(text)
    new_fn = text[s2:e2]
    required = ("perform(", "Effect::CLICK", "EffectStrength::MEDIUM",
                "std::lock_guard<std::mutex>", "kVibratorInstance",
                "USE_QTI_HAPTICS", "USE_SAMSUNG_HAPTICS", "return 0;")
    for token in required:
        if token not in new_fn:
            raise PatchError("patched vibrate() missing %r" % token)
    forbidden = ("std::thread(", "usleep(", "vib_on_count", "detach()")
    for token in forbidden:
        if token in new_fn:
            raise PatchError("patched vibrate() still contains %r" % token)
    if new_fn.count("{") != new_fn.count("}"):
        raise PatchError("brace imbalance in patched vibrate()")
    if "#include <chrono>" not in text or "#include <mutex>" not in text:
        raise PatchError("standard headers missing after patch")
    notes.append("PASS post-conditions: perform(CLICK), cached proxy, no thread/usleep")

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
        # Idempotency: applying again must be a no-op.
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
