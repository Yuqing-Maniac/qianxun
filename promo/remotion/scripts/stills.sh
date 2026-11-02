#!/bin/bash
# usage: stills.sh outdir frame1 frame2 ...
cd /home/claude/video/q/rm
out=$1; shift; mkdir -p $out
for f in "$@"; do npx remotion still src/index.ts Main $out/f$f.png --frame=$f --browser-executable=/tmp/chromium --log=error --scale=0.5 >/dev/null 2>&1 || echo "fail $f"; done
ls $out
