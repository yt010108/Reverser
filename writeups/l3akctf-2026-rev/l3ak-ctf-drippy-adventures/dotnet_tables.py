#!/usr/bin/env python3
"""Minimal ECMA-335 metadata + IL dumper."""
import struct, sys

path = sys.argv[1]
data = open(path, 'rb').read()

pe_off = struct.unpack_from('<I', data, 0x3c)[0]
coff = pe_off + 4
nsec = struct.unpack_from('<H', data, coff+2)[0]
opt_size = struct.unpack_from('<H', data, coff+16)[0]
opt = coff + 20
magic = struct.unpack_from('<H', data, opt)[0]
dd_off = opt + (96 if magic == 0x10b else 112)
rva_cli = struct.unpack_from('<I', data, dd_off + 14*8)[0]

sections = []
so = opt + opt_size
for i in range(nsec):
    base = so + i*40
    vsize, vaddr, rsize, roff = struct.unpack_from('<IIII', data, base+8)
    sections.append((vaddr, vsize, roff, rsize))

def rva2off(rva):
    for va, vs, ro, rs in sections:
        if va <= rva < va + max(vs, rs):
            return ro + (rva - va)
    raise ValueError(hex(rva))

cli = rva2off(rva_cli)
md_rva, md_size = struct.unpack_from('<II', data, cli+8)
md = rva2off(md_rva)

verlen = struct.unpack_from('<I', data, md+12)[0]
p = md + 16 + verlen
nstreams = struct.unpack_from('<H', data, p+2)[0]
p += 4
streams = {}
for i in range(nstreams):
    off, size = struct.unpack_from('<II', data, p); p += 8
    name = b''
    while data[p] != 0:
        name += data[p:p+1]; p += 1
    p += 1; p = (p + 3) & ~3
    streams[name.decode()] = (md+off, size)

str_off, str_size = streams['#Strings']
us_off, us_size = streams['#US']
blob_off, blob_size = streams['#Blob']
tab_off, tab_size = streams['#~']

strings_heap = data[str_off:str_off+str_size]
def s(idx):
    e = strings_heap.index(b'\0', idx)
    return strings_heap[idx:e].decode('utf-8','replace')

blob_heap = data[blob_off:blob_off+blob_size]
def blen(i):
    b0 = blob_heap[i]
    if b0 & 0x80 == 0: return b0, 1
    if b0 & 0xC0 == 0x80: return ((b0&0x3f)<<8)|blob_heap[i+1], 2
    return ((b0&0x1f)<<24)|(blob_heap[i+1]<<16)|(blob_heap[i+2]<<8)|blob_heap[i+3], 4
def b(idx):
    l, h = blen(idx)
    return blob_heap[idx+h:idx+h+l]

# Tables header
tb = tab_off
heap_sizes = data[tb+6]
valid, sorted_ = struct.unpack_from('<QQ', data, tb+8)
rows_off = tb + 24
rowcounts = {}
for i in range(64):
    if valid >> i & 1:
        rowcounts[i] = struct.unpack_from('<I', data, rows_off)[0]
        rows_off += 4
nrows = lambda t: rowcounts.get(t, 0)

STR = 4 if heap_sizes & 1 else 2
GUID = 4 if heap_sizes & 2 else 2
BLOB = 4 if heap_sizes & 4 else 2

def idx_size(*tables):
    return 4 if max(nrows(t) for t in tables) > 65535 else 2

def coded(tagsize_tables):  # list of tables, -1 = not allowed
    bits = (len(tagsize_tables)-1).bit_length()
    mx = 0
    for t in tagsize_tables:
        if t >= 0:
            mx = max(mx, nrows(t))
    return (bits, 4 if mx > (1 << (16-bits)) - 1 else 2)

TypeDefOrRef = coded([2,1,27])
HasConstant = coded([4,8,23])
HasCustomAttribute = coded([6,4,1,2,8,9,10,0,14,17,20,23,27,32,35,38,39,40,42,43,44])
HasFieldMarshal = coded([4,8])
HasDeclSecurity = coded([2,6,32])
MemberRefParent = coded([2,1,26,6,27])
HasSemantics = coded([20,23])
MethodDefOrRef = coded([6,10])
MemberForwarded = coded([4,6])
Implementation = coded([38,39,35])
CustomAttributeType = coded([-1,-1,6,10,-1])
ResolutionScope = coded([0,26,35,38])
TypeOrMethodDef = coded([2,6])

