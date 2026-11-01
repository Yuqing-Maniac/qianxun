set -e
cd /tmp/w/pb
S=/tmp/w/fcitx5-qt/qt6; Q=/tmp/w/qtb2; QI=$Q/include
CXX=aarch64-linux-gnu-g++-10
INC="-I$S/dbusaddons -I$S/platforminputcontext -I/tmp/w/fcitx5-qt/common -Igen -I$QI -I$QI/QtCore -I$QI/QtGui -I$QI/QtDBus -I$QI/QtWidgets -I$QI/QtCore/6.8.0 -I$QI/QtCore/6.8.0/QtCore -I$QI/QtGui/6.8.0 -I$QI/QtGui/6.8.0/QtGui -I$QI/QtDBus/6.8.0 -I$QI/QtDBus/6.8.0/QtDBus"
DEF="-DQT_NO_KEYWORDS_UNUSED -DQT_PLUGIN -DQT_GUI_LIB -DQT_CORE_LIB -DQT_DBUS_LIB -DQT_WIDGETS_LIB -DENABLE_X11 -DFCITX5_QT_WITH_FCITX_NAME -DFCITX_PLUGIN_DATA_FILE_PATH=\"/tmp/w/pb/gen/fcitx5.json\" -DQT_NO_DEBUG"
FL="-std=gnu++17 -O2 -fPIC -fvisibility=hidden -w"
SRCS="$S/dbusaddons/fcitxqtwatcher.cpp $S/dbusaddons/fcitxqtdbustypes.cpp $S/dbusaddons/fcitxqtinputcontextproxy.cpp $S/dbusaddons/fcitxqtinputcontextproxyimpl.cpp $S/dbusaddons/fcitxqtinputmethodproxy.cpp $S/dbusaddons/fcitxqtcontrollerproxy.cpp"
for f in fcitx4watcher fcitx4inputcontextproxy fcitx4inputcontextproxyimpl fcitx4inputmethodproxy hybridinputcontext qfcitxplatforminputcontext fcitxcandidatewindow fcitxtheme font qtkey main; do SRCS="$SRCS $S/platforminputcontext/$f.cpp"; done
rm -f obj/* ; MOCS=""
for h in $S/dbusaddons/*.h $S/platforminputcontext/*.h; do
  if grep -q "Q_OBJECT\|Q_GADGET" $h; then b=$(basename $h .h); $Q/libexec/moc $DEF $INC $h -o gen/moc_$b.cpp; MOCS="$MOCS gen/moc_$b.cpp"; fi
done
for c in $SRCS; do
  for m in $(grep -o '#include "[a-z0-9_]*\.moc"' $c | sed 's/.*"\(.*\)".*/\1/'); do $Q/libexec/moc $DEF $INC $c -o gen/$m; done
done
ls gen
for c in $SRCS $MOCS; do echo CC $c; $CXX $FL $DEF $INC -I$S/dbusaddons -I$S/platforminputcontext -c $c -o obj/$(basename $c).o & done; wait
