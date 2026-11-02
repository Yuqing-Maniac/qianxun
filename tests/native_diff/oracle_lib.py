"""Windows-semantics oracle on top of the Python reference (qianxun.py): builds an Index of a Linux-side corpus
(WINEPREFIX/drive_c/<name>) using Windows paths (C:\\<name>\\...), and runs Query/Searcher with IS_WIN/SEP patched."""
import os
import sys
import tempfile
import time

os.environ.setdefault('TZ', 'Asia/Shanghai')
time.tzset()
_tmp = tempfile.mkdtemp(prefix='oracle_home_')
os.environ['XDG_CONFIG_HOME'] = os.path.join(_tmp, 'cfg')
os.environ['XDG_CACHE_HOME'] = os.path.join(_tmp, 'cache')
os.environ.setdefault('QIANXUN_QT', 'none')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'app'))
import qianxun as q  # noqa: E402


class WinMode(object):
    def __enter__(self):
        self.old = (q.IS_WIN, q.SEP)
        q.IS_WIN, q.SEP = True, '\\'
        return self

    def __exit__(self, *a):
        q.IS_WIN, q.SEP = self.old


def build_index(linux_root, win_root):
    """Walk linux_root without following symlinks. Returns (Index, symlink_win_paths).
    Symlink entries are NOT indexed (Wine presents them ambiguously: dir symlinks as DIRECTORY|REPARSE_POINT, broken
    ones not at all) -- the harness removes them from the native result and separately checks nothing below them is listed."""
    idx = q.Index()
    syml = []
    with WinMode():
        with idx.lock:
            ids = {linux_root: idx._new_dir(win_root, -1)}
            todo = [linux_root]
            while todo:
                d = todo.pop()
                did = ids[d]
                wd = idx.dirs[did]
                try:
                    st = os.stat(d)
                    idx.dir_mtime[did] = st.st_mtime
                except OSError:
                    pass
                with os.scandir(d) as it:
                    ents = sorted(it, key=lambda e: e.name)
                for e in ents:
                    wp = q.join_path(wd, e.name)
                    if e.is_symlink():
                        syml.append(wp)
                        continue
                    st = e.stat(follow_symlinks=False)
                    if e.is_dir(follow_symlinks=False):
                        i = idx._add_entry(did, e.name, True, -1, float(int(st.st_mtime)))
                        nd = idx._new_dir(wp, i)
                        ids[e.path] = nd
                        todo.append(e.path)
                    else:
                        idx._add_entry(did, e.name, False, st.st_size, float(int(st.st_mtime)))
            idx.version += 1
    return idx, syml


class _TimeShim(object):
    """module-like replacement for qianxun.time with a fixed time.time() (for relative dm: queries)."""

    def __init__(self, now):
        self._now = now

    def time(self):
        return self._now

    def __getattr__(self, k):
        return getattr(time, k)


def is_timesens(text):
    import re
    return re.search(r'dm:(last)?\d+(d|days?|w|weeks?|m|months?|y|years?)\b', text.lower()) is not None


def run_query(idx, qd, now=None):
    """qd: query dict. Returns (sorted list of full paths, error string or None). now: pretend wall clock (epoch s)."""
    if now is not None:
        old = q.time
        q.time = _TimeShim(now)
        try:
            return run_query(idx, qd)
        finally:
            q.time = old
    with WinMode():
        extra = q.FILTERS[qd.get('filter', 0)][1]
        Q = q.Query(qd['text'], case=qd.get('case', False), whole=qd.get('whole', False),
                    match_path=qd.get('path', False), regex=qd.get('regex', False), extra=extra)
        if Q.error:
            return [], Q.error
        S = q.Searcher(idx)
        S.case = qd.get('case', False)
        with idx.lock:
            res = S.run(Q, extra)
            paths = [idx.fullpath(i) for i in res if idx.kind[i] != q.KIND_DEAD]
    return paths, None


def sort_key(p):
    n = p.rsplit('\\', 1)[-1]
    return (n.lower(), p)
