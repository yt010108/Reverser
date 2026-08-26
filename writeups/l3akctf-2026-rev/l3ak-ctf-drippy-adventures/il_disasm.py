#!/usr/bin/env python3
"""Dump IL of all methods in a .NET assembly."""
import struct, sys

path = sys.argv[1]
data = open(path, 'rb').read()

pe_off = struct.unpack_from('<I', data, 0x3c)[0]
coff = pe_off + 4
nsec = struct.unpack_from('<H', data, coff+2)[0]
opt_size = struct.unpack_from('<H', data, coff+16)[0]
opt = coff + 20
dd_off = opt + 96
rva_cli = struct.unpack_from('<I', data, dd_off + 14*8)[0]
sections = []
so = opt + opt_size
for i in range(nsec):
    base = so + i*40
    vsize, vaddr, rsize, roff = struct.unpack_from('<IIII', data, base+8)
    sections.append((vaddr,vsize,roff,rsize))
def rva2off(rva):
    for va,vs,ro,rs in sections:
        if va <= rva < va+max(vs,rs): return ro+(rva-va)
    raise ValueError(hex(rva))

cli = rva2off(rva_cli)
md_rva = struct.unpack_from('<I', data, cli+8)[0]
md = rva2off(md_rva)
verlen = struct.unpack_from('<I', data, md+12)[0]
p = md+16+verlen
nstreams = struct.unpack_from('<H', data, p+2)[0]; p += 4
streams={}
for i in range(nstreams):
    off,size = struct.unpack_from('<II', data, p); p+=8
    nm=b''
    while data[p]!=0: nm+=data[p:p+1]; p+=1
    p+=1; p=(p+3)&~3
    streams[nm.decode()]=(md+off,size)

str_off,str_size = streams['#Strings']
us_off,us_size = streams['#US']
tab_off,_ = streams['#~']
blob_off,blob_size = streams['#Blob']
strings_heap = data[str_off:str_off+str_size]
def s(i):
    e=strings_heap.index(b'\0',i); return strings_heap[i:e].decode('utf-8','replace')
blob_heap=data[blob_off:blob_off+blob_size]

# us string by offset
def us(off):
    o=us_off+off
    b0=data[o]
    if b0&0x80==0: ln=b0; hl=1
    elif b0&0xC0==0x80: ln=((b0&0x3f)<<8)|data[o+1]; hl=2
    else: ln=((b0&0x1f)<<24)|(data[o+1]<<16)|(data[o+2]<<8)|data[o+3]; hl=4
    raw=data[o+hl:o+hl+ln]
    return raw[:-1].decode('utf-16-le','replace')

# ---- tables (reuse logic) ----
heap_sizes=data[tab_off+6]
valid=struct.unpack_from('<Q',data,tab_off+8)[0]
rows_off=tab_off+24
rowcounts={}
for i in range(64):
    if valid>>i&1:
        rowcounts[i]=struct.unpack_from('<I',data,rows_off)[0]; rows_off+=4
STR=4 if heap_sizes&1 else 2
GUID=4 if heap_sizes&2 else 2
BLOB=4 if heap_sizes&4 else 2
nr=lambda t: rowcounts.get(t,0)
def idx(*ts): return 4 if max(nr(t) for t in ts)>65535 else 2
def coded(tables):
    bits=(len(tables)-1).bit_length()
    mx=max((nr(t) for t in tables if t>=0), default=0)
    return (bits, 4 if mx>(1<<(16-bits))-1 else 2)
