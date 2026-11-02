#!/bin/bash
# fetch_all.sh - build every bundled runtime from scratch (Linux x86_64/aarch64/syspyqt + Windows x64).
# Output goes to ${QX_WORK:-<repo>/_work}. See docs/BUILD_RUNTIMES.md.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
bash "$HERE/linux/build_runtime_linux.sh"
bash "$HERE/windows/build_runtime.sh"