def coded_idx(name):
    sizes = {'ResolutionScope': ResolutionScope,'TypeDefOrRef':TypeDefOrRef,'HasConstant':HasConstant,
             'HasCustomAttribute':HasCustomAttribute,'HasFieldMarshal':HasFieldMarshal,
             'HasDeclSecurity':HasDeclSecurity,'MemberRefParent':MemberRefParent,'HasSemantics':HasSemantics,
             'MethodDefOrRef':MethodDefOrRef,'MemberForwarded':MemberForwarded,'Implementation':Implementation,
             'CustomAttributeType':CustomAttributeType,'TypeOrMethodDef':TypeOrMethodDef,'Instantiation':MethodDefOrRef,
             'AssemblyRef':ResolutionScope}
    return ('coded_idx', name, sizes[name])

SCHEMAS = {
0:  [('u2','Generation'),('str','Name'),('u2','Mvid'),('u2','EncId'),('u2','EncBaseId')],
1:  [coded_idx('ResolutionScope'),('str','Name'),('str','Namespace')],
2:  [('u4','Flags'),('idx_str','Name'),('idx_str','Namespace'),coded_idx('TypeDefOrRef'),('fldlist','FieldList'),('methlist','MethodList')],
4:  [('u2','Flags'),('idx_str','Name'),('blob','Signature')],
6:  [('u4','RVA'),('u2','ImplFlags'),('u2','Flags'),('idx_str','Name'),('blob','Signature'),('param','ParamList')],
8:  [('u2','Flags'),('u2','Sequence'),('idx_str','Name')],
9:  [('td','Class'),coded_idx('TypeDefOrRef')],
10: [coded_idx('MemberRefParent'),('idx_str','Name'),('blob','Signature')],
11: [('u1b','Type'),('u1b','Pad'),('idx_blob','Value'),coded_idx('HasConstant')],
12: [coded_idx('HasCustomAttribute'),coded_idx('CustomAttributeType'),('idx_blob','Value')],
13: [coded_idx('HasFieldMarshal'),('idx_blob','NativeType')],
14: [('u2','Action'),coded_idx('HasDeclSecurity'),('idx_blob','PermissionSet')],
15: [('u2','PackingSize'),('u4','ClassSize'),('td','Parent')],
16: [('u4','Offset'),('fld','Field')],
17: [('blob','Signature')],
18: [('td','Parent'),('evtlist','EventList')],
20: [('u2','EventFlags'),('idx_str','Name'),coded_idx('TypeDefOrRef')],
21: [('td','Parent'),('prop','PropertyList')],
23: [('u2','Flags'),('idx_str','Name'),('blob','Type')],
24: [('u2','Semantics'),('md','Method'),coded_idx('HasSemantics')],
25: [('td','Class'),('mdb','MethodBody'),('mdb','MethodDeclaration')],
26: [('idx_str','Name')],
27: [('blob','Signature')],
28: [('u2','MappingFlags'),('idx_str','ImportName'),('mr','ImportScope'),('idx_blob','NativeIndex')],
29: [('u4','RVA'),('fld','Field')],
30: [('u4','Token'),('u4','FuncCode')],
31: [('u4','Token')],
32: [('u4','HashAlgId'),('u2','Major'),('u2','Minor'),('u2','Build'),('u2','Rev'),('u4','Flags'),('idx_blob','PublicKey'),('idx_str','Name'),('idx_str','Culture')],
33: [('u4','Processor')],
34: [('u4','OSID'),('u4','Major'),('u4','Minor')],
35: [('u2','Major'),('u2','Minor'),('u2','Build'),('u2','Rev'),('u4','Flags'),('idx_blob','PublicKeyOrToken'),('idx_str','Name'),('idx_str','Culture'),('idx_blob','HashValue')],
36: [('u4','Processor'),coded_idx('AssemblyRef')],
37: [('u4','OSID'),('u4','Major'),('u4','Minor'),coded_idx('AssemblyRef')],
38: [('u4','Flags'),('idx_str','Name'),('idx_blob','HashValue')],
39: [('u4','Flags'),('u4','TypeId'),('idx_str','TypeName'),('idx_str','TypeNamespace'),coded_idx('Implementation')],
40: [('u4','Offset'),('u4','Flags'),('idx_str','Name'),coded_idx('Implementation')],
41: [('u4','NestedClass'),('u4','EnclosingClass')],
42: [('u2','Number'),('u2','Flags'),('idx_str','Name'),coded_idx('TypeOrMethodDef')],
43: [('mdb','Method'),coded_idx('Instantiation')],
44: [('gp','Owner'),coded_idx('TypeDefOrRef')],
}

