#!/usr/bin/env python3
"""Live-update test for `--cli-watch`: modifies C:\\livecorpus from the Linux side while the exe watches, and measures
the latency until the reported count follows.   usage: live_test.py [--exe PATH] [--arch 64|32] [--runner CMD] [--tag T]"""
import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run_diff import env_for  # noqa: E402


class Tail(threading.Thread):
    def __init__(self, fn):
        super().__init__(daemon=True)
        self.fn, self.lines, self.stop = fn, [], False   # (arrival time, raw line)
        self.buf = b''

    def run(self):
        pos = 0
        while not self.stop:
            try:
                with open(self.fn, 'rb') as f:
                    f.seek(pos)
                    d = f.read()
                    pos += len(d)
            except OSError:
                d = b''
            if d:
                self.buf += d
                now = time.monotonic()
                while b'\n' in self.buf:
                    l, self.buf = self.buf.split(b'\n', 1)
                    self.lines.append((now, l.decode('utf-8', 'replace').strip()))
            time.sleep(0.01)


def parse_counts(lines):
    """-> list of (arrival, count). Accepts 'count=N', or 'TS COUNT' / 'COUNT TS' (timestamp column = strictly increasing)."""
    fm = [(t, re.match(r'^[\d.]+\s+(\d+)\s*$', l)) for t, l in lines if l and not l.startswith('#')]
    if fm and all(m for _, m in fm):
        return [(t, int(m.group(1))) for t, m in fm]
    rows = [(t, re.findall(r'-?\d+', l)) for t, l in lines if l and not l.startswith('#')]
    lab = [(t, re.search(r'count\s*[=:]\s*(\d+)', l, re.I)) for t, l in lines if l and not l.startswith('#')]
    if rows and all(m for _, m in lab):
        return [(t, int(m.group(1))) for t, m in lab]
    rows = [(t, [int(x) for x in r]) for t, r in rows if len(r) >= 2]
    if len(rows) < 3:
        return []
    ncol = min(len(r) for _, r in rows)
    inc = [c for c in range(ncol) if all(rows[i][1][c] < rows[i + 1][1][c] for i in range(len(rows) - 1))]
    cc = [c for c in range(ncol) if c not in inc]
    col = cc[0] if cc else (1 if inc and inc[0] == 0 else 0)
    return [(t, r[col]) for t, r in rows]


