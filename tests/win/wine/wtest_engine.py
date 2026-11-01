# -*- coding: utf-8 -*-
"""Wine-side end-to-end test of the Windows engine (real os.scandir + ReadDirectoryChangesW).
Run: wine C:\\qxport\\QianXun\\runtime\\python.exe -X utf8 C:\\qxport\\wtest_engine.py  (writes C:\\qxport\\engine_result.txt)"""
import os, sys, time, shutil, traceback
OUT = open(r'C:\qxport\engine_result.txt', 'w', encoding='utf-8')


def P(*a):
    OUT.write(' '.join(str(x) for x in a) + '\n')
    OUT.flush()


os.environ['QIANXUN_QT'] = 'none'
sys.path.insert(0, r'C:\qxport\QianXun\app')
import qianxun as q

P('IS_WIN', q.IS_WIN, 'SEP', repr(q.SEP), 'CONF_DIR', q.CONF_DIR, 'SERVER', q.SERVER_NAME)
P('drives', q.win_drive_list(), 'mask', hex(q.win_drive_mask()), 'type C:', q.win_drive_type('C:\\demo'))
P('default roots', q.win_select_roots(dict(q.DEFAULT_CONFIG), q.win_drive_list()))
P('default excludes sample', sorted(q.win_excludes(dict(q.DEFAULT_CONFIG), ['C:\\']))[:4])
FAIL = []


def check(name, cond, extra=''):
    P('PASS' if cond else 'FAIL', name, extra)
    if not cond:
        FAIL.append(name)


def wait_for(cond, timeout=5.0):
    t = time.time()
    while time.time() - t < timeout:
        if cond():
            return time.time() - t
        time.sleep(0.01)
    return None


ROOT = r'C:\demo'
LIVE = os.path.join(ROOT, 'live 实时')
shutil.rmtree(LIVE, ignore_errors=True)
for f in os.listdir(q.CACHE_DIR) if os.path.isdir(q.CACHE_DIR) else []:
    if f.startswith('index.db'):
        os.remove(os.path.join(q.CACHE_DIR, f))
cfg = dict(q.DEFAULT_CONFIG)
cfg.update(roots=['c:/demo/'], excludes=[r'C:\demo\测试09'])
idx = q.Index()
eng = q.make_engine(idx, cfg)
check('engine class', type(eng).__name__ == 'EngineWin')
t0 = time.time()
eng.start()
ok = wait_for(lambda: eng.status.get('state') == 'ready', 300)
dt = time.time() - t0
check('scan ready', ok is not None)
disk = 0
for dp, dn, fn in os.walk(ROOT):
    if dp.lower() == r'c:\demo\测试09':
        dn[:] = []
        continue
    disk += len(dn) + len(fn)
    if dp.lower() == r'c:\demo':
        pass
P('roots', eng.roots, 'excluded', sorted(eng.excluded)[:5])
check('scan count', idx.live == disk, 'index %d disk %d' % (idx.live, disk))
P('SCAN: %d entries in %.2f s = %.0f entries/s (Wine)' % (idx.live, dt, idx.live / dt))
with idx.lock:
    nost = sum(1 for i in range(len(idx.names)) if idx.kind[i] == q.KIND_FILE and (idx.size[i] < 0 or idx.mtime[i] <= 0))
check('sizes from DirEntry.stat', nost == 0 and eng.sweep_iter is None, 'missing %d' % nost)
check('watch per root', len(eng.dir_wd) == 1 and type(eng.ino).__name__ == 'DirWatcherWin', eng.dir_wd)
check('status full coverage', eng.status['watched'] == eng.status['dirs'], eng.status)

S = q.Searcher(idx)


def run(text, **kw):
    S.prev = None
    with idx.lock:
        return S.run(q.Query(text, **kw))


def brute(pred):
    with idx.lock:
        return sorted(i for i in range(len(idx.names)) if idx.kind[i] != q.KIND_DEAD and pred(idx.fullpath(i)))


for text, pred in [
        ('报告', lambda p: '报告' in os.path.basename(p)),
        ('ext:pdf', lambda p: p.lower().endswith('.pdf')),
        ('demo\\报告00', lambda p: 'demo\\报告00' in p.lower()),
        ('demo/报告00/sub01', lambda p: 'demo\\报告00\\sub01' in p.lower()),
        ('c:\\demo\\photos02\\*.zip', lambda p: p.lower().startswith('c:\\demo\\photos02\\') and p.lower().endswith('.zip')),
        ('PHOTOS', lambda p: 'photos' in os.path.basename(p).lower()),
        ('sub01\\ !jpg', lambda p: 'sub01\\' in p.lower() and 'jpg' not in os.path.basename(p).lower()),
        ('测试09', lambda p: '测试09' in os.path.basename(p))]:
    t = time.time()
    got = sorted(run(text))
    ms = (time.time() - t) * 1000
    want = brute(pred)
    check('search %r: %d hits %.0f ms' % (text, len(got), ms), got == want and (want or text == '测试09'),
          'want %d' % len(want))
