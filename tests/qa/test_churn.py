"""A log file appended every 100 ms inside a watched dir: how often does the GUI re-search, and CPU use."""
import os
import sys
import time
import shutil
import tempfile
import threading
import resource

from qa_common import q, wait_ready

app = q.QApplication.instance() or q.QApplication(sys.argv)
base = tempfile.mkdtemp(prefix='qa_churn_')
for i in range(2000):
    d = os.path.join(base, 'd%d' % (i % 40))
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'f%d.txt' % i), 'w').close()
logf = os.path.join(base, 'd1', 'app.log')
cfg = dict(q.DEFAULT_CONFIG)
cfg.update(roots=[base], excludes=[], index_removable=False)
idx = q.Index()
eng = q.Engine(idx, cfg)
eng.start()
assert wait_ready(eng)
win = q.MainWindow(cfg, idx, eng, q.make_app_icon())
win.show()
query = sys.argv[1] if len(sys.argv) > 1 else ''
win.search.setText(query)
win.flush_search()

calls = [0]
orig = win.do_search


def counted(*a, **k):
    calls[0] += 1
    return orig(*a, **k)


win.do_search = counted
stop = threading.Event()


def appender():
    while not stop.is_set():
        with open(logf, 'a') as f:
            f.write('line\n')
        time.sleep(0.1)


t = threading.Thread(target=appender)
t.start()
r0 = resource.getrusage(resource.RUSAGE_SELF)
t0 = time.time()
while time.time() - t0 < 10:
    app.processEvents()
    time.sleep(0.01)
r1 = resource.getrusage(resource.RUSAGE_SELF)
stop.set()
t.join()
cpu = (r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime)
print('query=%r rows=%d: %d re-searches in 10 s, CPU %.2f s' % (query, win.model.rowCount(), calls[0], cpu))
win.quit_app()
shutil.rmtree(base, ignore_errors=True)
