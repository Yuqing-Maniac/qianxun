import os, sys, time, tempfile, unittest
from pathlib import Path
from array import array
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'app'))
import qianxun as q

class Resources(unittest.TestCase):
 def make_index(self, n=150000):
  idx=q.Index(); d=idx._new_dir(os.path.abspath('sample'),-1)
  for i in range(n): idx._add_entry(d, 'File%07d.txt' % (n-i),False,i,float(i))
  return idx
 def test_compact_order_and_roundtrip(self):
  idx=self.make_index(); eng=q.make_engine(idx,q.DEFAULT_CONFIG)
  eng._compute_order(); self.assertEqual(idx.name_order[0].typecode,'I')
  self.assertLess(sys.getsizeof(idx.dir_children[0]),idx.live*5)
  s=q.Searcher(idx); rows=s.run(q.Query('File')); self.assertLess(sys.getsizeof(s.prev[4]),idx.live*5)
  for col in range(4):
   for desc in (False,True):
    out,_=q.sort_search_results(idx,s,list(rows),col,desc)
    key=idx.lnames.__getitem__ if col<2 else (idx.size if col==2 else idx.mtime).__getitem__
    self.assertEqual(out,sorted(rows,key=key,reverse=desc))
  idx._remove_entry(10,[])
  with tempfile.TemporaryDirectory() as td:
   fn=os.path.join(td,'index.db');idx.save(fn,{});other=q.Index();self.assertTrue(other.load(fn,{}));other.ensure_children()
   self.assertEqual(other.live,idx.live)
   self.assertEqual([n for n,k in zip(idx.names,idx.kind) if k!=q.KIND_DEAD],other.names)
   self.assertIsInstance(other.dir_children[0],array)
 def test_sort_ignores_stat_only_version(self):
  idx=self.make_index(30); eng=q.make_engine(idx,q.DEFAULT_CONFIG);eng._compute_order()
  idx.version+=1
  self.assertEqual(eng.order_version,idx.struct_version)
 def test_linux_sweep_is_bounded(self):
  idx=self.make_index(2000);eng=q.Engine(idx,q.DEFAULT_CONFIG);eng._start_sweep(None)
  with patch.object(q.os,'lstat',return_value=type('S',(),{'st_size':5,'st_mtime':1})()) as stat:
   self.assertTrue(eng._sweep_step());self.assertLessEqual(stat.call_count,256)
 def test_worker_returns_compact_consistent_result(self):
  idx=self.make_index(5000);s=q.Searcher(idx);task=q.SearchTask(idx,s,q.Query('txt'),None,0,False)
  task.start();task.join(10);self.assertTrue(task.done.is_set());self.assertIsNone(task.error)
  rows,ver,sver,gen,unsorted,ms=task.result
  self.assertIsInstance(rows,array);self.assertEqual(len(rows),idx.live)
  self.assertEqual(list(rows),sorted(rows,key=idx.lnames.__getitem__))
 def test_upgrade_journal_can_be_synced_on_windows(self):
  with tempfile.TemporaryDirectory() as td:
   journal=os.path.join(td,'journal')
   q._write_journal(journal,'progress',(1,2,2),(1,2,3),'app/qianxun.py',False)
   self.assertEqual(q._read_journal(journal)['state'],'progress')

if __name__=='__main__':unittest.main()
