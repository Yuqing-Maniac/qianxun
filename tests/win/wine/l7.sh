vis() { xdotool search --onlyvisible --name '文件秒搜' 2>/dev/null | wc -l; }
t0=$(date +%s.%N); wine 'C:\测试 目录\QianXun-1.2.0-portable.exe'; for i in $(seq 1 80); do [ "$(vis)" -ge 1 ] && break; sleep 0.25; done; echo "portable vis=$(vis) after $(echo "$(date +%s.%N)-$t0"|bc) s"; sleep 2
import -window root $WINEPREFIX/drive_c/qxport/portable_run.png
