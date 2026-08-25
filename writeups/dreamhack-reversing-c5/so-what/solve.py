import subprocess, glob, re, collections, json, sys
sys.setrecursionlimit(100000)
exec(open('analyze.py').read().split('shapes=collections')[0])
HEX='0123456789abcdef'
funcs={}   # (so,name)->target
for so in sorted(glob.glob('lib/*.so'))+['lib/start.so']:
    fs=analyze(so)
    for n,(sig,s) in fs.items():
        assert s and s.startswith('lib/'), (so,n,s)
        funcs[(so,n)]=s
print("nodes:",len(funcs))
# terminal detection: shape with only ret -> re-run quick check
def is_terminal(so):
    out=subprocess.run(['objdump','-d','--no-show-raw-insn','-j','.text',so],capture_output=True,text=True).stdout
    return out
term=('lib/219f2e3164.so','f_8')
# verify terminal body
out=is_terminal(term[0])
part=[p for p in re.split(r'\n(?=[0-9a-f]{4,16} <)',out) if re.search(r'<f_8>:',p)][0]
print("terminal body:", part[:300].replace('\n',' | '))
by_target=collections.defaultdict(list)
for (so,n),t in funcs.items():
    by_target[t].append((so,n))
def nxt(node,c):
    t=funcs[node]
    child=(t,'f_'+c)
    return child if child in funcs else None
# longest path to terminal with cycle guard
import functools
memo={}
INSTACK=-2
def longest(node, stack):
    if node==term: return 0
    if node in memo:
        v=memo[node]
        return v if v!=INSTACK else -1000
    if node in stack: return -1000
    stack.add(node)
    best=-1000; bestc=None
    for c in HEX:
        ch=nxt(node,c)
        if ch is None: continue
        r=longest(ch,stack)
        if r+1>best: best=r+1; bestc=c
    stack.discard(node)
    memo[node]=best
    return best
res={}
for c in HEX:
    n0=('lib/start.so','f_'+c)
    if n0 in funcs:
        r=longest(n0,set())
        res[c]=r
        print("start",c,"->",r)

# reconstruct longest path greedily
best_start=max(res, key=lambda c:res[c])
print("best start char:",best_start,res)
path=[]
node=('lib/start.so','f_'+best_start)
stack=set()
while node!=term:
    stack.add(node)
    best=-1000; bestc=None
    for c in HEX:
        ch=nxt(node,c)
        if ch is None: continue
        if ch in stack: continue
        r=longest(ch,set())
        if r+1>best: best=r+1; bestc=c
    path.append(bestc)
    print(node,'->',bestc,best)
    node=nxt(node,bestc)
print("PATH LEN",len(path))
s=best_start+''.join(path)
print("INPUT:",s,len(s))
open('input.txt','w').write(s+'\n')
