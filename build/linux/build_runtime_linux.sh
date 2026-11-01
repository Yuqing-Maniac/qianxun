#!/bin/bash
# build_runtime_linux.sh - rebuild the bundled Linux runtimes of QianXun from scratch.
#
# written 2026-10-22 to reproduce the hand-assembled runtimes; verified by diff against the originals
# (see docs/BUILD_RUNTIMES.md for the verification result and the known non-reproducible parts).
#
# Output (all under WORK=${QX_WORK:-<repo>/_work}, gitignored):
#   $WORK/dl                 download cache (sha256-pinned, re-verified on every run)
#   $WORK/runtime/x86_64     CPython 3.13.15 (pbs) + PyQt5 5.15.11 / Qt 5.15.18 (+ fcitx Qt5 input plugin)
#   $WORK/runtime/aarch64    CPython 3.13.15 (pbs) + PySide6 6.8.0.2 (+ prebuilt libxcb-cursor / fcitx5 plugin)
#   $WORK/syspyqt/x86_64     "system-Qt mode" PyQt5 5.14.1 extension modules for system python3.8 (focal debs)
#
# Usage: build/linux/build_runtime_linux.sh [x86_64] [aarch64] [syspyqt]     (default: all three)
# Idempotent: every target directory is deleted and rebuilt from the (cached) downloads.
#
# Prerequisites on a fresh Ubuntu 24.04 x86_64 machine (checked by check_prereqs below):
#   sudo apt-get install -y curl ca-certificates tar gzip unzip binutils dpkg python3 coreutils findutils
#   (binutils: readelf, used by trim_qt5.py / trim_pyside6.py; dpkg: dpkg-deb; python3: runs the trim scripts)
# Network needed: registry.npmjs.org, files.pythonhosted.org, archive.ubuntu.com (http). No GitHub.
set -eu

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
WORK=${QX_WORK:-$ROOT/_work}
LIN=$ROOT/build/linux
DL=$WORK/dl
mkdir -p "$DL"

check_prereqs() {
    miss=""
    for c in curl tar gzip unzip readelf dpkg-deb python3 sha256sum find cp; do
        command -v "$c" >/dev/null 2>&1 || miss="$miss $c"
    done
    if [ -n "$miss" ]; then
        echo "missing tools:$miss" >&2
        echo "install with: sudo apt-get install -y curl ca-certificates tar gzip unzip binutils dpkg python3 coreutils findutils" >&2
        exit 1
    fi
}

# fetch NAME URL SHA256  -> $DL/NAME (cached; verified before and after download)
fetch() {
    name=$1; url=$2; sha=$3; f=$DL/$name
    if [ -f "$f" ] && [ "$(sha256sum "$f" | cut -d' ' -f1)" = "$sha" ]; then
        echo "[cached] $name  sha256=$sha  $(wc -c <"$f") bytes"
        return 0
    fi
    echo "[download] $name"
    echo "           $url"
    curl -fsSL --retry 3 -o "$f.part" "$url"
    got=$(sha256sum "$f.part" | cut -d' ' -f1)
    if [ "$got" != "$sha" ]; then
        echo "SHA256 MISMATCH for $name: expected $sha got $got" >&2
        rm -f "$f.part"; exit 1
    fi
    mv "$f.part" "$f"
    echo "           sha256=$sha  $(wc -c <"$f") bytes OK"
}

PYPI=https://files.pythonhosted.org/packages
UBU=http://archive.ubuntu.com/ubuntu

fetch_inputs_x86_64() {
    fetch cli-linux-x64-0.1.0-alpha.7.tgz https://registry.npmjs.org/@rowstile/cli-linux-x64/-/cli-linux-x64-0.1.0-alpha.7.tgz \
        c9c61263a7bdd2ee71d05f6b2fa98087c96b8dccfbc2f17529afca07666017de
    fetch PyQt5-5.15.11-cp38-abi3-manylinux_2_17_x86_64.whl \
        $PYPI/b4/8c/4065950f9d013c4b2e588fe33cf04e564c2322842d84dbcbce5ba1dc28b0/PyQt5-5.15.11-cp38-abi3-manylinux_2_17_x86_64.whl \
        cd672a6738d1ae33ef7d9efa8e6cb0a1525ecf53ec86da80a9e1b6ec38c8d0f1
    fetch pyqt5_qt5-5.15.18-py3-none-manylinux2014_x86_64.whl \
        $PYPI/9a/46/ffe177f99f897a59dc237a20059020427bd2d3853d713992b8081933ddfe/pyqt5_qt5-5.15.18-py3-none-manylinux2014_x86_64.whl \
        bf2457e6371969736b4f660a0c153258fa03dbc6a181348218e6f05421682af7
    fetch pyqt5_sip-12.20.0-cp313-cp313-manylinux_2_5_x86_64.manylinux1_x86_64.whl \
        $PYPI/53/a2/cfc4871908b2829f5f1546a1490ee4d5cea0843e751661ded53c2ca9990f/pyqt5_sip-12.20.0-cp313-cp313-manylinux_2_5_x86_64.manylinux1_x86_64.whl \
        ed838dcd21d8d01598b48c4c5c3a77b671f50ba8bbde1223fe25a1727d88bbec
    fetch fcitx-frontend-qt5_1.2.4-1build2_amd64.deb \
        $UBU/pool/universe/f/fcitx-qt5/fcitx-frontend-qt5_1.2.4-1build2_amd64.deb \
        1ccd8383fc2dc369cdba8f20f13c1f33717488eb52015814ca37104f80d0e1d1
}

