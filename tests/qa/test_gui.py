"""Automated GUI harness. Run: QT_QPA_PLATFORM=offscreen QIANXUN_QT=PyQt5|PySide6 python3 test_gui.py"""
import os
import sys
import csv
import time
import shutil
import tempfile
import traceback

from qa_common import q, wait_ready, index_set

assert q.HAVE_QT, q._QT_ERROR
print('binding', q.QT_BINDING, q.QT_VER)
FAIL = []
app = q.QApplication.instance() or q.QApplication(sys.argv)

# ---- non-blocking stand-ins for modal dialogs ----
ANSWERS = {'question': q.QMessageBox.Yes, 'text': ('', False), 'save': ('', '')}
LOG = []
q.QMessageBox.question = staticmethod(lambda *a, **k: (LOG.append(('question', a[2] if len(a) > 2 else '')), ANSWERS['question'])[1])
q.QMessageBox.warning = staticmethod(lambda *a, **k: LOG.append(('warning', a[2] if len(a) > 2 else '')))
q.QMessageBox.information = staticmethod(lambda *a, **k: LOG.append(('info', a[2] if len(a) > 2 else '')))
q.QInputDialog.getText = staticmethod(lambda *a, **k: ANSWERS['text'])
q.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ANSWERS['save'])
OPEN_ARGS = []


def _no_open(*a, **k):
    OPEN_ARGS.append(a)
    return ('', '')


q.QFileDialog.getOpenFileName = staticmethod(_no_open)
OPENED = []
q.open_path = lambda p: OPENED.append(p)
q.show_in_folder = lambda p: OPENED.append(('folder', p))
q.QMenu.exec_ = lambda self, *a: None
q.QMenu.exec = lambda self, *a: None


def pump(t=0.05):
    end = time.time() + t
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def check(cond, what):
    if not cond:
        FAIL.append(what)
        print('FAIL', what)
        traceback.print_stack(limit=3)


base = tempfile.mkdtemp(prefix='qa_gui_')
root = os.path.join(base, '根 dir')
os.makedirs(os.path.join(root, 'sub dir'))
rb = os.fsencode(root)
files = {'alpha.txt': 10, 'Beta.TXT': 3000, 'gamma.pdf': 5, 'delta.docx': 70000, 'sub dir/zeta.txt': 1,
         'sub dir/eta.pdf': 123456, '报告2026.docx': 42}
for rel, n in files.items():
    with open(os.path.join(root, rel), 'wb') as f:
        f.write(b'x' * n)
    os.utime(os.path.join(root, rel), (1e9 + n, 1e9 + n))
with open(rb + b'/bad\xffname.txt', 'wb') as f:
    f.write(b'abc')

cfg = dict(q.DEFAULT_CONFIG)
cfg.update(roots=[root], excludes=[], index_removable=False, close_to_tray=True)
idx = q.Index()
eng = q.Engine(idx, cfg)
eng.start()
assert wait_ready(eng)
win = q.MainWindow(cfg, idx, eng, q.make_app_icon())
win.show()
pump(0.3)


def search(t):
    win.search.setText(t)
    win.flush_search()
    pump(0.05)
    return [win.model.entry(r) for r in range(win.model.rowCount())]


def names(rows):
    return [idx.names[i] for i in rows]


