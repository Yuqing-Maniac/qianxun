import sys, os, time, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'app'))
os.environ['XDG_CACHE_HOME']='/tmp/qianxun-tests/cache'; os.environ['XDG_CONFIG_HOME']='/tmp/qianxun-tests/conf'
import importlib; qx=importlib.import_module('qianxun')
root='/tmp/qianxun-tests/tree'; shutil.rmtree(root, ignore_errors=True)
for a in range(20):
    for b in range(50):
        d=f'{root}/项目{a}/sub{b}'; os.makedirs(d)
        for c in range(20): open(f'{d}/报告_{a}_{b}_{c}.docx' if c%3 else f'{d}/IMG_{c:04d}.jpg','w').write('x'*c)
cfg=dict(qx.DEFAULT_CONFIG); cfg['roots']=[root]; cfg['excludes']=[]
idx=qx.Index(); eng=qx.Engine(idx,cfg); t=time.time(); eng.start()
while eng.status['state']!='ready': time.sleep(0.05)
print('scan', idx.live, round(time.time()-t,2), eng.status)
S=qx.Searcher(idx)
def q(s, **k):
    Q=qx.Query(s, **k); 
    with idx.lock: r=S.run(Q)
    return r
print('报告', len(q('报告')), 'jpg', len(q('*.jpg')), 'ext', len(q('ext:jpg')), 'and', len(q('报告 _3_')), 'or', len(q('img_0001|img_0002')), 'not', len(q('sub1 !img')), 'path', len(q('项目3/sub1')), 'folder', len(q('folder:sub')), 'size', len(q('size:>10')), 'dm', len(q('dm:today')), 'regex', len(q('regex:^IMG_000[12]')))
# live updates
open(f'{root}/新建文件ABC.txt','w').close(); os.makedirs(f'{root}/新目录/深层'); open(f'{root}/新目录/深层/xyzfile','w').close()
os.rename(f'{root}/项目0', f'{root}/改名项目0'); shutil.rmtree(f'{root}/项目1')
time.sleep(1.5)
print('new', len(q('新建文件ABC')), len(q('xyzfile')), 'renamed', len(q('改名项目0/')), len(q('项目0/')), 'deleted', len(q('_1_')), 'live', idx.live)
with open(f'{root}/改名项目0/sub0/IMG_0000.jpg','w') as f: f.write('y'*5000)
time.sleep(1); r=q('改名项目0/sub0/IMG_0000.jpg'); print('size upd', idx.size[r[0]])
eng.post('quit'); eng.join(); print('saved', os.path.getsize('/tmp/qianxun-tests/cache/qianxun/index.db'))
idx2=qx.Index(); eng2=qx.Engine(idx2,cfg); t=time.time(); eng2.start()
while eng2.status['state']!='ready': time.sleep(0.02)
print('reload', idx2.live, round(time.time()-t,2), idx2.live==idx.live)
eng2.post('quit'); eng2.join()
