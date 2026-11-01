import os,subprocess,glob,sys
roots=sys.argv[1:]
elfs=[]
for root in roots:
  for dp,_,fs in os.walk(root):
    for f in fs:
        p=os.path.join(dp,f)
        if os.path.islink(p) or not os.path.isfile(p): continue
        if open(p,'rb').read(4)==b'\x7fELF': elfs.append(p)
def syms(p,flag):
    out=subprocess.run(['aarch64-linux-gnu-nm','-D',flag,p],capture_output=True,text=True).stdout
    return {l.split()[-1].split('@')[0] for l in out.splitlines() if l.strip()}
und=set(); dfn=set()
for p in elfs: und|=syms(p,'--undefined-only'); dfn|=syms(p,'--defined-only')
for p in glob.glob('/usr/aarch64-linux-gnu/lib/*.so*'):
    if os.path.isfile(p): dfn|=syms(p,'--defined-only')
miss=sorted(s for s in und-dfn if s.isidentifier() and not any(k in s for k in ('_ZN','_ZS','_Zn','_Zd','__cxa','__gxx','_Unwind')))
open('/tmp/stubs/stub2.c','w').write(''.join('void %s(void){__builtin_trap();}\n'%s for s in miss))
print(len(miss))
