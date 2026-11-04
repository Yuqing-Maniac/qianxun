vis() { xdotool search --onlyvisible --name '文件秒搜' 2>/dev/null | wc -l; }
wine 'C:\测试 目录\QianXun\QianXun.exe'; for i in $(seq 1 40); do [ "$(vis)" -ge 1 ] && break; sleep 0.25; done; echo "zip build vis=$(vis)"; sleep 3
import -window root $WINEPREFIX/drive_c/qxport/zip_run.png
wine 'C:\测试 目录\QianXun-1.2.1-portable.exe' --toggle; sleep 4; echo "portable --toggle to running instance: vis=$(vis) procs=$(ps aux | grep -c '[p]ythonw.exe')"
