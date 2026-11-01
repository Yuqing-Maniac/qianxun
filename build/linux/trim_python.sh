#!/bin/sh
# usage: trim_python.sh <runtime_dir>   -- strips stdlib baggage
R="$1"; L=$(echo $R/lib/python3.*)
rm -rf "$R/include" "$R/share" "$R/bin/"*-config "$R/licenses" 
cd "$L" || exit 1
rm -rf test tests idlelib tkinter turtledemo turtle.py lib2to3 ensurepip pydoc_data distutils/tests config-3.* _pyrepl
rm -rf unittest/test sqlite3/test ctypes/test
rm -f _sysconfigdata_*.py.orig
find "$R" -name '*.a' -delete
find "$R" -name __pycache__ -prune -exec rm -rf {} +
