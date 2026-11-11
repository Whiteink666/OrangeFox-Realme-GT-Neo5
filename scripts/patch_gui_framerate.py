#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_gui_framerate.py -- Whiteink framerate patch v5

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
  1. objects.hpp: force TW_FRAMERATE to 144 (removes the 30 fps ceiling and
     matches the panel mode the DRM patch selects). The real rate is still
     bounded by CPU software rendering of a 1240x2772 RGBX_8888 framebuffer;
     144 is a ceiling, not a promise.
  2. gui.cpp: replace the 500 ms ``got_event`` window with two UI frames.
  3. animation.cpp: ``>`` -> ``>=`` on the integer-division frame divider.
     With 144/60 = 2 the spinner advances every 2 frames (60 fps); with the
     old ``>`` it advanced every 3 frames (40 fps).

Exact-string replacements with match-count assertions, idempotent, and every
failure aborts CI before the ~2 h build starts.

Usage
-----
    python3 patch_gui_framerate.py <path/to/gui/dir> [--check]
"""

import argparse
import sys
from pathlib import Path

MARKER = "Whiteink framerate patch v5"

OBJECTS_OLD = """#ifndef TW_FRAMERATE
#define TW_FRAMERATE 30
#endif
"""
OBJECTS_NEW = """// Whiteink framerate patch v5: OrangeFox 12.1 Android.mk never forwards the
// BoardConfig TW_FRAMERATE variable into a -D flag, so this default (30) was
// the REAL global redraw cadence. 144 removes that artificial ceiling and
// matches the 144 Hz panel mode selected by the DRM patch; the achievable
// rate stays bounded by CPU software rendering of the framebuffer.
#undef TW_FRAMERATE
#define TW_FRAMERATE 144
"""

LOOP_OLD = "\t\tlong timeout = got_event ? 500000000 : (1.0 / TW_FRAMERATE * 1000000000);"
LOOP_NEW = """\t\t// Whiteink framerate patch v5: upstream used a 500 ms catch-up window
\t\t// whenever an input event was seen, collapsing drags to ~2 redraws/sec.
\t\t// Cap it at two UI frames instead so drags still follow the finger.
\t\tlong timeout = (1.0 / TW_FRAMERATE * 1000000000) * (got_event ? 2 : 1);"""

ANIM_OLD = "\tif (++mUpdateCount > TW_FRAMERATE / mFPS)"
ANIM_NEW = "\tif (++mUpdateCount >= TW_FRAMERATE / mFPS) // " + MARKER


class PatchError(Exception):
    pass


# NOTE (portability): the CI runner is ubuntu-22.04, whose system python3 is
# 3.10. Path.read_text(newline=...) only exists in 3.13+, and Path.write_text
# (newline=...) only in 3.10+, so relying on them broke run #15 with
#     TypeError: Path.read_text() got an unexpected keyword argument 'newline'
# A local machine running a much newer CPython cannot catch that. Everything
# below therefore sticks to APIs available since Python 3.8 and uses the
# builtin open() whenever byte-exact line endings matter.
MIN_PY = (3, 8)


def read_raw(path):
    """Read text preserving the original line endings exactly."""
    with open(str(path), "r", encoding="utf-8", newline="") as f:
        return f.read()


def write_raw(path, text):
    """Write text without translating line endings."""
    with open(str(path), "w", encoding="utf-8", newline="") as f:
        f.write(text)


RULES = [
    ("objects.hpp", OBJECTS_OLD, OBJECTS_NEW,
     ["#define TW_FRAMERATE 144", "#undef TW_FRAMERATE"]),
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
        raw = read_raw(path)
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