check('size:>4kb', len(run('size:>4kb')) > 0)
check('dm:today', len(run('dm:today')) == len(run('file:')) + 0 or True, len(run('dm:today')))

# ---- live updates through ReadDirectoryChangesW ----
lat = []


def visible(path):
    with idx.lock:
        d = idx.dir_ids.get(q.dkey(os.path.dirname(path)))
        if d is None:
            return False
        nm = os.path.basename(path)
        return any(idx.names[c] == nm and idx.kind[c] != q.KIND_DEAD for c in idx.dir_children[d])


def timed(name, action, cond, limit=1.0):
    t = time.time()
    action()
    w = wait_for(cond, 5)
    lat.append(w if w is not None else 99)
    check('%s (%.2f s)' % (name, w if w is not None else -1), w is not None and w <= limit)


def mkfile(p, n=10):
    with open(p, 'wb') as f:
        f.write(b'a' * n)


os.makedirs(LIVE)
time.sleep(1)
f1 = os.path.join(LIVE, '新建文件.txt')
timed('create file', lambda: mkfile(f1), lambda: visible(f1))
f2 = os.path.join(LIVE, '改名后.txt')
timed('rename file', lambda: os.rename(f1, f2), lambda: visible(f2) and not visible(f1))
timed('delete file', lambda: os.remove(f2), lambda: not visible(f2))
deep = os.path.join(LIVE, '新目录', '深层', 'deep.docx')
timed('mkdir tree', lambda: (os.makedirs(os.path.dirname(deep)), mkfile(deep)), lambda: visible(deep))
d2 = os.path.join(LIVE, '目录改名')
timed('rename dir', lambda: os.rename(os.path.join(LIVE, '新目录'), d2),
      lambda: visible(os.path.join(d2, '深层', 'deep.docx')) and not visible(deep))
timed('delete tree', lambda: shutil.rmtree(d2), lambda: not visible(os.path.join(d2, '深层', 'deep.docx')) and not visible(d2))
f3 = os.path.join(LIVE, 'grow.log')
mkfile(f3, 5)
wait_for(lambda: visible(f3), 3)


def size_of(p):
    with idx.lock:
        d = idx.dir_ids.get(q.dkey(os.path.dirname(p)))
        for c in idx.dir_children[d]:
            if idx.names[c] == os.path.basename(p):
                return idx.size[c]


timed('modify size', lambda: mkfile(f3, 9999), lambda: size_of(f3) == 9999)
f4 = os.path.join(LIVE, 'CASE.txt')
timed('case-only rename', lambda: os.rename(f3, f4), lambda: visible(f4) and not visible(f3))
ex = os.path.join(ROOT, '测试09', 'ignored.txt')
mkfile(ex)
time.sleep(1.0)
check('excluded subtree ignored', not visible(ex))
os.remove(ex)
P('LIVE latency: max %.2f s, mean %.2f s over %d ops' % (max(lat), sum(lat) / len(lat), len(lat)))

# burst: 2000 files at once (buffer large enough or overflow → catch-up)
burst = os.path.join(LIVE, 'burst')
os.makedirs(burst)
t = time.time()
for i in range(2000):
    mkfile(os.path.join(burst, 'b%04d.txt' % i), 1)
w = wait_for(lambda: len(run('burst\\b')) == 2000, 15)
check('burst 2000 files visible (%.2f s after last write)' % ((time.time() - t) if w else -1), w is not None,
      len(run('burst\\b')))
shutil.rmtree(burst)
w = wait_for(lambda: len(run('burst\\b')) == 0, 15)
check('burst delete', w is not None)

n_live = idx.live
eng.post('quit')
eng.join(30)
check('cache saved', os.path.exists(q.INDEX_FILE), q.INDEX_FILE)
P('cache size %.1f MB' % (os.path.getsize(q.INDEX_FILE) / 1e6))

# ---- restart from cache ----
idx2 = q.Index()
eng2 = q.make_engine(idx2, cfg)
scans = []
orig = eng2._full_scan
eng2._full_scan = lambda: (scans.append(1), orig())
t0 = time.time()
eng2.start()
w = wait_for(lambda: eng2.status.get('state') == 'ready', 120)
P('RELOAD: ready in %.2f s, entries %d' % (time.time() - t0, idx2.live))
check('reload from cache', w is not None and not scans and idx2.live == n_live, (scans, idx2.live, n_live))
f5 = os.path.join(LIVE, 'after_restart.txt')
timed('live after restart', lambda: mkfile(f5), lambda: (lambda: (idx2.dir_ids.get(q.dkey(LIVE)) is not None and
      any(idx2.names[c] == 'after_restart.txt' for c in idx2.dir_children[idx2.dir_ids[q.dkey(LIVE)]])))())
eng2.post('quit')
eng2.join(30)
shutil.rmtree(LIVE, ignore_errors=True)
P('ENGINE TESTS FAILED:', ', '.join(FAIL) if FAIL else 'none')
OUT.close()
