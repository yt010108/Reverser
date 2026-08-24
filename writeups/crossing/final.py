import json, collections
data=open('/challenge/input/flag.jpg.crossing','rb').read()
N=1359
cands=json.load(open('/challenge/work/cands.json'))
byidx=collections.defaultdict(list)
for p,o,i,v in cands: byidx[i].append((p,o,v))
mx=max(byidx)
def stitched(p,o):
    for po in (1,N):
        b=p-po; a=p+po
        if 0<=b<len(data) and 0<=a<len(data) and data[a]==1 and 2<=data[b]<=254:
            return True
    return False
resolved={}
for i,lst in byidx.items():
    good=[c for c in lst if not stitched(c[0],c[1])]
    resolved[i]=(good or lst)[0][2]
out=bytearray((mx+1)//2+1)
for j in range(len(out)):
    hi=resolved.get(2*j); lo=resolved.get(2*j+1)
    if hi is not None and lo is not None: out[j]=(hi<<4)|lo
jpg=bytes(out[:18447])
open('/challenge/output/flag_recovered.jpg','wb').write(jpg)
print("size",len(jpg),"head",jpg[:2].hex(),"tail",jpg[-2:].hex())
