#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_gui_framerate.py -- Whiteink framerate patch v6

Why this exists
---------------
Three independent things used to cap the OrangeFox UI, and v4/v5 only removed
two of them. Reading ``gui.cpp::loopTimer()`` and ``PageManager::Render()``
together makes the remaining one obvious.

1. ``gui/objects.hpp``
       #ifndef TW_FRAMERATE
       #define TW_FRAMERATE 30
       #endif
   OrangeFox 12.1's ``Android.mk`` never forwards the BoardConfig variable
   ``TW_FRAMERATE`` into a ``-DTW_FRAMERATE=...`` flag, so this default WAS the
   real cadence. v4 forces it to 144 (v6 keeps that, matching the 144 Hz DRM
   mode selected by patch_minuitwrp_drm_hz.py).

2. ``gui.cpp::loopTimer()``
       long timeout = got_event ? 500000000 : (1.0 / TW_FRAMERATE * 1000000000);
   Any input event stretched the catch-up window to 500 ms. v4 replaced it with
   ``* (got_event ? 2 : 1)``. That is still a floor of TWO UI frames on the
   frame period, and because the loop is serial -

       loopTimer()  ->  PageManager::Update()  ->  Render()  ->  flip()

   - the drag period is roughly

       max(2 / TW_FRAMERATE, render + flip)

   With a text-heavy list page that is 2/144 s (13.9 ms) of waiting plus ~10 ms
   of drawing plus a blocking atomic commit waiting for the next vblank. v6
   drops the window to HALF a frame while input is pending: enough to drain the
   queue (``InputHandler::processInput`` reads exactly one event per call and
   ``handleDrag`` sends at most one drag notice per render cycle), without
   putting a floor under the frame period.

3. ``gui/animation.cpp``
       if (++mUpdateCount > TW_FRAMERATE / mFPS)
   ``>`` -> ``>=`` so the spinner advances every 2 frames at 144/60 instead of
   every 3.

It also installs an OPTIONAL frame time trace. With ``/tmp/fox_render_trace``
present, every rendered frame appends one line to ``/tmp/fox_render.log``:

    ts=1794155414.612345 render=4821 flip=16903 ret=2

``render`` and ``flip`` are microseconds. That splits the frame cost into
"CPU drawing" vs "waiting for the panel", which is the only way to tell whether
the remaining jank is our renderer or the vblank interval. Without the file the
branch costs one ``access()`` per frame and nothing is written.

Exact-string replacements with match-count assertions, idempotent, and every
failure aborts CI before the ~1.5 h build starts.

Usage
-----
    python3 patch_gui_framerate.py <path/to/gui/dir> [--check]
"""

import argparse
import sys
from pathlib import Path

MIN_PY = (3, 8)
MARKER = "Whiteink framerate patch v6"

OBJECTS_OLD = """#ifndef TW_FRAMERATE
#define TW_FRAMERATE 30
#endif
"""
OBJECTS_NEW = """// Whiteink framerate patch v6: OrangeFox 12.1 Android.mk never forwards the
// BoardConfig TW_FRAMERATE variable into a -D flag, so this default (30) was
// the REAL global redraw cadence. 144 removes that ceiling and matches the
// 144 Hz panel mode selected by the DRM patch; the achievable rate stays
// bounded by CPU software rendering of the framebuffer.
#undef TW_FRAMERATE
#define TW_FRAMERATE 144
"""

LOOP_OLD = "\t\tlong timeout = got_event ? 500000000 : (1.0 / TW_FRAMERATE * 1000000000);"
LOOP_NEW = """\t\t// Whiteink framerate patch v6: upstream used a 500 ms catch-up window
\t\t// whenever an input event was seen, collapsing drags to ~2 redraws/sec.
\t\t// v5 capped it at two UI frames - still a FLOOR of 2/TW_FRAMERATE on the
\t\t// frame period, which added to render+flip is what showed up as "30 fps"
\t\t// while scrolling. Half a frame is enough to drain the input queue.
\t\tlong timeout = (long)((1.0 / TW_FRAMERATE * 1000000000) / (got_event ? 2 : 1));"""

TRACE_OLD = """#ifndef PRINT_RENDER_TIME
\t\t\tif (ret > 1)
\t\t\t\tPageManager::Render();