try:
    # ---- searching ----
    r = search('txt')
    check(set(names(r)) >= {'alpha.txt', 'Beta.TXT', 'zeta.txt'}, 'basic search')
    check(any('bad' in n for n in names(r)), 'non-utf8 name searchable')
    # display of each cell for every row/role must not raise
    for row in range(win.model.rowCount()):
        for col in range(4):
            mi = win.model.index(row, col)
            for role in (q.Qt.DisplayRole, q.Qt.DecorationRole, q.Qt.ToolTipRole, q.Qt.TextAlignmentRole):
                win.model.data(mi, role)
    # paint everything once (delegate)
    win.view.viewport().repaint()
    for t in ['', ' ', '|', '!', 'a | b', '"sub dir"', '"a|b"', 'ext:', 'size:', 'size:bad', 'dm:', 'dm:bad',
              'regex:(', 'regex:a{4294967296}', 'a{99999999999}', 'dm:9999', 'sub/*.pdf', '*/*.pdf', 'folder:"']:
        search(t)
    for key in ('case', 'whole_word', 'match_path', 'regex'):
        win.set_opt(key, True)
        search('a{99999999999}')
        search('A')
        win.set_opt(key, False)
    pump(0.1)

    # ---- sorting each column asc/desc ----
    search('')
    for col in range(4):
        for desc in (False, True):
            win.view.header().setSortIndicator(col, q.Qt.DescendingOrder if desc else q.Qt.AscendingOrder)
            pump(0.05)
            rows = [win.model.entry(r) for r in range(win.model.rowCount())]
            if col == 0:
                keys = [idx.lnames[i] for i in rows]
            elif col == 1:
                keys = [(idx.dir_prefixes(True)[idx.parent[i]], idx.lnames[i]) for i in rows]
            elif col == 2:
                keys = [idx.size[i] for i in rows]
            else:
                keys = [idx.mtime[i] for i in rows]
            check(keys == sorted(keys, reverse=desc), 'sort col %d desc=%s' % (col, desc))
    win.view.header().setSortIndicator(0, q.Qt.AscendingOrder)
    pump(0.05)

    # big-result name_order merge path
    q2 = q.Index()
    with q2.lock:
        d = q2._new_dir('/x', -1)
        import random
        rnd = random.Random(1)
        for k in range(130000):
            q2._add_entry(d, 'n%07d_%s' % (rnd.randint(0, 9999999), rnd.choice('aBcD')), False)
    eng2 = type('E', (), {'index': q2})()
    q.Engine._compute_order(eng2)
    with q2.lock:
        for k in range(500):   # entries added after order computed
            q2._add_entry(d, 'late%05d' % rnd.randint(0, 99999), False)
        rem = []
        q2._remove_entry(5, rem)
        q2.version += 1
    saved = win.index
    win.index = q2
    for desc in (False, True):
        win.sort_col, win.sort_desc = 0, desc
        res = [i for i in range(len(q2.names)) if q2.kind[i] != q.KIND_DEAD]
        out = win._sorted(list(res))
        check(sorted(out) == sorted(res), 'name_order merge keeps the same set (desc=%s)' % desc)
        ks = [q2.lnames[i] for i in out]
        check(ks == sorted(ks, reverse=desc), 'name_order merge sorted (desc=%s)' % desc)
    win.index = saved
    win.sort_col, win.sort_desc = 0, False

    # ---- keep_view ----
    r = search('')
    target = [i for i in r if idx.names[i] == 'gamma.pdf'][0]
    win.view.setCurrentIndex(win.model.index(r.index(target), 0))
    win.do_search(keep_view=True)
    pump(0.05)
    check(win.model.entry(win.view.currentIndex().row()) == target, 'keep_view restores current')

    # ---- context menu with no selection ----
    win.view.clearSelection()
    win.view.setCurrentIndex(q.QModelIndex())
    win.context_menu(q.QPoint(1, 1))
    win.act_copy(); win.act_copy_path(); win.act_rename(); win.act_trash(); win.act_props(); win.act_open()
    win.act_open_folder(); win.act_terminal(); win.act_copy_name(); win.act_copy_dir()

    def select_name(nm):
        rows = [win.model.entry(rr) for rr in range(win.model.rowCount())]
        hit = [k for k, i in enumerate(rows) if idx.names[i] == nm]
        check(hit, 'found %r in results' % nm)
        win.view.clearSelection()
        win.view.setCurrentIndex(win.model.index(hit[0], 0))
        win.view.selectionModel().select(win.model.index(hit[0], 0),
                                         q._QtCore.QItemSelectionModel.Select | q._QtCore.QItemSelectionModel.Rows)
        return rows[hit[0]]

    # ---- copy / copy path / non-UTF-8 ----
    search('bad')
    bad_name = os.fsdecode(b'bad\xffname.txt')
    select_name(bad_name)
    win.act_copy()
    md = q.QApplication.clipboard().mimeData()
    check(md is not None and md.hasUrls(), 'copy produced urls')
    win.act_copy_path()
    txt = q.QApplication.clipboard().text()
    check(txt.endswith('bad�name.txt'), 'copy path displays replacement char: %r' % txt)
    win.act_props()
    win.act_open()
    check(OPENED and OPENED[-1] == os.path.join(root, bad_name), 'open passes real (surrogate) path')
    md2 = win.model.mimeData([win.model.index(win.view.currentIndex().row(), 0)])
    urls = md2.urls()
    from urllib.parse import unquote_to_bytes
    enc = bytes(urls[0].toEncoded().data()) if urls else b''
    check(enc.startswith(b'file://') and unquote_to_bytes(enc[7:]) == os.fsencode(os.path.join(root, bad_name)),
          'drag/copy url keeps raw bytes for non-utf8: %r' % enc)

    # ---- rename ----
    search('alpha')
    select_name('alpha.txt')
    ANSWERS['text'] = ('alpha2.txt', True)
    win.act_rename()
    check(os.path.exists(os.path.join(root, 'alpha2.txt')), 'rename on disk')
    for nm in ('', 'alpha2.txt', 'a/b', '.', '..'):
        search('alpha2')
        pump(0.6)
        r = search('alpha2')
        if not r:
            break
        select_name('alpha2.txt')
        ANSWERS['text'] = (nm, True)
        LOG.clear()
        win.act_rename()
        check(os.path.exists(os.path.join(root, 'alpha2.txt')), 'rename to %r must be refused' % nm)
    # rename non-utf8 file keeps working
    search('bad')
    select_name(bad_name)
    ANSWERS['text'] = (q.disp(bad_name), True)   # user presses OK without editing
    win.act_rename()
    check(os.path.lexists(os.path.join(root, bad_name)), 'unchanged rename of non-utf8 name must not rename file')
    check(not os.path.lexists(os.path.join(root, 'bad�name.txt')), 'no U+FFFD file created by no-op rename')
    ANSWERS['text'] = ('', False)
    pump(0.6)

    # ---- trash ----
    os.environ['XDG_DATA_HOME'] = os.path.join(base, 'xdgdata')
    search('gamma')
    select_name('gamma.pdf')
    ANSWERS['question'] = q.QMessageBox.Yes
    win.act_trash()
    check(not os.path.exists(os.path.join(root, 'gamma.pdf')), 'trash removed file')
    # freedesktop fallback directly, incl. non-utf8
    p = os.path.join(root, os.fsdecode(b'tr\xfe.txt'))
    open(p, 'wb').close()
    check(q._trash_freedesktop(p), 'freedesktop trash ok')
    info = os.path.join(base, 'xdgdata', 'Trash', 'info')
    check(any(n.startswith(os.fsdecode(b'tr\xfe')) for n in os.listdir(info)), 'trashinfo written')
    # dialog "No"
    search('delta')
    select_name('delta.docx')
    ANSWERS['question'] = q.QMessageBox.No
    win.act_trash()
    check(os.path.exists(os.path.join(root, 'delta.docx')), 'No keeps file')
    ANSWERS['question'] = q.QMessageBox.Yes

    # ---- CSV export ----
    pump(0.6)
    search('')
    out = os.path.join(base, '导出 结果.csv')
    ANSWERS['save'] = (out, '')
    win.export_csv()
    with open(out, encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))
    check(len(rows) >= 5 and rows[0][0] == '名称', 'csv export rows=%d' % len(rows))
    ANSWERS['save'] = ('', '')

    # ---- rebuild while results are shown: stale rows must never map to other files ----
    search('')
    before = win.model.rowCount()
    eng.post('rebuild', dict(cfg))
    for _ in range(60):
        pump(0.02)
        for rr in range(win.model.rowCount()):
            for col in range(4):
                win.model.data(win.model.index(rr, col), q.Qt.DisplayRole)
    assert wait_ready(eng)
    pump(0.6)

    # ---- Esc behaviour ----
    win.search.setText('abc')
    from_key = getattr(q._QtGui, 'QKeyEvent')
    ev = from_key(q._QtCore.QEvent.KeyPress, q.Qt.Key_Escape, q.Qt.NoModifier)
    win.search.keyPressEvent(ev)
    check(win.search.text() == '', 'Esc clears text')
    win.search.keyPressEvent(ev)   # tray absent under offscreen -> must stay visible
    check(win.isVisible() or win.tray is not None, 'Esc w/o tray keeps window')

    labels = []
    for top in win.menuBar().actions():
        menu = top.menu()
        if menu is not None and '帮助' in top.text():
            labels = [act.text() for act in menu.actions()]
    check('增量升级…' in labels, 'help menu lists upgrade')
    check(labels.index('增量升级…') == labels.index('搜索语法与快捷键') + 1, 'upgrade follows F1')
    check(labels.index('关于千寻') == labels.index('增量升级…') + 1, 'about follows upgrade')
    before_log = len(LOG)
    win.incremental_upgrade()
    check(len(LOG) == before_log, 'empty upgrade path shows no message')
    got_args = OPEN_ARGS[-1][1:] if OPEN_ARGS else None
    check(got_args == ('选择升级包', q.HOME, 'Zip 压缩包 (*.zip)'), 'upgrade dialog args %r' % (got_args,))

    # ---- close with no tray ----
    print('tray available:', win.tray is not None)
finally:
    try:
        win.quit_app()
    except Exception:
        traceback.print_exc()
        FAIL.append('quit_app')
    check(not eng.is_alive(), 'engine stopped on quit')
    shutil.rmtree(base, ignore_errors=True)

print('GUI FAILED:', FAIL if FAIL else 'none')
sys.exit(1 if FAIL else 0)