TDOR=coded([2,1,27]); HCA=coded([6,4,1,2,8,9,10,0,14,17,20,23,27,32,35,38,39,40,42,43,44])
HCONST=coded([4,8,23]); HSEC=coded([2,6,32]); MRP=coded([2,1,26,6,27]); HS=coded([20,23])
MDOR=coded([6,10]); CA=coded([-1,-1,6,10,-1]); RS=coded([0,26,35,38]); TOMD=coded([2,6])
SC={
0:[('u2',''),('str','name'),('g','')][:2]+[('u2',''),('u2',''),('u2','')],
1:[('c',RS),('str','name'),('str','ns')],
2:[('u4',''),('s','name'),('s','ns'),('c',TDOR),('i',(4,)),('i',(6,))],
4:[('u2',''),('s','name'),('b','')],
6:[('u4','rva'),('u2',''),('u2',''),('s','name'),('b',''),('i',(8,))],
8:[('u2',''),('u2',''),('s','name')],
9:[('i',(2,)),('c',TDOR)],
10:[('c',MRP),('s','name'),('b','')],
11:[('u2','t'),('c',HCONST),('b','v')],
12:[('c',HCA),('c',CA),('b','')],
15:[('u2',''),('u4',''),('i',(2,))],
17:[('b','')],
18:[('i',(2,)),('i',(20,))],
20:[('u2',''),('s','name'),('c',TDOR)],
21:[('i',(2,)),('i',(23,))],
23:[('u2',''),('s','name'),('b','')],
24:[('u2',''),('i',(6,)),('c',HS)],
25:[('i',(2,)),('c',MDOR),('c',MDOR)],
26:[('s','name')],
27:[('b','')],
29:[('u4','rva'),('i',(4,))],
32:[('u4',''),('u2',''),('u2',''),('u2',''),('u2',''),('u4',''),('b',''),('s','name'),('s','')],
35:[('u2',''),('u2',''),('u2',''),('u2',''),('u4',''),('b',''),('s','name'),('s',''),('b','')],
41:[('i',(2,)),('i',(2,))],
42:[('u2',''),('u2',''),('s','name'),('c',TOMD)],
43:[('c',MDOR),('c',MDOR)],
}
CS={'u2':2,'u4':4,'str':STR,'s':STR,'b':BLOB,'g':GUID}
tables={}
pos=rows_off
for tid in sorted(rowcounts):
    n=rowcounts[tid]
    sch=SC.get(tid)
    rows=[]
    if sch is None: raise Exception('missing schema %d'%tid)
    widths=[]
    cols=[]
    for c in sch:
        k=c[0]
        if k=='u2': w=2
        elif k=='u4': w=4
        elif k=='str': w=STR
        elif k=='s': w=STR
        elif k=='b': w=BLOB
        elif k=='g': w=GUID
        elif k=='c': w=c[1][1]
        elif k=='i': w=idx(*c[1])
        cols.append(c); widths.append(w)
    for _ in range(n):
        vals={}; off=0
        for j,c in enumerate(cols):
            w=widths[j]
            if w==2: v=struct.unpack_from('<H',data,pos+off)[0]
            elif w==4: v=struct.unpack_from('<I',data,pos+off)[0]
            else: raise Exception()
            nm=c[1] if isinstance(c[1],str) and c[1] else 'x%d'%j
            vals[nm]=v
            off+=w
        rows.append(vals); pos+=sum(widths)
    tables[tid]=rows

typedefs=tables[2]; methods=tables[6]; typerefs=tables[1]; memberrefs=tables[10]
for i,t in enumerate(typedefs):
    t['_end_m']= typedefs[i+1][''] if False else None
# method ranges
mranges=[]
for i,t in enumerate(typedefs):
    start=t['x4']
    end=typedefs[i+1]['x4'] if i+1<len(typedefs) else len(methods)+1
    mranges.append((start,end))
franges=[]
for i,t in enumerate(typedefs):
    start=t['x5']
    end=typedefs[i+1]['x5'] if i+1<len(typedefs) else nr(4)+1
    franges.append((start,end))

def td_of_method(mi):
    for ti,(a,b) in enumerate(mranges):
        if a<=mi+1<b: return ti
    return -1
def typename(ti):
    t=typedefs[ti]
    ns=s(t['ns']) if t['ns'] else ''
    n=s(t['name'])
    return f'{ns}.{n}' if ns else n

