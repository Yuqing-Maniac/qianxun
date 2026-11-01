"""GUI reads (model.data / selected_paths) while the engine thread clears and rescans the index.
Before the fix: stale entry ids silently map to *different* files after a rebuild (wrong file trashed/renamed),
and model.data could raise IndexError mid-clear (PyQt5 aborts on uncaught exceptions in virtual methods)."""
import os
import sys
import time
import shutil
import tempfile
import threading

from qa_common import q

app = q.QApplication.instance() or q.QApplication(sys.argv)
base = tempfile.mkdtemp(prefix='qa_race_')
for i in range(3000):
    d = os.path.join(base, 'd%d' % (i % 50))
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'f%d.txt' % i), 'w').close()

idx = q.Index()
with idx.lock:
    s = idx._new_dir(base, -1)
idx.scan_tree([s], set())
model = q.ResultModel(idx)
srch = q.Searcher(idx)
with idx.lock:
    rows = srch.run(q.Query('f1'))
model.set_rows(rows, idx.gen) if model.set_rows.__code__.co_argcount > 2 else model.set_rows(rows)
orig_paths = {r: idx.fullpath(model.entry(r)) for r in range(len(rows))}

stop = threading.Event()
errors = []


def churn():
    k = 0
    while not stop.is_set():
        # reverse scan order so ids map to different names after each rebuild
        idx.clear()
        with idx.lock:
            s = idx._new_dir(base, -1)
        idx.scan_tree([s], set())
        k += 1


t = threading.Thread(target=churn)
t.start()
wrong = 0
end = time.time() + 4
n = 0
while time.time() < end:
    for r in range(0, len(rows), 7):
        for col in range(4):
            try:
                model.data(model.index(r, col), q.Qt.DisplayRole)
                model.data(model.index(r, col), q.Qt.ToolTipRole)
            except Exception as e:
                errors.append(repr(e))
        i = model.entry(r)
        if i >= 0:
            try:
                p = idx.fullpath(i)
            except Exception as e:
                errors.append(repr(e))
                continue
            if p is not None and p != orig_paths[r]:
                wrong += 1
        n += 1
stop.set()
t.join()
shutil.rmtree(base, ignore_errors=True)
print('reads', n, 'exceptions', len(errors), set(errors) if errors else '', 'stale-id->other-file', wrong)
sys.exit(1 if errors or wrong else 0)
