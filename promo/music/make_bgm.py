import json, numpy as np, os
from scipy import signal
from scipy.io import wavfile
SR=44100
rng=np.random.default_rng(7)
T=json.load(open('/home/claude/video/q/timeline.json'))
TOTAL=T['total']; N=int(round(TOTAL*SR))
sc={s['id']:(s['start'],s['end']) for s in T['scenes']}
OUT='/home/claude/video/q/music'
mtof=lambda m:440*2**((m-69)/12)
def tt(d): return np.arange(int(d*SR))/SR
def adsr(n,a,d,s,r):
    e=np.ones(n); a=int(a*SR); d=int(d*SR); r=int(r*SR)
    a=min(a,n); e[:a]=np.linspace(0,1,a,endpoint=False) if a else 1
    d=min(d,n-a); 
    if d>0: e[a:a+d]=np.linspace(1,s,d)
    e[a+d:]=s
    r=min(r,n)
    if r>0: e[n-r:]*=np.linspace(1,0,r)
    return e
def pblep(t,dt):
    o=np.zeros_like(t); m=t<dt; x=t[m]/dt; o[m]=2*x-x*x-1
    m=t>1-dt; x=(t[m]-1)/dt; o[m]=x*x+2*x+1
    return o
def saw(f,n,ph0=0.0):
    dt=f/SR; ph=(ph0+np.arange(n)*dt)%1.0
    return 2*ph-1-pblep(ph,dt)
def lp(x,fc,o=2): return signal.sosfilt(signal.butter(o,fc,'low',fs=SR,output='sos'),x)
def hp(x,fc,o=2): return signal.sosfilt(signal.butter(o,fc,'high',fs=SR,output='sos'),x)
def bp(x,a,b,o=2): return signal.sosfilt(signal.butter(o,[a,b],'band',fs=SR,output='sos'),x)
def pan(x,p): # p -1..1 constant power
    a=(p+1)*np.pi/4; return np.stack([x*np.cos(a),x*np.sin(a)],1)
def put(buf,x,t,p=0.0,g=1.0):
    i=int(round(t*SR))
    if i>=len(buf) or i+len(x)<=0: return
    if x.ndim==1: x=pan(x,p)
    s=max(0,-i); e=min(len(x),len(buf)-i)
    buf[i+s:i+e]+=g*x[s:e]
def vsweep(dur,f0,f1,q=0.15,seed=0):
    # state variable bandpass swept (log) over noise
    n=int(dur*SR); r=np.random.default_rng(seed).standard_normal(n)
    f=np.geomspace(f0,f1,n); F=2*np.sin(np.pi*np.minimum(f,SR/6)/SR)
    y=np.zeros(n); lo=bpv=0.0
    for i in range(n):
        hi=r[i]-lo-q*bpv; bpv+=F[i]*hi; lo+=F[i]*bpv; y[i]=bpv
    return y/ (np.max(np.abs(y))+1e-9)
# ---------- instruments ----------
def pad(notes,dur,a=0.6,r=1.5,cut=1100,detune=9,vel=1.0):
    n=int((dur+r)*SR); y=np.zeros(n)
    for m in notes:
        f=mtof(m)
        for c in (-detune,0,detune):
            y+=saw(f*2**(c/1200),n,rng.random())
    y=lp(y,cut,2); y=hp(y,140)
    return y*adsr(n,a,0.5,0.8,r)*vel/ (len(notes)*3)*1.8
def sub(m,dur,vel=1.0):
    n=int((dur+0.3)*SR); t=np.arange(n)/SR; f=mtof(m)
    y=np.sin(2*np.pi*f*t); y=np.tanh(1.8*y)*0.7+0.25*np.sin(4*np.pi*f*t)
    return y*adsr(n,0.01,0.2,0.85,0.25)*vel
