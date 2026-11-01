import numpy as np, re
from scipy.io import wavfile
src=open('make_bgm.py').read().split('# ---------- arrangement ----------')[0]
exec(src)
D='sfx/'
def save(name,y,peak_db=-3):
    if y.ndim==1: y=np.stack([y,y],1)
    y=y-y.mean(0); n=len(y); f=int(0.004*SR); y[:f]*=np.linspace(0,1,f)[:,None]; y[-f:]*=np.linspace(1,0,f)[:,None]
    y=y/np.abs(y).max()*10**(peak_db/20)
    wavfile.write(D+name,SR,(y*32767).astype(np.int16)); print(name,round(len(y)/SR,2))
def rv(y,rt=1.2,mix=0.3,tail=1.0):
    st=np.stack([y,y],1); st=np.vstack([st,np.zeros((int(tail*SR),2))])
    w=np.zeros_like(st)
    for c in range(2): w[:,c]=signal.fftconvolve(st[:,c],make_ir(rt,seed=3+c))[:len(st)]
    return st*(1-mix*0.5)+w*mix
# whoosh 0.6
n=int(0.6*SR); y=vsweep(0.6,400,7000,0.3,21); e=np.sin(np.pi*np.linspace(0,1,n))**1.6; y=y*e
y2=np.stack([y,np.roll(y,60)],1); save('whoosh.wav',y2)
# pop
t=tt(0.14); f=300+700*np.exp(-t*60); y=np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*38)+0.25*np.sin(2*np.pi*1900*t)*np.exp(-t*90)
save('pop.wav',rv(y,0.5,0.12,0.2),-5)
# click
t=tt(0.05); y=np.sin(2*np.pi*1800*t)*np.exp(-t*220)*0.6+np.random.default_rng(2).standard_normal(len(t))*np.exp(-t*500)*0.3
save('click.wav',hp(y,500),-9)
# key
t=tt(0.08); r=np.random.default_rng(4).standard_normal(len(t))
y=bp(r,1500,5000)*np.exp(-t*140)*0.5+np.sin(2*np.pi*420*t)*np.exp(-t*90)*0.5
save('key.wav',y,-10)
# success: two note chime
y=np.zeros(int(1.6*SR)); put_=lambda b,x,t0:b.__setitem__(slice(int(t0*SR),int(t0*SR)+len(x)),b[int(t0*SR):int(t0*SR)+len(x)]+x)
a=bell(86,1.2,0.6)[:int(1.2*SR)]; b=bell(93,1.4,0.7)[:int(1.4*SR)]
put_(y,a,0.0); put_(y,b[:int(1.3*SR)],0.13)
save('success.wav',rv(y,1.4,0.22,0.5),-4)
# riser 1.5
d=1.5; n=int(d*SR); r=vsweep(d,300,11000,0.3,8)*np.linspace(0,1,n)**2
p=pad([62,69,74,78],d,a=1.4,r=0.05,cut=2200,vel=1.0)[:n]*np.linspace(0,1,n)**2
y=r*0.8+p*0.8; save('riser.wav',y)
# hit
H=np.zeros((int(4.5*SR),2)); 
bo=boom(2.2,1.0); H[:len(bo)]+=bo[:,None]*0.9
b_=sum(bell(m,4.5,0.35) for m in [74,78,81,85,88]); H[:len(b_)]+=b_[:,None]*0.8
sh=shimmer(3.5,1.0); H[:len(sh)]+=pan(sh,0)*1.5
st=rv(H[:,0],2.2,0.35,0.3)[:len(H)]
H2=H+0.6*st; H2[:,1]=H[:,1]*1+0.6*st[:,1]; 
save('hit.wav',H2)
# tick
t=tt(0.09); y=np.sin(2*np.pi*2300*t)*np.exp(-t*90)+0.5*np.sin(2*np.pi*5500*t)*np.exp(-t*160)
save('tick.wav',y,-8)