def tokname(tok):
    tbl=tok>>24; rid=tok&0xFFFFFF
    try:
        if tbl==0x70: return '"'+us(rid)+'"'
        if tbl==0x0A:
            m=memberrefs[rid-1]; par=m['x0']
            ptag=par>>(32-MRP[0]) if False else par>> (MRP[0]*8-8*0 or 0)
            # decode coded tag: low bits
            bits,sz=MRP
            tag=par&((1<<bits)-1); idx_=par>>bits
            pname='?'
            if tag==0 and idx_>=1:
                t=typedefs[idx_-1]; pname=typename(idx_-1)
            elif tag==1 and idx_>=1:
                tr=typerefs[idx_-1]; pname=(s(tr['ns'])+'.' if tr['ns'] else '')+s(tr['name'])
            return f'{pname}::{s(m["name"])}'
        if tbl==0x06:
            mi=rid-1; m=methods[mi]; return f'{typename(td_of_method(mi))}::{s(m["name"])}'
        if tbl==0x01:
            tr=typerefs[rid-1]; return (s(tr['ns'])+'.' if tr['ns'] else '')+s(tr['name'])
        if tbl==0x02:
            return typename(rid-1)
        if tbl==0x04:
            f=tables[4][rid-1]; return 'fld:'+s(f['name'])
        if tbl==0x2B: return 'methodspec->'+tokname_2b(rid)
        if tbl==0x1B: return 'typespec'
    except Exception as e:
        return f'tok:{hex(tok)}({e})'
    return hex(tok)

def tokname_2b(rid):
    ms=tables[43][rid-1]
    return tokname(ms['x0'])

