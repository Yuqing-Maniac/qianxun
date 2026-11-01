#!/usr/bin/env python3
"""~1M-entry performance corpus: $WINEPREFIX/drive_c/perfcorpus (C:\\perfcorpus). 50 x 20 leaf dirs, ~950 files each.
usage: gen_perf.py [--prefix DIR] [--files N]   deterministic; mostly empty files, 3% sparse-sized, 5% dated."""
import argparse
import os
import random
import shutil
import time

ap = argparse.ArgumentParser()
ap.add_argument('--prefix', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prefix64'))
ap.add_argument('--files', type=int, default=950)
a = ap.parse_args()
root = os.path.join(a.prefix, 'drive_c', 'perfcorpus')
if os.path.exists(root):
    shutil.rmtree(root)
rnd = random.Random(424242)
en = ['report', 'invoice', 'photo', 'IMG', 'DSC', 'notes', 'backup', 'data', 'final', 'draft', 'test', 'config', 'readme', 'main',
      'util', 'index', 'Setup', 'Release', 'log', 'temp', 'cache', 'image', 'video', 'music', 'document', 'summary', 'project']
cn = ['报告', '发票', '照片', '方案', '总结', '会议纪要', '需求', '设计', '测试', '手册']
exts = ['txt', 'docx', 'pdf', 'jpg', 'png', 'xlsx', 'mp3', 'mp4', 'zip', 'py', 'cpp', 'h', 'js', 'md', 'log', 'dat', 'bin', 'exe', 'dll', 'json', '']
t0 = time.time()
n = nd = 0
lo, hi = 1546300800, 1792000000
for i in range(50):
    for j in range(20):
        d = os.path.join(root, 'top_%02d' % i, 'leaf_%02d_%s' % (j, rnd.choice(['src', 'data', 'docs', '资料', 'Photos', 'x64'])))
        os.makedirs(d)
        nd += 1
        seen = set()
        for k in range(a.files):
            w = rnd.choice(en) if rnd.random() < .8 else rnd.choice(cn)
            nm = '%s_%d%s' % (w, rnd.randint(0, 99999), ('.' + rnd.choice(exts)) if rnd.random() < .95 else '')
            if nm in seen:
                continue
            seen.add(nm)
            p = os.path.join(d, nm)
            fd = os.open(p, os.O_WRONLY | os.O_CREAT, 0o644)
            r = rnd.random()
            if r < .03:
                os.ftruncate(fd, rnd.randint(1, 50 << 20))
            os.close(fd)
            if rnd.random() < .05:
                t = rnd.randint(lo, hi)
                os.utime(p, (t, t))
            n += 1
print('perfcorpus %s: %d files, %d leaf dirs, %.0fs' % (root, n, nd, time.time() - t0))
