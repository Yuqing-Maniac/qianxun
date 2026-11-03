"""Shared helpers for QianXun QA tests (no Qt needed)."""
import os
import sys
import time
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'app')
sys.path.insert(0, APP)

_tmp_home = tempfile.mkdtemp(prefix='qa_home_')
os.environ['XDG_CONFIG_HOME'] = os.path.join(_tmp_home, 'cfg')
os.environ['XDG_CACHE_HOME'] = os.path.join(_tmp_home, 'cache')

import qianxun as q  # noqa: E402


def disk_set(root, excluded=()):
    """All paths below root (not following symlinks), like the index should contain."""
    out = set()
    for dp, dns, fns in os.walk(root, followlinks=False):
        keep = []
        for d in dns:
            full = os.path.join(dp, d)
            out.add(full)
            if full in excluded or os.path.islink(full):
                continue
            keep.append(d)
        dns[:] = keep
        for f in fns:
            out.add(os.path.join(dp, f))
    return out


def index_set(idx):
    with idx.lock:
        return set(idx.fullpath(i) for i in range(len(idx.names)) if idx.kind[i] != q.KIND_DEAD)


def check_consistent(idx):
    """Internal invariants of Index."""
    idx.ensure_children()
    idx.ensure_lnames()
    with idx.lock:
        n = len(idx.names)
        assert n == len(idx.lnames) == len(idx.parent) == len(idx.kind) == len(idx.size) == len(idx.mtime)
        nd = len(idx.dirs)
        assert nd == len(idx.dir_entry) == len(idx.dir_mtime) == len(idx.dir_children)
        live = sum(1 for k in idx.kind if k != q.KIND_DEAD)
        assert live == idx.live, (live, idx.live)
        for p, d in idx.dir_ids.items():
            assert idx.dirs[d] == p
        for e, d in idx.entry_dir.items():
            assert idx.kind[e] == q.KIND_DIR, ('entry_dir points to non-dir', e, idx.kind[e])
            assert idx.dirs[d] is not None
            assert idx.fullpath(e) == idx.dirs[d], (idx.fullpath(e), idx.dirs[d])
        for i in range(n):
            if idx.kind[i] != q.KIND_DEAD:
                assert idx.dirs[idx.parent[i]] is not None, ('live entry in dead dir', i, idx.names[i])
        # children lists contain only own entries
        for d in range(nd):
            for c in idx.dir_children[d]:
                assert idx.parent[c] == d


def make_engine(root, **cfg_over):
    cfg = dict(q.DEFAULT_CONFIG)
    cfg.update(roots=[root], excludes=[], index_removable=False)
    cfg.update(cfg_over)
    idx = q.Index()
    eng = q.Engine(idx, cfg)
    return idx, eng


def wait_ready(eng, timeout=30):
    t = time.time()
    while time.time() - t < timeout:
        if eng.status.get('state') == 'ready':
            return True
        time.sleep(0.05)
    return False


def settle(idx, eng, root, timeout=8.0, excluded=()):
    """Wait until index matches disk (returns diff on timeout)."""
    t = time.time()
    while True:
        want = disk_set(root, excluded)
        want.add(root) if False else None
        have = index_set(idx)
        if have == want:
            return None
        if time.time() - t > timeout:
            return (sorted(want - have)[:10], sorted(have - want)[:10])
        time.sleep(0.1)
