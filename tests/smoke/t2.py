import sys, os, time, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'app'))
import qianxun as qx
random.seed(1)
idx=qx.Index(); words=['report','报告','IMG','data','设计','config','lib','test','方案','video','backup','notes','x86','arm','总体']
exts=['.txt','.so','.py','.jpg','.docx','.pdf','.h','.c','.png','','.mp4']
t=time.time()
with idx.lock:
    dirs=[idx._new_dir('/',-1)]
    for k in range(60000):
        p=random.choice(dirs); e=idx._add_entry(p, f'{random.choice(words)}_{k}', True)
        dirs.append(idx._new_dir(qx.join_path(idx.dirs[p], idx.names[e]), e))
    for k in range(1000000):
        idx._add_entry(random.choice(dirs), f'{random.choice(words)}{k%977}_{random.choice(words)}{k}{random.choice(exts)}', False)
print('built', idx.live, round(time.time()-t,1))
import resource; print('RSS MB', resource.getrusage(resource.RUSAGE_SELF).ru_maxrss//1024)
eng=qx.Engine(idx, qx.DEFAULT_CONFIG); t=time.time(); eng._compute_order(); print('order', round(time.time()-t,2))
S=qx.Searcher(idx)
class W: pass
for s in ['', 'r','re','rep','repo','report','报告 方案','*.pdf','ext:jpg;png','report !img','data|video','backup/notes','regex:^img\\d+_','arm_ 99']:
    Q=qx.Query(s); t=time.time(); r=S.run(Q); t1=time.time()-t
    t=time.time()
    if len(r)>120000:
        order,n0=idx.name_order; mask=bytearray(len(idx.lnames))
        for i in r: mask[i]=1
        r=[i for i in order if mask[i]]
    else: r.sort(key=idx.lnames.__getitem__)
    print(f'{s!r:22} {len(r):>8}  search {t1*1000:6.0f}ms  sort {(time.time()-t)*1000:5.0f}ms')
t=time.time(); idx.save('/tmp/qianxun-tests/big.db', {'roots':['/'],'excludes':[]}); print('save', round(time.time()-t,2), os.path.getsize('/tmp/qianxun-tests/big.db')//2**20,'MB')
i2=qx.Index(); t=time.time(); print(i2.load('/tmp/qianxun-tests/big.db', {'roots':['/'],'excludes':[]}), 'load', round(time.time()-t,2))
print('RSS MB', resource.getrusage(resource.RUSAGE_SELF).ru_maxrss//1024)
