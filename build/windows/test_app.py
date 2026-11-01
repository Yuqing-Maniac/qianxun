# -*- coding: utf-8 -*-
# Stand-in app for launcher tests: shows a Chinese window, logs argv/env.
import sys, os
log = os.environ.get("QX_TEST_LOG")
info = "argv=%r\nQIANXUN_LAUNCHER=%r\nexe=%r\ncwd=%r\nfile=%r\n" % (
    sys.argv, os.environ.get("QIANXUN_LAUNCHER"), sys.executable, os.getcwd(), __file__)
if log:
    with open(log, "w", encoding="utf-8") as f: f.write(info)
from PyQt5 import QtWidgets, QtCore, QtNetwork
app = QtWidgets.QApplication(sys.argv)
w = QtWidgets.QWidget(); w.setWindowTitle("千寻 测试窗口")
lay = QtWidgets.QVBoxLayout(w)
lay.addWidget(QtWidgets.QLabel("千寻 文件秒搜 — 中文显示测试\n启动器：%s" % os.environ.get("QIANXUN_LAUNCHER")))
lay.addWidget(QtWidgets.QLineEdit("搜索：报告 ext:docx"))
w.resize(520, 200); w.show()
srv = QtNetwork.QLocalServer(); srv.removeServer("qx-test-%d" % os.getpid())
print("listen", srv.listen("qx-test-%d" % os.getpid()))
secs = int(os.environ.get("QX_TEST_SECS", "0"))
if secs: QtCore.QTimer.singleShot(secs * 1000, app.quit)
sys.exit(app.exec_())
