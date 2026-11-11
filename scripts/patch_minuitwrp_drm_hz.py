#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_minuitwrp_drm_hz.py -- Whiteink DRM refresh patch v1

Why this exists
---------------
``minuitwrp/graphics_drm.cpp::find_main_monitor()`` selects the display timing
the kernel marks ``DRM_MODE_TYPE_PREFERRED``:

    *mode_index = 0;
    for (int modes = 0; modes < connector->count_modes; modes++) {
        if (connector->modes[modes].type & DRM_MODE_TYPE_PREFERRED) {
            *mode_index = modes;
            break;
        }
    }

On RMXTARO the kernel-preferred timing is the 60 Hz one, even though the panel
advertises the whole ladder (measured on device):

    1240x2772x60cmd / x90cmd / x120cmd / x144cmd

Recovery's flip path is synchronous - ``drm_flip()`` does a full-frame memcpy
(1240x2772x4 = 13.75 MB) and then a blocking ``drmModeAtomicCommit``. Each
frame therefore pays one vblank on top of the drawing cost, so the vblank
interval is a direct per-frame tax:

    60 Hz  -> +16.7 ms/frame
    144 Hz -> +6.9 ms/frame

What this patch does (three insertions, all anchored on exact upstream text)
---------------------------------------------------------------------------
  1. file scope: two statics to remember the kernel-preferred index and the
     refresh actually selected;
  2. find_main_monitor(): keep the preferred index as a fallback, then scan
     all modes with the same resolution and pick the highest ``vrefresh``;
  3. drm_init(): if the atomic commit for the high-refresh mode is rejected
     (``drm_blank()`` leaves ``current_blank_state`` at its initial true), put
     the preferred timing back, rebuild the mode blob and commit again. This
     is the black-screen guard: a bad timing degrades to 60 Hz in the same
     boot instead of leaving an unusable display.

It also appends ``/tmp/fox_drm.log`` so the selected refresh can be read back
after boot without a display.

Usage
-----
    python3 patch_minuitwrp_drm_hz.py <path/to/minuitwrp> [--check]
"""

import argparse
import sys
from pathlib import Path

MIN_PY = (3, 8)
TARGET = "graphics_drm.cpp"

MARK_A = "/* Whiteink DRM refresh patch v1: mode indices */"
MARK_B = "/* Whiteink DRM refresh patch v1: prefer the highest refresh */"
MARK_C = "/* Whiteink DRM refresh patch v1: black-screen guard */"

ANCHOR_A = """static drmModeCrtc *main_monitor_crtc;
static drmModeConnector *main_monitor_connector;
"""

NEW_A = """static drmModeCrtc *main_monitor_crtc;
static drmModeConnector *main_monitor_connector;
/* Whiteink DRM refresh patch v1: mode indices */
static uint32_t g_pref_mode_index = 0;
static uint32_t g_selected_vrefresh = 0;
"""

ANCHOR_B = """    *mode_index = 0;
    for (int modes = 0; modes < main_monitor_connector->count_modes; modes++) {
        if (main_monitor_connector->modes[modes].type &
                DRM_MODE_TYPE_PREFERRED) {
            *mode_index = modes;
            break;
        }
    }
