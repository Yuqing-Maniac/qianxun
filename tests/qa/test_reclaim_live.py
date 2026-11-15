import os,sys,time,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'app'))
import qianxun as q
with tempfile.TemporaryDirectory() as td:
 root=Path(td)/'files';root.mkdir();data=Path(td)/'data';data.mkdir()
 q.INDEX_FILE=str(data/'index.db');q.CACHE_DIR=str(data);q.LOG_FILE=str(data/'test.log')
 (root/'before.txt').write_text('hello')
 cfg=dict(q.DEFAULT_CONFIG,roots=[str(root)],excludes=[],index_removable=False)
 idx=q.Index();eng=q.make_engine(idx,cfg)
 eng.COMPACT_INTERVAL=.1
 original_ready=eng._set_ready
 injected=[]
 def ready():
  original_ready()
  if not injected:
   with idx.lock:
    d=idx.dir_ids[q.dkey(str(root))]
    for i in range(66000):
     e=idx._add_entry(d,'dead-%d'%i,False)
     idx._remove_entry(e,[])
    injected.append(idx.gen)
 eng._set_ready=ready
 def wait(cond):
  deadline=time.monotonic()+15
  while time.monotonic()<deadline:
   with idx.lock:
    if cond():return
   time.sleep(.05)
  raise AssertionError(eng.status)
 def names():return {n for n,k in zip(idx.names,idx.kind) if k!=q.KIND_DEAD}
 eng.start()
 try:
  wait(lambda:eng.status['state']=='ready' and 'before.txt' in names())
  wait(lambda: injected and idx.gen > injected[0])
  assert len(idx.names)==idx.live
  (root/'created.txt').write_text('content');wait(lambda:'created.txt' in names())
  (root/'created.txt').rename(root/'renamed.txt');wait(lambda:'renamed.txt' in names() and 'created.txt' not in names())
  (root/'renamed.txt').unlink();wait(lambda:'renamed.txt' not in names())
 finally:
  eng.post('quit');eng.join(15)
 assert not eng.is_alive()
 other=q.Index();assert other.load(q.INDEX_FILE,eng._header());assert 'before.txt' in other.names
 print('PASS live compaction, watcher continuity, create/rename/delete/cache shutdown')
