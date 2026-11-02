"""EngineWin (Windows engine) driven on Linux: real files in temp "drives", a fake ReadDirectoryChangesW watcher
fed with the events Windows would report, and injectable drive enumeration. Checks scan-with-stats, live
updates (incl. latency), unknown-parent events, renames/swaps, deletes, MODIFIED, excluded subtrees, overflow,
lost/released handles, drive add/remove, and cache reload with dynamic roots."""
import os
import shutil
import tempfile
import threading
import time

from win_common import q, check, done
from qa_common import disk_set, index_set

# Linux paths in this test: SEP stays '/', but the engine runs its Windows code paths.


class FakeWatcher(object):
    last = None

    def __init__(self):
        self.w = {}
        self.q = []
        self.fail = set()
        self.lock = threading.Condition()
        self.hwnd_getter = None
        FakeWatcher.last = self

    def add(self, did, path, dyn=False, network=False):
        if path in self.fail:
            return False
        self.w[did] = path
        return True

    def remove(self, did):
        self.w.pop(did, None)

    def push(self, *ev):
        with self.lock:
            self.q.append(ev)
            self.lock.notify_all()

    def read(self, timeout):
        # like WaitForMultipleObjects: return as soon as an event arrives
        with self.lock:
            if not self.q:
                self.lock.wait(timeout)
            ev, self.q = self.q, []
        return ev

    def close(self):
        self.w.clear()


class TEngine(q.EngineWin):
    watcher_factory = FakeWatcher

    def __init__(self, index, cfg, drives):
        q.EngineWin.__init__(self, index, cfg)
        self.drives = drives        # [(path, dynamic)]
        self.full_scans = 0

    def _root_pairs(self):
        return list(self.drives)

    def _drive_mask(self):
        return hash(tuple(self.drives))

    def _full_scan(self):
        self.full_scans += 1
        q.EngineWin._full_scan(self)


def mk(p, data=b''):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'wb') as f:
        f.write(data)


def want_set(roots, excluded=()):
    s = set()
    for r in roots:
        s |= disk_set(r, excluded)
    return s


def settle(idx, roots, timeout=5.0, excluded=()):
    t = time.time()
    while True:
        w, h = want_set(roots, excluded), index_set(idx)
        if w == h:
            return None
        if time.time() - t > timeout:
            return sorted(w - h)[:5], sorted(h - w)[:5]
        time.sleep(0.02)


def wait_for(cond, timeout=5.0):
    t = time.time()
    while time.time() - t < timeout:
        if cond():
            return time.time() - t
        time.sleep(0.01)
    return None


base = tempfile.mkdtemp(prefix='qx_engwin_')
A, B, C = (os.path.join(base, n) for n in ('驱动器A', 'drive B', 'driveC'))
for r in (A, B, C):
    os.makedirs(r)
for i in range(30):
    mk(os.path.join(A, '项目%d' % (i % 5), 'sub%d' % (i % 3), '报告_%d.docx' % i), b'x' * i)
    mk(os.path.join(B, 'd%d' % (i % 4), 'f%d.txt' % i), b'y' * (i * 3))
mk(os.path.join(A, 'skip', 'secret.txt'))
mk(os.path.join(C, 'usb', 'photo.jpg'), b'z' * 1234)
os.symlink(A, os.path.join(A, 'loop'))   # link loop must not be followed

cfg = dict(q.DEFAULT_CONFIG)
cfg.update(roots=[], excludes=[os.path.join(A, 'skip')], index_removable=True)
EXC = {os.path.join(A, 'skip')}
q.INDEX_FILE = os.path.join(base, 'cache', 'index.db')

