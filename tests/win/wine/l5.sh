D=$WINEPREFIX/drive_c/qxport; DD=$WINEPREFIX/dosdevices
rm -f $D/drive.flag* $DD/x:
wine 'C:\qxport\QianXun\runtime\pythonw.exe' 'C:\qxport\drive.py' &
P=$!
while [ ! -f $D/drive.flag1 ]; do sleep 0.2; done; ln -s ${QX_WORK:-/tmp}/xdrive $DD/x:
while [ ! -f $D/drive.flag2 ]; do sleep 0.2; done; rm -f $DD/x:
wait $P; cat $D/drive.txt