def watch_scenario(a, cmdprefix, env, pfx, name, query, setup, ops, duration, extra_args=()):
    root = os.path.join(pfx, 'drive_c', 'livecorpus')
    side = os.path.join(pfx, 'drive_c', 'liveside')
    for d in (root, side):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
    n0 = setup(root, side)
    out_lin = os.path.join(pfx, 'drive_c', 'qxout', 'live_%s_%s.txt' % (a.tag, name))
    os.makedirs(os.path.dirname(out_lin), exist_ok=True)
    if os.path.exists(out_lin):
        os.remove(out_lin)
    out_win = 'C:\\qxout\\live_%s_%s.txt' % (a.tag, name)
    cmd = cmdprefix + ['--cli-watch', '--root', 'C:\\livecorpus', '--query', query, '--duration', str(duration), '--out', out_win] + list(extra_args)
    t0 = time.monotonic()
    p = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    tail = Tail(out_lin)
    tail.start()
    res = dict(name=name, query=query, initial_expected=n0, ops=[], ok=True, notes=[])
    # wait for the first reading
    deadline = time.monotonic() + 90
    cur = None
    while time.monotonic() < deadline and p.poll() is None:
        cs = parse_counts(list(tail.lines))
        if cs:
            cur = cs[-1][1]
            break
        time.sleep(0.05)
    if cur is None:
        res['ok'] = False
        res['notes'].append('no output within 90s (rc=%s)' % p.poll())
        p.kill()
        tail.stop = True
        return res
    res['first_output_s'] = round(time.monotonic() - t0, 2)
    # wait for the initial scan to settle at n0
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        cs = parse_counts(list(tail.lines))
        if cs and cs[-1][1] == n0:
            break
        time.sleep(0.05)
    else:
        res['notes'].append('initial count %s != expected %s' % (cs[-1][1] if cs else None, n0))
    time.sleep(1.0)
    expected = n0
    for label, fn, delta in ops:
        before = len(tail.lines)
        t_op = time.monotonic()
        fn(root, side)
        expected += delta
        first = settled = None
        end = t_op + 20
        while time.monotonic() < end and p.poll() is None:
            cs = parse_counts(list(tail.lines))
            for t, c in cs:
                if t < t_op:
                    continue
                if first is None and c != cs_prev(cs, t_op):
                    first = t - t_op
                if c == expected:
                    settled = t - t_op
                    break
            if settled is not None:
                break
            time.sleep(0.02)
        if delta == 0:
            settled = 0.0 if settled is None else settled
        r = dict(op=label, expected=expected, first_ms=None if first is None else int(first * 1000),
                 settled_ms=None if settled is None else int(settled * 1000))
        if settled is None:
            cs = parse_counts(list(tail.lines))
            r['final_seen'] = cs[-1][1] if cs else None
            res['ok'] = False
        res['ops'].append(r)
        time.sleep(1.2)
    try:
        rc = p.wait(timeout=duration + 30)
    except subprocess.TimeoutExpired:
        p.kill()
        rc = 'timeout'
        res['ok'] = False
    tail.stop = True
    res['rc'] = rc
    if rc != 0:
        res['ok'] = False
        res['notes'].append('exit code %s' % rc)
    cs = parse_counts(list(tail.lines))
    res['samples'] = len(cs)
    if len(cs) > 3:
        gaps = sorted(cs[i + 1][0] - cs[i][0] for i in range(len(cs) - 1))
        res['sample_interval_ms_median'] = int(gaps[len(gaps) // 2] * 1000)
        res['sample_interval_ms_max'] = int(gaps[-1] * 1000)
    res['lines_sample'] = [l for _, l in tail.lines[:3]] + ['...'] + [l for _, l in tail.lines[-2:]]
    return res


def cs_prev(cs, t_op):
    prev = None
    for t, c in cs:
        if t >= t_op:
            break
        prev = c
    return prev


# ---- scenarios ------------------------------------------------------------------------------------------
def touch(p, size=0):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'wb') as f:
        if size:
            f.truncate(size)


def setup_names(root, side):
    n = 0
    for d in range(10):
        for i in range(30):
            touch(os.path.join(root, 'd%02d' % d, 'base_%03d.txt' % i))
    for i in range(10):
        touch(os.path.join(root, 'd%02d' % (i % 10), 'lvtok_init_%02d.txt' % i))
        n += 1
    for i in range(5):
        touch(os.path.join(root, 'grp', 'lvtok_grp_%d.txt' % i))
        n += 1
    return n


def ops_names():
    R = lambda *p: os.path.join(*p)
    ops = []
    ops.append(('create 1 matching file', lambda r, s: touch(R(r, 'd00', 'lvtok_new1.txt')), +1))
    ops.append(('create 50 matching files (burst)', lambda r, s: [touch(R(r, 'd01', 'lvtok_b%02d.txt' % i)) for i in range(50)], +50))
    ops.append(('rename matching -> non-matching', lambda r, s: os.rename(R(r, 'd00', 'lvtok_new1.txt'), R(r, 'd00', 'plain_new1.txt')), -1))
    ops.append(('rename non-matching -> matching', lambda r, s: os.rename(R(r, 'd00', 'plain_new1.txt'), R(r, 'd00', 'lvtok_back1.txt')), +1))
    ops.append(('delete 1 matching file', lambda r, s: os.remove(R(r, 'd00', 'lvtok_back1.txt')), -1))
    ops.append(('create CJK-named matching file', lambda r, s: touch(R(r, 'd02', 'lvtok_中文名字_报告.txt')), +1))
    ops.append(('create new dir + 20 matching files inside', lambda r, s: [touch(R(r, 'newdir_a', 'sub', 'lvtok_n%02d.txt' % i)) for i in range(20)], +20))
    ops.append(('move matching dir out of root (5 files)', lambda r, s: os.rename(R(r, 'grp'), R(s, 'grp')), -5))
    ops.append(('move it back in', lambda r, s: os.rename(R(s, 'grp'), R(r, 'grp')), +5))
    ops.append(('delete whole subtree (newdir_a, 20 files)', lambda r, s: shutil.rmtree(R(r, 'newdir_a')), -20))
    ops.append(('rename directory d03 -> d03_renamed (files keep matching)', lambda r, s: os.rename(R(r, 'd03'), R(r, 'd03_renamed')), 0))
    ops.append(('create matching file inside renamed dir', lambda r, s: touch(R(r, 'd03_renamed', 'lvtok_after_rename.txt')), +1))
    ops.append(('create + delete 100 files rapidly (storm), net 0', lambda r, s: ([touch(R(r, 'd04', 'storm_%03d.tmp' % i)) for i in range(100)], [os.remove(R(r, 'd04', 'storm_%03d.tmp' % i)) for i in range(100)]), 0))
    ops.append(('create matching file after storm', lambda r, s: touch(R(r, 'd05', 'lvtok_after_storm.txt')), +1))
    return ops


def setup_size(root, side):
    for i in range(20):
        touch(os.path.join(root, 'lvsz_%02d.bin' % i), 0)
    touch(os.path.join(root, 'lvsz_big.bin'), 5000)
    return 1


def ops_size():
    R = os.path.join
    return [('grow lvsz_00 to 5000 bytes (size refresh)', lambda r, s: os.truncate(R(r, 'lvsz_00.bin'), 5000), +1),
            ('grow 3 more files', lambda r, s: [os.truncate(R(r, 'lvsz_%02d.bin' % i), 9000) for i in (1, 2, 3)], +3),
            ('shrink lvsz_00 to 0', lambda r, s: os.truncate(R(r, 'lvsz_00.bin'), 0), -1),
            ('append to existing file via write', lambda r, s: open(R(r, 'lvsz_05.bin'), 'ab').write(b'x' * 4000), +1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', default=os.path.join(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')), 'native', 'out', 'QianXun-x64.exe'))
    ap.add_argument('--arch', default=None)
    ap.add_argument('--runner', default=None)
    ap.add_argument('--tag', default=None)
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    arch = a.arch or ('32' if 'x86' in os.path.basename(a.exe).lower() else '64')
    a.tag = a.tag or time.strftime('%H%M%S')
    env, pfx = env_for(arch)
    cmdprefix = shlex.split(a.runner) if a.runner else ['wine', a.exe]
    results = []
    sc = [('names', 'lvtok', setup_names, ops_names(), 75),
          ('size', 'lvsz size:>1kb', setup_size, ops_size(), 35)]
    for name, q, st, ops, dur in sc:
        if a.only and name not in a.only.split(','):
            continue
        print('scenario', name, flush=True)
        results.append(watch_scenario(a, cmdprefix, env, pfx, name, q, st, ops, dur))
    L = ['# Live-update test (arch %s, %s)\n' % (arch, time.strftime('%F %T'))]
    allok = True
    for r in results:
        allok &= r['ok']
        L.append('## %s  query `%s`  -> %s\n' % (r['name'], r['query'], 'OK' if r['ok'] else 'PROBLEMS'))
        L.append('first output after %ss; samples %s, interval median %s ms, max %s ms; exit %s; %s\n' % (
            r.get('first_output_s'), r.get('samples'), r.get('sample_interval_ms_median'), r.get('sample_interval_ms_max'), r.get('rc'), r['notes']))
        L.append('| operation | expected count | first change (ms) | settled (ms) |\n|---|---|---|---|')
        for o in r['ops']:
            L.append('| %s | %s | %s | %s |' % (o['op'], o['expected'], o['first_ms'], o['settled_ms'] if o['settled_ms'] is not None else 'NEVER (saw %s)' % o.get('final_seen')))
        L.append('\nsample lines: `%s`\n' % ' | '.join(r.get('lines_sample', [])))
    os.makedirs(os.path.join(HERE, 'report'), exist_ok=True)
    fn = os.path.join(HERE, 'report', 'live_%s.md' % a.tag)
    open(fn, 'w').write('\n'.join(L))
    print('\n'.join(L))
    print('->', fn)
    return 0 if allok else 1


if __name__ == '__main__':
    sys.exit(main())