idx = q.Index()
idx.win_stats = True
eng = TEngine(idx, cfg, [(A, False), (B, False)])
eng.start()
check('ready', wait_for(lambda: eng.status.get('state') == 'ready', 20) is not None)
check('scan matches disk', settle(idx, [A, B], excluded=EXC) is None, settle(idx, [A, B], 0.1, EXC))
with idx.lock:
    stats_ok = all(idx.mtime[i] > 0 and (idx.size[i] >= 0 or idx.kind[i] == q.KIND_DIR)
                   for i in range(len(idx.names)) if idx.kind[i] != q.KIND_DEAD)
    sz = {idx.fullpath(i): idx.size[i] for i in range(len(idx.names)) if idx.kind[i] == q.KIND_FILE}
check('scan filled size/mtime without stat sweep', stats_ok and eng.sweep_iter is None)
check('sizes correct', all(sz[p] == os.lstat(p).st_size for p in sz))
W = FakeWatcher.last
rA, rB = idx.dir_ids[A], idx.dir_ids[B]
check('one watch per root', sorted(W.w) == sorted([rA, rB]))
check('status full coverage', eng.status['watched'] == eng.status['dirs'] > 0, eng.status)
check('symlink loop not followed', os.path.join(A, 'loop', '项目0') not in index_set(idx))


def ev(root, act, p):
    W.push(idx.dir_ids[root], act, os.path.relpath(p, root))


# live create — latency measured from the event to visibility in the index
p = os.path.join(A, '项目1', '新建文件.txt')
mk(p, b'hello')
t0 = time.time()
ev(A, q.FILE_ACTION_ADDED, p)
lat = wait_for(lambda: p in index_set(idx), 3)
check('create visible (%.2f s)' % (lat or -1), lat is not None and lat < 1.0)
# new subtree, only the deepest event (parent not indexed yet)
p = os.path.join(A, '新目录', '深层', 'deep.txt')
mk(p)
ev(A, q.FILE_ACTION_ADDED, p)
check('unknown-parent event refreshes nearest ancestor', settle(idx, [A, B], excluded=EXC) is None)
# rename dir
os.rename(os.path.join(A, '项目2'), os.path.join(A, '改名项目2'))
ev(A, q.FILE_ACTION_RENAMED_OLD_NAME, os.path.join(A, '项目2'))
ev(A, q.FILE_ACTION_RENAMED_NEW_NAME, os.path.join(A, '改名项目2'))
check('rename dir', settle(idx, [A, B], excluded=EXC) is None)
# swap two dirs within the debounce window (names stay, contents swap)
d0, d1, tmp = (os.path.join(B, n) for n in ('d0', 'd1', 'tmp'))
os.rename(d0, tmp)
os.rename(d1, d0)
os.rename(tmp, d1)
for a, b in ((d0, tmp), (d1, d0), (tmp, d1)):
    ev(B, q.FILE_ACTION_RENAMED_OLD_NAME, a)
    ev(B, q.FILE_ACTION_RENAMED_NEW_NAME, b)
check('swap dirs', settle(idx, [A, B], excluded=EXC) is None, settle(idx, [A, B], 0.1, EXC))
# delete tree (Windows reports children too)
victim = os.path.join(A, '项目3')
kids = [os.path.join(dp, f) for dp, dn, fn in os.walk(victim) for f in fn + dn]
shutil.rmtree(victim)
for k in kids:
    ev(A, q.FILE_ACTION_REMOVED, k)
ev(A, q.FILE_ACTION_REMOVED, victim)
check('delete tree', settle(idx, [A, B], excluded=EXC) is None)
# MODIFIED on file → size; MODIFIED on directory ignored
f = os.path.join(B, 'd2', 'f2.txt')
mk(f, b'q' * 7777)
ev(B, q.FILE_ACTION_MODIFIED, f)
ev(B, q.FILE_ACTION_MODIFIED, os.path.join(B, 'd2'))


def size_of(path):
    with idx.lock:
        d = idx.dir_ids[os.path.dirname(path)]
        for c in idx.dir_children[d]:
            if idx.names[c] == os.path.basename(path):
                return idx.size[c]
