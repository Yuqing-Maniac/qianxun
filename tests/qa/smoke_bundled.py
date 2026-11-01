"""Run with the bundled interpreter: <ext>/runtime/x86_64/bin/python3 smoke_bundled.py <ext>/app <root>"""
import os, sys, time
sys.path.insert(0, sys.argv[1])
import qianxun as q
app = q.QApplication(sys.argv[:1])
cfg = dict(q.DEFAULT_CONFIG); cfg.update(roots=[sys.argv[2]], excludes=[], index_removable=False)
idx = q.Index(); eng = q.Engine(idx, cfg); eng.start()
t = time.time()
while eng.status['state'] != 'ready' and time.time() - t < 30:
    time.sleep(0.05)
win = q.MainWindow(cfg, idx, eng, q.make_app_icon()); win.show()
win.search.setText('报告'); win.flush_search(); app.processEvents()
names = [idx.names[win.model.entry(r)] for r in range(win.model.rowCount())]
print('binding', q.QT_BINDING, q.QT_VER, 'python', sys.version.split()[0], 'indexed', idx.live, 'hits', names)
open(os.path.join(sys.argv[2], 'new 报告.txt'), 'w').close()
t = time.time()
while time.time() - t < 5 and win.model.rowCount() < 2:
    app.processEvents(); time.sleep(0.05)
print('live update hits', win.model.rowCount())
ok = win.model.rowCount() == 2
win.quit_app()
sys.exit(0 if ok else 1)
