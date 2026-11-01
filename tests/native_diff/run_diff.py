#!/usr/bin/env python3
"""Differential harness: native QianXun `--cli` vs Python-reference oracle (see NATIVE_SPEC.md section 9).

usage: run_diff.py [--exe PATH] [--arch 64|32] [--runner CMD] [--tag NAME] [-j N] [--cats a,b] [--ids q001,q002]
                   [--timeout S] [--no-regen] [--corpus NAME]
  --runner   command prefix that launches the exe (default: wine from the matching env64/env32 prefix).
             e.g. --runner "python3 fake_qianxun.py" runs the Python stand-in (harness self-test).
Output: report/<tag>/summary.md, results.json, diffs/<id>.diff"""
import argparse
import collections
import concurrent.futures as cf
import datetime
import json
import os
import re
import shlex
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def env_for(arch):
    pfx = os.path.join(HERE, 'prefix%s' % arch)
    e = dict(os.environ)
    e.update(WINEPREFIX=pfx, WINEARCH='win64' if arch == '64' else 'win32', WINEDEBUG='-all', TZ='Asia/Shanghai',
             LANG='zh_CN.UTF-8', LC_ALL='C.UTF-8', WINEDLLOVERRIDES='mscoree,mshtml=')
    e.pop('DISPLAY', None)
    return e, pfx


def ensure_expected(arch, corpus, regen):
    """retouch relative dates; (re)build oracle expected/ if missing or built on another day."""
    e, pfx = env_for(arch)
    cdir = os.path.join(pfx, 'drive_c', corpus)
    if corpus == 'corpus':
        subprocess.run([sys.executable, os.path.join(HERE, 'gen_corpus.py'), '--dest', cdir, '--retouch'],
                       stdout=subprocess.DEVNULL)
    exp = os.path.join(HERE, 'expected_%s' % arch)
    idxf = os.path.join(exp, 'index.json')
    need = regen
    if not os.path.exists(idxf):
        need = True
    else:
        meta = json.load(open(idxf))
        if meta['generated'][:10] != datetime.date.today().isoformat():
            need = True
        import queries
        if len(meta['queries']) != len(queries.QUERIES):
            need = True
    if need:
        print('building oracle expected set (arch %s)...' % arch, flush=True)
        subprocess.run([sys.executable, os.path.join(HERE, 'oracle.py'), '--prefix', pfx, '--corpus', corpus, '--out', exp],
                       check=True, stdout=subprocess.DEVNULL)
    return exp, pfx


_IDX = {}
_IDX_LOCK = __import__('threading').Lock()


def get_idx(a, pfx):
    with _IDX_LOCK:
        if 'i' not in _IDX:
            import oracle_lib as ol
            _IDX['i'] = ol.build_index(os.path.join(pfx, 'drive_c', a.corpus), 'C:\\' + a.corpus)[0]
    return _IDX['i']


def read_lines(fn):
    with open(fn, 'rb') as f:
        data = f.read()
    txt = data.decode('utf-8', 'surrogateescape')
    bom = txt.startswith('\ufeff')
    crlf = '\r\n' in txt
    lines = txt.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    return lines, bom, crlf


