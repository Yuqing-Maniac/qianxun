# fcitx platform input-context plugin for the aarch64 PySide6 6.8.0.2 runtime

Plugin: runtime/aarch64/.../PySide6/Qt/plugins/platforminputcontexts/libfcitx5platforminputcontextplugin.so
(+ symlink libfcitxplatforminputcontextplugin.so). Metadata Keys: "fcitx", "fcitx5"; IID
org.qt-project.Qt.QPlatformInputContextFactoryInterface.5.1; Qt version 6.8.0.

Source: fcitx5-qt git master (0285a5d, qt6/ part), BUILD_ONLY_PLUGIN+BUILD_STATIC_PLUGIN layout done by hand
(dbusaddons sources compiled straight into the plugin; it contains the fcitx4 DBus path: fcitx4watcher /
fcitx4inputcontextproxy as well as the fcitx5 one -> works with fcitx4 and fcitx5). Qt 6.8.0 headers incl. private
QPA ones from git tag v6.8.0 of qtbase (syncqt run, moc built from same tree). Compiled with
aarch64-linux-gnu-g++-10 (-O2 -fvisibility=hidden), linked against the bundle's Qt6 libs; empty stub libs for
libxkbcommon/libxcb at link time only. RUNPATH $ORIGIN/../../lib.

NEEDED: libxkbcommon.so.0, libxcb.so.1, libQt6Widgets/Gui/DBus/Core.so.6, libstdc++.so.6, libgcc_s.so.1, libc.so.6.
Max symbol versions: GLIBC_2.17, GLIBCXX_3.4.20, CXXABI_1.3.9.
Test: QPluginLoader.load() under qemu-aarch64 with the bundle -> True, metadata OK. A full QGuiApplication with
QT_IM_MODULE=fcitx could not run under qemu (libdbus is a trapping stub); not tested against a live fcitx daemon.
Use: QT_IM_MODULE=fcitx (fcitx4 or fcitx5 running). Needs the C++ ABI of Qt 6.8.x exactly (private API).
