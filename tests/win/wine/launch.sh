#!/bin/bash
# run inside xvfb-run
O=$WINEPREFIX/drive_c/qxport
L='C:\qxport\QianXun\QianXun.exe'
vis() { xwininfo -root -tree 2>/dev/null | grep -c '"千寻 - 文件秒搜"' ; }
mapped() { xdotool search --onlyvisible --name '文件秒搜' 2>/dev/null | wc -l; }
t0=$(date +%s.%N); wine "$L"; echo "launcher returned after $(echo "$(date +%s.%N)-$t0" | bc) s rc=$?"
for i in $(seq 1 60); do [ "$(mapped)" -ge 1 ] && break; sleep 0.25; done
echo "window viewable after $(echo "$(date +%s.%N)-$t0" | bc) s"
sleep 4; import -window root $O/l1.png
echo "procs: $(ps aux | grep -c '[p]ythonw.exe')"
wine "$L" --toggle; sleep 2; echo "after toggle viewable=$(mapped)"; import -window root $O/l2.png
wine "$L" --toggle; sleep 2; echo "after 2nd toggle viewable=$(mapped)"
wine "$L"; sleep 2; echo "after plain 2nd launch viewable=$(mapped) procs=$(ps aux | grep -c '[p]ythonw.exe')"
import -window root $O/l3.png
