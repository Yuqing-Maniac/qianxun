import os, sys, time
os.environ['QIANXUN_QT'] = 'none'
sys.path.insert(0, r'C:\qxport\QianXun\app')
import qianxun as q
out = open(r'C:\qxport\drive.txt', 'w', encoding='utf-8')
def P(*a): out.write(' '.join(map(str, a)) + '\n'); out.flush()
import ctypes
gdt = ctypes.windll.kernel32.GetDriveTypeW; gdt.argtypes = [ctypes.c_wchar_p]
def probe():   # Wine caches GetLogicalDrives per process; probe letters instead (test only)
    return [(chr(65 + i) + ':\\', gdt(chr(65 + i) + ':\\')) for i in range(26) if gdt(chr(65 + i) + ':\\') > 1]
class E(q.EngineWin):
    def _drive_mask(self):
        return tuple(probe())
    def _root_pairs(self):
        return [p for p in q.win_select_roots(self.cfg, probe()) if p[0][0] not in 'CZ']
q.INDEX_FILE = r'C:\qxport\drive_index.db'
idx = q.Index(); e = E(idx, dict(q.DEFAULT_CONFIG)); e.start()
t = time.time()
while e.status.get('state') != 'ready': time.sleep(0.05)
P('start roots', e.roots, 'mask', hex(q.win_drive_mask()))
open(r'C:\qxport\drive.flag1', 'w').close()
t = time.time()
while 'X:\\' not in e.roots and time.time() - t < 20: time.sleep(0.05)
P('X added after %.2f s' % (time.time() - t), e.roots, 'live', idx.live, 'watched', list(e.dir_wd), type(e.ino).__name__)
time.sleep(0.5)
open(r'X:\u盘\新照片.jpg', 'w').close()
t = time.time()
ok = False
while time.time() - t < 5 and not ok:
    with idx.lock:
        d = idx.dir_ids.get(q.dkey(r'X:\u盘'))
        ok = d is not None and any(idx.names[c] == '新照片.jpg' for c in idx.dir_children[d])
    time.sleep(0.02)
P('live on X: %s %.2f s' % (ok, time.time() - t))
open(r'C:\qxport\drive.flag2', 'w').close()
t = time.time()
while 'X:\\' in e.roots and time.time() - t < 20: time.sleep(0.05)
P('X removed after %.2f s' % (time.time() - t), e.roots, 'live', idx.live, 'dir_ids has X', q.dkey('X:\\') in idx.dir_ids, 'watches', list(e.dir_wd))
e.post('quit'); e.join(10)
P('DONE')
