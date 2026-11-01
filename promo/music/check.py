import numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from scipy.io import wavfile; from scipy import signal
sr,x=wavfile.read('bgm.wav'); x=x/32768; m=x.mean(1)
print('len',len(x)/sr,'peak',np.abs(x).max(),'dc',x.mean(0),'clipped',(np.abs(x)>=0.9999).sum(),'start/end',np.abs(x[:50]).max(),np.abs(x[-50:]).max())
d=np.abs(np.diff(m)); print('max sample jump',d.max())
f,t,S=signal.spectrogram(m,sr,nperseg=4096,noverlap=3072)
fig,ax=plt.subplots(2,1,figsize=(14,8))
ax[0].pcolormesh(t,f,10*np.log10(S+1e-12),vmin=-110,vmax=-40,shading='auto'); ax[0].set_ylim(0,12000)
for tt in [10.484,11.184,15.389,23.502,36.095,49.74,55.603,64.868,74.16]: ax[0].axvline(tt,color='w',lw=.6)
rms=[20*np.log10(np.sqrt((m[i:i+sr//2]**2).mean())+1e-9) for i in range(0,len(m),sr//2)]
ax[1].plot(np.arange(len(rms))/2,rms); ax[1].set_ylabel('RMS dB'); ax[1].grid()
plt.tight_layout(); plt.savefig('bgm_spectrogram.png',dpi=80)
# band energy
F,P=signal.welch(m,sr,nperseg=8192)
for a,b in [(20,150),(150,300),(300,3000),(3000,8000),(8000,20000)]:
    print(a,b,round(10*np.log10(P[(F>=a)&(F<b)].sum()+1e-15),1))
print([round(v) for v in rms[::4]])
