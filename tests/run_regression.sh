#!/bin/sh
# Linux regression suite for QianXun. Usage: tests/run_regression.sh [outdir]   (default /tmp/qianxun-tests/reg)
T=$(cd "$(dirname "$0")" && pwd)
O=${1:-/tmp/qianxun-tests/reg}
mkdir -p /tmp/qianxun-tests
mkdir -p "$O"
cd "$T/qa"
run() { n=$1; shift; echo "== $n"; ( "$@" ) > "$O/$n.log" 2>&1; echo "rc=$?" >> "$O/$n.log"; tail -3 "$O/$n.log"; }
run engine timeout 600 python3 test_engine.py
run search timeout 600 python3 test_search.py
run pathref timeout 300 python3 test_pathref.py
for B in PyQt5 PySide6; do
  run race_$B env QT_QPA_PLATFORM=offscreen QIANXUN_QT=$B timeout 300 python3 test_race.py
  run gui_$B env QT_QPA_PLATFORM=offscreen QIANXUN_QT=$B timeout 300 python3 test_gui.py
  run churn_$B env QT_QPA_PLATFORM=offscreen QIANXUN_QT=$B timeout 300 python3 test_churn.py
done
run perf env QT_QPA_PLATFORM=offscreen timeout 900 python3 test_perf.py 300000
run instance timeout 120 xvfb-run -a sh test_instance.sh
run t1 timeout 300 python3 "$T/smoke/t1.py"
cd "$T/smoke"
run t4_PyQt5 env QT_QPA_PLATFORM=offscreen timeout 300 python3 -u t4.py PyQt5
run t4_PySide6 env QT_QPA_PLATFORM=offscreen timeout 300 python3 -u t4.py PySide6
if [ -d "$T/win" ]; then
  for t in "$T"/win/test_*.py; do [ -f "$t" ] && run win_$(basename $t .py) timeout 300 python3 "$t"; done
fi
echo "--- suspicious:"; grep -lE "^FAIL |Traceback|^GUI FAILED: [^n]|FAILED: [^n]|TOTAL FAIL [1-9]| [1-9][0-9]* mismatches" "$O"/*.log
