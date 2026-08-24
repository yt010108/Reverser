import subprocess, glob, re, collections

def load_sections(so):
    out=subprocess.run(['readelf','-S','-W',so],capture_output=True,text=True).stdout
    secs=[]
    for line in out.splitlines():
        m=re.match(r'\s*\[\s*\d+\]\s+(\S+)\s+(\S+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)',line)
        if m:
            secs.append((m.group(1),int(m.group(3),16),int(m.group(4),16),int(m.group(5),16)))
    return secs  # name, vaddr, offset, size

raw=open('lib/start.so','rb').read()
secs=load_sections('lib/start.so')
print(secs[:5])

def make_getstr(so):
    data=open(so,'rb').read()
    secs=[s for s in load_sections(so) if s[3]>0 and not s[0].startswith('.note') and not s[0].startswith('.gnu')]
    def getstr(a):
        for name,vaddr,off,size in secs:
            if vaddr<=a<vaddr+size:
                o=off+(a-vaddr)
                end=data.find(b'\x00',o)
                return data[o:end].decode('latin1')
        return None
    return getstr

def analyze(so):
    gs=make_getstr(so)
    out=subprocess.run(['objdump','-d','--no-show-raw-insn',so],capture_output=True,text=True).stdout
    funcs={}
    parts=re.split(r'\n(?=[0-9a-f]+ <)',out)
    for part in parts:
        m=re.match(r'[0-9a-f]+ <([^>]+)>:\n(.*)',part,re.S)
        if not m or not re.fullmatch(r'f_.',m.group(1)): continue
        name=m.group(1)
        lines=m.group(2).splitlines()
        mnem=[]
        dl=None
        pending=None
        for ln in lines:
            mm=re.match(r'\s*[0-9a-f]+:\t(.*)',ln)
            if not mm: continue
            ins=mm.group(1).strip()
            core=re.sub(r'<[^>]*>','',ins.split('#')[0]).strip()
            cm=re.search(r'#\s*([0-9a-f]+)',ins)
            mnem.append(core)
            if cm and core.startswith('lea'):
                pending=int(cm.group(1),16)
            if 'call' in ins and 'dlopen' in ins and pending is not None and dl is None:
                dl=gs(pending)
        funcs[name]=('\n'.join(mnem),dl)
    return funcs

HEX='0123456789abcdef'
libs=sorted(glob.glob('lib/*.so'))+['lib/start.so']
info={}
for so in libs:
    for n,(sig,s) in analyze(so).items():
        if s is None:
            mv=re.search(r'mov\s+\$(0x[0-9a-f]+),%eax',sig)
            assert 'call' not in sig, (so,n,sig[:200])
            assert mv,(so,n,sig)
            info[(so,n)]=('leaf',int(mv.group(1),16))
        else:
            assert 'call' in sig
            assert re.fullmatch(r'lib/[0-9a-f]{10}\.so',s),(so,n,s)
            info[(so,n)]=('goto',s)
from collections import Counter
print(Counter(v[0] for v in info.values()))
zeros=[k for k,v in info.items() if v[0]=='leaf' and v[1]==0]
nonz=[k for k,v in info.items() if v[0]=='leaf' and v[1]!=0]
print('zero leaves:',len(zeros),'nonzero leaves:',len(nonz))

def nxt(M,c):
    ent=info.get((M,'f_'+c))
    if ent is None: return None      # dlsym fail -> exit(1)
    if ent[0]=='leaf': return ('leaf',ent[1])
    return ('goto',ent[1])

# forward DP: S[i] = set of libs where call #i (0-based, char c_i) executes
S=[{('lib/start.so')}]
for i in range(64):
    nxt_set=set()
    for M in S[-1]:
        for c in HEX:
            r=nxt(M,c)
            if r and r[0]=='goto':
                nxt_set.add(r[1])
    S.append(nxt_set)
for i,s in enumerate(S): print('level',i,len(s))

# candidates: at level 63, char c with zero leaf
cands=[(M,c) for M in S[63] for c in HEX if (M,'f_'+c) in info and info[(M,'f_'+c)]==('leaf',0)]
print('final candidates:',len(cands))

# backward reconstruct: parent of (M at level i) : find (P,c) with P in S[i-1]... need reverse
# do DFS from each candidate backwards using levels
prev={}  # level -> dict lib -> (parentlib,char) any one
for i in range(1,65):
    d={}
    for M in S[i]:
        for P in S[i-1]:
            found=False
            for c in HEX:
                r=nxt(P,c)
                if r and r[0]=='goto' and r[1]==M:
                    d[M]=(P,c); found=True; break
            if found: break
    prev[i]=d

import sys
sys.setrecursionlimit(10000)
def rebuild(M,i):
    if i==0: return ''
    P,c=prev[i][M]
    return rebuild(P,i-1)+c
answers=[rebuild(M,63)+c for M,c in cands]
print('answers:',answers)
open('answer.txt','w').write('\n'.join(answers)+'\n')
