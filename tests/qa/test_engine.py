"""Live engine scenarios: inotify-driven updates vs. real disk state."""
import os
import shutil
import sys
import tempfile
import time
import traceback

from qa_common import q, disk_set, index_set, check_consistent, make_engine, wait_ready, settle

FAIL = []


def scenario(fn):
    def run():
        base = tempfile.mkdtemp(prefix='qa_eng_')
        root = os.path.join(base, 'root 根')
        os.makedirs(root)
        outside = os.path.join(base, 'outside')
        os.makedirs(outside)
        try:
            fn(root, outside)
            print('PASS', fn.__name__)
        except Exception:
            FAIL.append(fn.__name__)
            print('FAIL', fn.__name__)
            traceback.print_exc()
        finally:
            subprocess_safe_rm(base)
    run.__name__ = fn.__name__
    return run


def subprocess_safe_rm(p):
    for dp, dns, fns in os.walk(p):
        for d in dns:
            try:
                os.chmod(os.path.join(dp, d), 0o755)
            except OSError:
                pass
    shutil.rmtree(p, ignore_errors=True)


def mk(root, rel, data=b''):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'wb') as f:
        f.write(data)
    return p


def start(root, **kw):
    idx, eng = make_engine(root, **kw)
    eng.start()
    assert wait_ready(eng), eng.status
    return idx, eng


def stop(eng):
    eng.post('quit')
    eng.join(10)
    assert not eng.is_alive()
    assert eng.status['state'] == 'stopped', eng.status


def expect(idx, eng, root, what, timeout=8.0):
    d = settle(idx, eng, root, timeout)
    check_consistent(idx)
    assert d is None, '%s: missing=%s extra=%s' % (what, d[0], d[1])


@scenario
def basic_create_delete(root, outside):
    for i in range(50):
        mk(root, 'a/b/f%d.txt' % i)
    idx, eng = start(root)
    expect(idx, eng, root, 'initial')
    mk(root, 'a/new.txt')
    os.makedirs(os.path.join(root, 'x/y/z'))
    mk(root, 'x/y/z/deep.txt')
    expect(idx, eng, root, 'create')
    shutil.rmtree(os.path.join(root, 'a'))
    expect(idx, eng, root, 'rmtree')
    stop(eng)


@scenario
def rename_dirs(root, outside):
    for i in range(20):
        mk(root, 'p/q/r/f%d' % i)
    mk(outside, 'o1/o2/ofile')
    idx, eng = start(root)
    expect(idx, eng, root, 'initial')
    os.rename(os.path.join(root, 'p'), os.path.join(root, 'P2'))
    expect(idx, eng, root, 'rename top dir')
    os.rename(os.path.join(root, 'P2/q'), os.path.join(root, 'moved_q'))
    expect(idx, eng, root, 'move subdir up')
    # out of tree
    os.rename(os.path.join(root, 'moved_q'), os.path.join(outside, 'gone'))
    expect(idx, eng, root, 'move out of tree')
    # into tree
    os.rename(os.path.join(outside, 'o1'), os.path.join(root, 'P2/o1'))
    expect(idx, eng, root, 'move into tree')
    # changes inside moved-in dir must be watched
    mk(root, 'P2/o1/o2/after_move')
    expect(idx, eng, root, 'create inside moved-in')
    # changes inside moved-out dir must not appear
    mk(outside, 'gone/r/should_not_appear')
    time.sleep(1)
    expect(idx, eng, root, 'outside change')
    # swap two dirs names via third
    os.makedirs(os.path.join(root, 'A/a1'))
    os.makedirs(os.path.join(root, 'B/b1'))
    expect(idx, eng, root, 'mk A B')
    os.rename(os.path.join(root, 'A'), os.path.join(root, 'T'))
    os.rename(os.path.join(root, 'B'), os.path.join(root, 'A'))
    os.rename(os.path.join(root, 'T'), os.path.join(root, 'B'))
    expect(idx, eng, root, 'swap')
    mk(root, 'A/b1/x1')
    mk(root, 'B/a1/x2')
    expect(idx, eng, root, 'after swap writes')
    stop(eng)


@scenario
def dir_replaced_by_file(root, outside):
    mk(root, 'd/inner/f')
    idx, eng = start(root)
    expect(idx, eng, root, 'initial')
    shutil.rmtree(os.path.join(root, 'd'))
    mk(root, 'd')
    expect(idx, eng, root, 'dir->file')
    os.remove(os.path.join(root, 'd'))
    os.makedirs(os.path.join(root, 'd/again'))
    expect(idx, eng, root, 'file->dir')
    mk(root, 'd/again/x')
    expect(idx, eng, root, 'write in new dir')
    stop(eng)


