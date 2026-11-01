"""Independent reference: path-substring terms vs naive `t in fullpath`."""
import random, sys
from qa_common import q
from test_search import build_index
idx = build_index(3000, 11)
rnd = random.Random(2)
s = q.Searcher(idx)
bad = 0
terms = ['/', '/r', '/r/', 'r/', 'ab', 'ab/', '/ab', 'b/a', 'dir/', 'd/r', '0/', '0dir/ab', 'c0/', '1_d/', 't/i',
         'é/', '告', 'r/abc', '.pdf', '/r/a']
for _ in range(200):
    t = rnd.choice(terms) if rnd.random() < 0.6 else ''.join(rnd.choice('abr/0d._') for _ in range(rnd.randint(1, 5)))
    for case in (False, True):
        for mp in (False, True):
            if '*' in t or '?' in t:
                continue
            Q = q.Query('"%s"' % t, case=case, match_path=mp)
            s.case = case
            with idx.lock:
                got = sorted(s.run(Q))
            tt = t if case else t.lower()
            usepath = mp or '/' in t
            exp = []
            for i in range(len(idx.names)):
                if idx.kind[i] == q.KIND_DEAD:
                    continue
                fp = idx.fullpath(i) if usepath else idx.names[i]
                if not case:
                    fp = fp.lower()
                if tt in fp:
                    exp.append(i)
            if got != exp:
                bad += 1
                print('MISMATCH', repr(t), case, mp, len(got), len(exp))
print('path reference mismatches:', bad)
sys.exit(1 if bad else 0)