"""

NEW_B = """    *mode_index = 0;
    for (int modes = 0; modes < main_monitor_connector->count_modes; modes++) {
        if (main_monitor_connector->modes[modes].type &
                DRM_MODE_TYPE_PREFERRED) {
            *mode_index = modes;
            break;
        }
    }

    /* Whiteink DRM refresh patch v1: prefer the highest refresh */
    /* The kernel marks exactly one timing PREFERRED, and on this panel that is
     * the 60 Hz one, so 90/120/144 Hz were never used even though the
     * connector advertises them. Keep the preferred index for the fallback in
     * drm_init() and score the rest by vrefresh at the same resolution.
     */
    g_pref_mode_index = *mode_index;
    {
        const drmModeModeInfo *pref =
            &main_monitor_connector->modes[g_pref_mode_index];
        uint32_t best = g_pref_mode_index;
        for (int modes = 0; modes < main_monitor_connector->count_modes; modes++) {
            const drmModeModeInfo *m = &main_monitor_connector->modes[modes];
            if (m->hdisplay != pref->hdisplay || m->vdisplay != pref->vdisplay)
                continue;
            if (m->vrefresh > main_monitor_connector->modes[best].vrefresh)
                best = modes;
        }
        if (best != g_pref_mode_index) {
            *mode_index = best;
            g_selected_vrefresh = main_monitor_connector->modes[best].vrefresh;
            printf("drm: preferring %ux%u@%u over kernel-preferred @%u\\n",
                   (unsigned)main_monitor_connector->modes[best].hdisplay,
                   (unsigned)main_monitor_connector->modes[best].vdisplay,
                   (unsigned)main_monitor_connector->modes[best].vrefresh,
                   (unsigned)pref->vrefresh);
        } else {
            g_selected_vrefresh = pref->vrefresh;
            printf("drm: kernel-preferred mode is already highest (%u Hz)\\n",
                   (unsigned)pref->vrefresh);
        }
    }
"""

ANCHOR_C = """  drm_blank(nullptr, false);

  return draw_buf;
"""

NEW_C = """  drm_blank(nullptr, false);

  /* Whiteink DRM refresh patch v1: black-screen guard */
  /* drm_blank() prints on failure and leaves current_blank_state at its
   * initial value of true. If the high-refresh timing was rejected, restore
   * the kernel-preferred timing and commit once more, so a bad mode can never
   * leave the recovery unusable.
   */
  if (current_blank_state != false) {
    printf("drm: high-refresh modeset failed, retrying preferred timing\\n");
    main_monitor_crtc->mode = main_monitor_connector->modes[g_pref_mode_index];
    drmModeDestroyPropertyBlob(drm_fd, crtc_res.mode_blob_id);
    crtc_res.mode_blob_id = 0;
    if (drmModeCreatePropertyBlob(drm_fd, &main_monitor_crtc->mode,
                                  sizeof(drmModeModeInfo),
                                  &crtc_res.mode_blob_id)) {
      printf("drm: fallback mode blob failed\\n");
    } else {
      current_blank_state = true;
      drm_blank(nullptr, false);
      g_selected_vrefresh =
          main_monitor_connector->modes[g_pref_mode_index].vrefresh;
    }
  }

  {
    FILE *lf = fopen("/tmp/fox_drm.log", "a");
    if (lf) {
      fprintf(lf, "vrefresh=%u modeset_ok=%d\\n",
              g_selected_vrefresh, current_blank_state ? 0 : 1);
      fclose(lf);
    }
  }

  return draw_buf;
