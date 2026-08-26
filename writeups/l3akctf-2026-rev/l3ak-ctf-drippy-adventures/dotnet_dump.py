#!/usr/bin/env python3
"""Minimal .NET metadata parser: dumps streams, heaps, table row counts."""
import struct, sys

data = open(sys.argv[1], 'rb').read()

# PE parsing
pe_off = struct.unpack_from('<I', data, 0x3c)[0]
assert data[pe_off:pe_off+4] == b'PE\0\0'
coff = pe_off + 4
nsec = struct.unpack_from('<H', data, coff+2)[0]
opt_size = struct.unpack_from('<H', data, coff+16)[0]
opt = coff + 20
magic = struct.unpack_from('<H', data, opt)[0]
if magic == 0x10b:
    dd_off = opt + 96
else:
    dd_off = opt + 112
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

# Metadata root
sig, maj, mnr, res, verlen = struct.unpack_from('<IHHII', data, md)
ver = data[md+16:md+16+verlen].split(b'\0')[0].decode()
p = md + 16 + verlen
flags, nstreams = struct.unpack_from('<HH', data, p)
p += 4
streams = {}
for i in range(nstreams):
    off, size = struct.unpack_from('<II', data, p)
    p += 8
    name = b''
    while data[p] != 0:
        name += data[p:p+1]; p += 1
    p += 1
    p = (p + 3) & ~3
    streams[name.decode()] = (md+off, size)

print('version:', ver)
print('streams:', {k: v for k, v in streams.items()})

# Dump #Strings heap
if '#Strings' in streams:
    o, s = streams['#Strings']
    heap = data[o:o+s]
    strs = [x.decode('utf-8', 'replace') for x in heap.split(b'\0') if x]
    open(sys.argv[2], 'w', encoding='utf-8').write('\n'.join(strs))
    print(f'#Strings: {len(strs)} entries -> {sys.argv[2]}')

# Dump #US (user strings): length-prefixed utf16
if '#US' in streams:
    o, s = streams['#US']
    blob = data[o:o+s]
    i = 1
    out = []
    while i < len(blob):
        # compressed length
        b0 = blob[i]
        if b0 & 0x80 == 0:
            ln = b0; hl = 1
        elif b0 & 0xC0 == 0x80:
            ln = ((b0 & 0x3f) << 8) | blob[i+1]; hl = 2
        else:
            ln = ((b0 & 0x1f) << 24) | (blob[i+1] << 16) | (blob[i+2] << 8) | blob[i+3]; hl = 4
        payload = blob[i+hl:i+hl+ln]
        i += hl + ln
        if ln == 0:
            continue
        raw = payload[:-1]
        try:
            txt = raw.decode('utf-16-le')
        except Exception:
            txt = repr(raw)
        out.append(txt)
    open(sys.argv[3], 'w', encoding='utf-8').write('\n'.join(out))
    print(f'#US: {len(out)} strings -> {sys.argv[3]}')
