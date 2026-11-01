#!/usr/bin/env python3
"""Report max GLIBC_x.y (and GLIBCXX/CXXABI/GCC) version required by ELF files under a dir."""
import os, re, subprocess, sys, collections
root=sys.argv[1]; res=collections.defaultdict(lambda:(( 0,0,0),None,None))
def ver(s): return tuple(int(x) for x in s.split('.'))
mx={}; elfs=0; archs=collections.Counter(); needed=collections.defaultdict(set)
for dp,_,fs in os.walk(root):
    for f in fs:
        p=os.path.join(dp,f)
        if os.path.islink(p) or not os.path.isfile(p): continue
        try:
            with open(p,'rb') as fh:
                if fh.read(4)!=b'\x7fELF': continue
        except OSError: continue
        elfs+=1
        h=subprocess.run(['readelf','-h',p],capture_output=True,text=True).stdout
        m=re.search(r'Machine:\s+(.*)',h); archs[m.group(1).strip() if m else '?']+=1
        out=subprocess.run(['readelf','-V',p],capture_output=True,text=True).stdout
        # version needs section: lines "Name: GLIBC_2.17  Flags: none  Version: 3"
        for k,v in re.findall(r'Name: (GLIBC|GLIBCXX|CXXABI|GCC)_([0-9.]+)',out):
            try: vv=ver(v)
            except: continue
            if k not in mx or vv>mx[k][0]: mx[k]=(vv,p)
        d=subprocess.run(['readelf','-d',p],capture_output=True,text=True).stdout
        for n in re.findall(r'NEEDED\)\s+Shared library: \[(.*?)\]',d): needed[n].add(p)
print('ELF files:',elfs,dict(archs))
for k,(v,p) in sorted(mx.items()): print(f'max {k}_{".".join(map(str,v))}  ({os.path.relpath(p,root)})')
if len(sys.argv)>2:
    bundled=set()
    for dp,_,fs in os.walk(root):
        for f in fs: bundled.add(f)
    ext=sorted(n for n in needed if n not in bundled)
    print('NEEDED not bundled:'); print('\n'.join('  '+n for n in ext))