def run_one(a, qd, meta, outdir_win, outdir_lin, cmdprefix, env, symlinks, expdir):
    out_lin = os.path.join(outdir_lin, qd['id'] + '.txt')
    out_win = outdir_win + '\\' + qd['id'] + '.txt'
    if os.path.exists(out_lin):
        os.remove(out_lin)
    args = ['--cli', '--root', 'C:\\' + a.corpus, '--query', qd['text']]
    if qd['case']:
        args.append('--case')
    if qd['whole']:
        args.append('--whole')
    if qd['path']:
        args.append('--path')
    if qd['regex']:
        args.append('--regex')
    if qd['filter']:
        args += ['--filter', str(qd['filter'])]
    args += ['--out', out_win]
    t0 = time.time()
    tsens = False
    try:
        import oracle_lib as _ol
        tsens = _ol.is_timesens(qd['text'])
    except Exception:
        pass
    res = dict(id=qd['id'], cat=qd['cat'], text=qd['text'], soft=qd['soft'], status='?', wall=0.0, ms=None, rc=None,
               notes=[])
    for attempt in (1, 2):
        t0 = time.time()
        try:
            # NOTE: never capture via pipes -- Wine helper processes (rpcss/services) spawned lazily by a run inherit the
            # pipe and keep it open, making subprocess wait until the wineserver exits (looked like a 120 s hang).
            logf = os.path.join(a.reportdir, 'logs', qd['id'] + '.log')
            with open(logf, 'wb') as lf:
                p = subprocess.run(cmdprefix + args, env=env, stdin=subprocess.DEVNULL, stdout=lf, stderr=lf, timeout=a.timeout)
            res['rc'] = p.returncode
            res['stderr'] = open(logf, 'rb').read()[-300:].decode('utf-8', 'replace')
        except subprocess.TimeoutExpired:
            res['rc'] = 'timeout'
        res['wall'] = time.time() - t0
        if (res['rc'] == 0 and os.path.exists(out_lin)) or attempt == 2 or a.no_retry:
            break
        res['notes'].append('FLAKE: attempt 1 failed (rc=%s after %.1fs), retried' % (res['rc'], res['wall']))
        res['flake'] = True
        if os.path.exists(out_lin):
            os.remove(out_lin)
    if res['rc'] == 'timeout':
        res['status'] = 'TIMEOUT'
        return res
    if res['rc'] != 0 or not os.path.exists(out_lin):
        res['status'] = 'CRASH'
        res['notes'].append('rc=%s outfile=%s' % (res['rc'], os.path.exists(out_lin)))
        return res
    lines, bom, crlf = read_lines(out_lin)
    footer = [l for l in lines if l.startswith('#')]
    got = [l for l in lines if not l.startswith('#')]
    if bom:
        res['notes'].append('BOM present in output')
    if crlf:
        res['notes'].append('CRLF line endings (spec: LF)')
    m = re.search(r'#count=(\d+)\s+#ms=(\d+(?:\.\d+)?)', lines[-1] if lines else '')
    if not m:
        res['status'] = 'FAIL'
        res['notes'].append('missing/invalid footer: %r' % (lines[-1] if lines else None))
        return res
    res['ms'] = float(m.group(2))
    if int(m.group(1)) != len(got):
        res['notes'].append('footer count %s != %d result lines' % (m.group(1), len(got)))
        res['count_mismatch'] = True
    res['count'] = len(got)
    # symlink handling
    ss = set(s.lower() for s in symlinks)
    inlink = [g for g in got if any(g.lower().startswith(s + '\\') for s in ss)]
    if inlink:
        res['notes'].append('SYMLINK RECURSION: %d entries below a link, e.g. %s' % (len(inlink), inlink[0]))
        res['loop'] = True
    got_f = [g for g in got if g.lower() not in ss and g not in inlink]
    res['symlink_listed'] = sorted(g for g in got if g.lower() in ss)
    exp_lines, _, _ = read_lines(os.path.join(expdir, qd['id'] + '.txt'))
    exp = exp_lines
    got_f = [(g[0].upper() + g[1:]) if g[1:2] == ':' else g for g in got_f]
    if len(set(got_f)) != len(got_f):
        res['notes'].append('duplicate result lines: %d' % (len(got_f) - len(set(got_f))))
        res['dups'] = True
    gs, es = set(got_f), set(exp)
    if tsens and not meta.get('error'):
        # relative dm: (lastNd ...): accept anything between the oracle evaluated at run end and at run start (+-2s)
        import oracle_lib as _ol
        idx = get_idx(a, a.pfx)
        hi, _e = _ol.run_query(idx, qd, now=t0 - 2)
        lo, _e = _ol.run_query(idx, qd, now=time.time() + 2)
        if set(lo) <= gs <= set(hi):
            es = gs
            res['notes'].append('time-relative: oracle window %d..%d, got %d' % (len(lo), len(hi), len(gs)))
        else:
            es = set(hi) if len(gs - set(hi)) == 0 else set(lo)
    if meta.get('error'):
        # expected: syntax error -> no results, no crash
        if gs:
            res['status'] = 'FAIL'
            res['notes'].append('expected syntax error (%s) but got %d results' % (meta['error'], len(gs)))
        else:
            res['status'] = 'PASS'
            res['notes'].append('error query: ok (error lines: %s)' % [f for f in footer if 'count=' not in f][:2])
    elif gs == es:
        res['status'] = 'PASS'
    else:
        miss, extra = sorted(es - gs), sorted(gs - es)
        res['missing'], res['extra'] = len(miss), len(extra)
        low_ok = set(x.lower() for x in gs) == set(x.lower() for x in es)
        res['status'] = 'CASEDIFF' if low_ok else 'FAIL'
        with open(os.path.join(a.reportdir, 'diffs', qd['id'] + '.diff'), 'w', encoding='utf-8') as f:
            f.write('# %s [%s] %r flags=%s\n# expected %d, got %d, missing %d, extra %d\n' % (
                qd['id'], qd['cat'], qd['text'], {k: qd[k] for k in ('case', 'whole', 'path', 'regex', 'filter')},
                len(es), len(gs), len(miss), len(extra)))
            for x in miss[:60]:
                f.write('- ' + x + '\n')
            for x in extra[:60]:
                f.write('+ ' + x + '\n')
    if res['status'] == 'PASS' and res.get('loop'):
        res['status'] = 'FAIL'
    if res['status'] == 'PASS' and (res.get('count_mismatch') or res.get('dups')):
        res['status'] = 'FAIL'
    # order check (soft): names sorted case-insensitively
    if got_f:
        names = [g.rsplit('\\', 1)[-1] for g in got_f]
        keys = collections.OrderedDict([
            ('lower', lambda n: n.lower()), ('upper', lambda n: n.upper()),
            ('lower-utf16', lambda n: n.lower().encode('utf-16-be', 'surrogatepass')),
            ('upper-utf16', lambda n: n.upper().encode('utf-16-be', 'surrogatepass'))])
        res['order'] = 'unsorted'
        best = None
        for kn, kf in keys.items():
            ks = [kf(n) for n in names]
            inv = sum(1 for i in range(len(ks) - 1) if ks[i] > ks[i + 1])
            if best is None or inv < best[1]:
                best = (kn, inv)
        # a handful of inversions can only come from Unicode case-folding differences (e.g. U+0130), allowed
        if best[1] <= 4:
            res['order'] = best[0]
            if best[1]:
                res['notes'].append('%d order inversions (unicode folding?)' % best[1])
        if res['order'] == 'unsorted' and res['status'] == 'PASS':
            res['status'] = 'FAIL'
            res['notes'].append('results not sorted by name (case-insensitive) as required by spec')
    if res['status'] != 'PASS' and qd['soft']:
        res['status'] = 'SOFT'
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', default=os.path.join(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')), 'native', 'out', 'QianXun-x64.exe'))
    ap.add_argument('--arch', default=None, choices=['64', '32'])
    ap.add_argument('--runner', default=None)
    ap.add_argument('--tag', default=None)
    ap.add_argument('-j', type=int, default=2)
    ap.add_argument('--cats', default='')
    ap.add_argument('--ids', default='')
    ap.add_argument('--timeout', type=int, default=120)
    ap.add_argument('--no-regen', action='store_true')
    ap.add_argument('--regen', action='store_true')
    ap.add_argument('--corpus', default='corpus')
    ap.add_argument('--no-retry', action='store_true', help='do not retry a failed/hung launch once (Wine start-up flakes)')
    a = ap.parse_args()
    arch = a.arch or ('32' if 'x86' in os.path.basename(a.exe).lower() else '64')
    if arch == '32' and not os.path.isdir(os.path.join(HERE, 'prefix32', 'drive_c', 'windows')):
        sys.exit('32-bit prefix not available')
    a.tag = a.tag or ('%s-%s' % (re.sub(r'\W+', '_', os.path.basename(a.exe)), time.strftime('%H%M%S')))
    a.reportdir = os.path.join(HERE, 'report', a.tag)
    os.makedirs(os.path.join(a.reportdir, 'diffs'), exist_ok=True)
    os.makedirs(os.path.join(a.reportdir, 'logs'), exist_ok=True)
    env, pfx = env_for(arch)
    a.pfx = pfx
    if not a.runner:   # keep wineserver alive between runs (auto-exit races with parallel launches)
        subprocess.run(['wineserver', '-p'], env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['wine', 'cmd', '/c', 'rem'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    expdir, _ = ensure_expected(arch, a.corpus, a.regen and not a.no_regen)
    meta = json.load(open(os.path.join(expdir, 'index.json')))
    from queries import QUERIES
    cmdprefix = shlex.split(a.runner) if a.runner else ['wine', a.exe]
    if a.runner is None and not os.path.exists(a.exe):
        sys.exit('exe not found: %s' % a.exe)
    outdir_lin = os.path.join(pfx, 'drive_c', 'qxout', a.tag)
    os.makedirs(outdir_lin, exist_ok=True)
    outdir_win = 'C:\\qxout\\' + a.tag
    qmeta = {m['id']: m for m in meta['queries']}
    sel = [q for q in QUERIES if (not a.cats or q['cat'] in a.cats.split(',')) and (not a.ids or q['id'] in a.ids.split(','))]
    print('running %d queries with %s (arch %s, -j%d) -> %s' % (len(sel), ' '.join(cmdprefix), arch, a.j, a.reportdir), flush=True)
    t0 = time.time()
    results = []
    with cf.ThreadPoolExecutor(a.j) as ex:
        futs = [ex.submit(run_one, a, q, qmeta[q['id']], outdir_win, outdir_lin, cmdprefix, env, meta['symlinks'], expdir)
                for q in sel]
        for k, f in enumerate(futs):
            r = f.result()
            results.append(r)
            if r['status'] not in ('PASS',):
                print('  %-7s %s [%s] %r %s' % (r['status'], r['id'], r['cat'], r['text'][:40], '; '.join(r['notes'])[:100]), flush=True)
            elif k % 50 == 0:
                print('  ... %d/%d' % (k, len(futs)), flush=True)
    total = time.time() - t0
    json.dump(results, open(os.path.join(a.reportdir, 'results.json'), 'w'), ensure_ascii=False, indent=1)
    # summary
    bycat = collections.OrderedDict()
    for r in results:
        c = bycat.setdefault(r['cat'], collections.Counter())
        c[r['status']] += 1
    tot = collections.Counter(r['status'] for r in results)
    L = []
    L.append('# Differential test: %s  (arch %s, %s)\n' % (os.path.basename(a.exe), arch, time.strftime('%Y-%m-%d %H:%M:%S')))
    L.append('Launch flakes (retried once): %d\n' % sum(1 for r in results if r.get('flake')))
    L.append('Queries: %d, wall %.0fs. PASS %d, FAIL %d, CRASH/TIMEOUT %d, CASEDIFF %d, SOFT (spec-ambiguous) %d\n' % (
        len(results), total, tot['PASS'], tot['FAIL'], tot['CRASH'] + tot['TIMEOUT'], tot['CASEDIFF'], tot['SOFT']))
    L.append('| category | n | PASS | FAIL | CRASH | CASEDIFF | SOFT |\n|---|---|---|---|---|---|---|')
    for c, cn in bycat.items():
        L.append('| %s | %d | %d | %d | %d | %d | %d |' % (c, sum(cn.values()), cn['PASS'], cn['FAIL'], cn['CRASH'] + cn['TIMEOUT'],
                                                           cn['CASEDIFF'], cn['SOFT']))
    ms = sorted(r['ms'] for r in results if r['ms'] is not None)
    wl = sorted(r['wall'] for r in results)
    if ms:
        L.append('\nQuery time (#ms footer): median %.1f, p90 %.1f, max %.1f ms.  Wall per run (scan+query+Wine start): median %.2fs, max %.2fs' % (
            ms[len(ms) // 2], ms[int(len(ms) * .9)], ms[-1], wl[len(wl) // 2], wl[-1]))
    od = collections.Counter(r.get('order') for r in results if r.get('order'))
    L.append('Result ordering (name case-insens): %s' % dict(od))
    L.append('\n## Non-PASS\n')
    for r in results:
        if r['status'] != 'PASS':
            L.append('- %s %s [%s] `%s` miss=%s extra=%s %s' % (r['status'], r['id'], r['cat'], r['text'].replace('`', "'"),
                                                              r.get('missing', ''), r.get('extra', ''), '; '.join(r['notes'])))
    open(os.path.join(a.reportdir, 'summary.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L[:3 + len(bycat) + 6]))
    print('report: %s/summary.md' % a.reportdir)
    return 0 if not (tot['FAIL'] or tot['CRASH'] or tot['TIMEOUT']) else 1


if __name__ == '__main__':
    sys.exit(main())
