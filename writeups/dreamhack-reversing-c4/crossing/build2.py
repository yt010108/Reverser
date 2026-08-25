import json, collections
data=open('/challenge/input/flag.jpg.crossing','rb').read()
N=1359
cands=json.load(open('/challenge/work/cands.json'))
byidx=collections.defaultdict(list)
for p,o,i,v in cands: byidx[i].append((p,o,v))
mx=max(byidx)

def stitched(p,o):
    # start cell interior to another pattern => along that pattern's dir:
    # previous cell is a digit(2..254) and next cell is ones(0x01)
    for po in (1,N):
        b=p-po; a=p+po
        if 0<=b<len(data) and 0<=a<len(data) and data[a]==1 and 2<=data[b]<=254:
            return True
    return False

resolved={}; manual=[]
for i,lst in byidx.items():
    if len(lst)==1: resolved[i]=lst[0][2]; continue
    good=[c for c in lst if not stitched(c[0],c[1])]
    if len(good)==1: resolved[i]=good[0][2]
    else: manual.append((i,lst))
print("manual:", len(manual))
for i,lst in manual: print(i, lst)
out=bytearray((mx+1)//2+1)
for j in range(len(out)):
    hi=resolved.get(2*j); lo=resolved.get(2*j+1)
    if hi is not None and lo is not None: out[j]=(hi<<4)|lo
open('/challenge/work/flag_rec.jpg','wb').write(bytes(out[:18447]))
print("written")
