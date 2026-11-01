#!/bin/bash
# Differential test of the native QianXun --cli against the Python oracle.
#   run_diff.sh [exe] [extra run_diff.py args]      default exe: <repo>/native/out/QianXun-x64.exe
#   run_diff.sh <repo>/native/out/QianXun-x86.exe          (32-bit Wine prefix, Win7 mode)
#   run_diff.sh --runner "python3 fake_qianxun.py" --tag stub          (harness self-test with the Python stand-in)
# Output: report/<tag>/summary.md, results.json, diffs/*.diff
cd "$(dirname "$0")"
EXE=$(cd ../.. && pwd)/native/out/QianXun-x64.exe
if [ -n "$1" ] && [ "${1#-}" = "$1" ]; then EXE="$1"; shift; fi
exec python3 run_diff.py --exe "$EXE" "$@"
