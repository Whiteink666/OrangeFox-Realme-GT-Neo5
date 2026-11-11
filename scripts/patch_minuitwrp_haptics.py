#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_minuitwrp_haptics.py -- Whiteink haptics patch v2

Rewrites upstream ``bootable/recovery/minuitwrp/events.cpp::vibrate()`` for the
realme GT Neo5 / GT3 (RMXTARO, AW8697 X-axis linear resonant actuator).

Background
----------
TWRP/OrangeFox calls ``vibrate(int timeout_ms)`` on every virtual-key / button
event. The upstream AIDL branch does a synchronous binder
``getService()``/``fromBinder()`` per tap, drives the motor with a constant
amplitude ``on(timeout_ms)`` (which reads as a rotor buzz on an X-axis LRA),
and - with ``USE_QTI_AIDL_HAPTICS_FIX_OFF`` - spawns a detached ``std::thread``
per tap to wait and call ``off()``.

v1 (run 12) tried to fix all of that by calling ``perform(CLICK)`` exclusively.
It REGRESSED to zero vibration, because:

  * ``status.isOk()`` was trusted without checking ``played_ms``. Vendor HALs
    can return OK with a zero duration when the RichTap waveform library under
    /odm/etc/vibrator is unreachable (common in recovery), i.e. "OK, played
    nothing".
  * The fallback was a 20 ms ``on()`` - too short to feel on an LRA.
  * Removing FIX_OFF also removed the explicit ``off()`` state management that
    some QTI HALs need between ``on()`` calls.

v2 guarantees vibration first
-----------------------------
  * Caches the ``IVibrator`` proxy (mutex-protected, 500 ms retry while the
    late-starting ``realme.vibrator`` comes up) -> no per-tap binder lookup.
  * Rate-limits bursty gesture / virtual-key events to one per 35 ms.
  * Calls ``off()`` synchronously before each event instead of spawning a
    thread -> keeps the HAL state machine clean without the per-tap thread.
  * Tries ``perform(Effect::CLICK, EffectStrength::MEDIUM, ...)`` and uses the
    waveform ONLY when the HAL reports ``isOk() && played_ms > 0``.
  * Otherwise falls back to the upstream ``on(timeout_ms)`` path with the
    caller's own duration (50 ms), which is the same behaviour as r11 and is
    guaranteed to produce feedback.
  * If the HAL is unavailable or both AIDL calls fail, falls back to the sysfs
    LED / timed_output vibrator nodes, so vibration is never silently lost.
  * Writes mode changes to ``/tmp/fox_haptics.log`` for field diagnosis.
  * Runtime kill switch (no rebuild): create ``/tmp/fox_haptics_force_on`` to
    force the guaranteed ``on(ms)`` path and skip ``perform()`` entirely.

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

MARKER = "// Whiteink haptics patch v2"
SIGNATURE = "int vibrate(int timeout_ms)"