\t\t\tif (ret > 0)
\t\t\t\tflip();
"""
TRACE_NEW = """#ifndef PRINT_RENDER_TIME
\t\t\t/* Whiteink framerate patch v6: optional frame timing trace.
\t\t\t * Enable with: adb shell touch /tmp/fox_render_trace
\t\t\t * Read with:   adb shell cat /tmp/fox_render.log
\t\t\t * render/flip are MICROSECONDS. flip includes the blocking atomic
\t\t\t * commit, so it reads ~16000 at 60 Hz and ~6900 at 144 Hz. */
\t\t\t{
\t\t\t\t/* Re-check every frame: the switch has to work AFTER boot.
\t\t\t\t * v6 cached this in a static, so `touch /tmp/fox_render_trace`
\t\t\t\t * from adb never took effect - the value was latched on the
\t\t\t\t * first rendered frame, long before the file existed. One
\t\t\t\t * access() syscall per rendered frame is ~1 us. */
\t\t\t\tconst int fox_trace = (access("/tmp/fox_render_trace", F_OK) == 0) ? 1 : 0;
\t\t\t\tif (!fox_trace) {
\t\t\t\t\tif (ret > 1)
\t\t\t\t\t\tPageManager::Render();
\t\t\t\t\tif (ret > 0)
\t\t\t\t\t\tflip();
\t\t\t\t} else {
\t\t\t\t\tstruct timespec t0, t1, t2;
\t\t\t\t\tclock_gettime(CLOCK_MONOTONIC, &t0);
\t\t\t\t\tif (ret > 1)
\t\t\t\t\t\tPageManager::Render();
\t\t\t\t\tclock_gettime(CLOCK_MONOTONIC, &t1);
\t\t\t\t\tif (ret > 0)
\t\t\t\t\t\tflip();
\t\t\t\t\tclock_gettime(CLOCK_MONOTONIC, &t2);
\t\t\t\t\tFILE *lf = fopen("/tmp/fox_render.log", "a");
\t\t\t\t\tif (lf) {
\t\t\t\t\t\tfprintf(lf, "ts=%ld.%06ld render=%ld flip=%ld ret=%d\\n",
\t\t\t\t\t\t\t(long)t2.tv_sec, (long)(t2.tv_nsec / 1000),
\t\t\t\t\t\t\t(long)((t1.tv_sec - t0.tv_sec) * 1000000L +
\t\t\t\t\t\t\t\t(t1.tv_nsec - t0.tv_nsec) / 1000),
\t\t\t\t\t\t\t(long)((t2.tv_sec - t1.tv_sec) * 1000000L +
\t\t\t\t\t\t\t\t(t2.tv_nsec - t1.tv_nsec) / 1000),
\t\t\t\t\t\t\tret);
\t\t\t\t\t\tfclose(lf);
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
"""

ANIM_OLD = "\tif (++mUpdateCount > TW_FRAMERATE / mFPS)"
ANIM_NEW = "\tif (++mUpdateCount >= TW_FRAMERATE / mFPS) // " + MARKER

# One entry per file. Multiple substitutions per file are applied to the SAME
# in-memory buffer, then written once - re-reading the file per rule would
# silently drop the earlier edit.
RULES = [
    ("objects.hpp", [
        (OBJECTS_OLD, OBJECTS_NEW,
         ["#define TW_FRAMERATE 144", "#undef TW_FRAMERATE", MARKER]),
    ]),
    ("gui.cpp", [
        (LOOP_OLD, LOOP_NEW,
         ["(got_event ? 2 : 1)", "long timeout = (long)("]),
        (TRACE_OLD, TRACE_NEW,
         ["/tmp/fox_render_trace", "/tmp/fox_render.log", "fox_trace"]),
    ]),
    ("animation.cpp", [
        (ANIM_OLD, ANIM_NEW,
         ["++mUpdateCount >= TW_FRAMERATE / mFPS"]),
    ]),
]


class PatchError(Exception):
    pass


# NOTE (portability): the CI runner is ubuntu-22.04, whose system python3 is
# 3.10. Path.read_text(newline=...) only exists in 3.13+, and Path.write_text
# (newline=...) only in 3.10+, so relying on them broke run #15 with
#     TypeError: Path.read_text() got an unexpected keyword argument 'newline'
# A local machine running a much newer CPython cannot catch that. Everything
# below therefore sticks to APIs available since Python 3.8 and uses the
# builtin open() whenever byte-exact line endings matter.
def read_raw(path):
    """Read text preserving the original line endings exactly."""
    with open(str(path), "r", encoding="utf-8", newline="") as f:
        return f.read()


def write_raw(path, text):
    """Write text without translating line endings."""
    with open(str(path), "w", encoding="utf-8", newline="") as f:
        f.write(text)


def apply(gui_dir):
    """Return (changed_files, notes, patches). Raises PatchError on mismatch."""
    notes = []
    changed = []
    patches = {}

    for name, subs in RULES:
        path = gui_dir / name
        if not path.is_file():
            raise PatchError("missing %s" % path)
        raw = read_raw(path)
        nl = "\r\n" if "\r\n" in raw else "\n"
        text = raw.replace("\r\n", "\n")
        touched = False

        for old, new, post in subs:
            if all(tok in text for tok in post):
                notes.append("SKIP %s: %s already present" % (name, post[0]))
                continue
            n = text.count(old)
            if n != 1:
                raise PatchError("%s: expected exactly 1 upstream snippet, "
                                 "found %d" % (name, n))
            text = text.replace(old, new, 1)
            for tok in post:
                if tok not in text:
                    raise PatchError("%s: patched file missing %r" % (name, tok))
            notes.append("PASS %s patched (%s)" % (name, post[0]))
            touched = True

        if touched:
            if MARKER not in text:
                raise PatchError("%s: marker missing after patch" % name)
            patches[name] = (text.replace("\n", nl), nl)
            changed.append(name)

    # Cross-file post-conditions on the resulting content
    def content(fname):
        if fname in patches:
            return patches[fname][0]
        return read_raw(gui_dir / fname)

    obj = content("objects.hpp")
    gui = content("gui.cpp")
    anim = content("animation.cpp")

    for label, text, bad in (
        ("objects.hpp", obj, ["#define TW_FRAMERATE 30"]),
        ("gui.cpp", gui, ["500000000",
                          "* (got_event ? 2 : 1)",
                          "#ifndef PRINT_RENDER_TIME\n\t\t\tif (ret > 1)"]),
        ("animation.cpp", anim, ["++mUpdateCount > TW_FRAMERATE / mFPS"]),
    ):
        for tok in bad:
            if tok in text:
                raise PatchError("%s still contains %r" % (label, tok))
    notes.append("PASS cross-file post-conditions: 144 fps default / "
                 "half-frame drag window / no unwrapped render path")

    return changed, notes, patches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gui_dir", help="path to bootable/recovery/gui")
    ap.add_argument("--check", action="store_true",
                    help="report only, do not write files")
    args = ap.parse_args()

    print("python %s (min supported %d.%d)"
          % (sys.version.split()[0], MIN_PY[0], MIN_PY[1]))
    if sys.version_info < MIN_PY:
        print("ERROR: this script needs Python %d.%d+" % MIN_PY)
        return 1

    gui_dir = Path(args.gui_dir)
    if not gui_dir.is_dir():
        print("ERROR: not a directory: %s" % gui_dir)
        return 1

    try:
        changed, notes, patches = apply(gui_dir)
        if not args.check:
            for name, (out, _) in patches.items():
                write_raw(gui_dir / name, out)
                print("wrote %s" % (gui_dir / name))
            again, _, _ = apply(gui_dir)
            if again:
                raise PatchError("patch is not idempotent")
            notes.append("PASS idempotent (second apply is a no-op)")
    except PatchError as e:
        print("ERROR: %s" % e)
        return 1

    for n in notes:
        print(n)
    print("gui framerate patch: %s" % ("APPLIED to %s" % ", ".join(changed)
                                       if changed else "already present"))
    print("ALL CHECKS PASS")
    if args.check:
        print("--check: files not modified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