def pluck(m,dur=0.5,vel=1.0,bright=3000):
    n=int(dur*SR); t=np.arange(n)/SR; f=mtof(m); y=np.zeros(n)
    for h in range(1,9):
        y+=np.sin(2*np.pi*f*h*t)/h**1.3*np.exp(-t*(6+h*5))
    y+=0.5*np.sin(2*np.pi*f*t)*np.exp(-t*7)
    y=lp(y,bright,2)
    return y*vel*np.minimum(1,t/0.003)
def bell(m,dur=3.5,vel=1.0):
    n=int(dur*SR); t=np.arange(n)/SR; f=mtof(m); y=np.zeros(n)
    for ratio,amp,dec in [(1,1,1.2),(2.0,0.5,1.6),(2.76,0.35,2.2),(4.07,0.22,3.0),(5.4,0.12,4.0),(6.8,0.07,5.5)]:
        y+=amp*np.sin(2*np.pi*f*ratio*t+rng.random()*6)*np.exp(-t*dec)
    return y*vel*np.minimum(1,t/0.002)*0.5
def kick(vel=1.0):
    n=int(0.45*SR); t=np.arange(n)/SR
    f=45+110*np.exp(-t*28); ph=2*np.pi*np.cumsum(f)/SR
    y=np.sin(ph)*np.exp(-t*8)+0.15*np.random.default_rng(1).standard_normal(n)*np.exp(-t*120)
    return np.tanh(1.5*y)*vel*0.9
def clap(vel=1.0,seed=0):
    n=int(0.3*SR); r=np.random.default_rng(seed).standard_normal(n); t=np.arange(n)/SR
    y=bp(r,1200,5500)*(np.exp(-t*22)+0.6*np.exp(-((t-0.012)%0.012)*0)*np.exp(-t*60))
    y*=np.minimum(1,t/0.001); return y*vel*0.5
def snap(vel=1.0):
    n=int(0.12*SR); t=np.arange(n)/SR; r=np.random.default_rng(3).standard_normal(n)
    return bp(r,2000,6000)*np.exp(-t*50)*vel*0.4+np.sin(2*np.pi*1100*t)*np.exp(-t*60)*0.2*vel
def hat(vel=1.0,open_=False,seed=0):
    n=int((0.25 if open_ else 0.05)*SR); t=np.arange(n)/SR
    r=np.random.default_rng(seed).standard_normal(n)
    return hp(r,7000)*np.exp(-t*(14 if open_ else 90))*vel*0.25
def tick(vel=1.0,hi=True):
    n=int(0.09*SR); t=np.arange(n)/SR; f=2300 if hi else 1500
    y=np.sin(2*np.pi*f*t)*np.exp(-t*90)+0.5*np.sin(2*np.pi*f*2.4*t)*np.exp(-t*160)
    return y*vel*0.5
def revcym(dur,seed=1,vel=1.0):
    y=vsweep(dur,500,9000,0.35,seed)+0.6*hp(np.random.default_rng(seed).standard_normal(int(dur*SR)),5000)*np.linspace(0,1,int(dur*SR))**2
    t=np.linspace(0,1,len(y)); y=y*t**2.2
    y[-int(0.004*SR):]*=np.linspace(1,0,int(0.004*SR))
    return y/ (np.max(np.abs(y))+1e-9)*vel
def boom(dur=2.0,vel=1.0):
    n=int(dur*SR); t=np.arange(n)/SR; f=38+60*np.exp(-t*7); ph=2*np.pi*np.cumsum(f)/SR
    y=np.sin(ph)*np.exp(-t*2.3)*np.minimum(1,t/0.004)
    return np.tanh(1.3*y)*vel*0.9
def shimmer(dur=3.5,vel=1.0):
    n=int(dur*SR); t=np.arange(n)/SR; r=np.random.default_rng(5).standard_normal(n)
    y=hp(r,6000)*np.exp(-t*1.6)*(0.6+0.4*np.sin(2*np.pi*9*t)); return lp(y,14000)*vel*0.12