NEW_FUNCTION = r'''int vibrate(int timeout_ms)
{
    // === Whiteink haptics patch v2 ===
    // v1 trusted perform()'s isOk() without checking played_ms and fell back
    // to a 20 ms on() with no off() management -> zero vibration in recovery
    // when the /odm RichTap waveform library is unreachable.
    // v2 keeps the cached proxy / throttle / no-thread wins, but makes the
    // upstream on(timeout_ms) the GUARANTEED fallback. A waveform is used only
    // when the HAL reports a real played duration.
    if (timeout_ms > 10000) timeout_ms = 1000;
    char tout[6];
    sprintf(tout, "%i", timeout_ms);

#ifdef USE_QTI_HAPTICS
    android::sp<android::hardware::vibrator::V1_2::IVibrator> vib = android::hardware::vibrator::V1_2::IVibrator::getService();
    if (vib != nullptr) {
        vib->on((uint32_t)timeout_ms);
    }
#elif defined(USE_QTI_AIDL_HAPTICS)
    static std::chrono::steady_clock::time_point sLastBuzz;
    static std::mutex sVibMutex;
    static std::shared_ptr<IVibrator> sVib;
    static std::chrono::steady_clock::time_point sLastProbe;
    static int sLastMode = -1;

    const auto now = std::chrono::steady_clock::now();
    // Gesture navigation can emit events faster than an LRA can reproduce.
    if (now - sLastBuzz < std::chrono::milliseconds(35)) return 0;
    sLastBuzz = now;

    // Runtime kill switch, no rebuild needed:
    //   adb shell touch /tmp/fox_haptics_force_on   -> always use on(ms)
    //   adb shell rm    /tmp/fox_haptics_force_on   -> back to auto
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
    int32_t played_ms = 0;
    if (sVib != nullptr) {
        // Return the HAL to idle first. Upstream FIX_OFF did this from a
        // detached worker after a timed wait; doing it synchronously here
        // removes the per-tap thread without losing the off() state handling.
        sVib->off();

        if (!force_on) {
            const auto status = sVib->perform(
                ::aidl::android::hardware::vibrator::Effect::CLICK,
                ::aidl::android::hardware::vibrator::EffectStrength::MEDIUM,
                nullptr, &played_ms);
            // isOk() alone is NOT enough: vendor HALs can return OK with a
            // zero duration when the waveform file cannot be found.
            if (status.isOk() && played_ms > 0) {
                mode = 1;
            }
        }
        if (mode == 0) {
            // Guaranteed fallback: same constant-amplitude on(ms) as r11,
            // using the caller's own duration (VIBRATOR_TIME_MS = 50).
            if (sVib->on((uint32_t)timeout_ms, nullptr).isOk()) {
                mode = 2;
            }
        }
    }
    if (mode == 0) {
        // HAL unavailable or both AIDL calls failed: sysfs fallback so the
        // user never ends up with completely dead haptics.
        if (std::ifstream(LEDS_HAPTICS_ACTIVATE_FILE).good()) {
            write_to_file(LEDS_HAPTICS_DURATION_FILE, tout);
            write_to_file(LEDS_HAPTICS_ACTIVATE_FILE, "1");
        } else {
            write_to_file(VIBRATOR_TIMEOUT_FILE, tout);
        }
        mode = 3;
    }

    // Log only on mode changes: /tmp is tmpfs and this stays cheap.
    // mode 1 = RichTap waveform, 2 = on(ms) fallback, 3 = sysfs fallback.
    if (mode != sLastMode) {
        sLastMode = mode;
        FILE* f = fopen("/tmp/fox_haptics.log", "a");
        if (f != nullptr) {
            fprintf(f, "mode=%d played_ms=%d timeout_ms=%d force_on=%d\n",
                    mode, played_ms, timeout_ms, force_on ? 1 : 0);
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
        # Already patched: verify structure, do not touch the file.
        if text.count("int vibrate(int timeout_ms)") != 1:
            raise PatchError("already patched but vibrate() signature count != 1")
        for token in ("Effect::CLICK", "EffectStrength::MEDIUM", "sVibMutex",
                      "played_ms > 0", "fox_haptics_force_on",
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
    notes.append("PASS replaced vibrate() with v2 (guaranteed on(ms) fallback)")

    # --- 5. post-conditions -------------------------------------------------
    s2, e2 = find_function_span(text)
    new_fn = text[s2:e2]
    required = ("perform(", "Effect::CLICK", "EffectStrength::MEDIUM",
                "std::lock_guard<std::mutex>", "kVibratorInstance",
                "USE_QTI_HAPTICS", "USE_SAMSUNG_HAPTICS", "return 0;",
                # v2 regression guards - these MUST all be present
                "status.isOk() && played_ms > 0",
                "sVib->on((uint32_t)timeout_ms, nullptr).isOk()",
                "sVib->off()",
                "LEDS_HAPTICS_ACTIVATE_FILE",
                "/tmp/fox_haptics.log",
                "/tmp/fox_haptics_force_on")
    for token in required:
        if token not in new_fn:
            raise PatchError("patched vibrate() missing %r" % token)
    forbidden = ("std::thread(", "usleep(", "vib_on_count", "detach()",
                 "sVib->on(20, nullptr)")
    for token in forbidden:
        if token in new_fn:
            raise PatchError("patched vibrate() still contains %r" % token)
    if new_fn.count("{") != new_fn.count("}"):
        raise PatchError("brace imbalance in patched vibrate()")
    if "#include <chrono>" not in text or "#include <mutex>" not in text:
        raise PatchError("standard headers missing after patch")
    notes.append("PASS post-conditions: played_ms guard, guaranteed on(ms), "
                 "sysfs fallback, no thread")

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
