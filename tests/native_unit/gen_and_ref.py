"""Generate a synthetic Windows-path listing + query list, and compute Python reference results
(qianxun.py Query/Searcher in WinMode)."""
import os, sys, random, time, itertools
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'win'))
os.environ.setdefault('QIANXUN_QT', 'none')
from win_common import q, WinMode

def gen(path, n=6000, seed=11):
    rnd = random.Random(seed)
    words = ['Users', '文档', 'Program Files', 'AppData', 'report', 'Report', '报告', '草稿', 'Photos', 'src', 'Data',
             'x64', 'ab', 'abc', 'Abc', 'IMG_', 'é', 'ß', 'tmp', 'a.b', 'ab.c', '[x]', 'a-b', 'x y', 'foo_bar',
             '会议纪要', 'Ünïcode', 'ＡＢＣ', '#hash', '!bang', 'a+b', '(1)', 'ver1.2']
    exts = ['txt', 'docx', 'pdf', 'PDF', 'exe', 'jpg', '', 'tar.gz', 'py', 'c', 'mp4', 'zip']
    now = int(time.time())
    lines = ['R\t\t\tC:\\', 'R\t\t\tD:\\']
    dirs = ['C:\\', 'D:\\']
    seen = set()
    count = 0
    while count < n:
        par = rnd.choice(dirs)
        if rnd.random() < 0.15:
            nm = rnd.choice(words) + ('' if rnd.random() < 0.5 else str(rnd.randint(0, 9)))
            full = q.join_path_sep(par, nm, '\\')
            if full.lower() in seen: continue
            seen.add(full.lower())
            mt = now - rnd.randint(0, 800) * 86400 - rnd.randint(0, 86399)
            lines.append('D\t-1\t%d\t%s' % (mt, full)); dirs.append(full)
        else:
            ext = rnd.choice(exts)
            nm = ''.join(rnd.choice(words) for _ in range(rnd.randint(1, 3))) + ('_' + str(rnd.randint(0, 99)) if rnd.random() < .5 else '') + ('.' + ext if ext else '')
            full = q.join_path_sep(par, nm, '\\')
            if full.lower() in seen: continue
            seen.add(full.lower())
            sz = rnd.choice([0, 5, 1023, 1024, 10240, 20000, 102400, 2 * 1024 ** 2, 50 * 1024 ** 2, 200 * 1024 ** 2])
            mt = now - rnd.choice([0, 0, 1, 3, 10, 40, 400]) * 86400 - rnd.randint(0, 86399)
            lines.append('F\t%d\t%d\t%s' % (sz, mt, full))
        count += 1
    # a few deletions
    files = [l for l in lines if l.startswith('F')]
    for l in rnd.sample(files, 30):
        lines.append('X\t\t\t' + l.split('\t')[3])
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

QUERIES = ['', '   ', '|', '||', '!', '!!', '! a', 'a | b', 'a |', '| a', '"x y"', '"a|b"', '"', '""',
    '*.pdf', 'r/*.pdf', '/r/*', '*/ab*', 'ext:', 'ext:;', 'ext:pdf;txt', 'ext:.PDF', 'ext:gz', 'size:', 'size:abc', 'size:>1mb',
    'size:1kb..', 'size:..1kb', 'size:<0', 'size:=1024', 'size:1kb', 'size:>=1023', 'size:<=1kb', 'size:1.5k..2mb',
    'size:empty', 'size:tiny', 'size:small', 'size:medium', 'size:large', 'size:huge', 'size:gigantic', 'size:1 mb', 'size:1e3',
    'dm:', 'dm:bad', 'dm:2026-13', 'dm:9999', 'dm:today', 'dm:yesterday', 'dm:thisweek', 'dm:thismonth', 'dm:thisyear',
    'dm:last7days', 'dm:2w', 'dm:last1y', 'dm:3m', 'dm:2025', 'dm:2026-10', 'dm:2025.1.2', 'dm:..2025', 'dm:2025..', 'dm:2025..2026-06',
    'regex:(', 'regex:a{4294967296}', 'regex:^ab', 'regex:\\d{2}\\.', 'regex:^[a-z]+$', 'regex:报告|草稿', 'regex:', 'regex:IMG_\\d',
    'file:', 'folder:', 'folder:"', 'file:"', 'path:', 'path:r/ab', 'path:报告', 'path:users\\文档', 'case:Abc', 'ww:ab', '!ext:pdf',
    'ab !ab', 'a{99999999999}', '\\', '[', '(?', '***', '?', '/', '//', 'é', 'ß', '报告 !草稿', 'Abc', 'ABC', 'abc',
    'users\\文档', 'users/文档', 'USERS/文档', 'c:\\users', 'd:/', '\\report', 'files\\', '"program files\\"',
    '"program files\\src"', 'c:\\*.exe', '*\\photos\\*.jpg', 'photos/*.jpg', 'appdata\\ !report', 'src\\|data\\',
    '[x]', '[x]*', '*[x]*', '[!a]*', '[a-c]*', '[]]*', '[!]*', '*[0-9].txt', '*[z-a]*', 'a-b', 'a+b', '(1)', '#hash', '!bang', '!!bang',
    'ver1.2', '.', '..', 'foo_bar', 'foo', 'bar', 'x y', '"x y" ab', 'ＡＢＣ', 'ａｂｃ', 'ünïcode', 'ÜNÏCODE', 'tar.gz', 'ext:tar.gz',
    'folder:report', 'file:report', 'dir:data', 'folder:*a*', 'file:*.pdf', 'folder:"x y"', 'ab abc', 'ab|abc|报告', '!ab|abc',
    'report size:>1mb', 'dm:today ext:pdf', 'ext:pdf|ext:txt', 'size:>1mb|size:<10', '!size:>1mb', '会议', '纪要 report',
    '*', '?b', 'a?', '*.', '*.*', 'C:', 'c:', 'C:\\', 'd:\\*', 'd:\\*\\*', '\\\\', 'nocase:ab', 'wholeword:report', 'foo:bar', 'Ext:PDF',
    'EXT:pdf', 'SIZE:>1MB', 'DM:TODAY', 'x　y', 'report　ab', 'ab\u3000abc']