def make_ir(rt=2.8,pre=0.02,seed=0,damp=6500):
    n=int((rt*1.15)*SR); r=np.random.default_rng(seed).standard_normal(n); t=np.arange(n)/SR
    ir=r*10**(-3*t/rt); ir=lp(ir,damp,2); ir=hp(ir,180,1)
    ir=lp(ir,damp*0.6,1)*1.0
    ir=np.concatenate([np.zeros(int(pre*SR)),ir]); ir[:int(0.04*SR)]*=np.linspace(0.2,1,int(0.04*SR))
    return ir/np.sqrt(np.sum(ir**2))
def reverb(x,rt=2.8,wet_hp=250):
    out=np.zeros((len(x)+int(rt*1.3*SR)+4000,2))
    for c in range(2):
        ir=make_ir(rt,seed=11+c)
        out[:len(x)+len(ir)-1 if len(x)+len(ir)-1<len(out) else len(out),c]=signal.fftconvolve(x[:,c],ir)[:len(out)]
    return out

# ---------- arrangement ----------
BPM=100; BEAT=60/BPM; BAR=BEAT*4
CH={ 'D':dict(pad=[62,66,69,74],pad_lo=[50,57],root=38,arp=[69,74,78,81],name='D'),
     'A':dict(pad=[61,64,69,73],pad_lo=[45,52],root=33,arp=[69,73,76,81],name='A'),
     'Bm':dict(pad=[62,66,71,74],pad_lo=[47,54],root=35,arp=[71,74,78,83],name='Bm'),
     'G':dict(pad=[62,67,71,74],pad_lo=[43,50],root=31,arp=[67,71,74,79],name='G')}
PROG=['D','A','Bm','G']
dry=np.zeros((N,2)); wet=np.zeros((N,2)); duck=np.zeros((N,2)); bassb=np.zeros((N,2)); drum=np.zeros((N,2)); kickt=[]
G0=sc['search'][0]   # groove grid origin
hit_t=sc['title'][0]+0.7
# hook: bars from 0, Bm/G alternating, tension
hook_end=sc['title'][0]
bars=int(np.ceil(hook_end/BAR))
for b in range(bars):
    t0=b*BAR; ch=CH[['Bm','G','Bm','A'][b%4]]
    d=min(BAR,hook_end+0.7-t0)
    if d<=0: break
    # low pulsing pad: 4 pulses per bar through amplitude modulation
    p=pad(ch['pad_lo']+[ch['pad'][0]],d,a=0.5,r=0.8,cut=520+60*b,vel=0.55)
    tm=np.arange(len(p))/SR; p*= (0.55+0.45*np.sin(2*np.pi*(1/BEAT)*tm-np.pi/2)**2)
    put(wet,p,t0,0,0.9); put(dry,p,t0,0,0.5)
    put(bassb,sub(ch['root'],d,0.5),t0,0)
    for k in range(4): put(dry,tick(0.45+0.15*(k==0),k%2==0),t0+k*BEAT,-0.3+0.2*k%0.6-0.3)
    if b>=1:
        for k,m in enumerate([ch['arp'][1],ch['arp'][2]]):
            put(wet,pluck(m,0.9,0.22,2200),t0+(1.5+k*1.0)*BEAT,0.4*(-1)**k,1.0)
