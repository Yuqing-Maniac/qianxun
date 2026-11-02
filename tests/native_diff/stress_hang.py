#!/usr/bin/env python3
"""Repeat one query N times (parallel J) to catch rare hangs/crashes: stress_hang.py N J [exe] [arch] [query]"""
import concurrent.futures as cf, subprocess, sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_diff import env_for
N, J = int(sys.argv[1]), int(sys.argv[2])
exe = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')), 'native', 'out', 'QianXun-x64.exe')
arch = sys.argv[4] if len(sys.argv) > 4 else ('32' if 'x86' in exe else '64')
query = sys.argv[5] if len(sys.argv) > 5 else 'REPORT'
env, pfx = env_for(arch)
os.makedirs(pfx + '/drive_c/qxout/stress', exist_ok=True)
def one(i):
    t0 = time.time()
    try:
        p = subprocess.run(['wine', exe, '--cli', '--root', 'C:\\corpus', '--query', query, '--out', 'C:\\qxout\\stress\\s%d.txt' % i], env=env, stdin=subprocess.DEVNULL, stdout=open('/tmp/stress_%d.log' % i, 'wb'), stderr=subprocess.STDOUT, timeout=45)
        return i, p.returncode, time.time() - t0
    except subprocess.TimeoutExpired:
        return i, 'timeout', time.time() - t0
bad = []
with cf.ThreadPoolExecutor(J) as ex:
    for i, rc, w in ex.map(one, range(N)):
        if rc != 0:
            bad.append((i, rc, round(w, 1)))
print('runs %d, problems %d: %s' % (N, len(bad), bad))
