#!/bin/bash
# Create the 64-bit Wine prefix used to test the Python/Qt Windows build ($WORK/wine/qianxun64):
# wineboot + Noto CJK font substitutes so Chinese UI renders. Written 2026-10-22 (the original prefix
# was set up by hand with the same font registry file).
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/env.sh"
mkdir -p "$WINEPREFIX"
xvfb-run -a wineboot -i >/dev/null 2>&1 || true
mkdir -p "$WINEPREFIX/drive_c/windows/Fonts"
cp -n /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc "$WINEPREFIX/drive_c/windows/Fonts/" || true
xvfb-run -a wine regedit /S "$(dirname "$0")/fonts.reg" >/dev/null 2>&1
wineserver -w
echo "prefix ready: $WINEPREFIX"
