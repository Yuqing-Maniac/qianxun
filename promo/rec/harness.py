#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QianXun screen-recording harness.
  python3 harness.py prebuild        # build + save the index cache (headless)
  python3 harness.py R1 [R2 ...]     # record clips
"""
import os, sys, time, json, math, subprocess, heapq, shutil, signal, traceback

REC = '/home/claude/video/q/rec'
DISP = ':91'
SCALE = 1.5
os.environ.update({
    'DISPLAY': DISP, 'QT_SCALE_FACTOR': str(SCALE), 'LANG': 'zh_CN.UTF-8', 'PYTHONUTF8': '1',
    'HOME': '/home/kylin', 'XDG_CONFIG_HOME': '/home/kylin/.config', 'XDG_CACHE_HOME': '/home/kylin/.cache',
    'XDG_DATA_HOME': '/home/kylin/.local/share', 'QT_QPA_PLATFORM': 'xcb', 'QT_AUTO_SCREEN_SCALE_FACTOR': '0',
    'QT_LOGGING_RULES': '*.debug=false;qt.qpa.*=false',
})
os.environ.pop('QT_SCREEN_SCALE_FACTORS', None)
sys.path.insert(0, '/home/claude/build/app')
import qianxun as qx

FPS = 30
W, H = 2400, 1440
LOGW, LOGH = 1600, 960
HOMEDIR = '/home/kylin'
CFG = {
    'roots': ['/home/kylin', '/data', '/usr'],
    'excludes': ['/proc', '/sys', '/dev', '/run', '/snap', '/var/lib/docker', '/var/lib/containerd',
                 '/home/kylin/.cache', '/home/kylin/.config', '/home/kylin/.local', '/usr/local'],
    'index_removable': False, 'index_network': False, 'close_to_tray': False,
    'case': False, 'whole_word': False, 'match_path': False, 'regex': False,
    'filter': 0, 'sort_col': 0, 'sort_desc': False, 'geometry': '', 'header': '',
}


def write_cfg():
    os.makedirs(qx.CONF_DIR, exist_ok=True)
    c = dict(qx.DEFAULT_CONFIG)
    c.update(CFG)
    with open(qx.CONF_FILE, 'w', encoding='utf-8') as f:
        json.dump(c, f, ensure_ascii=False, indent=1)


def wait_engine_idle(engine, index, app=None, timeout=900, quiet=True):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if app:
            app.processEvents()
        st = engine.status
        if (st.get('state') == 'ready' and engine.sweep_iter is None
                and engine.order_version == index.version and not engine.cmds.qsize()):
            time.sleep(0.5)
            if engine.sweep_iter is None and engine.order_version == index.version:
                return True
        time.sleep(0.1)
    return False


def prebuild():
    write_cfg()
    for p in (qx.INDEX_FILE,):
        if os.path.exists(p):
            os.remove(p)
    cfg = qx.load_config()
    index = qx.Index()
    engine = qx.Engine(index, cfg)
    t0 = time.time()
    engine.start()
    ok = wait_engine_idle(engine, index, timeout=1800)
    print('ready=%s live=%d dirs=%s watched=%s time=%.0fs status=%s' % (
        ok, index.live, engine.status.get('dirs'), engine.status.get('watched'), time.time() - t0, engine.status), flush=True)
    engine.post('save')
    time.sleep(1)
    engine.post('quit')
    engine.join(60)
    print('cache', os.path.getsize(qx.INDEX_FILE) if os.path.exists(qx.INDEX_FILE) else None)


# ---------------------------------------------------------------- X / ffmpeg
def ensure_xvfb():
    r = subprocess.run(['pgrep', '-f', 'Xvfb %s' % DISP], capture_output=True)
    if r.returncode != 0:
        subprocess.Popen(['Xvfb', DISP, '-screen', '0', '%dx%dx24' % (W, H), '-nolisten', 'tcp', '-ac'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)


FFLOG = REC + '/ffmpeg_last.log'


def start_ffmpeg(raw):
    f = open(FFLOG, 'wb')
    p = subprocess.Popen(['ffmpeg', '-y', '-f', 'x11grab', '-draw_mouse', '0', '-framerate', str(FPS),
                          '-video_size', '%dx%d' % (W, H), '-i', DISP + '.0',
                          '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '12', '-pix_fmt', 'yuv420p', raw],
                         stdin=subprocess.PIPE, stdout=f, stderr=f)
    return p


def stop_ffmpeg(p):
    try:
        p.stdin.write(b'q')
        p.stdin.flush()
    except Exception:
        pass
    try:
        p.wait(30)
    except Exception:
        p.terminate()
        p.wait(10)
    txt = open(FFLOG, 'rb').read().decode('utf-8', 'ignore').replace('\r', '\n')
    last = [l for l in txt.split('\n') if 'frame=' in l]
    return last[-1] if last else txt[-300:]


# ---------------------------------------------------------------- Qt environment
from PyQt5.QtCore import Qt, QPoint, QTimer, QEvent, QModelIndex, QRect
from PyQt5.QtGui import QFont, QInputMethodEvent
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtTest import QTest


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (6 * u - 15) + 10)   # smootherstep


class Rec(object):
    def __init__(self, app, win, index, engine):
        self.app, self.win, self.index, self.engine = app, win, index, engine
        self.reset_clip()

    def reset_clip(self):
        self.actions = []
        self.seq = 0
        self.moves = []
        self.mi = 0
        self.cur = (800.0, 480.0)
        self.cursor_log = []
        self.events = []
        self.search_ms = []
        self.T0 = None
        self.dur = 0
        self.down = False
        self.last_log = -1
        self.last_watch = 0
        self.last_sig = None
        self.last_rows = {}
        self.pending_q = None
        self.last_key_wall = 0
        self.extra_rects = {}
        self.done = False
        self.ds_log = []
        self.ver_seen = None

    # ------- scheduling
    def at(self, t, fn):
        heapq.heappush(self.actions, (t, self.seq, fn))
        self.seq += 1

    def move(self, t, target, dur=0.45):
        """glide cursor to target (tuple or callable -> logical px) starting at t"""
        self.moves.append({'t0': t, 'dur': dur, 'target': target, 'started': False})
        self.moves.sort(key=lambda m: m['t0'])

    def now(self):
        return time.time() - self.T0

    def ev(self, typ, label='', value=None, t=None):
        e = {'t': round(self.now() if t is None else t, 3), 'type': typ, 'label': label}
        if value is not None:
            e['value'] = value
        self.events.append(e)
        return e

    # ------- input primitives (real Qt events through the window system path)
    def wh(self):
        return self.win.windowHandle()

    def ipt(self):
        return QPoint(int(round(self.cur[0])), int(round(self.cur[1])))

    def press(self, btn=Qt.LeftButton, label=''):
        self.down = True
        self.ev('rightclick' if btn == Qt.RightButton else 'click', label, {'x': round(self.cur[0] * SCALE), 'y': round(self.cur[1] * SCALE)})
        QTest.mousePress(self.wh(), btn, Qt.NoModifier, self.ipt())

    def release(self, btn=Qt.LeftButton):
        QTest.mouseRelease(self.wh(), btn, Qt.NoModifier, self.ipt())
        self.down = False

    def click(self, t, label='', hold=0.09):
        self.at(t, lambda: self.press(Qt.LeftButton, label))
        self.at(t + hold, lambda: self.release(Qt.LeftButton))

    def rclick(self, t, label='', hold=0.09):
        self.at(t, lambda: QTimer.singleShot(0, lambda: self.press(Qt.RightButton, label)))
        self.at(t + hold, lambda: QTimer.singleShot(0, lambda: self.release(Qt.RightButton)))

    def key(self, t, key, mod=Qt.NoModifier, label=''):
        def f():
            self.ev('key', label or QKeySequenceName(key, mod))
            tgt = QApplication.activePopupWidget() or QApplication.activeModalWidget() or QApplication.focusWidget() or self.win
            QTest.keyClick(tgt, key, mod)
        self.at(t, f)

    def key_async(self, t, key, mod=Qt.NoModifier, label=''):
        self.at(t, lambda: QTimer.singleShot(0, lambda: (self.ev('key', label), QTest.keyClick(
            QApplication.activePopupWidget() or QApplication.activeModalWidget() or QApplication.focusWidget() or self.win, key, mod))))

    def select_all(self, t):
        def f():
            self.ev('key', 'Ctrl+A')
            self.win.search.setFocus()
            QTest.keyClick(self.win.search, Qt.Key_A, Qt.ControlModifier)
        self.at(t, f)

    def type_text(self, t, text, ascii_delay=0.065, cjk_gap=0.12, label=None):
        """chunks: CJK runs are committed whole (IME-like); ASCII char by char."""
        chunks = []
        buf = ''
        for ch in text:
            if ord(ch) > 0x2e80:
                buf += ch
            else:
                if buf:
                    chunks.append(('c', buf)); buf = ''
                chunks.append(('a', ch))
        if buf:
            chunks.append(('c', buf))
        # split CJK runs into 2-char words (like "总体" + "方案")
        words = []
        for k, v in chunks:
            if k == 'c':
                for i in range(0, len(v), 2):
                    words.append(('c', v[i:i + 2]))
            else:
                words.append((k, v))
        tt = t
        for k, v in words:
            self.at(tt, self._mk_type(k, v, text, label))
            tt += cjk_gap if k == 'c' else ascii_delay
        end = tt
        self.at(end - 0.001, lambda: self._expect(label or text))
        return end

    def _mk_type(self, k, v, full, label):
        def f():
            s = self.win.search
            self.last_key_wall = time.time()
            if k == 'c':
                ev = QInputMethodEvent()
                ev.setCommitString(v)
                QApplication.sendEvent(s, ev)
            else:
                QTest.keyClicks(s, v)
            self.ev('type', v, {'text': s.text()})
        return f

    def _expect(self, q):
        self.pending_q = {'q': q, 'since': time.time()}

    def fs(self, t, label, fn):
        def f():
            self.ev('fs', label)
            self._fs_t = self.now()
            fn()
        self.at(t, f)

    # ------- watching results
    def row_names(self):
        m = self.win.model
        idx = self.index
        out = []
        for r in range(min(m.rowCount(), 60)):
            e = m.entry(r)
            out.append(idx.names[e] if 0 <= e < len(idx.names) else '?')
        return out

    def watch(self):
        w = self.win
        n = w.model.rowCount()
        names = self.row_names() if n <= 60 else None
        sig = (n, tuple(names) if names is not None else tuple(self.row_names()[:12]), w.last_search)
        if sig != self.last_sig:
            prev = self.last_sig
            self.last_sig = sig
            if prev is not None:
                val = {'rows': n, 'search_ms': round(w.search_ms, 1)}
                lab = 'results'
                if names is not None and self.last_rows.get('names') is not None and n <= 60:
                    old, new = set(self.last_rows['names']), set(names)
                    add, rem = sorted(new - old), sorted(old - new)
                    if add: val['added'] = add
                    if rem: val['removed'] = rem
                    lab = (' '.join(['+' + a for a in add] + ['-' + r for r in rem]) if len(add) + len(rem) <= 4 else 'results') or 'results'
                self.ev('result', lab, val)
            self.last_rows = {'names': names}
        pq = self.pending_q
        if pq and not w.timer.isActive() and w.last_search >= self.last_key_wall and w.search.text() != '' or \
                (pq and pq.get('allow_empty') and not w.timer.isActive() and w.last_search >= self.last_key_wall):
            self.pending_q = None
            cand = [x for x in self.ds_log if x[0] >= self.last_key_wall and x[1] == w.search.text()]
            ms = round(cand[0][2], 1) if cand else round(w.search_ms, 1)
            t = round(self.now(), 3)
            self.ev('query', pq['q'], {'rows': n, 'search_ms': ms})
            self.search_ms.append({'t': t, 'q': pq['q'], 'ms': ms, 'rows': n})

    # ------- main tick
    def tick(self):
        if self.T0 is None or self.done:
            return
        now = self.now()
        # actions
        while self.actions and self.actions[0][0] <= now:
            _, _, fn = heapq.heappop(self.actions)
            try:
                fn()
            except Exception:
                traceback.print_exc()
        # cursor moves
        moved = False
        while self.mi < len(self.moves):
            m = self.moves[self.mi]
            if now < m['t0']:
                break
            if not m['started']:
                m['started'] = True
                m['p0'] = self.cur
                tg = m['target']
                try:
                    m['p1'] = tg() if callable(tg) else tg
                except Exception:
                    traceback.print_exc()
                    m['p1'] = self.cur
                dx, dy = m['p1'][0] - m['p0'][0], m['p1'][1] - m['p0'][1]
                L = math.hypot(dx, dy) or 1.0
                m['nx'], m['ny'] = -dy / L, dx / L
                m['bend'] = min(40.0, L * 0.06) * (1 if (int(m['t0'] * 10) % 2 == 0) else -1)
            u = ease((now - m['t0']) / m['dur'])
            p0, p1 = m['p0'], m['p1']
            x = p0[0] + (p1[0] - p0[0]) * u
            y = p0[1] + (p1[1] - p0[1]) * u
            b = math.sin(math.pi * u) * m['bend']
            x += m['nx'] * b
            y += m['ny'] * b
            self.cur = (x, y)
            moved = True
            if now >= m['t0'] + m['dur']:
                self.cur = p1
                self.mi += 1
                continue
            break
        if moved:
            try:
                QTest.mouseMove(self.wh(), self.ipt())
            except Exception:
                traceback.print_exc()
        if now - self.last_log >= 1.0 / FPS - 0.004:
            self.last_log = now
            self.cursor_log.append({'t': round(now, 3), 'x': round(self.cur[0] * SCALE, 1), 'y': round(self.cur[1] * SCALE, 1), 'down': bool(self.down)})
        v = self.index.version
        if v != self.win.last_version:
            if self.ver_seen is None or self.ver_seen[0] != v:
                self.ver_seen = (v, time.time())
            elif time.time() - self.ver_seen[1] > 0.25 and not self.win.timer.isActive():
                self.win.do_search(keep_view=True)
                self.ev('refresh', 'do_search(keep_view) after index change (harness nudge)')
        if now - self.last_watch >= 0.02:
            self.last_watch = now
            self.watch()
        if now >= self.dur:
            self.done = True


def QKeySequenceName(key, mod):
    from PyQt5.QtGui import QKeySequence
    return QKeySequence(int(key) | int(mod)).toString()


# ---------------------------------------------------------------- geometry helpers
def gmap(w, r=None):
    """rect of widget w (or sub-rect r in w coords) in physical px of the screen"""
    if r is None:
        r = w.rect()
    tl = w.mapToGlobal(r.topLeft())
    return [round(tl.x() * SCALE), round(tl.y() * SCALE), round(r.width() * SCALE), round(r.height() * SCALE)]


def wcenter(win, w, r=None, fx=0.5, fy=0.5):
    """logical (window) coordinates inside widget"""
    if r is None:
        r = w.rect()
    p = w.mapTo(win, QPoint(int(r.x() + r.width() * fx), int(r.y() + r.height() * fy)))
    return (float(p.x()), float(p.y()))


def row_pt(win, row, x=240):
    v = win.view
    r = v.visualRect(win.model.index(row, 0))
    p = v.viewport().mapTo(win, QPoint(x, r.center().y()))
    return (float(p.x()), float(p.y()))


def collect_rects(win, nrows=14):
    v = win.view
    hdr = v.header()
    R = {
        'window': [0, 0, W, H],
        'search': gmap(win.search), 'filter': gmap(win.filter),
        'results': gmap(v.viewport()), 'header': gmap(hdr),
        'statusbar': gmap(win.statusBar()), 'status_count': gmap(win.lbl_count), 'status_state': gmap(win.lbl_state),
    }
    for i, nm in enumerate(['header_name', 'header_path', 'header_size', 'header_mtime']):
        lg = hdr.logicalIndex(i)
        x = hdr.sectionViewportPosition(lg)
        R[nm] = gmap(hdr, QRect(x, 0, hdr.sectionSize(lg), hdr.height()))
    rows = []
    for r in range(min(win.model.rowCount(), nrows)):
        vr = v.visualRect(win.model.index(r, 0))
        if vr.isValid():
            rows.append(gmap(v.viewport(), QRect(0, vr.y(), v.viewport().width(), vr.height())))
    R['rows'] = rows
    return R


def popup_rects(R, tag):
    pw = QApplication.activePopupWidget()
    if pw is not None:
        R[tag] = gmap(pw)
    return pw


# ---------------------------------------------------------------- app setup
def build_app():
    write_cfg()
    ensure_xvfb()
    app = QApplication(sys.argv)
    app.setApplicationName('qianxun')
    app.setStyle('Fusion')
    f = QFont('Noto Sans CJK SC', 11)
    f.setStyleName('Regular')
    app.setFont(f)
    icon = qx.make_app_icon()
    app.setWindowIcon(icon)
    cfg = qx.load_config()
    index = qx.Index()
    engine = qx.Engine(index, cfg)
    engine.start()
    win = qx.MainWindow(cfg, index, engine, icon)
    win.setGeometry(0, 0, LOGW, LOGH)
    hdr = win.view.header()
    hdr.resizeSection(0, 500)
    hdr.resizeSection(1, 620)
    hdr.resizeSection(2, 110)
    hdr.resizeSection(3, 180)
    win.show()
    win.move(0, 0)
    win.resize(LOGW, LOGH)
    app.processEvents()
    QApplication.setActiveWindow(win)
    return app, win, index, engine


def spin(app, secs):
    t = time.time() + secs
    while time.time() < t:
        app.processEvents()
        time.sleep(0.005)


def reset_ui(app, win, text='', filt=0, col=0, desc=False):
    if win.filter.currentIndex() != filt:
        win.filter.setCurrentIndex(filt)
    win.sort_col, win.sort_desc = col, desc
    hdr = win.view.header()
    hdr.blockSignals(True)
    hdr.setSortIndicator(col, Qt.DescendingOrder if desc else Qt.AscendingOrder)
    hdr.blockSignals(False)
    win.search.setText(text)
    win.timer.stop()
    win.searcher.prev = None
    win.do_search()
    win.view.clearSelection()
    win.view.setCurrentIndex(QModelIndex())
    win.view.scrollToTop()
    win.search.setFocus()
    win.search.setCursorPosition(len(text))
    win.search.deselect()
    spin(app, 0.4)


def warm(app, win, queries):
    cold = {}
    for q in queries:
        win.search.setText(q)
        win.timer.stop()
        win.searcher.prev = None
        win.do_search()
        cold[q] = round(win.search_ms, 1)
        app.processEvents()
        # second pass = warm numbers
    return cold


# ---------------------------------------------------------------- clip definitions
def A(x, y):
    return (float(x), float(y))


def clip_R1(r, win, app):
    """scene 'search': p04 starts at 0.600; '结果即刻呈现' at ~2.0; p05 at 3.98-7.0"""
    dur = 9.0
    sb = lambda: wcenter(win, win.search, fx=0.30)
    r.cur = A(900, 560)
    r.move(0.15, lambda: wcenter(win, win.search, fx=0.22), 0.5)
    r.click(0.62, 'click search box')
    end = r.type_text(1.62, '总体方案', cjk_gap=0.12, label='总体方案')
    # hover over results
    r.move(2.75, lambda: row_pt(win, 3, 300), 1.2)
    r.move(4.2, lambda: row_pt(win, 5, 420), 1.4)
    r.move(5.8, lambda: row_pt(win, 4, 380), 1.0)
    r.move(7.0, lambda: row_pt(win, 0, 300), 0.6)
    r.click(7.78, 'select row 1')
    r.dur = dur
    return dur, {'search': None}


def clip_R2(r, win, app):
    """clip t=0 = p07 start - 0.4s; length = p07 dur + 1.2"""
    dur = 4.571429 + 1.2
    r.cur = A(1330, 700)
    d = HOMEDIR + '/文档/汇报/'
    r.fs(1.0, 'touch 第三季度汇报_终稿.docx', lambda: (open(d + '第三季度汇报_终稿.docx', 'a').close(), os.utime(d + '第三季度汇报_终稿.docx', None)))
    r.fs(2.4, 'mv 第二季度汇报.pptx 第二季度汇报_定稿.pptx', lambda: os.rename(d + '第二季度汇报.pptx', d + '第二季度汇报_定稿.pptx'))
    r.fs(3.8, 'rm 季度汇报_草稿.docx', lambda: os.remove(d + '季度汇报_草稿.docx'))
    r.dur = dur
    return dur, {}


def clip_R3(r, win, app):
    """scene 'syntax' rel: p09 0.50, p10 3.336, p11 8.127; length 14.2"""
    dur = 14.2
    r.cur = A(1000, 500)
    r.move(0.8, lambda: wcenter(win, win.search, fx=0.25), 0.6)
    r.click(1.55, 'click search box')
    plan = [
        (3.05, '报告 2024', 0.055), (4.35, 'jpg|png', 0.055), (5.75, '报告 !草稿', 0.055),
        (7.75, '*.pdf', 0.03), (9.0, 'ext:docx;wps', 0.03), (10.2, 'size:>100mb', 0.03), (11.4, 'dm:today', 0.03),
    ]
    for t, q, dl in plan:
        r.select_all(t - 0.1)
        r.type_text(t, q, ascii_delay=dl, label=q)
    # light cursor drift over results
    r.move(6.4, lambda: row_pt(win, 3, 340), 0.9)
    r.move(8.9, lambda: row_pt(win, 5, 460), 1.0)
    r.move(11.8, lambda: row_pt(win, 2, 300), 1.2)
    r.dur = dur
    return dur, {}


def clip_R4(r, win, app):
    """scene 'filter' rel: p12 0.45 (文档 1.53, 图片 2.6, 视频 3.25, 点击表头 3.47, 即可排序 4.33); length 6.4"""
    dur = 6.4
    r.cur = A(900, 560)
    hdr = win.view.header()
    r.move(0.3, lambda: wcenter(win, win.filter, fx=0.5), 0.65)
    r.click(1.1, 'open filter combo')
    pv = lambda i: (lambda: popup_item_pt(win, i))
    r.move(1.5, pv(2), 0.35)      # 文档
    r.move(1.95, pv(3), 0.4)      # 图片
    r.click(2.55, 'select 图片')
    hsz = lambda: wcenter(win, hdr, QRect(hdr.sectionViewportPosition(2), 0, hdr.sectionSize(2), hdr.height()), fx=0.5)
    r.move(2.85, hsz, 0.55)
    r.click(3.5, 'header 大小 (asc)')
    r.click(4.4, 'header 大小 (desc)')
    r.move(5.0, lambda: row_pt(win, 3, 300), 0.8)
    r.dur = dur
    return dur, {}


def popup_item_pt(win, i):
    v = win.filter.view()
    r = v.visualRect(win.filter.model().index(i, 0))
    p = v.viewport().mapToGlobal(QPoint(r.x() + 60, r.center().y()))
    return (float(p.x()), float(p.y()))


def menu_item_pt(label_prefix):
    m = QApplication.activePopupWidget()
    from PyQt5.QtWidgets import QMenu
    for a in m.actions():
        if a.text().startswith(label_prefix):
            g = m.actionGeometry(a)
            p = m.mapToGlobal(QPoint(60, g.center().y()))
            return (float(p.x()), float(p.y()))
    return (float(m.x() + 60), float(m.y() + 20))


def clip_R5(r, win, app):
    """scene 'ops' rel: p13 0.45-5.28 (打开 0.87, 定位文件夹 1.53, 复制 2.82, 重命名 3.47, 一气呵成 4.33); length 6.08"""
    dur = 4.833 + 0.45 + 0.8
    r.cur = A(900, 560)
    r.move(0.0, lambda: row_pt(win, 1, 380), 0.5)
    r.rclick(0.55, 'right-click row 2')
    r.at(0.75, lambda: (r.ev('menu', 'context menu open'), r.extra_rects.__setitem__('menu', gmap(QApplication.activePopupWidget()))
                        if QApplication.activePopupWidget() else None))
    r.move(0.8, lambda: menu_item_pt('打开'), 0.3)
    r.move(1.45, lambda: menu_item_pt('打开所在文件夹'), 0.3)
    r.move(2.65, lambda: menu_item_pt('复制　'), 0.5)
    r.move(3.3, lambda: menu_item_pt('重命名'), 0.45)
    for t, lab in [(1.0, '打开'), (1.55, '打开所在文件夹'), (2.95, '复制'), (3.6, '重命名')]:
        r.at(t, (lambda lab=lab: (r.ev('hover', lab), r.extra_rects.__setitem__('hover_' + lab, menu_item_rect(lab)))))
    r.key_async(4.2, Qt.Key_Escape, label='Escape (close menu)')
    r.at(4.45, lambda: QTimer.singleShot(0, lambda: (r.ev('key', 'F2'), QTest.keyClick(win.view, Qt.Key_F2))))

    def dlg():
        d = QApplication.activeModalWidget()
        if d is not None:
            QApplication.setActiveWindow(d)
            r.ev('dialog', 'rename dialog')
            r.extra_rects['dialog'] = gmap(d)
            r.extra_rects['dialog_edit'] = gmap(d.findChild(qx.QLineEdit)) if d.findChild(qx.QLineEdit) else None
    r.at(4.75, dlg)
    r.key_async(5.65, Qt.Key_Escape, label='Escape (close dialog)')
    r.dur = dur
    return dur, {}


def menu_item_rect(prefix):
    m = QApplication.activePopupWidget()
    if m is None:
        return None
    for a in m.actions():
        if a.text().startswith(prefix):
            return gmap(m, m.actionGeometry(a))
    return None


CLIPS = {
    'R1': (clip_R1, {'query': '', 'queries': ['总体方案']}),
    'R2': (clip_R2, {'query': '季度汇报', 'queries': ['季度汇报']}),
    'R3': (clip_R3, {'query': '', 'queries': ['报告 2024', 'jpg|png', '报告 !草稿', '*.pdf', 'ext:docx;wps', 'size:>100mb', 'dm:today']}),
    'R4': (clip_R4, {'query': '2024', 'queries': ['2024']}),
    'R5': (clip_R5, {'query': '总体方案', 'queries': ['总体方案']}),
}


def r2_prepare():
    d = HOMEDIR + '/文档/汇报/'
    for f in ('第三季度汇报_终稿.docx', '第二季度汇报_定稿.pptx'):
        if os.path.exists(d + f):
            if f.startswith('第二'):
                os.rename(d + f, d + '第二季度汇报.pptx')
            else:
                os.remove(d + f)
    if not os.path.exists(d + '季度汇报_草稿.docx'):
        r2_restore_draft()


def r2_restore_draft():
    d = HOMEDIR + '/文档/汇报/'
    p = d + '季度汇报_草稿.docx'
    fd = os.open(p, os.O_WRONLY | os.O_CREAT)
    os.ftruncate(fd, 187432)
    os.close(fd)
    mt = time.mktime((2026, 10, 12, 16, 40, 0, 0, 0, -1))
    os.utime(p, (mt, mt))


def r2_restore():
    d = HOMEDIR + '/文档/汇报/'
    if os.path.exists(d + '第三季度汇报_终稿.docx'):
        os.remove(d + '第三季度汇报_终稿.docx')
    if os.path.exists(d + '第二季度汇报_定稿.pptx'):
        os.rename(d + '第二季度汇报_定稿.pptx', d + '第二季度汇报.pptx')
    if not os.path.exists(d + '季度汇报_草稿.docx'):
        r2_restore_draft()


def detect_marker(raw):
    """return index of first frame (after marker was seen) where marker is gone"""
    cmd = ['ffmpeg', '-v', 'error', '-i', raw, '-vf', 'crop=18:18:9:9,scale=1:1:flags=area', '-pix_fmt', 'rgb24',
           '-f', 'rawvideo', '-frames:v', '240', '-']
    data = subprocess.run(cmd, capture_output=True).stdout
    n = len(data) // 3
    on = [data[i * 3] > 170 and data[i * 3 + 1] < 90 and data[i * 3 + 2] < 90 for i in range(n)]
    first_on = next((i for i, v in enumerate(on) if v), None)
    if first_on is None:
        return None, None, n
    off = next((i for i in range(first_on, n) if not on[i]), None)
    return first_on, off, n


def record(name, app, win, index, engine):
    fn, spec = CLIPS[name]
    lock = REC + '/RECORDING.lock'
    r = Rec(app, win, index, engine)
    win.rec = r
    if not hasattr(win, '_orig_ds'):
        win._orig_ds = win.do_search
        def _ds(keep_view=False, _w=win):
            rr = getattr(_w, 'rec', None)
            res = _w._orig_ds(keep_view)
            if rr is not None and rr.T0 is not None:
                rr.ds_log.append((time.time(), _w.search.text(), _w.search_ms))
            return res
        win.do_search = _ds
        win.timer.timeout.disconnect()
        win.timer.timeout.connect(lambda: win.do_search())
    if name == 'R2':
        r2_prepare()
        spin(app, 1.0)
    # warm all queries (cold timing numbers), then reset UI
    reset_ui(app, win, '', 0)
    cold = warm(app, win, spec['queries'])
    # warm twice to settle caches
    cold2 = warm(app, win, spec['queries'])
    filt = 0
    reset_ui(app, win, spec['query'], filt)
    if name == 'R4':
        pass
    spin(app, 0.5)
    r.reset_clip()
    dur, extra = fn(r, win, app)
    rects = collect_rects(win)
    marker = QWidget()
    marker.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.X11BypassWindowManagerHint)
    marker.setStyleSheet('background:#e01010;')
    marker.setGeometry(0, 0, 24, 24)
    raw = '%s/%s_raw.mp4' % (REC, name)
    open(lock, 'w').write(str(os.getpid()))
    try:
        ff = start_ffmpeg(raw)
        spin(app, 1.0)
        marker.show()
        marker.raise_()
        spin(app, 0.7)
        # go
        r.dur = dur
        marker.hide()
        r.T0 = time.time()
        r.last_log = -1
        r.ev('start', 'clip start')
        tk = QTimer()
        tk.setInterval(3)
        tk.setTimerType(Qt.PreciseTimer)
        tk.timeout.connect(r.tick)
        tk.start()
        while not r.done:
            app.processEvents()
            time.sleep(0.002)
        tk.stop()
        spin(app, 0.5)
        rects_end = collect_rects(win)
        stats_line = stop_ffmpeg(ff)
    finally:
        if os.path.exists(lock):
            os.remove(lock)
        marker.close()
    print(name, 'ffmpeg:', stats_line, flush=True)
    # trim
    fo, off, nfr = detect_marker(raw)
    print(name, 'marker first_on=%s off=%s frames_scanned=%s' % (fo, off, nfr), flush=True)
    if off is None:
        raise RuntimeError('marker not found in %s' % raw)
    ss = off / float(FPS)
    out = '%s/%s.mp4' % (REC, name)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', raw, '-ss', '%.4f' % ss, '-t', '%.3f' % dur, '-c:v', 'libx264', '-preset', 'veryfast',
                    '-crf', '14', '-pix_fmt', 'yuv420p', '-r', str(FPS), '-an', out], check=True)
    # restore fs for R2 and let the app catch up
    if name == 'R2':
        r2_restore()
        spin(app, 1.8)
    pr = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', out], capture_output=True, text=True).stdout.strip()
    for e in r.search_ms:
        e['ms_full'] = cold2.get(e['q'])
    rects.update({k: v for k, v in r.extra_rects.items() if v})
    st_txt = win.lbl_state.text()
    js = {
        'fps': FPS, 'width': W, 'height': H, 'scale': SCALE, 'duration': round(dur, 3),
        'cursor': r.cursor_log, 'events': r.events, 'rects': rects,
        'stats': {'indexed': index.live, 'search_ms': r.search_ms, 'cold_ms': cold, 'warm_ms': cold2,
                  'status_text': st_txt, 'count_text_end': win.lbl_count.text()},
        'sync': {'marker_first_on_frame': fo, 'marker_off_frame': off, 'trim_ss': round(ss, 4)},
    }
    json.dump(js, open('%s/%s.json' % (REC, name), 'w'), ensure_ascii=False, indent=1)
    print(name, 'done: mp4 duration', pr, 'events', len(r.events), flush=True)
    os.remove(raw) if os.environ.get('KEEP_RAW') != '1' else None


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    if args[0] == 'prebuild':
        prebuild()
        return
    app, win, index, engine = build_app()
    ok = wait_engine_idle(engine, index, app, timeout=900)
    print('engine idle:', ok, 'live', index.live, 'status', engine.status, flush=True)
    spin(app, 1.0)
    for name in args:
        try:
            record(name, app, win, index, engine)
        except Exception:
            traceback.print_exc()
            if os.path.exists(REC + '/RECORDING.lock'):
                os.remove(REC + '/RECORDING.lock')
    engine.post('quit')
    engine.join(60)
    os._exit(0)


if __name__ == '__main__':
    main()
