"""Query/Searcher: syntax edge cases + property test (incremental vs fresh results)."""
import os
import random
import re
import sys
import time

from qa_common import q

FAIL = []


def build_index(n_files=4000, seed=1):
    rnd = random.Random(seed)
    idx = q.Index()
    words = ['ab', 'abc', 'Abc', 'b', 'report', 'Report', '报告', '草稿', 'x y', 'a|b', 'data', 'Data', 'img',
             'IMG_', 'é', 'ß', 'İ', 'tmp', 'a.b', 'ab.c']
    exts = ['txt', 'pdf', 'PDF', 'docx', 'c', '', 'tar.gz', 'py']
    with idx.lock:
        root = idx._new_dir('/r', -1)
        dirs = [root]
        for k in range(200):
            par = rnd.choice(dirs)
            name = rnd.choice(words) + str(rnd.randint(0, 9)) + rnd.choice(['', 'Dir', '_d'])
            full = q.join_path(idx.dirs[par], name)
            if full in idx.dir_ids:
                continue
            e = idx._add_entry(par, name, True)
            dirs.append(idx._new_dir(full, e))
        for k in range(n_files):
            par = rnd.choice(dirs)
            nm = ''.join(rnd.choice(words) for _ in range(rnd.randint(1, 3)))
            ext = rnd.choice(exts)
            name = nm + ('.' + ext if ext else '')
            if rnd.random() < 0.01:
                name = os.fsdecode(b'bad\xff' + os.fsencode(name))
            i = idx._add_entry(par, name, False)
            idx.size[i] = rnd.choice([0, 5, 1024, 20000, 2 * 1024 ** 2, 50 * 1024 ** 2])
            idx.mtime[i] = time.time() - rnd.randint(0, 400) * 86400
        for i in range(len(idx.names)):
            if idx.mtime[i] < 0:
                idx.size[i] = -1
                idx.mtime[i] = time.time()
        # some dead entries
        removed = []
        for i in rnd.sample(range(len(idx.names)), 50):
            idx._remove_entry(i, removed)
        idx.version += 1
    return idx


def ref_match(idx, i, text, case, whole, path, regex, extra):
    """Naive reference implementation, independent of Searcher code paths."""
    Q = q.Query(text, case, whole, path, regex, extra)
    if Q.error:
        return None
    s = q.Searcher(idx)
    s.case = case
    return Q


def fresh(idx, text, opts, extra):
    case, whole, path, regex = opts
    Q = q.Query(text, case, whole, path, regex, extra)
    s = q.Searcher(idx)
    s.case = case
    with idx.lock:
        return sorted(s.run(Q, extra))


def brute(idx, text, opts, extra):
    """Evaluate a Query predicate-by-predicate per entry with no candidate narrowing at all."""
    case, whole, path, regex = opts
    Q = q.Query(text, case, whole, path, regex, extra)
    if Q.error:
        return []
    s = q.Searcher(idx)
    s.case = case
    out = []
    alive = [i for i in range(len(idx.names)) if idx.kind[i] != q.KIND_DEAD]
    sets = []
    for neg, alts in Q.groups:
        hit = set()
        for a in alts:
            hit.update(s._filter(a, list(alive)))
        sets.append((neg, hit))
    for i in alive:
        ok = True
        for neg, hit in sets:
            if (i in hit) == neg:
                ok = False
                break
        if ok:
            out.append(i)
    return out


def test_syntax_edges():
    idx = build_index(500)
    s = q.Searcher(idx)
    cases = ['', '   ', '|', '||', '!', '!!', '! a', 'a | b', 'a |', '| a', '"x y"', '"a|b"', '"', '""',
             '*.pdf', 'r/*.pdf', '/r/*', '*/ab*', 'ext:', 'ext:;', 'ext:pdf;txt', 'size:', 'size:abc', 'size:>1mb',
             'size:1kb..', 'size:..1kb', 'size:<0', 'dm:', 'dm:bad', 'dm:2026-13', 'dm:9999', 'dm:today',
             'dm:last7days', 'dm:2025', 'regex:(', 'regex:a{4294967296}', 'regex:' + '(' * 300 + 'a' + ')' * 300,
             'file:', 'folder:', 'folder:"', 'file:"', 'path:', 'path:r/ab', 'case:Abc', 'ww:ab', '!ext:pdf',
             'ab !ab', 'a{99999999999}', '\\', '[', '(?', '***', '?', '/', '//', 'é', 'İ', 'ß', '报告 !草稿',
             os.fsdecode(b'bad\xff')]
    for regex in (False, True):
        for whole in (False, True):
            for case in (False, True):
                for path in (False, True):
                    for t in cases:
                        try:
                            Q = q.Query(t, case, whole, path, regex, None)
                            with idx.lock:
                                s.case = case
                                r = s.run(Q)
                            assert isinstance(r, list)
                        except Exception as e:
                            FAIL.append(('syntax', t, case, whole, path, regex, repr(e)))
    print('syntax edges done, failures so far:', len(FAIL))


