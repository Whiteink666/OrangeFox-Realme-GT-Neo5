#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_py_compat.py -- guard the CI patch scripts against too-new Python APIs.

Why this exists
---------------
Run #15 died in 6 minutes with

    TypeError: Path.read_text() got an unexpected keyword argument 'newline'

The local machine runs CPython 3.14, where ``Path.read_text(newline=...)``
(added in 3.13) works fine; the GitHub runner is ``ubuntu-22.04`` whose system
``python3`` is 3.10. A local replay therefore proves nothing about CI.

This script statically checks the patch scripts against a fixed target version
(default 3.8, i.e. below anything the runner could plausibly be):

  * ``ast.parse(..., feature_version=(3, 8))`` rejects syntax that is too new.
  * A table of stdlib attributes/keywords that only appeared after 3.8 is
    walked over the AST; any hit is a hard error.

Usage
-----
    python3 check_py_compat.py [--target 3.8] FILE_OR_DIR [FILE_OR_DIR ...]

Exit code 0 = all clean, 1 = at least one incompatibility, 2 = usage error.
"""

import argparse
import ast
import sys
from pathlib import Path

# Module calls: only flagged when the receiver is that exact module name, so
# e.g. ast.walk() is never confused with Path.walk() (3.12+).
MODULE_ATTRS = {
    ("itertools", "pairwise"): (3, 10),
    ("itertools", "batched"): (3, 12),
    ("asyncio", "timeout"): (3, 11),
    ("typing", "override"): (3, 12),
    ("typing", "Self"): (3, 11),
    ("enum", "StrEnum"): (3, 11),
    ("datetime", "UTC"): (3, 11),
}

# Method calls: keyword that only the newer version accepts. These names are
# unambiguous regardless of receiver.
METHOD_KWARGS = {
    "read_text": {"newline": (3, 13)},
    "write_text": {"newline": (3, 10)},
}

# Method calls whose mere existence requires a newer Python. Kept to names
# that no older stdlib/type ever used, so receive type need not be resolved.
METHOD_NAMES = {
    "removeprefix": (3, 9),
    "removesuffix": (3, 9),
    "bit_count": (3, 10),
    "is_junction": (3, 12),
    "hardlink_to": (3, 10),
}

FORBIDDEN_KWARGS = {
    # keyword: first version (call-site based, any receiver)
    "strict": (3, 10),      # zip(..., strict=)
}


def target_tuple(s):
    parts = s.split(".")
    if len(parts) != 2:
        raise ValueError("target must look like 3.8")
    return (int(parts[0]), int(parts[1]))


def check_file(path, target):
    problems = []
    src = Path(path).read_bytes().decode("utf-8", "replace")

    # 1. Syntax-level check
    try:
        tree = ast.parse(src, filename=str(path), feature_version=target)
    except TypeError:
        # Very old ast.parse wants a bare minor int.
        try:
            tree = ast.parse(src, filename=str(path),
                             feature_version=target[1])
        except SyntaxError as e:
            problems.append("line %s: syntax not valid on Python %d.%d (%s)"
                            % (e.lineno, target[0], target[1], e.msg))
            return problems
    except SyntaxError as e:
        problems.append("line %s: syntax not valid on Python %d.%d (%s)"
                        % (e.lineno, target[0], target[1], e.msg))
        return problems

    # 2. Attribute / keyword checks
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        attr = func.attr if isinstance(func, ast.Attribute) else None
        kwnames = [k.arg for k in node.keywords if k.arg]

        # Method keyword gating needs the attribute name; bare keywords such as
        # zip(..., strict=True) must still be checked, so this runs first.
        handled = set()
        if attr:
            for kw, since in METHOD_KWARGS.get(attr, {}).items():
                if kw in kwnames:
                    handled.add(kw)
                    if since > target:
                        problems.append(
                            "line %d: .%s(%s=...) needs Python %d.%d, target is %d.%d"
                            % (node.lineno, attr, kw, since[0], since[1],
                               target[0], target[1]))

        for kw in kwnames:
            if kw in handled:
                continue
            since = FORBIDDEN_KWARGS.get(kw)
            if since and since > target:
                problems.append(
                    "line %d: keyword %s= needs Python %d.%d, target is %d.%d"
                    % (node.lineno, kw, since[0], since[1], target[0], target[1]))

        if not attr:
            continue

        # module-qualified call, e.g. itertools.batched(...)
        recv = func.value
        mod = recv.id if isinstance(recv, ast.Name) else None
        since = MODULE_ATTRS.get((mod, attr)) if mod else None
        if since and since > target:
            problems.append(
                "line %d: %s.%s needs Python %d.%d, target is %d.%d"
                % (node.lineno, mod, attr, since[0], since[1],
                   target[0], target[1]))

        # method that simply does not exist before a given version
        since = METHOD_NAMES.get(attr)
        if since and since > target:
            problems.append(
                "line %d: .%s() needs Python %d.%d, target is %d.%d"
                % (node.lineno, attr, since[0], since[1], target[0], target[1]))
    return problems


def collect(paths):
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files.extend(sorted(p.glob("*.py")))
        elif p.is_file():
            files.append(p)
        else:
            print("ERROR: no such file or directory: %s" % p)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--target", default="3.8")
    args = ap.parse_args()

    try:
        target = target_tuple(args.target)
    except ValueError as e:
        print("ERROR: %s" % e)
        return 2

    files = collect(args.paths)
    if not files:
        print("ERROR: nothing to check")
        return 2

    bad = 0
    for f in files:
        problems = check_file(f, target)
        if problems:
            bad += 1
            print("FAIL %s" % f)
            for p in problems:
                print("     %s" % p)
        else:
            print("ok   %s" % f)

    print("\nchecking against Python %d.%d" % target)
    if bad:
        print("COMPAT CHECK FAILED: %d file(s) use APIs newer than the runner"
              % bad)
        return 1
    print("COMPAT CHECK PASS: %d file(s) safe for Python %d.%d"
          % (len(files), target[0], target[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
