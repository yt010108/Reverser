#!/usr/bin/env python3
import hashlib, re, struct, sys

data = open('/challenge/input/Assembly-CSharp.dll','rb').read()

# collect hash-like names from #Strings heap
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
def off2rva(off):
    for va,vs,ro,rs in sections:
        if ro <= off < ro+rs: return va + (off-ro)
    return None

names = re.findall(rb'[0-9A-F]{40}', data[50860+12572:50860+12572+13964])
names = set(n.decode() for n in names)
print('hash names:', len(names))

found = {}
sizes = sorted(set([16,24,285,498] + list(range(8,64))))
for sz in sizes:
    for o in range(0, len(data)-sz, 4):
        h = hashlib.sha1(data[o:o+sz]).hexdigest().upper()
        if h in names:
            found[h] = (o, sz)
            print('MATCH', h, 'file_off', hex(o), 'size', sz)

print('\n--- blob contents ---')
for h,(o,sz) in sorted(found.items(), key=lambda kv: kv[1][1]):
    b = data[o:o+sz]
    print(h, sz, 'rva', hex(off2rva(o)) if off2rva(o) else '?')
    print(' hex :', b.hex())
    try:
        print(' utf8:', b.decode('utf-8'))
    except Exception:
        pass