check('modified size', wait_for(lambda: size_of(f) == 7777, 3) is not None, size_of(f))
# events inside an excluded subtree are ignored (not indexed, no crash)
s2 = os.path.join(A, 'skip', 'more', 'x.txt')
mk(s2)
ev(A, q.FILE_ACTION_ADDED, s2)
time.sleep(0.8)
check('excluded subtree ignored', s2 not in index_set(idx) and settle(idx, [A, B], excluded=EXC) is None)
# overflow: change things silently, then report overflow for root B
mk(os.path.join(B, 'silent', 's.txt'))
os.remove(os.path.join(B, 'd3', 'f3.txt'))
W.push(rB, q.WATCH_OVERFLOW, '')
check('overflow catch-up', settle(idx, [A, B], excluded=EXC) is None)
# lost handle while root still exists → re-watched after hold, with catch-up
W.push(rB, q.WATCH_LOST, '')
check('lost unwatched', wait_for(lambda: rB not in W.w, 2) is not None)
mk(os.path.join(B, 'during_gap.txt'))
check('lost re-watched', wait_for(lambda: rB in W.w, 8) is not None)
check('gap caught up', settle(idx, [A, B], excluded=EXC) is None)
# released for safe removal → held off
W.push(rB, q.WATCH_LOST, 'released')
check('released not re-watched immediately', wait_for(lambda: rB not in W.w, 2) is not None and
      wait_for(lambda: rB in W.w, 3) is None)
# drive removed
eng.drives = [(A, False)]
check('drive removed', wait_for(lambda: B not in idx.dir_ids, 6) is not None)
check('drive removed: entries gone', settle(idx, [A], excluded=EXC) is None and eng.roots == [A])
# drive added (dynamic)
eng.drives = [(A, False), (C, True)]
check('drive added', wait_for(lambda: C in idx.dir_ids, 6) is not None)
check('drive added: scanned', settle(idx, [A, C], excluded=EXC) is None)
check('drive added: watched', wait_for(lambda: idx.dir_ids.get(C) in W.w, 3) is not None)
check('header excludes dynamic root', eng._header()['roots'] == [A], eng._header())
eng.post('quit')
eng.join(10)
check('saved cache', os.path.exists(q.INDEX_FILE))

# restart with the USB drive gone → cache still valid (header has only fixed roots), USB subtree dropped
idx2 = q.Index()
idx2.win_stats = True
eng2 = TEngine(idx2, cfg, [(A, False)])
t0 = time.time()
eng2.start()
check('reload ready', wait_for(lambda: eng2.status.get('state') == 'ready', 20) is not None)
load_s = time.time() - t0
check('reload used cache (%.2f s)' % load_s, eng2.full_scans == 0)
check('reload dropped absent dynamic root', settle(idx2, [A], excluded=EXC) is None and C not in idx2.dir_ids)
eng2.post('quit')
eng2.join(10)
# restart with the USB drive present again → cache valid, USB root rescanned
idx3 = q.Index()
idx3.win_stats = True
eng3 = TEngine(idx3, cfg, [(A, False), (C, True)])
eng3.start()
check('reload2 ready', wait_for(lambda: eng3.status.get('state') == 'ready', 20) is not None)
check('reload2 cache + new dynamic root', eng3.full_scans == 0 and settle(idx3, [A, C], excluded=EXC) is None)
# watcher unavailable → status says so and polling covers everything
eng3.post('quit')
eng3.join(10)


class Broken(object):
    def __init__(self):
        raise OSError('no RDCW')


class TEngine2(TEngine):
    watcher_factory = Broken


idx4 = q.Index()
idx4.win_stats = True
eng4 = TEngine2(idx4, cfg, [(A, False)])
eng4.start()
check('no watcher: ready', wait_for(lambda: eng4.status.get('state') == 'ready', 20) is not None)
check('no watcher: status', eng4.status.get('inotify') is False and eng4.status.get('watched') == 0)
eng4.post('quit')
eng4.join(10)
shutil.rmtree(base, ignore_errors=True)
done()