# opcode table (minimal but sufficient)
OPS1={
0x00:'nop',0x01:'break',0x02:'ldarg.0',0x03:'ldarg.1',0x04:'ldarg.2',0x05:'ldarg.3',
0x06:'ldloc.0',0x07:'ldloc.1',0x08:'ldloc.2',0x09:'ldloc.3',
0x0A:'stloc.0',0x0B:'stloc.1',0x0C:'stloc.2',0x0D:'stloc.3',
0x0E:('ldarg.s','u1'),0x0F:('ldarga.s','u1'),0x10:('starg.s','u1'),
0x11:('ldloc.s','u1'),0x12:('ldloca.s','u1'),0x13:('stloc.s','u1'),
0x14:'ldnull',0x15:'ldc.i4.m1',
0x16:'ldc.i4.0',0x17:'ldc.i4.1',0x18:'ldc.i4.2',0x19:'ldc.i4.3',0x1A:'ldc.i4.4',0x1B:'ldc.i4.5',0x1C:'ldc.i4.6',0x1D:'ldc.i4.7',0x1E:'ldc.i4.8',
0x1F:('ldc.i4.s','i1'),0x20:('ldc.i4','i4'),0x21:('ldc.i8','i8'),
0x22:('ldc.r4','r4'),0x23:('ldc.r8','r8'),
0x25:'dup',0x26:'pop',0x27:('jmp','tok'),0x28:('call','tok'),0x29:('calli','tok'),0x2A:'ret',
0x2B:('br.s','br1'),0x2C:('brfalse.s','br1'),0x2D:('brtrue.s','br1'),0x2E:('beq.s','br1'),
0x2F:('bge.s','br1'),0x30:('bgt.s','br1'),0x31:('ble.s','br1'),0x32:('blt.s','br1'),
0x33:('bne.un.s','br1'),0x34:('bge.un.s','br1'),0x35:('bgt.un.s','br1'),0x36:('ble.un.s','br1'),0x37:('blt.un.s','br1'),
0x38:('br','br4'),0x39:('brfalse','br4'),0x3A:('brtrue','br4'),0x3B:('beq','br4'),
0x3C:('bge','br4'),0x3D:('bgt','br4'),0x3E:('ble','br4'),0x3F:('blt','br4'),
0x40:('bne.un','br4'),0x41:('bge.un','br4'),0x42:('bgt.un','br4'),0x43:('ble.un','br4'),0x44:('blt.un','br4'),
0x45:('switch','sw'),
0x46:'ldind.i1',0x47:'ldind.u1',0x48:'ldind.i2',0x49:'ldind.u2',0x4A:'ldind.i4',0x4B:'ldind.u4',0x4C:'ldind.i8',
0x4D:'ldind.r4',0x4E:'ldind.r8',0x4F:'ldind.ref',
0x50:'stind.ref',0x51:'stind.i1',0x52:'stind.i2',0x53:'stind.i4',0x54:'stind.i8',0x55:'stind.r4',0x56:'stind.r8',
0x58:'add',0x59:'sub',0x5A:'mul',0x5B:'div',0x5C:'div.un',0x5D:'rem',0x5E:'rem.un',
0x5F:'and',0x60:'or',0x61:'xor',0x62:'shl',0x63:'shr',0x64:'shr.un',
0x65:'neg',0x66:'not',0x67:'conv.i1',0x68:'conv.i2',0x69:'conv.i4',0x6A:'conv.i8',
0x6B:'conv.r4',0x6C:'conv.r8',0x6D:'conv.u4',0x6E:'conv.u8',
0x6F:('callvirt','tok'),0x70:('cpobj','tok'),0x71:('ldobj','tok'),0x72:('ldstr','tok'),
0x73:('newobj','tok'),0x74:('castclass','tok'),0x75:('isinst','tok'),0x76:'conv.r.un',
0x79:('unbox','tok'),0x7A:'throw',0x7B:('ldfld','tok'),0x7C:('ldflda','tok'),0x7D:('stfld','tok'),
0x7E:('ldsfld','tok'),0x7F:('ldsflda','tok'),0x80:('stsfld','tok'),0x81:('stobj','tok'),
0x82:'conv.ovf.i1.un',0x83:'conv.ovf.i2.un',0x84:'conv.ovf.i4.un',0x85:'conv.ovf.i8.un',
0x86:'conv.ovf.u1.un',0x87:'conv.ovf.u2.un',0x88:'conv.ovf.u4.un',0x89:'conv.ovf.u8.un',
0x8A:'conv.ovf.i.un',0x8B:'conv.ovf.u.un',
0x8C:('box','tok'),0x8D:('newarr','tok'),0x8E:'ldlen',0x8F:('ldelema','tok'),
0x90:'ldelem.i1',0x91:'ldelem.u1',0x92:'ldelem.i2',0x93:'ldelem.u2',0x94:'ldelem.i4',0x95:'ldelem.u4',0x96:'ldelem.i8',
0x97:'ldelem.r4',0x98:'ldelem.r8',0x99:'ldelem.ref',
0x9A:'stelem.i',0x9B:'stelem.i1',0x9C:'stelem.i2',0x9D:'stelem.i4',0x9E:'stelem.i8',0x9F:'stelem.r4',
0xA0:'stelem.r8',0xA1:'stelem.ref',
0xA2:'ldelem',0xA3:('stelem','tok'),0xA4:('ldelem','tok'),0xA5:('unbox.any','tok'),
0xB3:'conv.ovf.i1',0xB4:'conv.ovf.u1',0xB5:'conv.ovf.i2',0xB6:'conv.ovf.u2',
0xB7:'conv.ovf.i4',0xB8:'conv.ovf.u4',0xB9:'conv.ovf.i8',0xBA:'conv.ovf.u8',
0xC2:('refanyval','tok'),0xC3:'ckfinite',0xC6:('mkrefany','tok'),
0xD0:('ldtoken','tok'),0xD1:'conv.u2',0xD2:'conv.u1',0xD3:'conv.i',0xD6:'add.ovf',0xD7:'add.ovf.un',
0xD8:'mul.ovf',0xD9:'mul.ovf.un',0xDA:'sub.ovf',0xDB:'sub.ovf.un',0xDC:'endfinally',
0xDD:('leave','br4'),0xDE:('leave.s','br1'),0xDF:'stind.i',0xE0:'conv.u',
}
OPS2={
0x00:'arglist',0x01:'ceq',0x02:'cgt',0x03:'cgt.un',0x04:'clt',0x05:'clt.un',
0x06:('ldftn','tok'),0x07:('ldvirtftn','tok'),
0x09:('ldarg','u2'),0x0A:('ldarga','u2'),0x0B:('starg','u2'),
0x0C:('ldloc','u2'),0x0D:('ldloca','u2'),0x0E:('stloc','u2'),
0x0F:'localloc',0x11:'endfilter',0x12:('unaligned.','u1'),0x13:'volatile.',0x14:'tail.',0x15:('initobj','tok'),
0x16:('constrained.','tok'),0x17:'cpblk',0x18:'initblk',0x19:'no.',
0x1A:('rethrow',''),0x1C:('sizeof','tok'),0x1D:'refanytype',0x1E:'readonly.',
}

