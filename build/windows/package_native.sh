#!/bin/bash
# Native Win7-11 packages. Python 3.13 cannot run on Windows 7, so this exe is the Win7 build.
# Each zip has QianXun.exe beside the QianXun folder. The exe already carries the icon.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd); WORK=${QX_WORK:-$ROOT/_work}; D=$WORK/dist
VER=$(sed -n "s/^VERSION = '\(.*\)'$/\1/p" "$ROOT/app/qianxun.py"); [ -n "$VER" ] || { echo "VERSION not found in app/qianxun.py" >&2; exit 1; }
[ -s "$ROOT/native/res/qianxun.ico" ] || { echo "missing native icon $ROOT/native/res/qianxun.ico" >&2; exit 1; }
bash "$ROOT/native/build.sh" all
mkdir -p "$D"
pack_one() {
  local bits=$1
  local exe=$ROOT/native/out/QianXun-$bits.exe
  python3 "$ROOT/build/portable_layout.py" exe "$exe"
  local stage=$D/stage-native-$bits
  rm -rf "$stage"
  mkdir -p "$stage/QianXun"
  cp "$exe" "$stage/QianXun.exe"
  cp "$ROOT/native/pkg/README.txt" "$stage/QianXun/README.txt"
  local out=$D/qianxun-$VER-windows7-$bits.zip
  rm -f "$out"
  python3 - "$stage" "$out" <<'PY'
import sys, os, zipfile, time
root, out = sys.argv[1:]
names = []
for r, ds, fs in os.walk(root):
    ds.sort()
    for f in sorted(fs):
        p = os.path.join(r, f)
        names.append((os.path.relpath(p, root).replace(os.sep, "/"), p))
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for n, p in names:
        n.encode("ascii")
        zi = zipfile.ZipInfo(n, time.localtime(max(os.path.getmtime(p), 315532800))[:6])
        zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = 0o644 << 16
        zi.create_system = 0
        z.writestr(zi, open(p, "rb").read(), compresslevel=9)
print("zip entries:", len(names), out)
PY
  python3 "$ROOT/build/portable_layout.py" archive "$out" --folder QianXun --entry QianXun.exe \
    --need QianXun/README.txt
}
pack_one x64
pack_one x86
