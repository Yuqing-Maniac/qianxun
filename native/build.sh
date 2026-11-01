#!/bin/bash
# 千寻 QianXun 原生 Windows 版构建脚本：mingw-w64 交叉编译 x64 / x86 两个单文件 exe（静态链接，零运行库依赖）
set -e
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
cd "$(dirname "$SELF")"
mkdir -p out obj
SRC="src/main.cpp src/cli.cpp src/ui_main.cpp src/ui_dialogs.cpp src/shell.cpp src/engine.cpp src/config.cpp \
     src/plat_win.cpp src/index.cpp src/query.cpp src/search.cpp src/textutil.cpp"
DEFS="-DUNICODE -D_UNICODE -D_WIN32_WINNT=0x0601 -DWINVER=0x0601 -DNTDDI_VERSION=0x06010000 -DPSAPI_VERSION=2"
CXXFLAGS="-std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter -Wno-cast-function-type -Wno-missing-field-initializers $DEFS"
LIBS="-lcomctl32 -lshell32 -lole32 -luuid -lshlwapi -ladvapi32 -luxtheme -lgdi32 -luser32 -lkernel32"
build() {  # arch triple, output, extra flags
    local T=$1 OUT=$2 EXTRA=$3 LD=$4
    local CXX=$T-g++-win32
    local O=obj/$T; mkdir -p $O
    $T-windres -c 65001 -I res res/qianxun.rc -O coff -o $O/res.o
    local objs=""
    for f in $SRC; do
        local o=$O/$(basename ${f%.cpp}).o
        if [ ! -f $o ] || [ $f -nt $o ] || [ -n "$(find src -name '*.h' -newer $o 2>/dev/null)" ]; then
            $CXX $CXXFLAGS $EXTRA -c $f -o $o &
        fi
        objs="$objs $o"
    done
    wait
    $CXX -O2 -s -static -static-libgcc -static-libstdc++ -municode -mwindows $EXTRA $objs $O/res.o -o $OUT $LIBS $LD
    echo "built $OUT ($(stat -c %s $OUT) bytes)"
}
case "${1:-all}" in
  x64) build x86_64-w64-mingw32 out/QianXun-x64.exe "" "-Wl,--stack,8388608 -Wl,--dynamicbase -Wl,--nxcompat -Wl,--high-entropy-va" ;;
  x86) build i686-w64-mingw32 out/QianXun-x86.exe "-msse2 -mfpmath=sse -mstackrealign" "-Wl,--stack,4194304 -Wl,--dynamicbase -Wl,--nxcompat -Wl,--large-address-aware" ;;
  all) "$SELF" x64 && "$SELF" x86 ;;
esac
