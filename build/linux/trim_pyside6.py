import os,sys,subprocess,shutil
sp=sys.argv[1]; q=os.path.join(sp,'PySide6'); qt=os.path.join(q,'Qt')
keep_mods=['QtCore','QtGui','QtWidgets','QtNetwork','QtDBus','QtSvg','QtSvgWidgets']
for f in os.listdir(q):
    p=os.path.join(q,f)
    if f=='Qt' or f=='support' or f=='__init__.py' or f=='_config.py' or f=='_git_pyside_version.py' or f.startswith('libpyside6.abi3'): continue
    if f.endswith('.abi3.so') and f.split('.')[0] in keep_mods: continue
    shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
def needed(path):
    out=subprocess.run(['readelf','-d',path],capture_output=True,text=True).stdout
    return [l.split('[')[1].split(']')[0] for l in out.splitlines() if '(NEEDED)' in l]
libdir=os.path.join(qt,'lib'); have=set(os.listdir(libdir))
roots=[os.path.join(q,m+'.abi3.so') for m in keep_mods]
keep_plugins={'platforms':['libqxcb.so','libqoffscreen.so','libqminimal.so'],'xcbglintegrations':['*'],
 'platforminputcontexts':['libcomposeplatforminputcontextplugin.so','libibusplatforminputcontextplugin.so'],
 'imageformats':['libqgif.so','libqico.so','libqjpeg.so','libqsvg.so'],'iconengines':['*'],'platformthemes':['*'],'tls':['*']}
pl=os.path.join(qt,'plugins')
for d in os.listdir(pl):
    dp=os.path.join(pl,d)
    if d not in keep_plugins: shutil.rmtree(dp); continue
    for f in os.listdir(dp):
        if keep_plugins[d]!=['*'] and f not in keep_plugins[d]: os.remove(os.path.join(dp,f))
    roots+=[os.path.join(dp,f) for f in os.listdir(dp)]
roots.append(os.path.join(libdir,'libQt6XcbQpa.so.6'))
keep=set(); stack=list(roots)
while stack:
    p=stack.pop()
    for n in needed(p):
        if n in have and n not in keep: keep.add(n); stack.append(os.path.join(libdir,n))
for f in have-keep: os.remove(os.path.join(libdir,f))
for d in os.listdir(qt):
    if d not in ('lib','plugins'): 
        p=os.path.join(qt,d); shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
print(sorted(keep))
