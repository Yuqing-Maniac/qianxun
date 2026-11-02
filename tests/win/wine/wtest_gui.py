# -*- coding: utf-8 -*-
"""Wine-side GUI test: real main() with a scripted session. Writes C:\\qxport\\gui_result.txt and screenshots."""
import os, sys, time, json, shutil, traceback
OUT = open(r'C:\qxport\gui_result.txt', 'w', encoding='utf-8')


def P(*a):
    OUT.write(' '.join(str(x) for x in a) + '\n')
    OUT.flush()


sys.path.insert(0, r'C:\qxport\QianXun\app')
import qianxun as q
os.makedirs(q.CONF_DIR, exist_ok=True)
json.dump({'roots': [r'C:\demo'], 'excludes': [], 'index_removable': False}, open(q.CONF_FILE, 'w', encoding='utf-8'))
P('binding', q.QT_BINDING, q.QT_VER, 'python', sys.version.split()[0])
FAIL = []


def check(name, cond, extra=''):
    P('PASS' if cond else 'FAIL', name, extra)
    if not cond:
        FAIL.append(name)


T = os.path.join(r'C:\demo', 'gui 测试')
shutil.rmtree(T, ignore_errors=True)
os.makedirs(T)
for n in ('说明.txt', '待删除.txt', '改名前.txt'):
    open(os.path.join(T, n), 'w').write('hello')
shutil.copy(r'C:\qxport\QianXun\QianXun.exe', os.path.join(T, 'tool.exe'))

QTimer, QApplication, QMessageBox = q.QTimer, q.QApplication, q.QMessageBox
LOG = []
QMessageBox.question = staticmethod(lambda *a, **k: (LOG.append(('question', a[2])), QMessageBox.Yes)[1])
QMessageBox.information = staticmethod(lambda *a, **k: LOG.append(('info', a[2] if len(a) > 2 else '')))
QMessageBox.warning = staticmethod(lambda *a, **k: LOG.append(('warning', a[2] if len(a) > 2 else '')))
q.QInputDialog.getText = staticmethod(lambda *a, **k: ('已改名.txt', True))


def closer():
    w = QApplication.activeModalWidget() or QApplication.activePopupWidget()
    if w:
        P('  closing', type(w).__name__)
        w.reject() if hasattr(w, 'reject') else w.close()


def find_row(w, name):
    for r in range(w.model.rowCount()):
        i = w.model.entry(r)
        if i >= 0 and w.index.names[i] == name:
            return r
    return -1


def select(w, name):
    r = find_row(w, name)
    w.view.clearSelection()
    if r >= 0:
        w.view.setCurrentIndex(w.model.index(r, 0))
    return r >= 0


def script():
    ws = [x for x in QApplication.topLevelWidgets() if isinstance(x, q.MainWindow)]
    if not ws or ws[0].engine.status['state'] != 'ready':
        QTimer.singleShot(200, script)
        return
    w = ws[0]
    try:
        check('engine is EngineWin', type(w.engine).__name__ == 'EngineWin')
        check('font', True, QApplication.font().family())
        check('hotkey registered', w.hotkey is not None and w.hotkey.ok, w.cfg.get('hotkey'))
        check('native filter installed', getattr(w, 'native_filter', None) is not None)
        t0 = time.time()
        while time.time() - t0 < 3 and '索引就绪' not in w.lbl_state.text():
            QApplication.processEvents()
            time.sleep(0.05)
        P('status:', w.lbl_state.text())
        check('status full coverage', '实时监控已全覆盖' in w.lbl_state.text())
        w.search.setText('"gui 测试\\"')
        w.flush_search()
        QApplication.processEvents()
        check('path search rows', w.model.rowCount() == 4, w.model.rowCount())
        # icons
        ics = [w.model.data(w.model.index(r, 0), q.Qt.DecorationRole) for r in range(w.model.rowCount())]
        check('icons non-null', all(ic is not None and not ic.isNull() for ic in ics))
        P('icon cache: ext', sorted(w.model.icons.cache), 'paths', list(w.model.icons.lru))
        w.grab().save(r'C:\qxport\gui_grab1.png')
        # copy → CF_HDROP via URLs
        select(w, '说明.txt')
        w.act_copy()
        md = QApplication.clipboard().mimeData()
        check('clipboard urls', md.hasUrls() and md.urls()[0].toLocalFile().replace('/', '\\').lower() ==
              os.path.join(T, '说明.txt').lower(), [u.toString() for u in md.urls()])
        P('clipboard formats', list(md.formats()))
        w.act_copy_path()
        check('copy path', QApplication.clipboard().text() == os.path.join(T, '说明.txt'), QApplication.clipboard().text())
        # live update visible in the GUI
        t0 = time.time()
        open(os.path.join(T, '新文件.txt'), 'w').close()
        while time.time() - t0 < 5 and w.model.rowCount() < 5:
            QApplication.processEvents()
            time.sleep(0.02)
        dt = time.time() - t0
        check('GUI live update %.2f s' % dt, w.model.rowCount() == 5 and dt <= 1.0, w.model.rowCount())
        # rename
        select(w, '改名前.txt')
        w.act_rename()
        t0 = time.time()
        while time.time() - t0 < 5 and find_row(w, '已改名.txt') < 0:
            QApplication.processEvents()
            time.sleep(0.02)
        check('rename', os.path.exists(os.path.join(T, '已改名.txt')) and find_row(w, '已改名.txt') >= 0)
        # trash
        select(w, '待删除.txt')
        w.act_trash()
        check('trash removed file', not os.path.exists(os.path.join(T, '待删除.txt')), LOG[-2:])
        t0 = time.time()
        while time.time() - t0 < 5 and find_row(w, '待删除.txt') >= 0:
            QApplication.processEvents()
            time.sleep(0.02)
        check('trash reflected', find_row(w, '待删除.txt') < 0)
        # open / show in folder / props / terminal: must not raise
        for name, fn in (('show_in_folder', w.act_open_folder), ('props', w.act_props), ('open', w.act_open),
                         ('terminal', w.act_terminal)):
            select(w, '说明.txt')
            try:
                fn()
                check('action %s no crash' % name, True)
            except Exception:
                check('action %s no crash' % name, False, traceback.format_exc())
        P('message log', LOG)
        QTimer.singleShot(400, closer)
        w.open_options()
        QTimer.singleShot(400, closer)
        w.show_help()
        QTimer.singleShot(400, closer)
        w.context_menu(q.QPoint(10, 10))
        w.search.setText('ext:docx 报告')
        w.flush_search()
        w.view.header().setSortIndicator(2, q.Qt.DescendingOrder)
        QApplication.processEvents()
        w.grab().save(r'C:\qxport\gui_grab2.png')
        check('sorted rows', w.model.rowCount() > 0, w.model.rowCount())
    except Exception:
        check('script', False, traceback.format_exc())
    P('GUI TESTS FAILED:', ', '.join(FAIL) if FAIL else 'none')
    OUT.flush()
    QTimer.singleShot(3000, w.quit_app)   # leave time for an external screenshot


_orig = q.MainWindow.__init__


def _init(self, *a, **k):
    _orig(self, *a, **k)
    QTimer.singleShot(300, script)


q.MainWindow.__init__ = _init
sys.argv = [r'C:\qxport\QianXun\app\qianxun.py']
rc = q.main()
P('rc', rc)
OUT.close()
shutil.rmtree(T, ignore_errors=True)