out=open('/challenge/work/il.txt','w')
def W(*a): print(*a,file=out)

for mi,m in enumerate(methods):
    rva=m['rva']
    if not rva: continue
    o=rva2off(rva)
    b0=data[o]
    if b0&3==2:
        codesize=b0>>2; code=o+1; maxstack=8
    else:
        flags_size=struct.unpack_from('<H',data,o)[0]
        hsize=(flags_size>>12)*4
        maxstack=struct.unpack_from('<H',data,o+2)[0]
        codesize=struct.unpack_from('<I',data,o+4)[0]
        code=o+hsize
    tn=typename(td_of_method(mi))
    W(f'\n=== {tn}::{s(m["name"])} (method {mi+1}, size {codesize}) ===')
    i=code; end=code+codesize
    while i<end:
        pc=i-code
        op=data[i]
        if op==0xFE:
            op2=data[i+1]; info=OPS2.get(op2); i+=2
        else:
            info=OPS1.get(op); i+=1
        if info is None:
            W(f'  [FLAG REDACTED]: ?? {op:02x}')
            continue
        if isinstance(info,str):
            W(f'  [FLAG REDACTED]: {info}')
            continue
        name,kind=info
        if kind=='u1':
            v=data[i]; i+=1; W(f'  [FLAG REDACTED]: {name} {v}')
        elif kind=='i1':
            v=struct.unpack_from('<b',data,i)[0]; i+=1; W(f'  [FLAG REDACTED]: {name} {v}')
        elif kind=='u2':
            v=struct.unpack_from('<H',data,i)[0]; i+=2; W(f'  [FLAG REDACTED]: {name} {v}')
        elif kind=='i4':
            v=struct.unpack_from('<i',data,i)[0]; i+=4; W(f'  [FLAG REDACTED]: {name} {v} (0x{v&0xffffffff:x})')
        elif kind=='i8':
            v=struct.unpack_from('<q',data,i)[0]; i+=8; W(f'  [FLAG REDACTED]: {name} {v}')
        elif kind=='r4':
            v=struct.unpack_from('<f',data,i)[0]; i+=4; W(f'  [FLAG REDACTED]: {name} {v}')
        elif kind=='r8':
            v=struct.unpack_from('<d',data,i)[0]; i+=8; W(f'  [FLAG REDACTED]: {name} {v}')
        elif kind=='br1':
            d=struct.unpack_from('<b',data,i)[0]; i+=1; W(f'  [FLAG REDACTED]: {name} [FLAG REDACTED]')
        elif kind=='br4':
            d=struct.unpack_from('<i',data,i)[0]; i+=4; W(f'  [FLAG REDACTED]: {name} [FLAG REDACTED]')
        elif kind=='sw':
            n=struct.unpack_from('<I',data,i)[0]; i+=4
            ts=[]
            for k in range(n):
                d=struct.unpack_from('<i',data,i)[0]; i+=4
                ts.append(d)
            base=i-code
            tg=[f'[FLAG REDACTED]' for t in ts]
            W(f'  [FLAG REDACTED]: switch ({", ".join(tg)})')
        elif kind=='tok':
            tok=struct.unpack_from('<I',data,i)[0]; i+=4
            W(f'  [FLAG REDACTED]: {name} {tokname(tok)}')
out.close()
print('done')
