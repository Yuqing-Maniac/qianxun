L='C:\qxport\QianXun\QianXun.exe'
vis() { xdotool search --onlyvisible --name '文件秒搜' 2>/dev/null | wc -l; }
wine "$L"; sleep 6; echo "vis=$(vis)"
W=$(xdotool search --onlyvisible --name '文件秒搜' | head -1); xdotool windowfocus --sync $W 2>/dev/null; xdotool mousemove 500 300 click 1; sleep 1
xdotool key ctrl+alt+f; sleep 2; echo "focused+hotkey vis=$(vis)"
xdotool key ctrl+alt+f; sleep 2; echo "hotkey again (no wine focus) vis=$(vis)"
