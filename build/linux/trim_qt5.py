import os,sys,subprocess,shutil,glob
sp=sys.argv[1]; q=os.path.join(sp,'PyQt5'); qt=os.path.join(q,'Qt5')
keep_mods=['QtCore','QtGui','QtWidgets','QtNetwork','QtDBus','QtSvg']
for f in os.listdir(q):
    p=os.path.join(q,f)
    if f=='Qt5': continue
    if f.endswith('.abi3.so'):
        if f.split('.')[0] not in keep_mods: os.remove(p)
    elif f.endswith('.pyi') or f=='bindings': 
        os.remove(p) if os.path.isfile(p) else shutil.rmtree(p)
def needed(path):
    out=subprocess.run(['readelf','-d',path],capture_output=True,text=True).stdout
    return [l.split('[')[1].split(']')[0] for l in out.splitlines() if '(NEEDED)' in l]
libdir=os.path.join(qt,'lib')
have=set(os.listdir(libdir))
roots=[os.path.join(q,m+'.abi3.so') for m in keep_mods]+[os.path.join(qt,'plugins',x) for x in []]
keep_plugins={'platforms':['libqxcb.so','libqoffscreen.so','libqminimal.so'],
 'xcbglintegrations':['*'],'platforminputcontexts':['*'],
 'imageformats':['libqgif.so','libqico.so','libqjpeg.so','libqsvg.so'],
 'iconengines':['*'],'platformthemes':['*'],'bearer':['libqgenericbearer.so']}
pl=os.path.join(qt,'plugins')
for d in os.listdir(pl):
    dp=os.path.join(pl,d)
    if d not in keep_plugins: shutil.rmtree(dp); continue
    for f in os.listdir(dp):
        if keep_plugins[d]!=['*'] and f not in keep_plugins[d]: os.remove(os.path.join(dp,f))
    roots+= [os.path.join(dp,f) for f in os.listdir(dp)]
roots.append(os.path.join(libdir,'libQt5XcbQpa.so.5'))
keep=set(); stack=list(roots)
while stack:
    p=stack.pop()
    for n in needed(p):
        if n in have and n not in keep:
            keep.add(n); stack.append(os.path.join(libdir,n))
for f in have-keep:
    os.remove(os.path.join(libdir,f))
for d in ['qml','qsci']:
    shutil.rmtree(os.path.join(qt,d),ignore_errors=True)
tr=os.path.join(qt,'translations')
for f in os.listdir(tr):
    if not (f.startswith('qtbase_zh_CN') ): os.remove(os.path.join(tr,f))
print(sorted(keep))
