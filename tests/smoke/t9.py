import sys, os, time, json, shutil
os.environ['XDG_CACHE_HOME']='/tmp/qianxun-tests/c9'; os.environ['XDG_CONFIG_HOME']='/tmp/qianxun-tests/f9'
os.makedirs('/tmp/qianxun-tests/f9/qianxun', exist_ok=True)
json.dump({'roots':['/tmp/qianxun-tests/tree'],'excludes':[]}, open('/tmp/qianxun-tests/f9/qianxun/config.json','w'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'app')); import qianxun as qx
QTimer=qx.QTimer; QApplication=qx.QApplication
res=[]
def run(w):
    w.search.setText('延迟测试'); w.flush_search()
    seq=[('create','/tmp/qianxun-tests/tree/延迟测试A.txt',None),('rename','/tmp/qianxun-tests/tree/延迟测试A.txt','/tmp/qianxun-tests/tree/延迟测试B.txt'),('delete','/tmp/qianxun-tests/tree/延迟测试B.txt',None)]
    log=open('/tmp/qianxun-tests/tree/延迟日志.log','a')
    st={'k':0,'t0':0,'phase':'act'}
    def names(): return [w.index.names[i] for i in w.model.rows]
    def tick():
        log.write('x'*100+'\n'); log.flush()   # 持续追加的日志干扰
        k=st['k']
        if k>=len(seq): print('results', res); w.quit_app(); return
        op,a,b=seq[k]
        if st['phase']=='act':
            if op=='create': open(a,'w').close()
            elif op=='rename': os.rename(a,b)
            else: os.remove(a)
            st['t0']=time.time(); st['phase']='wait'
        else:
            n=names(); ok = ('延迟测试A.txt' in n) if op=='create' else (('延迟测试B.txt' in n and '延迟测试A.txt' not in n) if op=='rename' else ('延迟测试B.txt' not in n))
            if ok: res.append((op, round(time.time()-st['t0'],2))); st['k']+=1; st['phase']='act'
            elif time.time()-st['t0']>15: res.append((op,'timeout')); st['k']+=1; st['phase']='act'
        QTimer.singleShot(50, tick)
    QTimer.singleShot(500, tick)
def script():
    w=[w for w in QApplication.topLevelWidgets() if isinstance(w, qx.MainWindow)][0]
    if w.engine.status['state']!='ready': QTimer.singleShot(200, script); return
    run(w)
_o=qx.MainWindow.__init__
def _i(self,*a,**k): _o(self,*a,**k); QTimer.singleShot(300, script)
qx.MainWindow.__init__=_i
sys.argv=['q']; qx.main()
