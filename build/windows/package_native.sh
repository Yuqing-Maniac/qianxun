#!/bin/bash
# Build the native Win32 version (native/build.sh) and package it into $WORK/dist.
# Written 2026-10-22 for the repository (the original release zip was assembled by hand with the same layout).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd); WORK=${QX_WORK:-$ROOT/_work}; D=$WORK/dist; VER=1.2.0
bash "$ROOT/native/build.sh" all
mkdir -p "$D"
cp "$ROOT/native/out/QianXun-x64.exe" "$ROOT/native/out/QianXun-x86.exe" "$D/"
python3 - "$ROOT" "$D/qianxun-$VER-windows-native.zip" <<'PY'
import sys, zipfile
root, out = sys.argv[1:]
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for src, dst in [('native/out/QianXun-x64.exe', 'QianXun/QianXun-x64.exe'),
                     ('native/out/QianXun-x86.exe', 'QianXun/QianXun-x86.exe'),
                     ('native/pkg/README.txt', 'QianXun/README.txt')]:
        dst.encode('ascii'); z.write(f'{root}/{src}', dst)
print('wrote', out)
PY
