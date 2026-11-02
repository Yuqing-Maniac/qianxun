L='C:\qxport\QianXun\QianXun.exe'
vis() { xdotool search --onlyvisible --name '文件秒搜' 2>/dev/null | wc -l; }
wine "$L"; sleep 6; echo "procs=$(ps aux | grep -c '[p]ythonw.exe') vis=$(vis)"
wine 'C:\qxport\QianXun\runtime\python.exe' 'C:\qxport\sock.py'; cat $WINEPREFIX/drive_c/qxport/sock.txt
wine "$L" --toggle; sleep 5; echo "after toggle procs=$(ps aux | grep -c '[p]ythonw.exe') vis=$(vis)"
xdotool search --onlyvisible --name '文件秒搜' windowactivate --sync 2>&1 | head -2; sleep 1
wine "$L" --toggle; sleep 3; echo "after activate+toggle vis=$(vis)"
wine "$L" --toggle; sleep 3; echo "after 3rd toggle vis=$(vis)"
