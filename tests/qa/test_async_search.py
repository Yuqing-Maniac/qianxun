import os,sys,time,threading,tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'app'))
import qianxun as q
assert q.HAVE_QT,q._QT_ERROR
app=q.QApplication([])
# OS shell icon extraction and tray integration are independent of search scheduling.
class Icons:
 def get(self,*a):return q.QIcon()
q.IconCache=Icons
q.MainWindow._build_tray=lambda self,icon:setattr(self,'tray',None)
idx=q.Index();d=idx._new_dir(os.path.abspath('sample'),-1)
for n in ['alpha.txt','beta.pdf','latest.json']:idx._add_entry(d,n,False,10,1)
eng=q.make_engine(idx,q.DEFAULT_CONFIG)
win=q.MainWindow(dict(q.DEFAULT_CONFIG),idx,eng,q.QIcon());win.show()
def pump_until(cond,timeout=5):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  app.processEvents()
  if cond():return
  time.sleep(.005)
 raise AssertionError('timed out')
def idle():return win._search_task is None and not win.timer.isActive()
pump_until(idle)
assert win.model.rowCount()==3
original=win.searcher.run
entered=threading.Event();release=threading.Event()
def slow(*a):
 entered.set();assert release.wait(3);return original(*a)
win.searcher.run=slow
win.search.setText('alpha');win.flush_search()
assert entered.wait(1)
t=time.monotonic();win.model.data(win.model.index(0,0));assert time.monotonic()-t<.1
beats=[];timer=q.QTimer();timer.setInterval(10);timer.timeout.connect(lambda:beats.append(1));timer.start()
win.search.setText('beta');win.flush_search();win.search.setText('latest');win.flush_search()
end=time.monotonic()+.15
while time.monotonic()<end:app.processEvents();time.sleep(.005)
assert len(beats)>=5,beats
release.set();pump_until(idle)
assert [idx.names[i] for i in win.model.rows]==['latest.json']
# Completed results from a replaced index must not be installed.
entered.clear();release.clear();win.search.setText('alpha');win.flush_search();assert entered.wait(1)
release.set();win._search_task[1].join(2)
with idx.lock:
 idx.clear();d=idx._new_dir(os.path.abspath('new'),-1);idx._add_entry(d,'alpha-new.txt',False,1,1)
win.searcher.run=original
pump_until(idle)
assert [idx.names[i] for i in win.model.rows]==['alpha-new.txt']
# Result counts and exports retain the full set while the view fetches pages.
with idx.lock:
 for i in range(5000):idx._add_entry(d,'paged%05d.txt'%i,False,1,1)
win.search.setText('paged');win.flush_search();pump_until(idle)
assert len(win.model.rows)==5000
assert win.model.rowCount()<5000
assert win.model.canFetchMore()
before=win.model.rowCount();win.model.fetchMore();assert win.model.rowCount()>before
win.model.load_through(5000);assert win.model.rowCount()==5000
assert not win.model.canFetchMore()
win.quitting=True;win.close();timer.stop()
print('PASS responsive GUI, latest request wins, stale generation rejected')

