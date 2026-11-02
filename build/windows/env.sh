# source this: Wine test env for QianXun
_qx_here=$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)
QX_ROOT=$(cd "$_qx_here/../.." && pwd); QX_WORK=${QX_WORK:-$QX_ROOT/_work}; export QX_ROOT QX_WORK
export WINEPREFIX=$QX_WORK/wine/qianxun64 WINEDEBUG=-all WINEARCH=win64
export LANG=zh_CN.UTF-8 LC_ALL=C.UTF-8
# run GUI:  xvfb-run -a -s "-screen 0 1280x800x24" wine <exe> ...
