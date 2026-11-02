#!/bin/bash
# usage: setup_prefix.sh 64|32  — configure a Wine prefix: Win7 mode + CJK font substitutes
T=$(cd "$(dirname "$0")" && pwd)
source $T/env$1.sh
mkdir -p $WINEPREFIX/drive_c/windows/Fonts
cp -n /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc $WINEPREFIX/drive_c/windows/Fonts/
xvfb-run -a wine reg add 'HKCU\Software\Wine' /v Version /t REG_SZ /d win7 /f >/dev/null 2>&1
xvfb-run -a wine regedit /S $T/fonts.reg >/dev/null 2>&1
wineserver -w
echo "prefix $1: $(xvfb-run -a wine reg query 'HKCU\Software\Wine' /v Version 2>&1 | grep -i version)"