# riser into title
rs=hit_t-2.6
r=vsweep(2.6,300,10000,0.3,3); r=r*np.linspace(0,1,len(r))**2.0
put(wet,pan(r,0),rs,0,0.55); put(dry,pan(r,0),rs,0,0.35)
# reverse swell on tonal: pad rise
pr=pad([62,69,74,78],2.6,a=2.4,r=0.05,cut=900,vel=0.8)*np.linspace(0,1,int(2.65*SR))**2
put(wet,pr,rs,0,0.8)
# the hit
put(bassb,boom(2.2,1.0),hit_t,0)
b_ = sum(bell(m,4.5,0.35) for m in [74,78,81,85,88])
put(wet,b_,hit_t,0,1.0); put(dry,b_,hit_t,0,0.35)
put(wet,pan(shimmer(),0),hit_t,0,1.0); put(dry,pan(shimmer(),0),hit_t,0,0.6)
# title pad airy (hit_t .. groove start)
for i,k in enumerate(['D','A']):
    t0=hit_t+i*BAR*0.0 if i==0 else hit_t+BAR
    d=(sc['search'][0]-t0)+0.3 if i==1 else BAR
    p=pad(CH[k]['pad']+CH[k]['pad_lo'],d,a=0.2,r=1.2,cut=1500,vel=0.8)
    put(wet,p,t0,0,0.9); put(dry,p,t0,0,0.45)
    for j,m in enumerate(CH[k]['arp']):
        put(wet,pluck(m+12 if j<2 else m,1.2,0.12,2600),t0+0.5+j*BEAT*0.5,(-1)**j*0.5,1.0)
# groove
def section_bars():
    t=G0; i=0
    while t<TOTAL-0.5:
        yield i,t; t+=BAR; i+=1
OFF0=sc['offline'][0]; OUT0=sc['outro'][0]
arp_pat=[0,1,2,3,2,1,2,3]
for i,t0 in section_bars():
    if t0>=OUT0-0.01: break
    ch=CH[PROG[i%4]]
    offline=t0>=OFF0-0.01
    # pad: sustained through bar (overlap)
    p=pad(ch['pad']+ch['pad_lo'],BAR+0.2,a=0.25,r=0.9,cut=1250 if not offline else 1600,vel=0.85 if not offline else 1.05)
    put(duck,p,t0,0,1.0)
    if offline:
        p2=pad([m+12 for m in ch['pad'][:3]],BAR+0.2,a=0.4,r=1.0,cut=3000,vel=0.45,detune=12); put(duck,p2,t0,0.2,1.0)
    bs=sub(ch['root'],BAR*0.5-0.02,0.9) ; put(bassb,bs,t0,0); put(bassb,sub(ch['root'],BAR*0.5-0.02,0.8),t0+BAR*0.5,0)
    if offline: put(bassb,sub(ch['root']+12,BEAT*0.5,0.3),t0+3.5*BEAT,0)
    # drums
    for k in (0,2):
        put(drum,kick(1.0 if k==0 else 0.85),t0+k*BEAT,0,1.0); kickt.append(t0+k*BEAT)
    if offline: kickt.append(t0+1.5*BEAT); put(drum,kick(0.35),t0+3.5*BEAT,0)
    for k in (1,3):
        put(drum,clap(0.8,i*7+k),t0+k*BEAT,0.1,1.0)
        put(drum,snap(0.5),t0+k*BEAT,-0.1,1.0)
    for k in range(8):
        v=0.5 if k%2 else 0.8
        put(drum,hat(v*(1.0 if offline else 0.7),False,k),t0+(k*0.5+0.0)*BEAT+(0.02 if k%2 else 0),(-1)**k*0.35,1.0)
    if offline: put(drum,hat(0.9,True,9),t0+1.5*BEAT,0.3,0.8)
    # arp pluck 8ths
    for k in range(8):
        m=ch['arp'][arp_pat[k]]
        put(wet,pluck(m,0.55,0.20 if not offline else 0.22,2600),t0+k*BEAT*0.5,np.sin(k*1.3)*0.6,1.0)
        put(duck,pluck(m,0.4,0.10,2200),t0+k*BEAT*0.5,np.sin(k*1.3)*0.6,1.0)
    # counter arp 16ths high (offline)
    if offline:
        seq=[3,2,1,2,3,1,2,0]
        for k in range(16):
            if k%2==1 or k%4==0:
                m=ch['arp'][seq[k%8]]+12
                put(wet,pluck(m,0.3,0.10,5000),t0+k*BEAT*0.25+0.01,np.cos(k*0.9)*0.8,1.0)
    # bell accents on bar 1 of each 4
    if i%4==0:
        put(wet,bell(ch['arp'][1]+12,2.5,0.12),t0,0.3,1.0)
