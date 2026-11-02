cd /tmp/w/pb
S=/tmp/w/fcitx5-qt/qt6; Q=/tmp/w/qtb2; QI=$Q/include
INC="-I$S/dbusaddons -I$S/platforminputcontext -I/tmp/w/fcitx5-qt/common -Igen -I$QI -I$QI/QtCore -I$QI/QtGui -I$QI/QtDBus -I$QI/QtWidgets -I$QI/QtCore/6.8.0 -I$QI/QtCore/6.8.0/QtCore -I$QI/QtGui/6.8.0 -I$QI/QtGui/6.8.0/QtGui -I$QI/QtDBus/6.8.0 -I$QI/QtDBus/6.8.0/QtDBus"
DEF="-DQT_NO_KEYWORDS_UNUSED -DQT_PLUGIN -DQT_GUI_LIB -DQT_CORE_LIB -DQT_DBUS_LIB -DQT_WIDGETS_LIB -DENABLE_X11 -DFCITX5_QT_WITH_FCITX_NAME -DFCITX_PLUGIN_DATA_FILE_PATH=\"/tmp/w/pb/gen/fcitx5.json\" -DQT_NO_DEBUG"
c=$1; o=obj/$(basename $c).o
[ -s $o ] && exit 0
aarch64-linux-gnu-g++-10 -std=gnu++17 -O1 -fPIC -fvisibility=hidden -w $DEF $INC -c $c -o $o || { rm -f $o; echo FAIL $c; }
