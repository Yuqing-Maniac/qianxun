"""~1M synthetic entries: per-keystroke search latency, sort by size/date, name_order merge."""
import random
import sys
import time

from qa_common import q

N = int(sys.argv[1]) if len(sys.argv) > 1 else 1000000
rnd = random.Random(5)
words = ['report', 'data', 'img', 'lib', 'test', 'config', 'readme', 'main', 'util', 'backup', '报告', '会议纪要',
         'src', 'build', 'cache', 'log', 'photo', 'video', 'doc', 'temp']
exts = ['txt', 'pdf', 'docx', 'c', 'h', 'py', 'so', 'png', 'jpg', 'log', 'json', 'xml', '']
idx = q.Index()
t = time.time()
with idx.lock:
    dirs = [idx._new_dir('/', -1)]
    while len(idx.names) < N:
        if rnd.random() < 0.08 or len(dirs) < 50:
            par = rnd.choice(dirs)
            nm = rnd.choice(words) + str(rnd.randint(0, 999))
            full = q.join_path(idx.dirs[par], nm)
            if full in idx.dir_ids:
                continue
            e = idx._add_entry(par, nm, True)
            dirs.append(idx._new_dir(full, e))
        else:
            par = rnd.choice(dirs)
            e = rnd.choice(exts)
            nm = '%s_%s%d%s' % (rnd.choice(words), rnd.choice(words), rnd.randint(0, 99999), '.' + e if e else '')
            i = idx._add_entry(par, nm, False)
            idx.size[i] = rnd.randint(0, 1 << 30)
            idx.mtime[i] = 1.6e9 + rnd.randint(0, 1 << 26)
    for i in range(len(idx.names)):
        if idx.mtime[i] < 0:
            idx.mtime[i] = 1.6e9
print('built %d entries / %d dirs in %.1fs' % (len(idx.names), len(idx.dirs), time.time() - t))
eng = type('E', (), {'index': idx})()
t = time.time()
q.Engine._compute_order(eng)
print('compute_order %.2fs' % (time.time() - t))

s = q.Searcher(idx)
s.case = False


def timed(text, **kw):
    Q = q.Query(text, **kw)
    t = time.time()
    with idx.lock:
        r = s.run(Q, kw.get('extra'))
    return (time.time() - t) * 1000, len(r)


print('--- typing "report_data" (incremental)')
ms_all = []
for k in range(1, len('report_data') + 1):
    ms, n = timed('report_data'[:k])
    ms_all.append(ms)
    print('  %-12r %7.1f ms  %8d hits' % ('report_data'[:k], ms, n))
for text in ['报告', 'ext:pdf', '*.pdf', 'src/', 'size:>500mb', 'dm:2026', 'report|photo', 'report !data', 'regex:^img_',
             'path:lib', 'folder:']:
    s.prev = None
    ms, n = timed(text)
    print('  fresh %-14r %7.1f ms %8d hits' % (text, ms, n))
s.prev = None
for opt in ('match_path', 'whole'):
    ms, n = timed('report', **{opt: True})
    print('  %-10s report  %7.1f ms %8d' % (opt, ms, n))

# sorting cost (GUI _sorted equivalent)
if q.HAVE_QT:
    app = q.QApplication.instance() or q.QApplication([])

    class W(object):
        _sorted = q.MainWindow._sorted

    w = W()
    w.index = idx
    w.searcher = s
    for text in ['', 'report', 'data']:
        with idx.lock:
            s.prev = None
            res = s.run(q.Query(text))
        for col in range(4):
            for desc in (False, True):
                w.sort_col, w.sort_desc = col, desc
                r = list(res)
                t = time.time()
                with idx.lock:
                    out = w._sorted(r)
                print('  sort %-8r n=%7d col=%d desc=%d %7.0f ms%s' % (text, len(res), col, desc,
                                                                       (time.time() - t) * 1000,
                                                                       ' (unsorted)' if w.rows_unsorted else ''))
