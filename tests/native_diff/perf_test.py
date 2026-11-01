#!/usr/bin/env python3
"""Performance test on C:\\perfcorpus (~1M entries). Each --cli run rescans, so wall(no-match query) ~ startup + scan.
usage: perf_test.py [--exe PATH] [--arch 64|32] [--runner CMD] [--tag T] [--reps N] [--no-counts]"""
import argparse
import json
import os
import shlex
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run_diff import env_for  # noqa: E402

PQ = [('p01', 'a', {}), ('p02', 'report', {}), ('p03', '报告', {}), ('p04', 'zzqxnomatch', {}), ('p05', '*.txt', {}),
      ('p06', 'ext:jpg', {}), ('p07', 'regex:^img_\\d+', {}), ('p08', 'size:>1mb', {}), ('p09', 'dm:2024', {}),
      ('p10', 'report !final', {}), ('p11', 'img_1', {}), ('p12', 'IMG', {'case': 1}), ('p13', 'data', {'path': 1}),
      ('p14', '2024 pdf', {}), ('p15', 'folder:', {}), ('p16', 'report | invoice | 报告', {}), ('p17', 'report', {'whole': 1}),
      ('p18', 'top_07\\leaf_05', {}), ('p19', 'data 99', {}), ('p20', '_1', {}), ('p21', 'x', {}), ('p22', '', {'filter': 3}),
      ('p23', 'photo', {'filter': 3})]


def cmd_args(text, fl, out):
    a = ['--cli', '--root', 'C:\\perfcorpus', '--query', text]
    for k in ('case', 'whole', 'path', 'regex'):
        if fl.get(k):
            a.append('--' + k)
    if fl.get('filter'):
        a += ['--filter', str(fl['filter'])]
    return a + ['--out', out]


def timed(cmd, env):
    t0 = time.time()
    p = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _, st, ru = os.wait4(p.pid, 0)
    p.returncode = os.waitstatus_to_exitcode(st)
    return time.time() - t0, p.returncode, ru.ru_maxrss / 1024.0


def expected_counts(pfx):
    fn = os.path.join(HERE, 'work', 'perf_expected.json')
    sig = os.stat(os.path.join(pfx, 'drive_c', 'perfcorpus')).st_mtime
    if os.path.exists(fn):
        d = json.load(open(fn))
        if d.get('sig') == sig and d.get('day') == time.strftime('%F'):
            return d['counts']
    import oracle_lib as ol
    t0 = time.time()
    idx, _ = ol.build_index(os.path.join(pfx, 'drive_c', 'perfcorpus'), 'C:\\perfcorpus')
    print('oracle indexed %d entries in %.0fs' % (idx.live, time.time() - t0), flush=True)
    counts = {}
    for pid, text, fl in PQ:
        qd = dict(text=text, case=bool(fl.get('case')), whole=bool(fl.get('whole')), path=bool(fl.get('path')),
                  regex=bool(fl.get('regex')), filter=fl.get('filter', 0))
        paths, err = ol.run_query(idx, qd)
        counts[pid] = len(paths)
    json.dump(dict(sig=sig, day=time.strftime('%F'), counts=counts), open(fn, 'w'))
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', default=os.path.join(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')), 'native', 'out', 'QianXun-x64.exe'))
    ap.add_argument('--arch', default=None)
    ap.add_argument('--runner', default=None)
    ap.add_argument('--tag', default=None)
    ap.add_argument('--reps', type=int, default=1)
    ap.add_argument('--no-counts', action='store_true')
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    arch = a.arch or ('32' if 'x86' in os.path.basename(a.exe).lower() else '64')
    a.tag = a.tag or time.strftime('%H%M%S')
    env, pfx = env_for(arch)
    pc = os.path.join(pfx, 'drive_c', 'perfcorpus')
    if not os.path.isdir(pc):
        sys.exit('perfcorpus missing in %s (run gen_perf.py --prefix ...)' % pfx)
    cmdprefix = shlex.split(a.runner) if a.runner else ['wine', a.exe]
    exp = None if a.no_counts else expected_counts(os.path.join(HERE, 'prefix64'))
    outd = os.path.join(pfx, 'drive_c', 'qxout')
    os.makedirs(outd, exist_ok=True)
    # startup baseline: tiny root
    ts = []
    for _ in range(3):
        w, rc, rss = timed(cmdprefix + ['--cli', '--root', 'C:\\windows\\system32\\drivers', '--query', 'zz', '--out', 'C:\\qxout\\perf_base.txt'], env)
        ts.append(w)
    base = sorted(ts)[1]
    rows = []
    for pid, text, fl in PQ:
        if a.only and pid not in a.only.split(','):
            continue
        walls, mss, rsss = [], [], []
        count = None
        status = 'ok'
        for r in range(a.reps):
            of = os.path.join(outd, 'perf_%s.txt' % pid)
            if os.path.exists(of):
                os.remove(of)
            w, rc, rss = timed(cmdprefix + cmd_args(text, fl, 'C:\\qxout\\perf_%s.txt' % pid), env)
            if rc != 0 or not os.path.exists(of):
                status = 'CRASH rc=%s' % rc
                break
            last = open(of, 'rb').read().rstrip(b'\n').rsplit(b'\n', 1)[-1].decode('utf-8', 'replace')
            import re
            m = re.search(r'#count=(\d+)\s+#ms=([\d.]+)', last)
            if not m:
                status = 'bad footer'
                break
            count = int(m.group(1))
            mss.append(float(m.group(2)))
            walls.append(w)
            rsss.append(rss)
        row = dict(id=pid, text=text, flags=fl, status=status, count=count, ms=min(mss) if mss else None,
                   wall=min(walls) if walls else None, rss_mb=max(rsss) if rsss else None)
        if exp is not None and count is not None:
            row['expected'] = exp[pid]
            if exp[pid] != count:
                row['status'] = 'COUNT MISMATCH'
        rows.append(row)
        print(row, flush=True)
    L = ['# Performance (arch %s, %s)  corpus: %s\n' % (arch, time.strftime('%F %T'), 'C:\\perfcorpus ~951k entries'),
         'Startup baseline (tiny root, wine launch + exit): %.2fs.  Each run rescans, so `wall - startup` ~ scan + query + output.' % base, '',
         '| id | query | flags | count | expected | #ms | wall s | peak RSS MB | status |', '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        L.append('| %s | `%s` | %s | %s | %s | %s | %s | %s | %s |' % (r['id'], r['text'], r['flags'] or '', r['count'], r.get('expected', ''), r['ms'],
                                                                 '%.2f' % r['wall'] if r['wall'] else '', '%.0f' % r['rss_mb'] if r['rss_mb'] else '', r['status']))
    nm = [r for r in rows if r['id'] == 'p04' and r['wall']]
    if nm:
        L.append('\nScan estimate (wall of no-match query p04 minus startup): %.1fs for ~951k entries.' % (nm[0]['wall'] - base))
    ms = sorted(r['ms'] for r in rows if r['ms'] is not None)
    if ms:
        L.append('Query #ms over %d queries: median %.0f, p90 %.0f, max %.0f.' % (len(ms), ms[len(ms) // 2], ms[int(len(ms) * .9)], ms[-1]))
    fn = os.path.join(HERE, 'report', 'perf_%s.md' % a.tag)
    open(fn, 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))
    print('->', fn)


if __name__ == '__main__':
    main()
