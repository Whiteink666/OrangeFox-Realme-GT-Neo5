#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_diag_zip.py -- 把 scripts/diag_zip/ 打成一个能在 recovery 里刷的 zip。

为什么需要它
------------
用户是远控手机、身边没有电脑，跑不了 `adb push` + `adb shell`。唯一还能在
recovery 内执行任意脚本的通道就是"刷一个 zip"：OrangeFox 会执行 zip 里的
META-INF/com/google/android/update-binary。所以把诊断脚本做成 zip 发布，
用户在手机上直接下载、在 REC 里 Install 即可。

要点：
  * update-binary 必须有可执行位（zip 的 external_attr = 0o755 << 16），
    否则 TWRP 会报 "update-binary not found / not executable"。
  * 只用 LF 行尾：CRLF 会让 /sbin/sh 报 "not found" 之类的怪错。
  * 不做 JAR 签名。TWRP/OrangeFox 的"校验 zip 签名"默认关闭；如果用户手动
    打开过这项，需要先关掉。

用法：
    python scripts/build_diag_zip.py [--out dist/fox-diag.zip]
"""

import argparse
import os
import sys
import zipfile
from pathlib import Path

SRC = Path(__file__).resolve().parent / "diag_zip"
EXEC_FILES = {"META-INF/com/google/android/update-binary"}


def build(out_path):
    entries = []
    for p in sorted(SRC.rglob("*")):
        if p.is_file():
            entries.append(p)
    if not entries:
        raise SystemExit("ERROR: %s 是空的" % SRC)

    need = "META-INF/com/google/android/update-binary"
    names = [p.relative_to(SRC).as_posix() for p in entries]
    if need not in names:
        raise SystemExit("ERROR: 缺少 %s" % need)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in entries:
            name = p.relative_to(SRC).as_posix()
            data = p.read_bytes()
            # 强制 LF：任何 CRLF 都会让 recovery 的 sh 解释失败
            if name.startswith("META-INF/com/google/android/") or name.endswith(".sh"):
                if b"\r\n" in data:
                    data = data.replace(b"\r\n", b"\n")
                    print("  规范化行尾(LF): %s" % name)
            zi = zipfile.ZipInfo(name)
            mode = 0o755 if name in EXEC_FILES else 0o644
            zi.external_attr = mode << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, data)
            print("  + %-52s %7d  mode=%o" % (name, len(data), mode))

    size = out_path.stat().st_size
    print("\n写出 %s (%d bytes)" % (out_path, size))

    # 自检：重新读回来确认可执行位与内容都在
    with zipfile.ZipFile(out_path) as z:
        bad = z.testzip()
        if bad:
            raise SystemExit("ERROR: zip 损坏于 %s" % bad)
        info = z.getinfo("META-INF/com/google/android/update-binary")
        mode = info.external_attr >> 16
        body = z.read(info)
        print("自检: update-binary mode=%o, %d bytes, 首行=%r"
              % (mode, len(body), body.split(b"\n")[0]))
        if not mode & 0o111:
            raise SystemExit("ERROR: update-binary 没有可执行位")
        if not body.startswith(b"#!"):
            raise SystemExit("ERROR: update-binary 不是脚本（缺 shebang）")
        if b"\r\n" in body:
            raise SystemExit("ERROR: update-binary 仍含 CRLF")
    print("OK")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(SRC.parent.parent / "dist" / "fox-diag.zip"))
    args = ap.parse_args()
    return build(args.out)


if __name__ == "__main__":
    sys.exit(main())