def test_semantics():
    idx = build_index(500)
    s = q.Searcher(idx)

    def run(t, **kw):
        Q = q.Query(t, **kw)
        with idx.lock:
            s.case = kw.get('case', False)
            return set(s.run(Q))
    alive = set(i for i in range(len(idx.names)) if idx.kind[i] != q.KIND_DEAD)
    assert run('') == alive
    assert run('   ') == alive
    assert run('a | b') == run('a|b')
    assert run('ab !ab') == set()
    assert run('folder:') == set(i for i in alive if idx.kind[i] == q.KIND_DIR)
    assert run('file:') == set(i for i in alive if idx.kind[i] == q.KIND_FILE)
    if not run('folder:"') <= set(i for i in alive if idx.kind[i] == q.KIND_DIR): FAIL.append('folder:" ignores kind')
    # set(i for i in alive if idx.kind[i] == q.KIND_DIR), 'folder:" ignores kind'
    r = run('ext:pdf')
    assert r and all(idx.lnames[i].endswith('.pdf') for i in r)
    assert run('ext:PDF') == r
    assert all('Abc' in idx.names[i] for i in run('Abc', case=True))
    assert run('Abc', case=True) < run('abc')
    print('semantics ok')


def test_property(iters=3000, seed=7):
    idx = build_index(4000, seed)
    rnd = random.Random(seed)
    alphabet = ['a', 'b', 'c', 'A', 'B', ' ', 'r', 'e', 'p', 'o', 't', '报', '告', '.', 'x', 'd', 'I', 'é',
                '|', '!', '*', '"', '/', 'ext:', 'size:>1kb', 'folder:', '?']
    plain_alpha = [c for c in alphabet if c not in ('|', '!', '*', '"', '/', '?') and ':' not in c]
    s = q.Searcher(idx)
    text = ''
    opts = [False, False, False, False]
    filt = 0
    mism = 0
    for it in range(iters):
        r = rnd.random()
        if r < 0.55:
            text += rnd.choice(plain_alpha if rnd.random() < 0.85 else alphabet)
        elif r < 0.8:
            text = text[:-rnd.randint(1, 3)]
        elif r < 0.86:
            k = rnd.randrange(4)
            opts[k] = not opts[k]
        elif r < 0.9:
            filt = rnd.randrange(len(q.FILTERS))
        elif r < 0.95:
            # index changes between keystrokes
            with idx.lock:
                live = [i for i in range(len(idx.names)) if idx.kind[i] != q.KIND_DEAD and idx.kind[i] == q.KIND_FILE]
                if live and rnd.random() < 0.5:
                    idx._remove_entry(rnd.choice(live), [])
                else:
                    d = rnd.choice([d for d, p in enumerate(idx.dirs) if p is not None])
                    idx._add_entry(d, rnd.choice(['abc', 'rep', 'x.pdf', 'Abc d']) + str(it), False)
                    idx.size[-1] = 10
                    idx.mtime[-1] = time.time()
                idx.version += 1
        else:
            text = ''
        extra = q.FILTERS[filt][1]
        case, whole, path, regex = opts
        if regex:
            if rnd.random() < 0.5:
                opts[3] = False
                regex = False
        Q = q.Query(text, case, whole, path, regex, extra)
        with idx.lock:
            s.case = case
            got = sorted(s.run(Q, extra))
            # simulate the GUI mutating the returned list in place (sort/reverse) as _sorted does
        exp = fresh(idx, text, tuple(opts), extra)
        if got != exp:
            mism += 1
            if mism <= 5:
                FAIL.append(('incremental', repr(text), tuple(opts), filt, len(got), len(exp)))
        if it % 300 == 0:
            b = sorted(brute(idx, text, tuple(opts), extra))
            if b != exp:
                FAIL.append(('brute', repr(text), tuple(opts), filt, len(b), len(exp)))
    print('property: %d iterations, %d mismatches' % (iters, mism))


def test_incremental_with_gui_sort():
    """GUI sorts / reverses / replaces the returned list; cached prev results must stay a valid superset."""
    idx = build_index(3000, 3)
    s = q.Searcher(idx)
    seq = ['a', 'ab', 'abc', 'ab', 'a', 'r', 're', 'rep', 'repo']
    for t in seq:
        Q = q.Query(t)
        with idx.lock:
            r = s.run(Q)
            r.sort(key=idx.lnames.__getitem__)
            r.reverse()
            del_ok = sorted(r)
        assert del_ok == fresh(idx, t, (False,) * 4, None), t
    print('incremental+gui sort ok')


def test_size_date_parse():
    for v, ok in [('>1mb', True), ('1.5k', True), ('', False), ('abc', False), ('1..', True), ('..', True),
                  ('>=', False), ('1 mb', True), ('1e3', False), ('-5', False)]:
        try:
            q.size_range(v)
            res = True
        except ValueError:
            res = False
        if res != ok:
            FAIL.append(('size_range', v, res))
    for v in ['today', 'yesterday', 'thisweek', 'thismonth', 'thisyear', 'last3days', '2w', '2026', '2026-10',
              '2026-12', '2026-10-17', '2026.1.2', '..2026', '2025..2026']:
        try:
            a, b = q.date_range(v)
            assert a <= b, v
        except Exception as e:
            FAIL.append(('date_range', v, repr(e)))


if __name__ == '__main__':
    test_syntax_edges()
    test_semantics()
    test_size_date_parse()
    test_incremental_with_gui_sort()
    test_property(int(sys.argv[1]) if len(sys.argv) > 1 else 3000)
    for f in FAIL[:40]:
        print('FAIL', f)
    print('TOTAL FAIL', len(FAIL))
    sys.exit(1 if FAIL else 0)
