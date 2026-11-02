#!/bin/bash
# usage: wine_run.sh [-s WxH] <command...>   e.g.  wine_run.sh wine runtime/pythonw.exe -X utf8 app.py
# Runs the command under Xvfb with the QianXun Wine prefix (CJK font substitutes pre-registered).
source "$(cd "$(dirname "$0")" && pwd)/env.sh"
exec xvfb-run -a -s "-screen 0 1280x800x24" "$@"