# whoosh/reverse swells ending at scene starts
for sid in ['search','how','syntax','filter','ops','offline','outro']:
    te=sc[sid][0]; d=1.6 if sid!='outro' else 2.2
    rc=revcym(d,hash(sid)%100,0.38)
    put(wet,pan(rc,0.0),te-d,0,0.8); put(dry,pan(rc,0),te-d,0,0.35)
# outro: final resolve
fin=sc['outro'][0]
fpad=pad([50,57,62,66,69,74,81],TOTAL-fin+1,a=0.15,r=0.1,cut=1700,vel=1.2)
# let pad envelope decay naturally
fpad*=np.exp(-np.arange(len(fpad))/SR/3.5)
put(wet,fpad,fin,0,1.0); put(dry,fpad,fin,0,0.5)
put(bassb,sub(38,3.5,0.9),fin,0)
put(bassb,boom(1.5,0.5),fin,0)
for j,m in enumerate([74,78,81,86]):
    b2=bell(m,6,0.40 if j==0 else 0.28); put(wet,b2,fin+0.12+j*0.14,(j-1.5)*0.35,1.0); put(dry,b2,fin+0.12+j*0.14,(j-1.5)*0.35,0.4)
put(wet,pan(shimmer(),0),fin,0,0.8)
# ---------- mix ----------
# sidechain from kick times
env=np.zeros(N)
for t in kickt:
    i=int(t*SR); n=int(0.35*SR)
    c=np.minimum(1,np.arange(n)/(0.28*SR)); g=1-0.55*(1-c)**1.6
    seg=env[i:i+n]; 
    if len(seg)==len(g) or True: pass
    cur=np.ones(min(n,N-i))*1.0; 
    env[i:i+len(cur)]=np.maximum(env[i:i+len(cur)],1-g[:len(cur)])
scg=1-0.5*env
duck*=scg[:,None]*1.0
wet_in=wet.copy(); wet_in+=duck*0.6
wet_in*=1.0
rv=reverb(wet_in,2.8)[:N]
rv=hp(rv.T,220,2).T if False else rv
mix=dry*0.7+duck*1.0+rv*0.75+bassb*0.9+drum*0.55
# duck wet pad slightly too
# mid-range carve for voice-over
def peak(x,f0,gdb,Q):
    A=10**(gdb/40); w=2*np.pi*f0/SR; al=np.sin(w)/(2*Q); c=np.cos(w)
    b=[1+al*A,-2*c,1-al*A]; a=[1+al/A,-2*c,1-al/A]
    return signal.lfilter(np.array(b)/a[0],np.array(a)/a[0],x,axis=0)
mix=peak(mix,500,-2.5,0.7); mix=peak(mix,1600,-3.5,0.6); mix=peak(mix,2800,-1.5,0.8)
mix=hp(mix.T,35,2).T
# stereo widen mild (mid/side)
m=(mix[:,0]+mix[:,1])/2; s=(mix[:,0]-mix[:,1])/2
mix=np.stack([m+1.25*s,m-1.25*s],1)
# fade out
fo=3.8; nfo=int(fo*SR); mix[-nfo:]*=(0.5+0.5*np.cos(np.linspace(0,np.pi,nfo)))[:,None]**1.5
mix[:int(0.02*SR)]*=np.linspace(0,1,int(0.02*SR))[:,None]
mix[-int(0.05*SR):]*=np.linspace(1,0,int(0.05*SR))[:,None]
np.save('/tmp/claude-0/mix_raw.npy',mix) if False else None
np.save(OUT+'/_mix_raw.npy',mix.astype(np.float32))
print('raw done',np.abs(mix).max())
