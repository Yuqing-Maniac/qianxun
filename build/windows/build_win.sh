#!/bin/bash
# Re-runnable: assemble $WORK/dist/stage-win/QianXun, zip, portable exe, SHA256SUMS from current sources.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd); WORK=${QX_WORK:-$ROOT/_work}
W=$ROOT/build/windows; RT=$WORK/win/runtime; OBJ=$WORK/win/obj; D=$WORK/dist
VER=$(sed -n "s/^VERSION = '\(.*\)'$/\1/p" "$ROOT/app/qianxun.py"); [ -n "$VER" ] || { echo "VERSION not found in app/qianxun.py" >&2; exit 1; }
APP=$ROOT/app/qianxun.py
CC=x86_64-w64-mingw32-gcc; WR=x86_64-w64-mingw32-windres
[ -d $RT/Lib/site-packages/PyQt5 ] || bash $W/build_runtime.sh
mkdir -p $D $OBJ/launcher
cp $W/launcher/* $OBJ/launcher/
# icon from svg (generated into the work dir, never into the source tree)
for s in 16 24 32 48 64 128 256; do rsvg-convert -w $s -h $s $ROOT/assets/icons/qianxun.svg -o $OBJ/ico$s.png; done
(cd $OBJ && convert ico16.png ico24.png ico32.png ico48.png ico64.png ico128.png ico256.png $OBJ/launcher/qianxun.ico)
# launchers
(cd $OBJ/launcher && $WR -c 65001 -O coff launcher.rc -o $OBJ/res.o &&
 $CC -municode -mwindows -O2 -s -Wall -static -o $OBJ/QianXun.exe launcher.c $OBJ/res.o &&
 $CC -municode -mwindows -O2 -s -Wall -static -DPORTABLE -o $OBJ/QianXun-stub.exe launcher.c $OBJ/res.o -lcomctl32 -lz)
# stage folder
S=$D/stage-win/QianXun; rm -rf $D/stage-win; mkdir -p $S/app
cp $OBJ/QianXun.exe $S/; cp $APP $S/app/qianxun.py; cp -a $RT $S/runtime
python3 - "$W" "$S" <<'PY'
import sys, os
w, s = sys.argv[1:]
src = os.path.join(w, "README_WIN.txt")
if os.path.exists(src):
    t = open(src, encoding="utf-8-sig").read()
else:
    t = ("千寻 文件秒搜（Windows 版）\n\n"
         "使用：解压整个文件夹到任意位置（无需管理员权限），双击 QianXun.exe 即可。\n"
         "要求：Windows 10 或更高版本（64 位）。\n"
         "便携模式：在 QianXun.exe 同目录新建空文件 portable.txt，数据将保存在 data 文件夹内。\n"
         "卸载：直接删除整个文件夹；数据位于 %LOCALAPPDATA%\\QianXun\\。\n")
t = t.replace("\r\n", "\n").replace("\n", "\r\n")
open(os.path.join(s, "README.txt"), "wb").write(b"\xef\xbb\xbf" + t.encode("utf-8"))
PY
# zip (ASCII names, python zipfile)
Z=$D/qianxun-$VER-windows-x64.zip; rm -f $Z
python3 - "$D/stage-win" "$Z" <<'PY'
import sys, os, zipfile, time
root, out = sys.argv[1:]
names = []
for r, ds, fs in os.walk(root):
    ds.sort()
    for f in sorted(fs):
        p = os.path.join(r, f); names.append((os.path.relpath(p, root).replace(os.sep, "/"), p))
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for n, p in names:
        n.encode("ascii")
        zi = zipfile.ZipInfo(n, time.localtime(max(os.path.getmtime(p), 315532800))[:6])
        zi.compress_type = zipfile.ZIP_DEFLATED; zi.external_attr = 0o644 << 16; zi.create_system = 0
        z.writestr(zi, open(p, "rb").read(), compresslevel=9)
print("zip entries:", len(names))
PY
# portable
P=$D/QianXun-$VER-portable.exe
python3 $W/pack_portable.py $OBJ/QianXun-stub.exe $S/runtime $S/app $P
# sums
touch $D/SHA256SUMS.txt
grep -v -F -e "qianxun-$VER-windows-x64.zip" -e "QianXun-$VER-portable.exe" $D/SHA256SUMS.txt > $D/SHA256SUMS.tmp || true
(cd $D && sha256sum "qianxun-$VER-windows-x64.zip" "QianXun-$VER-portable.exe" | sed 's/ \*/  /') >> $D/SHA256SUMS.tmp
mv $D/SHA256SUMS.tmp $D/SHA256SUMS.txt
ls -la $Z $P; tail -2 $D/SHA256SUMS.txt
