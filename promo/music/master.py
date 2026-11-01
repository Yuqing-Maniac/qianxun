import numpy as np, pyloudnorm as pyln, subprocess, json
from scipy import signal
from scipy.io import wavfile
SR=44100
x=np.load('_mix_raw.npy').astype(np.float64)
# gentle RMS-ish compressor (linked), 1.8:1 above -22 dBFS
env=np.abs(x).max(1); 
a=np.exp(-1/(0.02*SR)); r=np.exp(-1/(0.25*SR))
sm=signal.lfilter([1-a],[1,-a],env)  # avg-ish
sm=np.maximum(sm,1e-6); db=20*np.log10(sm)
over=np.maximum(db+20,0); gr=-over*(1-1/1.8)
g=10**(gr/20)
# smooth release
gs=signal.lfilter([1-r],[1,-r],g); g=np.minimum(g,gs) if False else gs
x*=g[:,None]
def tp(y):
    return 20*np.log10(np.abs(signal.resample_poly(y,4,1,axis=0)).max())
m=pyln.Meter(SR)
def limiter(y,ceil_db):
    c=10**(ceil_db/20); L=int(0.003*SR)
    pk=np.abs(y).max(1); need=np.minimum(1,c/np.maximum(pk,1e-9))
    # lookahead min filter then smooth
    from scipy.ndimage import minimum_filter1d, uniform_filter1d
    gm=minimum_filter1d(need,2*L+1,mode='nearest'); gm=uniform_filter1d(gm,L*2+1,mode='nearest')
    gm=np.minimum(gm,need) if False else gm
    out=y*gm[:,None]
    return out
y=x
for it in range(6):
    l=m.integrated_loudness(y); y=y*10**((-16-l)/20)
    y=limiter(y,-2.2)
    # final hard safety
    print(it,round(m.integrated_loudness(y),2),round(tp(y),2))
    if abs(m.integrated_loudness(y)+16)<0.15 and tp(y)<=-1.0: break
y=np.clip(y,-0.89,0.89)
y=y-y.mean(0)
wavfile.write('bgm.wav',SR,(np.clip(y,-1,1)*32767).astype(np.int16))
