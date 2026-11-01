"""Search semantics with Windows paths (IS_WIN/SEP switched): backslash and slash path terms, drive-anchored
wildcards, case-insensitive dir lookups. Cross-checks every query against brute-force full-path evaluation."""
import fnmatch
import random

from win_common import q, check, done, WinMode

with WinMode():
    idx = q.Index()
    rnd = random.Random(7)
    words = ['Users', '文档', 'Program Files', 'AppData', 'report', '报告', 'Photos', 'src', 'Data', 'x64']
    exts = ['txt', 'docx', 'pdf', 'exe', 'jpg', '']
    with idx.lock:
        roots = [idx._new_dir('C:\\', -1), idx._new_dir('D:\\', -1)]
        dirs = list(roots)
        while len(idx.names) < 6000:
            par = rnd.choice(dirs)
            if rnd.random() < 0.15:
                nm = rnd.choice(words) + ('' if rnd.random() < 0.5 else str(rnd.randint(0, 9)))
                full = q.join_path(idx.dirs[par], nm)
                if q.dkey(full) in idx.dir_ids:
                    continue
                e = idx._add_entry(par, nm, True)
                dirs.append(idx._new_dir(full, e))
            else:
                ext = rnd.choice(exts)
                nm = rnd.choice(words) + '_' + str(rnd.randint(0, 99)) + ('.' + ext if ext else '')
                idx._add_entry(par, nm, False)

    def full(i):
        return idx.fullpath(i)

    def brute(pred):
        return sorted(i for i in range(len(idx.names)) if idx.kind[i] != q.KIND_DEAD and pred(full(i)))

    S = q.Searcher(idx)

    def run(text, **kw):
        Q = q.Query(text, **kw)
        S.prev = None
        with idx.lock:
            return sorted(S.run(Q))

    cases = [
        ('users\\文档', lambda p: 'users\\文档' in p.lower()),
        ('users/文档', lambda p: 'users\\文档' in p.lower()),
        ('USERS/文档', lambda p: 'users\\文档' in p.lower()),
        ('c:\\users', lambda p: p.lower().startswith('c:\\users')),
        ('d:/', lambda p: p.lower().startswith('d:\\')),
        ('\\report_1', lambda p: '\\report_1' in p.lower()),
        ('files\\', lambda p: 'files\\' in p.lower()),
        ('"program files\\"', lambda p: 'program files\\' in p.lower()),
        ('"program files\\src"', lambda p: 'program files\\src' in p.lower()),
        ('c:\\*.exe', lambda p: fnmatch.fnmatchcase(p.lower(), 'c:\\*.exe')),
        ('*\\photos\\*.jpg', lambda p: fnmatch.fnmatchcase(p.lower(), '*\\photos\\*.jpg')),
        ('photos/*.jpg', lambda p: fnmatch.fnmatchcase(p.lower(), '*photos\\*.jpg')),
        ('path:报告', lambda p: '报告' in p.lower()),
        ('appdata\\ !report', lambda p: 'appdata\\' in p.lower() and 'report' not in p.lower().rsplit('\\', 1)[1]),
        ('src\\|data\\', lambda p: 'src\\' in p.lower() or 'data\\' in p.lower()),
    ]
    for text, pred in cases:
        got, want = run(text), brute(pred)
        check('search %r (%d hits)' % (text, len(want)), got == want and len(want) > 0,
              'got %d want %d' % (len(got), len(want)))
    # match_path option with a plain word, and a name-only search (no separator) is not a path search
    got = run('报告', match_path=True)
    check('match_path plain', got == brute(lambda p: '报告' in p.lower()))
    got = run('报告')
    check('name-only plain', got == brute(lambda p: '报告' in p.rsplit('\\', 1)[1].lower()))
    # backslash in a term on Windows marks it as a path term; dir_prefixes end with the separator
    dp = idx.dir_prefixes(True)
    check('dir_prefixes win', dp[roots[0]] == 'c:\\' and all(d.endswith('\\') for d in dp if d))
    # case-insensitive dir lookup & highlight
    k = next(d for d in idx.dirs if d and d.count('\\') >= 2)
    check('dir_ids case-insensitive', q.dkey(k.upper()) in idx.dir_ids)
    Q = q.Query('users\\文档')
    check('highlight last component', Q.highlights == ['文档'], Q.highlights)
    # remove_root keeps invariants
    removed = idx.remove_root(roots[1])
    ok = all(idx.dirs[d] is not None and q.dkey(idx.dirs[d]) == k for k, d in idx.dir_ids.items())
    ok = ok and all(idx.dirs[idx.parent[i]] is not None for i in range(len(idx.names)) if idx.kind[i] != q.KIND_DEAD)
    ok = ok and sum(1 for k in idx.kind if k != q.KIND_DEAD) == idx.live
    check('remove_root invariants', ok)
    check('remove_root', idx.dirs[roots[1]] is None and 'd:\\' not in idx.dir_ids and len(removed) >= 1 and
          not run('d:\\'))

# Linux semantics unchanged: a backslash is not a path separator on Linux
Q = q.Query('a\\b')
check('linux backslash not path', not Q.groups[0][1][0].path)
Q = q.Query('a/b')
check('linux slash is path', Q.groups[0][1][0].path)
done()
