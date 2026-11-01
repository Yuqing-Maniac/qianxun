L='C:\qxport\QianXun\QianXun.exe'
vis() { xdotool search --onlyvisible --name '文件秒搜' 2>/dev/null | wc -l; }
wine 'C:\qxport\QianXun\runtime\python.exe' 'C:\qxport\integ.py'; cat $WINEPREFIX/drive_c/qxport/integ.txt
wine "$L"; sleep 6; echo "vis=$(vis)"
wine "$L" --toggle; sleep 4; echo "after toggle vis=$(vis)"
xdotool key ctrl+alt+f; sleep 2; echo "after hotkey vis=$(vis)"
xdotool search --onlyvisible --name '文件秒搜' windowactivate --sync >/dev/null 2>&1; xdotool key ctrl+alt+f; sleep 2; echo "after hotkey2 vis=$(vis)"
