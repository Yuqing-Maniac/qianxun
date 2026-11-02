import sys
d=sys.argv[1]
def parse(fn):
    res=[];cur=None
    for l in open(fn,encoding='utf-8'):
        if l.startswith('Q'): cur=[l.split()[1], set()]; res.append(cur)
        else: cur[1].add(l.strip('\n')[2:])
    return res
a=parse(d+'/ref.txt'); b=parse(d+'/'+(sys.argv[2] if len(sys.argv)>2 else 'cpp.txt'))
qs=[l.rstrip('\n') for l in open(d+'/queries.tsv',encoding='utf-8')]
bad=0
for i,(x,y) in enumerate(zip(a,b)):
    if x!=y:
        bad+=1
        if bad<=25: print('MISMATCH', i, repr(qs[i]), x[0], len(x[1]), y[0], len(y[1]), 'py-only', sorted(x[1]-y[1])[:2], 'c-only', sorted(y[1]-x[1])[:2])
print('total', len(a), len(b), 'mismatches', bad)
