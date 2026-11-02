#!/usr/bin/env python3
"""Build expected results for queries.py against the corpus.
usage: oracle.py [--prefix DIR(default prefix64)] [--corpus NAME(default corpus)] [--out DIR(default expected)]
Writes expected/<id>.txt (sorted full Windows paths) and expected/index.json."""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import oracle_lib as ol  # noqa: E402
from queries import QUERIES  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prefix', default=os.path.join(HERE, 'prefix64'))
    ap.add_argument('--corpus', default='corpus')
    ap.add_argument('--out', default=os.path.join(HERE, 'expected'))
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    t0 = time.time()
    lroot = os.path.join(a.prefix, 'drive_c', a.corpus)
    idx, syml = ol.build_index(lroot, 'C:\\' + a.corpus)
    print('indexed %d entries, %d dirs, %d symlinks skipped in %.1fs' % (idx.live, len(idx.dirs), len(syml), time.time() - t0))
    os.makedirs(a.out, exist_ok=True)
    meta = {'symlinks': syml, 'queries': [], 'generated': time.strftime('%Y-%m-%d %H:%M:%S'), 'corpus': a.corpus,
            'entries': idx.live}
    for qd in QUERIES:
        if a.only and not qd['id'] in a.only.split(','):
            continue
        paths, err = ol.run_query(idx, qd)
        paths.sort(key=ol.sort_key)
        with open(os.path.join(a.out, qd['id'] + '.txt'), 'w', encoding='utf-8', newline='\n') as f:
            for p in paths:
                f.write(p + '\n')
        m = dict(qd)
        m['count'] = len(paths)
        m['error'] = err
        meta['queries'].append(m)
    json.dump(meta, open(os.path.join(a.out, 'index.json'), 'w'), ensure_ascii=False, indent=1)
    errs = sum(1 for m in meta['queries'] if m['error'])
    zero = [m['id'] for m in meta['queries'] if m['count'] == 0 and not m['error']]
    print('%d queries (%d syntax errors); %d with zero hits; %.1fs' % (len(meta['queries']), errs, len(zero), time.time() - t0))
    print('zero-hit (not error):', ' '.join('%s[%s]' % (m['id'], m['text']) for m in meta['queries'] if m['id'] in zero))


if __name__ == '__main__':
    main()
