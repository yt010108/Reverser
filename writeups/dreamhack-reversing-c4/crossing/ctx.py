import json
data=open('/challenge/input/flag.jpg.crossing','rb').read()
N=1359
manual=[(162,[(106705,1359,3),(1343635,1,0)]),
(121,[(223179,1,4),(530734,1,0)]),
(7,[(322484,1,0),(1218563,1,0)]),
(171,[(375948,1,14),(1523851,1359,0)]),
(107,[(397962,1359,15),(1373442,1,0)]),
(211,[(426677,1,1),(968465,1,0)]),
(189,[(430440,1,9),(1481422,1359,0)]),
(10,[(554774,1,1),(571497,1,0)]),
(14999,[(677157,1,0),(947650,1359,13)]),
(117,[(760574,1,12),(897422,1,0)])]
for i,lst in manual:
    print("=== idx",i)
    for p,o,v in lst:
        r,c=divmod(p,N)
        o="H" if o==1 else "V"
        print(f" cand pos={p} ([FLAG REDACTED],[FLAG REDACTED]) orient={o} v={v}")
        # neighborhood +-4 both dirs
        rows=[]
        for dr in range(-2,3):
            row=""
            for dc in range(-6,8):
                q=p+dr*N+dc
                b=data[q] if 0<=q<len(data) else -1
                if b==-1: ch='?'
                elif b==0xFF: ch='#'
                elif b==0: ch='.'
                elif b==1: ch='1'
                elif 2<=b<=254: ch='d'
                else: ch='!'
                row+=ch
            rows.append(row)
        print("\n".join(rows))