fetch_inputs_aarch64() {
    fetch cli-linux-arm64-0.1.0-alpha.7.tgz https://registry.npmjs.org/@rowstile/cli-linux-arm64/-/cli-linux-arm64-0.1.0-alpha.7.tgz \
        8fd0b497905395a8d3f26dc6d26fd113480aa7dcd49d67973ea5af80070c5191
    fetch PySide6_Essentials-6.8.0.2-cp39-abi3-manylinux_2_31_aarch64.whl \
        $PYPI/6f/ee/9023d3851054db24c28312744de8bdb80dcf8de20bd583b6520da416484f/PySide6_Essentials-6.8.0.2-cp39-abi3-manylinux_2_31_aarch64.whl \
        cf490145d18812a6cff48b0b0afb0bfaf7066744bfbd09eb071c3323f1d6d00d
    fetch shiboken6-6.8.0.2-cp39-abi3-manylinux_2_31_aarch64.whl \
        $PYPI/13/cd/e9a6d0aa8794f777627a9fb3cffed0ac8449881b33e2325b5bcff10c36bc/shiboken6-6.8.0.2-cp39-abi3-manylinux_2_31_aarch64.whl \
        1aaa8b7f9138818322ef029b2c487d1c6e00dc3f53084e62e1d11bdea47e47c2
}

fetch_inputs_syspyqt() {
    fetch python3-pyqt5_5.14.1+dfsg-3build1_amd64.deb $UBU/pool/universe/p/pyqt5/python3-pyqt5_5.14.1+dfsg-3build1_amd64.deb \
        4efdb25d9e10879973350881531142da2540f76da09baa70d2d0f61e3d1177fc
    fetch python3-pyqt5.qtsvg_5.14.1+dfsg-3build1_amd64.deb $UBU/pool/universe/p/pyqt5/python3-pyqt5.qtsvg_5.14.1+dfsg-3build1_amd64.deb \
        b01265ffe348aec930fc5d3b6769fa2cee5a2d673003376db135701ee1b40788
    fetch python3-sip_4.19.21+dfsg-1build1_amd64.deb $UBU/pool/universe/s/sip4/python3-sip_4.19.21+dfsg-1build1_amd64.deb \
        9314b3b008eea8e89ffbd73616b4482ee9b799a04b2881c54e7e0a51fb08ab9e
}

# python_base NPMTGZ OUTDIR : extract pbs CPython from the npm package, keep bin/python3.13 + lib/python3.13, trim stdlib
python_base() {
    tgz=$1; out=$2
    tmp=$(mktemp -d "$WORK/.tmp.XXXXXX")
    tar -xzf "$tgz" -C "$tmp"
    rm -rf "$out"; mkdir -p "$out/bin" "$out/lib"
    cp -p  "$tmp/package/python/bin/python3.13" "$out/bin/python3.13"
    cp -rp "$tmp/package/python/lib/python3.13" "$out/lib/python3.13"
    rm -rf "$tmp"
    sh "$LIN/trim_python.sh" "$out"
}

# unwheel WHEEL... : unzip wheels into the site-packages dir given by $SP
unwheel() { for w in "$@"; do unzip -q -o "$DL/$w" -d "$SP"; done; }

