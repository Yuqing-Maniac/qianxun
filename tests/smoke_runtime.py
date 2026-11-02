import sys, os
from PyQt5 import QtCore, QtGui, QtWidgets, QtNetwork
from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR, QTimer
try:
    from PyQt5 import QtDBus, QtSvg
    extra="DBus+Svg ok"
except Exception as e: extra="EXTRA FAIL %r"%e
app = QtWidgets.QApplication(sys.argv)
w = QtWidgets.QWidget(); w.setWindowTitle("t"); lay=QtWidgets.QVBoxLayout(w)
lay.addWidget(QtWidgets.QLabel("你好 hello")); lay.addWidget(QtWidgets.QPushButton("btn"))
w.show()
# local server/socket
name="smoke_%d"%os.getpid()
srv=QtNetwork.QLocalServer(); QtNetwork.QLocalServer.removeServer(name); ok=srv.listen(name)
sock=QtNetwork.QLocalSocket(); sock.connectToServer(name); conn=sock.waitForConnected(1000)
img=QtGui.QImage(20,20,QtGui.QImage.Format_ARGB32); img.fill(0xff00ff00)
print("Qt",QT_VERSION_STR,"PyQt",PYQT_VERSION_STR,"platform",app.platformName(),"server",ok,"conn",conn,extra,
      "ctxs",os.environ.get("QT_IM_MODULE"),"imgfmts",sorted(bytes(f).decode() for f in QtGui.QImageReader.supportedImageFormats())[:12])
print("exe", sys.executable, "libpaths", QtCore.QCoreApplication.libraryPaths())
QTimer.singleShot(500, app.quit)
rc=app.exec_(); print("exit",rc); sys.exit(rc)
