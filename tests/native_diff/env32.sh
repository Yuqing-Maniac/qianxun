# source this: 32-bit Wine (Win7 mode) test env for native QianXun
export TESTDIR=$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)
QX_ROOT=$(cd "$TESTDIR/../.." && pwd); QX_WORK=${QX_WORK:-$QX_ROOT/_work}; export QX_ROOT QX_WORK
export WINEPREFIX=$QX_WORK/wine/native32 WINEARCH=win32 WINEDEBUG=-all
export TZ=Asia/Shanghai LANG=zh_CN.UTF-8 LC_ALL=C.UTF-8
export WINEDLLOVERRIDES="mscoree,mshtml="
export QX_ARCH=32
