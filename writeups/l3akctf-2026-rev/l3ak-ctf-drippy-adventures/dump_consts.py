#!/usr/bin/env python3
# Dump Constant table entries resolved to owning field/method, esp. string constants
import struct, sys
sys.argv=['x','/challenge/input/Assembly-CSharp.dll']
data=open('/challenge/input/Assembly-CSharp.dll','rb').read()
exec(open('/challenge/work/il_disasm.py').read().split("out=open('/challenge/work/il.txt','w')")[0].replace("import struct, sys","import sys"))
# now tables etc available
consts=tables[11]
for c in consts:
    tok=c['x1']
    hconst=HCONST
    bits,sz=hconst
    tag=tok&((1<<bits)-1); idx_=tok>>bits
    l,h=blen(c['v']) if False else (0,0)
    # decode blob at index c['x1']
    vi=c['v']
    b0=blob_heap[vi]
    if b0&0x80==0: ln=b0; hl=1
    elif b0&0xC0==0x80: ln=((b0&0x3f)<<8)|blob_heap[vi+1]; hl=2
    else: ln=((b0&0x1f)<<24)|(blob_heap[vi+1]<<16)|(blob_heap[vi+2]<<8)|blob_heap[vi+3]; hl=4
    raw=blob_heap[vi+hl:vi+hl+ln]
    owner=''
    if tag==0:
        f=tables[4][idx_-1]; owner='field '+s(f['name'])
        if c['t']==0x12:
            print(owner,'=',repr(raw.decode('utf-16-le')))
        else:
            print(owner,'type',hex(c['t']),'=',raw.hex())
    elif tag==1:
        p=tables[8][idx_-1]; owner='param '+s(p['name'])
        print(owner,'type',hex(c['t']),'=',raw.hex())
    elif tag==2:
        pr=tables[23][idx_-1]; owner='property '+s(pr['name'])
        if c['t']==0x12:
            print(owner,'=',repr(raw.decode('utf-16-le')))
        else:
            print(owner,'type',hex(c['t']),'=',raw.hex())