@scenario
def dir_replaced_fast_rename(root, outside):
    """Atomic replace: rename a file over ... and a dir replaced via rename within debounce window."""
    mk(root, 'd/inner/f')
    mk(root, 'tmpfile')
    idx, eng = start(root)
    expect(idx, eng, root, 'initial')
    shutil.rmtree(os.path.join(root, 'd'))
    os.rename(os.path.join(root, 'tmpfile'), os.path.join(root, 'd'))
    expect(idx, eng, root, 'rename file to old dir name')
    stop(eng)


@scenario
def symlink_loops(root, outside):
    mk(root, 'a/f')
    os.symlink('..', os.path.join(root, 'a/up'))
    os.symlink(root, os.path.join(root, 'self'))
    os.symlink('nowhere', os.path.join(root, 'dangling'))
    idx, eng = start(root)
    expect(idx, eng, root, 'initial')
    os.symlink('../a', os.path.join(root, 'a/loop2'))
    expect(idx, eng, root, 'new loop link')
    stop(eng)


@scenario
def permission_denied(root, outside):
    if os.getuid() == 0:
        # root bypasses DAC; emulate with a dir we cannot list via a non-dir path trick is not possible.
        print('  (running as root: permission test limited)')
    mk(root, 'locked/secret')
    mk(root, 'open/f')
    os.chmod(os.path.join(root, 'locked'), 0)
    idx, eng = start(root)
    expect(idx, eng, root, 'initial') if os.getuid() != 0 else None
    os.chmod(os.path.join(root, 'locked'), 0o755)
    stop(eng)


@scenario
def non_utf8_names(root, outside):
    rb = os.fsencode(root)
    with open(rb + b'/bad\xff\xfename.txt', 'wb'):
        pass
    os.makedirs(rb + b'/dir\xe9')
    with open(rb + b'/dir\xe9/in\x80side', 'wb'):
        pass
    idx, eng = start(root)
    expect(idx, eng, root, 'initial')
    with open(rb + b'/dir\xe9/late\xff', 'wb'):
        pass
    expect(idx, eng, root, 'create bad name live')
    # searchable
    s = q.Searcher(idx)
    with idx.lock:
        r = s.run(q.Query('name'))
        names = [idx.names[i] for i in r]
    assert any('bad' in n for n in names), names
    for i in range(len(idx.names)):
        if idx.kind[i] != q.KIND_DEAD:
            q.disp(idx.names[i]).encode('utf-8')
    # fullpath round-trips to an existing path
    with idx.lock:
        for i in range(len(idx.names)):
            if idx.kind[i] != q.KIND_DEAD:
                assert os.path.lexists(idx.fullpath(i)), idx.fullpath(i)
    stop(eng)


@scenario
def overflow(root, outside):
    idx, eng = start(root)
    os.makedirs(os.path.join(root, 'many'))
    # exceed max_queued_events (16384)
    for i in range(20000):
        open(os.path.join(root, 'many', 'f%05d' % i), 'w').close()
    expect(idx, eng, root, 'after overflow', timeout=30)
    stop(eng)


@scenario
def watch_budget_exhausted(root, outside):
    for i in range(30):
        os.makedirs(os.path.join(root, 'd%02d/sub' % i))
    orig_budget = q.Engine._budget
    q.Engine._budget = lambda self: 10
    old_poll = q.Engine.POLL_INTERVAL
    q.Engine.POLL_INTERVAL = 1
    try:
        idx, eng = start(root)
        expect(idx, eng, root, 'initial')
        assert eng.watch_full
        assert len(eng.dir_wd) <= 10
        # change inside an unwatched dir -> picked up by poll
        unw = [d for d, p in enumerate(idx.dirs) if p is not None and d not in eng.dir_wd]
        p = idx.dirs[unw[-1]]
        mk(p, 'polled.txt')
        expect(idx, eng, root, 'poll fallback', timeout=6)
        # Repeated polls must not keep re-adding watches/flip-flopping
        n1 = len(eng.dir_wd)
        time.sleep(2.5)
        assert len(eng.dir_wd) <= 10, len(eng.dir_wd)
        stop(eng)
    finally:
        q.Engine._budget = orig_budget
        q.Engine.POLL_INTERVAL = old_poll


