#!/bin/bash
# One-shot: build every QianXun release artifact into $WORK/dist (default <repo>/_work/dist).
#   1. runtimes (Linux x86_64/aarch64 + system-Qt shim, Windows x64)   build/fetch_all.sh
#   2. Kylin/Linux packages: deb + tar.gz + zip (x86_64, aarch64)       build/linux/build_release.sh
#   3. Windows 10/11 (Python/Qt): zip + single-file portable exe        build/windows/build_win.sh
#   4. Windows 7-11 native (C++/Win32): x64 + x86 exe + zip             build/windows/package_native.sh
#   5. incremental noop zip (from_version is the VERSION line)        app/qianxun.py --pack-incremental
# Written 2026-10-22 for the repository.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); WORK=${QX_WORK:-$ROOT/_work}; export QX_WORK=$WORK
bash "$ROOT/build/fetch_all.sh"
sh   "$ROOT/build/linux/build_release.sh"
bash "$ROOT/build/windows/build_win.sh"
bash "$ROOT/build/windows/package_native.sh"
VER=$(sed -n "s/^VERSION = '\(.*\)'$/\1/p" "$ROOT/app/qianxun.py")
[ -n "$VER" ] || { echo "VERSION not found in app/qianxun.py" >&2; exit 1; }
mkdir -p "$WORK/dist"
python3 "$ROOT/app/qianxun.py" --pack-incremental "$VER" "$ROOT" "$WORK/dist/qianxun-${VER}-incremental.zip"
cd "$WORK/dist" && sha256sum $(ls *.deb *.tar.gz *.zip *.exe) > SHA256SUMS.txt && cat SHA256SUMS.txt
