import sys, os, time, json
B=sys.argv[1]; os.environ['QIANXUN_QT']=B
os.environ['XDG_CACHE_HOME']='/tmp/qianxun-tests/c4'+B; os.environ['XDG_CONFIG_HOME']='/tmp/qianxun-tests/f4'+B
os.makedirs(os.environ['XDG_CONFIG_HOME']+'/qianxun', exist_ok=True)
json.dump({'roots':['/tmp/qianxun-tests/tree','/usr/share/icons'],'excludes':[]}, open(os.environ['XDG_CONFIG_HOME']+'/qianxun/config.json','w'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'app'))
import qianxun as qx
print('binding', qx.QT_BINDING, qx.QT_VER)
sys.argv=['qianxun']
app_holder={}
QTimer=qx.QTimer; QApplication=qx.QApplication
def closer():
    w=QApplication.activeModalWidget() or QApplication.activePopupWidget()
    if w: print('  closing', type(w).__name__); w.close() if not hasattr(w,'reject') else w.reject()
def script():
    ws=[w for w in QApplication.topLevelWidgets() if isinstance(w, qx.MainWindow)]
    if not ws: QTimer.singleShot(200, script); return
    w=ws[0]
    if w.engine.status['state']!='ready': QTimer.singleShot(200, script); return
    w.search.setText('IMG | folder')
    def s2():
        w.grab().save('/tmp/qianxun-tests/shot_%s.png'%B); print('rows', w.model.rowCount(), w.lbl_count.text())
        w.view.setCurrentIndex(w.model.index(0,0)); w.act_copy(); print('clip', QApplication.clipboard().text()[:60])
        QTimer.singleShot(300, closer); w.show_help()
        QTimer.singleShot(300, closer); w.open_options()
        QTimer.singleShot(300, closer); w.context_menu(qx.QPoint(10,10))
        w.view.header().setSortIndicator(3, qx.Qt.DescendingOrder); print('sorted', w.model.rowCount())
        w.quit_app()
    QTimer.singleShot(700, s2)
_orig=qx.MainWindow.__init__
def _init(self,*a,**k):
    _orig(self,*a,**k); QTimer.singleShot(300, script)
qx.MainWindow.__init__=_init
rc=qx.main(); print('rc', rc)