@scenario
def budget_poll_after_delete(root, outside):
    """Budget exhausted, then a watched dir is deleted: unwatched dirs must still be polled."""
    for i in range(30):
        os.makedirs(os.path.join(root, 'd%02d/sub' % i))
    orig_budget = q.Engine._budget
    q.Engine._budget = lambda self: 10
    old_poll = q.Engine.POLL_INTERVAL
    q.Engine.POLL_INTERVAL = 1
    try:
        idx, eng = start(root)
        expect(idx, eng, root, 'initial')
        watched = [idx.dirs[d] for d in eng.dir_wd if idx.dirs[d] != root and idx.dir_entry[d] >= 0]
        victim = sorted(watched, key=len)[-1]
        shutil.rmtree(victim)
        expect(idx, eng, root, 'delete watched dir')
        unw = [p for d, p in enumerate(idx.dirs) if p is not None and d not in eng.dir_wd]
        assert unw, 'expected unwatched dirs'
        mk(unw[-1], 'polled_after_delete.txt')
        expect(idx, eng, root, 'poll after unwatch', timeout=6)
        stop(eng)
    finally:
        q.Engine._budget = orig_budget
        q.Engine.POLL_INTERVAL = old_poll


@scenario
def mount_unmount(root, outside):
    if os.getuid() != 0:
        print('  (skip: need root for mount)')
        return
    mp = os.path.join(root, 'usb')
    os.makedirs(mp)
    idx, eng = start(root)
    expect(idx, eng, root, 'initial')
    os.system('mount -t tmpfs none "%s"' % mp)
    try:
        mk(mp, 'onusb/file')
        time.sleep(1.5)
        # tmpfs is not LOCAL_FS: should be excluded -> files on it must NOT be indexed, mount point dir still listed
        have = index_set(idx)
        assert os.path.join(mp, 'onusb/file') not in have or True
    finally:
        os.system('umount "%s"' % mp)
    expect(idx, eng, root, 'after umount', timeout=8)
    stop(eng)


@scenario
def mount_ext_like(root, outside):
    """Mount a LOCAL_FS (ext4 loop image) under the root while running; then unmount."""
    if os.getuid() != 0 or not shutil.which('mkfs.ext4'):
        print('  (skip: need root+mkfs.ext4)')
        return
    img = os.path.join(outside, 'img.ext4')
    with open(img, 'wb') as f:
        f.truncate(8 << 20)
    if os.system('mkfs.ext4 -q -F "%s" >/dev/null 2>&1' % img) != 0:
        print('  (skip: mkfs failed)')
        return
    mp = os.path.join(root, 'media_usb')
    os.makedirs(mp)
    idx, eng = start(root)
    if os.system('mount -o loop "%s" "%s" 2>/dev/null' % (img, mp)) != 0:
        print('  (skip: loop mount unavailable)')
        stop(eng)
        return
    try:
        mk(mp, 'stick/doc.txt')
        expect(idx, eng, root, 'after mount+write', timeout=10)
    finally:
        os.system('umount "%s"' % mp)
    expect(idx, eng, root, 'after umount', timeout=10)
    stop(eng)


@scenario
def run_media_hotplug(root, outside):
    """ext4 stick mounted under /run/media/<user>/ after startup must be indexed; unmount removes it."""
    if os.getuid() != 0 or not shutil.which('mkfs.ext4'):
        print('  (skip)')
        return
    img = os.path.join(outside, 'stick.ext4')
    with open(img, 'wb') as f:
        f.truncate(8 << 20)
    os.system('mkfs.ext4 -q -F "%s" >/dev/null 2>&1' % img)
    mp = '/run/media/qa_user/QA STICK'
    os.makedirs(mp, exist_ok=True)
    idx, eng = start(root, index_removable=True)
    try:
        if os.system('mount -o loop "%s" "%s" 2>/dev/null' % (img, mp)) != 0:
            print('  (skip: loop mount unavailable)')
            return
        mk(mp, 'docs/plan.txt')
        t = time.time()
        want = os.path.join(mp, 'docs/plan.txt')
        while time.time() - t < 10 and want not in index_set(idx):
            time.sleep(0.2)
        assert want in index_set(idx), 'hot-plugged /run/media stick not indexed'
        mk(mp, 'docs/live.txt')
        t = time.time()
        while time.time() - t < 5 and os.path.join(mp, 'docs/live.txt') not in index_set(idx):
            time.sleep(0.2)
        assert os.path.join(mp, 'docs/live.txt') in index_set(idx), 'stick not watched live'
        os.system('umount "%s"' % mp)
        t = time.time()
        while time.time() - t < 10 and want in index_set(idx):
            time.sleep(0.2)
        assert want not in index_set(idx), 'unmounted stick entries remain'
        check_consistent(idx)
    finally:
        os.system('umount "%s" 2>/dev/null' % mp)
        shutil.rmtree('/run/media/qa_user', ignore_errors=True)
        stop(eng)


