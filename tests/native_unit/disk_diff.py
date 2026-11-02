"""Differential test on a real directory tree: native CLI (--batch, under Wine) vs qianxun.py Query/Searcher
(WinMode) fed with an os.walk of the same tree mapped to Z:\\ paths."""
import os, sys, random, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_and_ref as G
q, WinMode = G.q, G.WinMode

def make_tree(root, n=2500, seed=3):
    rnd = random.Random(seed)
    words = ['Users', '文档', 'Program Files', 'AppData', 'report', 'Report', '报告', '草稿', 'Photos', 'src', 'Data',
             'x64', 'ab', 'abc', 'IMG_', 'é', 'ß', 'tmp', 'a.b', 'ab.c', '[x]', 'a-b', 'x y', 'foo_bar', '会议纪要',
             'Ünïcode', 'ＡＢＣ', '#hash', '!bang', 'a+b', '(1)', 'ver1.2', "it's", 'semi;colon', '😀emoji']
    exts = ['txt', 'docx', 'pdf', 'PDF', 'exe', 'jpg', '', 'tar.gz', 'py', 'c', 'mp4', 'zip']
    if os.path.exists(root):
        subprocess.call(['rm', '-rf', root])
    os.makedirs(root)
    dirs = [root]; seen = set()
    now = time.time()
    for i in range(n):
        par = rnd.choice(dirs)
        if rnd.random() < 0.15:
            nm = rnd.choice(words) + ('' if rnd.random() < 0.5 else str(rnd.randint(0, 9)))
        else:
            ext = rnd.choice(exts)
            nm = ''.join(rnd.choice(words) for _ in range(rnd.randint(1, 3))) + ('.' + ext if ext else '')
        full = os.path.join(par, nm)
        if full.lower() in seen or len(full) > 200: continue
        seen.add(full.lower())
        if rnd.random() < 0.15:
            os.mkdir(full); dirs.append(full)
        else:
            with open(full, 'wb') as f:
                f.write(b'x' * rnd.choice([0, 5, 1024, 20000, 150000, 2 * 1024 ** 2]))
        mt = now - rnd.choice([0, 0, 1, 3, 10, 40, 400]) * 86400 - rnd.randint(0, 86399)
        os.utime(full, (mt, mt))

WINE = os.environ.get('QX_WINE', '/usr/lib/wine/wine64')
def to_win(p, root, wroot):
    return wroot + p[len(root):].replace('/', '\\')

def reference(root, wroot, qfile, out):
    with WinMode():
        idx = q.Index()
        with idx.lock:
            rd = idx._new_dir(wroot, -1)
            ids = {root: rd}
            for dp, dns, fns in os.walk(root):
                d = ids[dp]
                for nm in sorted(dns) + sorted(fns):
                    full = os.path.join(dp, nm)
                    st = os.lstat(full)
                    isd = os.path.isdir(full)
                    i = idx._add_entry(d, nm, isd, -1 if isd else st.st_size, st.st_mtime)
                    if isd:
                        ids[full] = idx._new_dir(to_win(full, root, wroot), i)
        S = q.Searcher(idx)
        with open(out, 'w', encoding='utf-8') as f:
            for n, line in enumerate(open(qfile, encoding='utf-8')):
                o, flt, t = line.rstrip('\n').split('\t', 2)
                extra = q.FILTERS[int(flt)][1]
                Q = q.Query(t, o[0] == '1', o[1] == '1', o[2] == '1', o[3] == '1', extra)
                S.case = o[0] == '1'
                S.prev = None
                with idx.lock:
                    r = S.run(Q, extra)
                ps = sorted(idx.fullpath(i) for i in r)
                f.write('Q%d %s count=%d\n' % (n, 'err' if Q.error else 'ok', len(ps)))
                for p in ps: f.write('  %s\n' % p)

if __name__ == '__main__':
    S = sys.argv[1]
    root = os.path.join(S, 'disktree')
    wroot = 'Z:' + root.replace('/', '\\')
    make_tree(root)
    qs = []
    for o in ['0000', '1000', '0100', '0010', '0001', '0110']:
        for t in G.QUERIES: qs.append((o, 0, t))
    for t in G.QUERIES[::4]:
        for flt in range(1, 9): qs.append(('0000', flt, t))
    qf = os.path.join(S, 'dq.tsv')
    with open(qf, 'w', encoding='utf-8') as f:
        for o, flt, t in qs: f.write('%s\t%d\t%s\n' % (o, flt, t))
    reference(root, wroot, qf, os.path.join(S, 'dref.txt'))
    env = dict(os.environ, WINEPREFIX=os.environ.get('QX_PREFIX', os.path.join(os.environ.get('QX_WORK', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '_work')), 'wine', 'qianxun64')), WINEDEBUG='-all', LC_ALL='C.UTF-8')
    t0 = time.time()
    rc = subprocess.call([WINE, sys.argv[2], '--cli', '--root', wroot, '--batch', 'Z:' + qf.replace('/', '\\'),
                          '--out', 'Z:' + os.path.join(S, 'dcpp.txt').replace('/', '\\')], env=env)
    print('cli rc', rc, 'time %.1fs' % (time.time() - t0))
    def parse(fn):
        res = []
        for l in open(fn, encoding='utf-8'):
            if l.startswith('Q'): res.append([l.split()[1], set()])
            else: res[-1][1].add(l.rstrip('\n')[2:])
        return res
    a, b = parse(os.path.join(S, 'dref.txt')), parse(os.path.join(S, 'dcpp.txt'))
    bad = 0
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            bad += 1
            if bad <= 20:
                print('MISMATCH', i, qs[i], x[0], len(x[1]), y[0], len(y[1]), 'py-only', sorted(x[1] - y[1])[:2], 'c-only', sorted(y[1] - x[1])[:2])
    print('queries', len(a), len(b), 'mismatches', bad, 'entries', len(a[0][1]))
