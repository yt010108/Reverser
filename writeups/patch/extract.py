#!/usr/bin/env python3
import re, subprocess, sys

BIN = "/challenge/input/Patch.exe"
FUNCS = ["0x140001240","0x140001560","0x1400017a0","0x1400019d0","0x140001c80",
         "0x140001f20","0x1400020f0","0x140002390","0x140002640","0x140002870",
         "0x140002b80","0x140002c40"]

out = subprocess.run(
    ["r2","-q","-e","scr.color=0","-e","bin.relocs.apply=true","-c",
     "aaa;" + "".join(f"pdf @ {f};" for f in FUNCS),
     BIN], capture_output=True, text=True).stdout

lines = out.splitlines()
# state: current function, tracked values for registers and stack args
cur = None
regs = {}
stackargs = {}   # offset -> value
calls = []       # (func, target, args)

def val(tok):
    tok = tok.strip()
    m = re.match(r'^([0-9a-fx]+)$', tok.replace("h",""), re.I)
    if not m: return None
    t = tok.rstrip('h')
    try:
        return int(t, 0)
    except ValueError:
        return None

i = 0
while i < len(lines):
    L = lines[i]
    m = re.match(r'/\s*(\d+):\s*fcn\.([0-9a-f]+)', L)
    if m:
        cur = "fcn." + m.group(2)
        regs, stackargs = {}, {}
        i += 1
        continue
    m = re.search(r'0x(14[0-9a-f]{8})\s+([0-9a-f]+)\s+(.+?)\s*;', L)
    if not m:
        m = re.search(r'0x(14[0-9a-f]{8})\s+([0-9a-f]+)\s+(\S.*)$', L)
        if not m:
            i += 1
            continue
    addr, ins_txt = "0x"+m.group(1), m.group(3).strip()
    # normalize
    ins = ins_txt
    if ins.startswith("mov ") or ins.startswith("lea "):
        mm = re.match(r'(mov|lea)\s+(\w+),\s*(.+)$', ins)
        if mm:
            dst, src = mm.group(2), mm.group(3).strip()
            v = None
            sm = re.match(r'^(?:dword\s*)?\[?[0-9a-fx]+\]?$', src)
            vm = re.match(r'^0x([0-9a-f]+)$', src)
            hm = re.match(r'^([0-9a-f]+)h$', src)
            if vm or hm:
                v = int(src.rstrip('h'), 16)
            elif re.match(r'^\d+$', src):
                v = int(src)
            elif ';' in src:
                pre = src.split(';')[0].strip()
                if re.match(r'^0x[0-9a-f]+$', pre): v = int(pre,16)
                elif re.match(r'^\d+$', pre): v = int(pre)
            if v is not None:
                if dst.startswith('[') or 'sp_' in dst or 'var_sp' in dst:
                    # stack var: figure out offset
                    om = re.search(r'sp_\s?([0-9a-f]+)h?\]', dst) or re.search(r'\+ 0x([0-9a-f]+)\]', dst)
                    if 'var_sp' in dst or 'sp_' in dst:
                        om2 = re.search(r'sp(?:_)?([0-9a-f]+)h', dst)
                        if om2: stackargs[int(om2.group(1),16)] = v
                    elif om:
                        stackargs[int(om.group(1),16)] = v
                else:
                    regs[dst] = v
    if 'call' in ins:
        tm = re.search(r'reloc\S*?\.?([\w.]*GdipDrawLineI)|sym\.imp\.[\w.]*_(GdipDrawLineI)', ins)
        isdraw = 'GdipDrawLineI' in ins
        iswrap = 'fcn.140002b80' in ins
        if isdraw or iswrap:
            x1 = regs.get('r8d') or regs.get('r8')
            y1 = regs.get('r9d') or regs.get('r9')
            x2 = stackargs.get(0x20)
            y2 = stackargs.get(0x28)
            calls.append((cur, addr, iswrap, x1, y1, x2, y2))
        regs.pop('r8d', None); regs.pop('r9d', None); regs.pop('r8',None); regs.pop('r9',None)
    i += 1

for c in calls:
    print(c)

# Render ASCII art
segs = [(x1,y1,x2,y2) for (_,_,_,x1,y1,x2,y2) in calls if None not in (x1,y1,x2,y2)]
print(f"# segments: {len(segs)}")
if segs:
    xs = [v for s in segs for v in (s[0],s[2])]
    ys = [v for s in segs for v in (s[1],s[3])]
    print("# x range", min(xs), max(xs), "y range", min(ys), max(ys))