OPTS = ['0000', '1000', '0100', '0010', '0001', '1100', '0110', '1010', '1001', '0011', '1111', '0101']

def queries(path):
    rnd = random.Random(5)
    out = []
    for o in OPTS:
        for t in QUERIES:
            out.append((o, 0, t))
    for t in QUERIES[::3]:
        for flt in range(1, 9):
            out.append(('0000', flt, t))
    # random incremental typing sequences
    alpha = ['a', 'b', 'c', 'A', ' ', 'r', 'e', 'p', 'o', '报', '告', '.', 'x', 'd', '|', '!', '*', '"', '/', 'ext:', '?']
    text = ''
    for i in range(1500):
        r = rnd.random()
        if r < 0.6: text += rnd.choice(alpha)
        elif r < 0.85: text = text[:-rnd.randint(1, 3)]
        else: text = ''
        out.append((rnd.choice(['0000', '0000', '1000', '0010', '0100']), rnd.choice([0, 0, 0, 2, 1]), text))
    with open(path, 'w', encoding='utf-8') as f:
        for o, flt, t in out:
            f.write('%s\t%d\t%s\n' % (o, flt, t))
    return out

def ref(listing, qfile, outp):
    with WinMode():
        idx = q.Index()
        with idx.lock:
            for line in open(listing, encoding='utf-8'):
                k, sz, mt, p = line.rstrip('\n').split('\t')
                if k == 'R': idx._new_dir(p, -1); continue
                par, nm = q.split_path_sep(p, '\\')
                d = idx.dir_ids[q.dkey(par)]
                if k == 'X':
                    for c in idx.dir_children[d]:
                        if idx.kind[c] != q.KIND_DEAD and idx.names[c] == nm:
                            idx._remove_entry(c, []); break
                    continue
                isd = k == 'D'
                i = idx._add_entry(d, nm, isd, -1 if isd else int(sz), float(mt))
                if isd: idx._new_dir(p, i)
        S = q.Searcher(idx)
        with open(outp, 'w', encoding='utf-8') as f:
            for n, line in enumerate(open(qfile, encoding='utf-8')):
                o, flt, t = line.rstrip('\n').split('\t', 2)
                extra = q.FILTERS[int(flt)][1]
                Q = q.Query(t, o[0] == '1', o[1] == '1', o[2] == '1', o[3] == '1', extra)
                S.case = o[0] == '1'
                with idx.lock:
                    r = S.run(Q, extra)
                ps = sorted(idx.fullpath(i) for i in r)
                f.write('Q%d %s count=%d\n' % (n, 'err' if Q.error else 'ok', len(ps)))
                for p in ps: f.write('  %s\n' % p)

if __name__ == '__main__':
    d = sys.argv[1]
    gen(os.path.join(d, 'listing.tsv'))
    queries(os.path.join(d, 'queries.tsv'))
    ref(os.path.join(d, 'listing.tsv'), os.path.join(d, 'queries.tsv'), os.path.join(d, 'ref.txt'))