build_x86_64() {
    echo "=== runtime/x86_64"
    fetch_inputs_x86_64
    R=$WORK/runtime/x86_64
    python_base "$DL/cli-linux-x64-0.1.0-alpha.7.tgz" "$R"
    SP=$R/lib/python3.13/site-packages; mkdir -p "$SP"
    unwheel PyQt5-5.15.11-cp38-abi3-manylinux_2_17_x86_64.whl pyqt5_qt5-5.15.18-py3-none-manylinux2014_x86_64.whl \
            pyqt5_sip-12.20.0-cp313-cp313-manylinux_2_5_x86_64.manylinux1_x86_64.whl
    python3 -I "$LIN/trim_qt5.py" "$SP" >/dev/null
    rm -rf "$SP/PyQt5/uic/widget-plugins"      # uic helpers for Qt modules that are not shipped
    find "$SP" -type d -empty -delete          # e.g. the empty pyqt5_sip.libs of the sip wheel
    # fcitx (fcitx4/5 DBus frontend) Qt5 input-context plugin from Ubuntu focal (built for Qt 5.12, loads in 5.15)
    t=$(mktemp -d "$WORK/.tmp.XXXXXX")
    dpkg-deb -x "$DL/fcitx-frontend-qt5_1.2.4-1build2_amd64.deb" "$t"
    cp -p "$t/usr/lib/x86_64-linux-gnu/qt5/plugins/platforminputcontexts/libfcitxplatforminputcontextplugin.so" \
          "$SP/PyQt5/Qt5/plugins/platforminputcontexts/"
    chmod 755 "$SP/PyQt5/Qt5/plugins/platforminputcontexts/libfcitxplatforminputcontextplugin.so"
    rm -rf "$t"
    cp "$LIN/hx_qtboot.py" "$SP/hx_qtboot.py"
    printf 'import hx_qtboot\n' > "$SP/hx_qtboot.pth"
    find "$R" -name __pycache__ -prune -exec rm -rf {} +
    echo "runtime/x86_64 done: $(du -sh "$R" | cut -f1)"
}

build_aarch64() {
    echo "=== runtime/aarch64"
    fetch_inputs_aarch64
    R=$WORK/runtime/aarch64
    python_base "$DL/cli-linux-arm64-0.1.0-alpha.7.tgz" "$R"
    SP=$R/lib/python3.13/site-packages; mkdir -p "$SP"
    unwheel PySide6_Essentials-6.8.0.2-cp39-abi3-manylinux_2_31_aarch64.whl shiboken6-6.8.0.2-cp39-abi3-manylinux_2_31_aarch64.whl
    python3 -I "$LIN/trim_pyside6.py" "$SP" >/dev/null
    rm -f "$SP/shiboken6/Shiboken.pyi"
    # hand-compiled prebuilt binaries (not reproducible here, see docs/FCITX_AARCH64.md)
    cp -p "$LIN/prebuilt/aarch64/libxcb-cursor.so.0" "$SP/PySide6/Qt/lib/"
    cp -p "$LIN/prebuilt/aarch64/libfcitx5platforminputcontextplugin.so" "$SP/PySide6/Qt/plugins/platforminputcontexts/"
    mkdir -p "$R/licenses"
    cat > "$R/licenses/xcb-util-cursor.COPYING" <<'LIC'
Copyright © 2013 Michael Stapelberg

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Except as contained in this notice, the names of the authors or their
institutions shall not be used in advertising or otherwise to promote the
sale, use or other dealings in this Software without prior written
authorization from the authors.
LIC
    cp "$LIN/hx_qtboot6.py" "$SP/hx_qtboot.py"
    printf 'import hx_qtboot\n' > "$SP/hx_qtboot.pth"
    find "$R" -name __pycache__ -prune -exec rm -rf {} +
    echo "runtime/aarch64 done: $(du -sh "$R" | cut -f1)"
}

build_syspyqt() {
    echo "=== syspyqt/x86_64"
    fetch_inputs_syspyqt
    R=$WORK/syspyqt/x86_64
    rm -rf "$R"; mkdir -p "$R/PyQt5"
    t=$(mktemp -d "$WORK/.tmp.XXXXXX")
    for d in python3-pyqt5_5.14.1+dfsg-3build1_amd64.deb python3-pyqt5.qtsvg_5.14.1+dfsg-3build1_amd64.deb python3-sip_4.19.21+dfsg-1build1_amd64.deb; do
        dpkg-deb -x "$DL/$d" "$t"
    done
    D=$t/usr/lib/python3/dist-packages
    cp -p "$D/PyQt5/__init__.py" "$R/PyQt5/"
    for m in Core Gui Widgets Network DBus Svg; do
        cp -p "$D/PyQt5/Qt$m.cpython-38-x86_64-linux-gnu.so" "$R/PyQt5/"
    done
    cp -p "$D/sip.cpython-38-x86_64-linux-gnu.so" "$R/"
    rm -rf "$t"
    echo "syspyqt/x86_64 done: $(du -sh "$R" | cut -f1)"
}

check_prereqs
[ $# -gt 0 ] || set -- x86_64 aarch64 syspyqt
mkdir -p "$WORK"
for t in "$@"; do
    case $t in
        x86_64) build_x86_64;; aarch64) build_aarch64;; syspyqt) build_syspyqt;;
        *) echo "unknown target $t" >&2; exit 1;;
    esac
done
echo "all done; WORK=$WORK"
