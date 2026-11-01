#!/bin/bash
# build_runtime.sh - rebuild the Windows x64 runtime of QianXun ($WORK/win/runtime) from scratch.
#
# Inputs (downloaded into $WORK/dl, sha256-pinned): python-build-standalone 3.13.15 from the npm package
# @rowstile/cli-win32-x64 0.1.0-alpha.7, and the PyQt5 5.15.11 / PyQt5-Qt5 5.15.2 / PyQt5-sip 12.20.0 win_amd64 wheels.
# Original logic unchanged (trimmed stdlib, trimmed Qt, sitecustomize.py, unchecked-hash .pyc); only paths and
# downloads were made repo-relative / self-contained on 2026-10-22 (see docs/BUILD_RUNTIMES.md).
#
# wine is needed ONLY to byte-compile the stdlib to unchecked-hash .pyc (python.exe is a Windows binary).
# Without wine the runtime is still complete and works, just without precompiled .pyc (slower first start).
# WINEPREFIX defaults to $WORK/win/wineprefix (created on first use, 64-bit).
#
# Prerequisites (Ubuntu 24.04): sudo apt-get install -y curl ca-certificates tar gzip unzip coreutils findutils
#                               [optional, for .pyc] wine64 (xvfb not needed for python.exe)
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd); WORK=${QX_WORK:-$ROOT/_work}
W=$ROOT/build/windows; DL=$WORK/dl; T=$WORK/win/tmp; RT=$WORK/win/runtime
for c in curl tar unzip sha256sum find; do command -v $c >/dev/null || { echo "missing tool: $c (sudo apt-get install -y curl tar unzip coreutils findutils)" >&2; exit 1; }; done
mkdir -p "$DL" "$T"

fetch() {  # fetch NAME URL SHA256
  local f=$DL/$1
  if [ -f "$f" ] && [ "$(sha256sum "$f" | cut -d' ' -f1)" = "$3" ]; then
    echo "[cached] $1  sha256=$3  $(wc -c <"$f") bytes"; return 0; fi
  echo "[download] $1"; echo "           $2"
  curl -fsSL --retry 3 -o "$f.part" "$2"
  local got; got=$(sha256sum "$f.part" | cut -d' ' -f1)
  [ "$got" = "$3" ] || { echo "SHA256 MISMATCH for $1: expected $3 got $got" >&2; rm -f "$f.part"; exit 1; }
  mv "$f.part" "$f"; echo "           sha256=$3  $(wc -c <"$f") bytes OK"
}
PYPI=https://files.pythonhosted.org/packages
fetch cli-win32-x64-0.1.0-alpha.7.tgz https://registry.npmjs.org/@rowstile/cli-win32-x64/-/cli-win32-x64-0.1.0-alpha.7.tgz \
  971f68ca2fc4f75730b452ddebc125a8dcd40f8ab20bce78529c4791da42b094
fetch PyQt5-5.15.11-cp38-abi3-win_amd64.whl $PYPI/56/d5/68eb9f3d19ce65df01b6c7b7a577ad3bbc9ab3a5dd3491a4756e71838ec9/PyQt5-5.15.11-cp38-abi3-win_amd64.whl \
  bdde598a3bb95022131a5c9ea62e0a96bd6fb28932cc1619fd7ba211531b7517
fetch PyQt5_Qt5-5.15.2-py3-none-win_amd64.whl $PYPI/37/97/5d3b222b924fa2ed4c2488925155cd0b03fd5d09ee1cfcf7c553c11c9f66/PyQt5_Qt5-5.15.2-py3-none-win_amd64.whl \
  750b78e4dba6bdf1607febedc08738e318ea09e9b10aea9ff0d73073f11f6962
fetch pyqt5_sip-12.20.0-cp313-cp313-win_amd64.whl $PYPI/0c/24/16df862e13a9ea7ba173dd4c150dc34d06ce1a76fcc895d2aa754ef85a57/pyqt5_sip-12.20.0-cp313-cp313-win_amd64.whl \
  194ec42291089077c3290ad02c74a4b4922eb0f6608dd0bb133fbca60b985acd

rm -rf "$T/x" "$T/q" "$RT"; mkdir -p "$T/x" "$T/q"
tar xzf "$DL/cli-win32-x64-0.1.0-alpha.7.tgz" -C "$T/x"
(cd "$T/q" && for w in PyQt5-5.15.11-cp38-abi3-win_amd64.whl PyQt5_Qt5-5.15.2-py3-none-win_amd64.whl pyqt5_sip-12.20.0-cp313-cp313-win_amd64.whl; do unzip -oq "$DL/$w"; done)
cp -r "$T/x/package/python" "$RT"; cd "$RT"
rm -rf Lib/test Lib/idlelib Lib/tkinter Lib/ensurepip Lib/lib2to3 Lib/turtledemo Lib/pydoc_data Lib/curses Lib/_pyrepl
rm -f Lib/turtle.py Lib/pydoc.py Lib/this.py Lib/antigravity.py
find . -name __pycache__ -prune -exec rm -rf {} +
rm -f DLLs/_test*.pyd DLLs/_ctypes_test.pyd DLLs/_ssl.pyd DLLs/_hashlib.pyd DLLs/libssl-3-x64.dll DLLs/libcrypto-3-x64.dll
SP=Lib/site-packages; mkdir -p $SP
cp -r "$T/q/PyQt5" "$T"/q/*.dist-info $SP/
cd $SP/PyQt5
ls *.pyd | grep -v -E '^(QtCore|QtGui|QtWidgets|QtNetwork|QtSvg|sip\.cp313-win_amd64)\.pyd$' | xargs rm -f
rm -f *.pyi; rm -rf uic bindings
cd Qt5; rm -rf qml qsci
(cd bin; ls | grep -v -E '^(Qt5Core|Qt5Gui|Qt5Widgets|Qt5Network|Qt5Svg|msvcp140|msvcp140_1|msvcp140_2|concrt140|vcruntime140|vcruntime140_1)\.dll$' | xargs rm -f)
(cd plugins; ls | grep -v -E '^(platforms|styles|imageformats|iconengines)$' | xargs rm -rf
 rm -f platforms/q{minimal,offscreen,webgl}.dll
 cd imageformats; ls | grep -v -E '^q(ico|svg|jpeg|gif)\.dll$' | xargs rm -f)
(cd translations; ls | grep -v '^qt_zh_CN.qm$' | xargs rm -f)
cp "$W/sitecustomize.py" "$RT/Lib/site-packages/"
cd "$RT"
if command -v wine >/dev/null 2>&1; then
  export WINEPREFIX=${WINEPREFIX:-$WORK/win/wineprefix} WINEDEBUG=-all WINEARCH=win64 DISPLAY=${DISPLAY:-}
  wine python.exe -I -m compileall -q --invalidation-mode unchecked-hash -f Lib 2>&1 | cat || true
else
  echo "WARNING: wine not found - runtime built without precompiled .pyc" >&2
fi
rm -rf "$T/x" "$T/q"
echo "runtime done: $(du -sh "$RT" | cut -f1)"
