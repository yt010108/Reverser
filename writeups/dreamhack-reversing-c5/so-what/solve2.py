import subprocess, glob, re, collections, sys
sys.setrecursionlimit(100000)
exec(open('analyze.py').read().split('shapes=collections')[0])
HEX='0123456789abcdef'
info={}
for so in sorted(glob.glob('lib/*.so'))+['lib/start.so']:
    fs=analyze(so)
    for n,(sig,s) in fs.items():
        info[(so,n)]=(sig,s)
leaves=[]; inner=0
for (so,n),(sig,s) in list(info.items()):
    if 'call' not in sig:
        m=re.search(r'mov\s+\$(0x[0-9a-f]+),%eax',sig)
        val=int(m.group(1),16) if m else None
        info[(so,n)]=('leaf',val)
        if val==0: leaves.append((so,n))
    else:
        assert s and s.startswith('lib/'),(so,n,s)
        inner+=1
print("inner:",inner,"zero-leaves:",len(leaves))
for l in leaves: print("leaf0:",l)
def nxt(node,c):
    t=info[node]
    if t[0]=='leaf': return None
    child=(t[1],'f_'+c)
    return child if child in info else None
terms=set(leaves)
memo={}
def longest(node, stack):
    if node in terms: return 0
    if node in memo: 
        v=memo[node]
        return v
    if node in stack: return -10**6
    stack.add(node)
    best=-10**6
    for c in HEX:
        ch=nxt(node,c)
        if ch is None: continue
        r=longest(ch,stack)
        if r+1>best: best=r+1
    stack.discard(node)
    memo[node]=best
    return best
res={}
for c in HEX:
    n0=('lib/start.so','f_'+c)
    res[c]=longest(n0,set())
print({k:v for k,v in res.items()})
best_start=max(res,key=lambda c:res[c])
path=[];node=('lib/start.so','f_'+best_start);stack=set()
while node not in terms:
    stack.add(node)
    best=-10**6;bestc=None
    for c in HEX:
        ch=nxt(node,c)
        if ch is None or ch in stack: continue
        r=longest(ch,set())
        if r+1>best: best=r+1;bestc=c
    path.append(bestc);node=nxt(node,bestc)
s=best_start+''.join(path)
print("PATHLEN",len(path))
print("INPUT:",s)
open('input.txt','w').write(s+'\n')