# expand named coded idx tuples into ('coded', tagbits, size)
def expand(schema):
    out = []
    for col in schema:
        if col[0] == 'coded_idx':
            _, nm, packed = col
            bits, sz = packed
            out.append(('coded', nm, bits, sz))
        elif col[0] == 'coded':
            out.append(col)
        else:
            out.append(col)
    return out

COLSIZE = {
    'u2':2,'u4':4,'u1b':2,  # u1b handled specially
    'str':STR,'idx_str':STR,'blob':BLOB,'idx_blob':BLOB,'guid':GUID,'u2g':GUID,
    'td':idx_size(2),'fld':idx_size(4),'md':idx_size(6),'param':idx_size(8),
    'evt':idx_size(20),'prop':idx_size(23),'gp':idx_size(42),'mr':idx_size(10),
    'fldlist':idx_size(4),'methlist':idx_size(6),'evtlist':idx_size(20),'prop':idx_size(23),'param':idx_size(8),
    'mdb':idx_size(6,10),
}
def colsize(col, tbl):
    k = col[0]
    if k=='coded':
        return col[3]
    if k in COLSIZE:
        return COLSIZE[k]
    raise Exception(f'{tbl} {col}')

table_rows = {}  # tid -> list of dict(raw ints)
pos = rows_off
for tid in sorted(rowcounts):
    n = rowcounts[tid]
    schema = SCHEMAS.get(tid)
    rows = []
    if schema:
        widths=[]
        cols=expand(schema)
        for c in cols:
            if c[0]=='u1b':
                widths.append(1)
            else:
                widths.append(colsize(c,tid))
        for i in range(n):
            vals={}
            off=0
            raw={}
            for j,c in enumerate(cols):
                w=widths[j]
                if c[0]=='u1b':
                    v=data[pos+off]; raw[c[1]]=v; off+=1
                    continue
                if w==2: v=struct.unpack_from('<H',data,pos+off)[0]
                elif w==4: v=struct.unpack_from('<I',data,pos+off)[0]
                else: raise Exception()
                raw[c[-2] if len(c)>3 else c[1]]=v
                off+=w
            raw['_off']=pos
            rows.append(raw)
            pos+=sum(widths)
        table_rows[tid]=rows
    else:
        raise Exception('unknown table %d' % tid)

print('rowcounts:', {hex(k):v for k,v in rowcounts.items()})

# Build lookups
typedefs = table_rows.get(2,[])
methods = table_rows.get(6,[])
fields = table_rows.get(4,[])
fieldrva = table_rows.get(29,[])

# typedef method/field ranges
for i, td in enumerate(typedefs):
    end_m = typedefs[i+1]['MethodList'] if i+1 < len(typedefs) else len(methods)+1
    end_f = typedefs[i+1]['FieldList'] if i+1 < len(typedefs) else len(fields)+1
    td['_m']=(td['MethodList'],end_m)
    td['_f']=(td['FieldList'],end_f)

out=open('/challenge/work/il_dump.txt','w')
def W(*a): print(*a,file=out)

W('=== TypeDefs ===')
for i,td in enumerate(typedefs):
    W(i+1, hex(td['Flags']), s(td['Namespace']), s(td['Name']), 'methods', td['_m'], 'fields', td['_f'])

W('\n=== Fields ===')
for i,f in enumerate(fields):
    W(i+1, hex(f['Flags']), s(f['Name']), 'sig', b(f['Signature']).hex())

W('\n=== FieldRVA ===')
print('rowcounts:', {hex(k):v for k,v in rowcounts.items()})
for fr in fieldrva:
    W('raw:', hex(fr['RVA']), fr['Field'])
    fld = fields[fr['Field']-1]
    o=rva2off(fr['RVA'])
    W(hex(fr['RVA']), 'field', fr['Field'], fld['Name'])
    W('  data:', data[o:o+512].hex())

W('\n=== Methods ===')
for i,m in enumerate(methods):
    W(i+1, hex(m['RVA']), m['Name'], 'sig:', b(m['Signature']).hex())

out.close()

import json
json.dump({'typedefs':[{'ns':t['Namespace'],'name':t['Name'],'m':t['_m']} for t in typedefs]}, open('/challenge/work/typedefs.json','w'))
print('done')