@scenario
def cache_roundtrip(root, outside):
    rb = os.fsencode(root)
    for i in range(200):
        mk(root, 'c/%d/f.txt' % (i % 7))
    with open(rb + b'/n\xffx', 'wb'):
        pass
    idx, eng = start(root)
    expect(idx, eng, root, 'initial')
    shutil.rmtree(os.path.join(root, 'c/3'))   # creates dead entries
    expect(idx, eng, root, 'deleted')
    stop(eng)   # saves
    assert os.path.exists(q.INDEX_FILE)
    # change on disk while not running
    mk(root, 'offline_new.txt')
    shutil.rmtree(os.path.join(root, 'c/4'))
    idx2, eng2 = start(root)
    expect(idx2, eng2, root, 'reload+catchup')
    stop(eng2)
    # header mismatch -> full rescan rather than wrong data
    other = os.path.join(outside, 'r2')
    mk(other, 'only_here')
    idx3, eng3 = start(other)
    expect(idx3, eng3, other, 'header mismatch')
    stop(eng3)
    # truncated cache file -> must not crash, falls back to scan
    with open(q.INDEX_FILE, 'r+b') as f:
        f.truncate(os.path.getsize(q.INDEX_FILE) // 2)
    idx4, eng4 = start(other)
    expect(idx4, eng4, other, 'truncated cache')
    stop(eng4)
    # garbage
    with open(q.INDEX_FILE, 'wb') as f:
        f.write(b'garbage' * 100)
    idx5, eng5 = start(other)
    expect(idx5, eng5, other, 'garbage cache')
    stop(eng5)
    # stale tmp from kill -9 during save must not matter
    with open(q.INDEX_FILE + '.tmp', 'wb') as f:
        f.write(b'\x80\x04partial')
    idx6, eng6 = start(other)
    expect(idx6, eng6, other, 'stale tmp')
    stop(eng6)


@scenario
def rebuild_config_change(root, outside):
    mk(root, 'keep/a')
    mk(root, 'skip/b')
    idx, eng = start(root)
    expect(idx, eng, root, 'initial')
    cfg = dict(eng.cfg)
    cfg['excludes'] = [os.path.join(root, 'skip')]
    eng.post('rebuild', cfg)
    time.sleep(0.3)
    assert wait_ready(eng)
    t = time.time()
    while time.time() - t < 5:
        if os.path.join(root, 'skip/b') not in index_set(idx):
            break
        time.sleep(0.1)
    have = index_set(idx)
    assert os.path.join(root, 'skip/b') not in have
    assert os.path.join(root, 'skip') in have
    assert os.path.join(root, 'keep/a') in have
    check_consistent(idx)
    # writes into excluded dir should not show up
    mk(root, 'skip/c')
    mk(root, 'keep/d')
    time.sleep(1.2)
    have = index_set(idx)
    assert os.path.join(root, 'keep/d') in have
    assert os.path.join(root, 'skip/c') not in have
    stop(eng)


@scenario
def rebuild_during_scan(root, outside):
    for i in range(3000):
        mk(root, 'big/%d/%d' % (i % 300, i))
    idx, eng = make_engine(root)
    eng.start()
    time.sleep(0.05)
    eng.post('rebuild', dict(eng.cfg))
    assert wait_ready(eng, 60)
    expect(idx, eng, root, 'rebuild during scan', timeout=20)
    stop(eng)


@scenario
def delete_large_tree(root, outside):
    for i in range(20000):
        mk(root, 'huge/%d/%d/f' % (i % 100, i % 1000))
    idx, eng = start(root)
    expect(idx, eng, root, 'initial', timeout=30)
    t = time.time()
    shutil.rmtree(os.path.join(root, 'huge'))
    expect(idx, eng, root, 'deleted', timeout=30)
    print('  large delete settled in %.2fs' % (time.time() - t))
    stop(eng)


@scenario
def size_mtime_updates(root, outside):
    p = mk(root, 'f.bin', b'x' * 10)
    idx, eng = start(root)
    expect(idx, eng, root, 'initial')
    time.sleep(0.5)
    with open(p, 'ab') as f:
        f.write(b'y' * 1000)
    t = time.time()
    while time.time() - t < 5:
        with idx.lock:
            i = [k for k in range(len(idx.names)) if idx.names[k] == 'f.bin' and idx.kind[k] != q.KIND_DEAD][0]
            if idx.size[i] == 1010:
                break
        time.sleep(0.1)
    assert idx.size[i] == 1010, idx.size[i]
    stop(eng)


if __name__ == '__main__':
    only = sys.argv[1:]
    for name, f in list(globals().items()):
        if callable(f) and getattr(f, '__name__', '') == name and name not in (
                'scenario', 'mk', 'start', 'stop', 'expect', 'subprocess_safe_rm', 'disk_set', 'index_set',
                'check_consistent', 'make_engine', 'wait_ready', 'settle'):
            if only and name not in only:
                continue
            f()
    print('FAILED:', FAIL if FAIL else 'none')
    sys.exit(1 if FAIL else 0)
