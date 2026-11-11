#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_gui_framerate.py -- Whiteink framerate patch v4

Why this exists
---------------
OrangeFox 12.1's ``Android.mk`` does NOT forward the BoardConfig variable
``TW_FRAMERATE`` into a ``-DTW_FRAMERATE=...`` compiler flag (only a few TW_*
variables such as TW_DEFAULT_LANGUAGE get that treatment). The value actually
used by the GUI therefore comes from ``gui/objects.hpp``:

    #ifndef TW_FRAMERATE
    #define TW_FRAMERATE 30
    #endif

``gui/gui.cpp::loopTimer()`` uses it as the global redraw cadence:

    long timeout = got_event ? 500000000 : (1.0 / TW_FRAMERATE * 1000000000);

So the UI was hard-capped at **30 fps**, and any input event stretched the
catch-up window to **500 ms** (~2 redraws/sec while dragging). Setting
``TW_FRAMERATE := 60`` in BoardConfig.mk never changed either of these.

What this patch does (on the freshly synced upstream sources)
-------------------------------------------------------------
  1. objects.hpp: force TW_FRAMERATE to 120 (removes the 30 fps ceiling).
     The real rate is still bounded by CPU software rendering of a
     1240x2772 RGBX_8888 framebuffer; 120 is a ceiling, not a promise.
  2. gui.cpp: replace the 500 ms ``got_event`` window with two UI frames.
  3. animation.cpp: ``>`` -> ``>=`` on the integer-division frame divider.
     With 120/60 = 2 the spinner now advances every 2 frames (60 fps);
     with the old ``>`` it advanced every 3 frames (40 fps).

Exact-string replacements with match-count assertions, idempotent, and every
failure aborts CI before the ~2 h build starts.

Usage
-----
    python3 patch_gui_framerate.py <path/to/gui/dir> [--check]
"""

import argparse
import sys
from pathlib import Path

MARKER = "Whiteink framerate patch v4"

OBJECTS_OLD = """#ifndef TW_FRAMERATE
#define TW_FRAMERATE 30
#endif
"""
OBJECTS_NEW = """// Whiteink framerate patch v4: OrangeFox 12.1 Android.mk never forwards the
// BoardConfig TW_FRAMERATE variable into a -D flag, so this default (30) was
// the REAL global redraw cadence. 120 removes that artificial ceiling; the
// achievable rate stays bounded by CPU software rendering of the framebuffer.
#undef TW_FRAMERATE
#define TW_FRAMERATE 120
"""

LOOP_OLD = "\t\tlong timeout = got_event ? 500000000 : (1.0 / TW_FRAMERATE * 1000000000);"
LOOP_NEW = """\t\t// Whiteink framerate patch v4: upstream used a 500 ms catch-up window
\t\t// whenever an input event was seen, collapsing drags to ~2 redraws/sec.
\t\t// Cap it at two UI frames instead so drags still follow the finger.
\t\tlong timeout = (1.0 / TW_FRAMERATE * 1000000000) * (got_event ? 2 : 1);"""

ANIM_OLD = "\tif (++mUpdateCount > TW_FRAMERATE / mFPS)"
ANIM_NEW = "\tif (++mUpdateCount >= TW_FRAMERATE / mFPS) // " + MARKER


class PatchError(Exception):
    pass


RULES = [
    ("objects.hpp", OBJECTS_OLD, OBJECTS_NEW,
     ["#define TW_FRAMERATE 120", "#undef TW_FRAMERATE"]),
    ("gui.cpp", LOOP_OLD, LOOP_NEW,
     ["(got_event ? 2 : 1)"]),
    ("animation.cpp", ANIM_OLD, ANIM_NEW,
     ["++mUpdateCount >= TW_FRAMERATE / mFPS"]),
]


def apply(gui_dir):
    """Return (changed_files, notes). Raises PatchError on any mismatch."""
    notes = []
    changed = []
    patches = {}

    for name, old, new, post in RULES:
        path = gui_dir / name
        if not path.is_file():
            raise PatchError("missing %s" % path)
        raw = path.read_text(encoding="utf-8", newline="")
        nl = "\r\n" if "\r\n" in raw else "\n"
        text = raw.replace("\r\n", "\n")

        if MARKER in text:
            for token in post:
                if token not in text:
                    raise PatchError("%s already patched but missing %r" % (name, token))
            notes.append("SKIP %s already patched (idempotent)" % name)
            continue

        n = text.count(old)
        if n != 1:
            raise PatchError("%s: expected exactly 1 upstream snippet, found %d"
                             % (name, n))
        text = text.replace(old, new, 1)
        for token in post:
            if token not in text:
                raise PatchError("%s: patched file missing %r" % (name, token))
        if MARKER not in text:
            raise PatchError("%s: marker missing after patch" % name)
        notes.append("PASS %s patched (1 exact match)" % name)
        patches[name] = (text.replace("\n", nl), nl)
        changed.append(name)

    # Cross-file post-conditions on the resulting content
    obj = patches.get("objects.hpp", (None, None))[0]
    if obj is None:
        obj = (gui_dir / "objects.hpp").read_text(encoding="utf-8", errors="replace")
    gui = patches.get("gui.cpp", (None, None))[0]
    if gui is None:
        gui = (gui_dir / "gui.cpp").read_text(encoding="utf-8", errors="replace")
    anim = patches.get("animation.cpp", (None, None))[0]
    if anim is None:
        anim = (gui_dir / "animation.cpp").read_text(encoding="utf-8", errors="replace")

    for label, text, bad in (
        ("objects.hpp", obj, ["#define TW_FRAMERATE 30"]),
        ("gui.cpp", gui, ["500000000"]),
        ("animation.cpp", anim, ["++mUpdateCount > TW_FRAMERATE / mFPS"]),
    ):
        for token in bad:
            if token in text:
                raise PatchError("%s still contains %r" % (label, token))
    notes.append("PASS cross-file post-conditions: no 30 fps default / "
                 "no 500 ms window / no '>' frame divider")

    return changed, notes, patches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gui_dir", help="path to bootable/recovery/gui")
    ap.add_argument("--check", action="store_true",
                    help="report only, do not write files")
    args = ap.parse_args()

    gui_dir = Path(args.gui_dir)
    if not gui_dir.is_dir():
        print("ERROR: not a directory: %s" % gui_dir)
        return 1

    try:
        changed, notes, patches = apply(gui_dir)
        if not args.check:
            for name, (out, _) in patches.items():
                (gui_dir / name).write_text(out, encoding="utf-8", newline="")
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
