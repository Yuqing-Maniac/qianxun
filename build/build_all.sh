#!/bin/bash
# One-shot: build every QianXun release artifact into $WORK/dist (default <repo>/_work/dist).
#   1. runtimes (Linux x86_64/aarch64 + system-Qt shim, Windows x64)   build/fetch_all.sh
#   2. Kylin/Linux packages: deb + tar.gz + zip (x86_64, aarch64)       build/linux/build_release.sh
#   3. Windows 10/11 (Python/Qt): zip, QianXun.exe beside QianXun/      build/windows/build_win.sh
#   4. Windows 7-11 native (C++/Win32): x64 and x86 zips                build/windows/package_native.sh
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
# This release's sums are the two portable archives that go on the release page.
# build_release.sh still builds the Kylin x86_64 archives, and package_native.sh
# still builds the Windows 7 zips. They are not in this checksum file.
cd "$WORK/dist"
files="qianxun-${VER}-kylin-aarch64.tar.gz qianxun-${VER}-windows-x64.zip"
sha256sum $files > SHA256SUMS.txt
cat SHA256SUMS.txt