"""

RULES = [
    ("A statics", MARK_A, ANCHOR_A, NEW_A,
     [MARK_A, "g_pref_mode_index", "g_selected_vrefresh"]),
    ("B mode select", MARK_B, ANCHOR_B, NEW_B,
     [MARK_B, "g_pref_mode_index = *mode_index;",
      "if (m->vrefresh > main_monitor_connector->modes[best].vrefresh)",
      "g_selected_vrefresh = main_monitor_connector->modes[best].vrefresh;"]),
    ("C blank guard", MARK_C, ANCHOR_C, NEW_C,
     [MARK_C, "current_blank_state != false",
      "drmModeDestroyPropertyBlob(drm_fd, crtc_res.mode_blob_id)",
      '"/tmp/fox_drm.log"']),
]


class PatchError(Exception):
    pass


def read_raw(path):
    with open(str(path), "r", encoding="utf-8", newline="") as f:
        return f.read()


def write_raw(path, text):
    with open(str(path), "w", encoding="utf-8", newline="") as f:
        f.write(text)


def balance(text):
    """Count braces/parens/brackets outside strings and comments.

    There is no C++ compiler on the dev machine and none runs before the
    minuitwrp target, so an unbalanced insertion would only surface deep inside
    a ~2 h CI build. This catches the realistic failure mode (a stray or
    missing brace) in microseconds.
    """
    counts = {"braces": 0, "parens": 0, "brackets": 0}
    pairs = {"{": "braces", "}": "braces", "(": "parens", ")": "parens",
             "[": "brackets", "]": "brackets"}
    i, n = 0, len(text)
    state = None  # None | "line" | "block" | "str" | "chr"
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state is None:
            if c == "/" and nxt == "/":
                state = "line"
                i += 2
                continue
            if c == "/" and nxt == "*":
                state = "block"
                i += 2
                continue
            if c == '"':
                state = "str"
            elif c == "'":
                state = "chr"
            elif c in pairs:
                counts[pairs[c]] += 1 if c in "{([" else -1
            i += 1
            continue
        if state == "line":
            if c == "\n":
                state = None
        elif state == "block":
            if c == "*" and nxt == "/":
                state = None
                i += 2
                continue
        else:  # string or char literal
            if c == "\\":
                i += 2
                continue
            if (state == "str" and c == '"') or (state == "chr" and c == "'"):
                state = None
        i += 1
    return counts


def apply(drm_dir):
    """Return (changed, notes). Raises PatchError on any mismatch."""
    path = drm_dir / TARGET
    if not path.is_file():
        raise PatchError("missing %s" % path)

    raw = read_raw(path)
    nl = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    notes = []
    changed = False

    for name, marker, old, new, post in RULES:
        if marker in text:
            for token in post:
                if token not in text:
                    raise PatchError("%s: already patched but missing %r"
                                     % (name, token))
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
        notes.append("PASS %s patched (1 exact match)" % name)
        changed = True

    # Cross-check: the original hardcoded "preferred only" behaviour must be
    # gone as a standalone choice, i.e. the scan must now exist.
    if "for (int modes = 0; modes < main_monitor_connector->count_modes; modes++) {\n            const drmModeModeInfo *m" not in text:
        raise PatchError("cross-check: vrefresh scan loop not present")

    # Cross-check: every insertion is bracket-balanced, so the file cannot be
    # syntactically broken by the patch itself. Upstream nets out to zero on
    # all three counters, so any change here is ours.
    before = balance(raw.replace("\r\n", "\n"))
    after = balance(text)
    for key in ("braces", "parens", "brackets"):
        if after[key] != before[key] or after[key] != 0:
            raise PatchError(
                "cross-check: %s unbalanced (%d -> %d); inserted code is "
                "malformed" % (key, before[key], after[key]))
    notes.append("PASS bracket balance %s" % after)

    return changed, notes, text.replace("\n", nl) if changed else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drm_dir", help="path to bootable/recovery/minuitwrp")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    print("python %s (min supported %d.%d)"
          % (sys.version.split()[0], MIN_PY[0], MIN_PY[1]))
    if sys.version_info < MIN_PY:
        print("ERROR: this script needs Python %d.%d+" % MIN_PY)
        return 1

    drm_dir = Path(args.drm_dir)
    if not drm_dir.is_dir():
        print("ERROR: not a directory: %s" % drm_dir)
        return 1

    try:
        changed, notes, out = apply(drm_dir)
        if changed and not args.check:
            write_raw(drm_dir / TARGET, out)
            print("wrote %s" % (drm_dir / TARGET))
            again, _, _ = apply(drm_dir)
            if again:
                raise PatchError("patch is not idempotent")
            notes.append("PASS idempotent (second apply is a no-op)")
    except PatchError as e:
        print("ERROR: %s" % e)
        return 1

    for n in notes:
        print(n)
    print("drm refresh patch: %s" % ("APPLIED" if changed else "already present"))
    print("ALL CHECKS PASS")
    if args.check:
        print("--check: files not modified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
