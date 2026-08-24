import math, collections
data = open('/challenge/input/flag.jpg.crossing','rb').read()
N = int(math.isqrt(len(data)))
print("size", len(data), "n", N, "square", N*N==len(data))

def parse(data, N):
    cands=[]
    L=len(data)
    for p in range(L):
        if data[p]!=0xFF: continue
        for orient in (1, N):
            q=p+orient; digs=[]; ok=True
            while 0<=q<L:
                b=data[q]
                if b==0xFF: break
                if b<2 or b>254: ok=False; break
                digs.append(b-2); q+=orient
            if not ok or not digs: continue
            r=q+orient; k=0
            while 0<=r<L and data[r]==1:
                k+=1; r+=orient
            if k<1 or k>16: continue
            idx=0
            for j,d in enumerate(digs): idx+=d*(253**j)
            idx-=1
            v=k-1
            ext=len(digs)+v+3
            last=p+(ext-1)*orient
            if last<0 or last>=L: continue
            cands.append((p,orient,idx,v,len(digs)))
    return cands

cands=parse(data,N)
print("candidates:", len(cands))
byidx=collections.defaultdict(list)
for c in cands: byidx[c[2]].append(c)
mx=max(byidx)
missing=[i for i in range(mx+1) if i not in byidx]
dup=[i for i in byidx if len(byidx[i])>1]
print("max idx", mx, "unique", len(byidx), "missing", len(missing), "dups", len(dup))
print("missing sample", missing[:20])
for i in dup[:20]:
    print("dup idx",i,[(hex(c[0]),c[1],c[3]) for c in byidx[i]])
outliers=[i for i in byidx if i> mx and False]
# distribution of idx gaps beyond median
vals=sorted(byidx)
print("min idx", vals[0])
import json
json.dump([[c[0],c[1],c[2],c[3]] for c in cands], open('/challenge/work/cands.json','w'))
