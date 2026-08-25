import json, collections
data=open('/challenge/input/flag.jpg.crossing','rb').read()
N=1359
cands=json.load(open('/challenge/work/cands.json'))
byidx=collections.defaultdict(list)
for p,o,i,v in cands: byidx[i].append((p,o,v))
mx=max(byidx)
print("bytes:", (mx+1)//2)

def looks_stitched(p,o):
    # start cell that is actually the terminator of a perpendicular pattern:
    # along the perpendicular direction: digits before, ones after
    for po in (1,N):
        if po==o: continue
        b=p-po; a=p+po
        if 0<=b<len(data) and 0<=a<len(data) and data[a]==1 and 2<=data[b]<=254:
            return True
    return False

resolved={}
manual=[]
for i,lst in byidx.items():
    if len(lst)==1:
        resolved[i]=lst[0][2]
    else:
        good=[c for c in lst if not looks_stitched(c[0],c[1])]
        if len(good)==1:
            resolved[i]=good[0][2]
        else:
            manual.append((i,lst))
print("auto-resolved, manual left:", len(manual))

out=bytearray((mx+1)//2+1)
unknown=[]
for i in range(mx+1):
    if i in resolved:
        v=resolved[i]
    else:
        unknown.append(i); v=None
for j in range(len(out)):
    hi=resolved.get(2*j); lo=resolved.get(2*j+1)
    if hi is None or lo is None: continue
    out[j]=(hi<<4)|lo
open('/challenge/work/flag_rec.jpg','wb').write(bytes(out[:18447]))
print("unknown slots:", unknown)
h=bytes(out[:4]); print("head", h.hex())
tail=bytes(out[18447-4:18447]).hex(); print("tail", tail)
