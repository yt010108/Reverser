import sys

code = open(sys.argv[1] if len(sys.argv) > 1 else '/challenge/input/command', 'rb').read()

pc = 0
segs = []           # list of (input_index_for_pop, [ops...])
cur_imm = {}        # pending immediate loads in current segment
cur_ops = []
npush = 0

def flush():
    global cur_imm, cur_ops
    if cur_ops or cur_imm:
        segs.append((cur_imm, list(cur_ops)))
    cur_imm = {}
    cur_ops = []

while pc < len(code):
    op = code[pc]
    if op == 0x20:      # halt
        cur_ops.append(('halt',))
        pc += 1
        break
    elif op == 0x21:    # putchar imm
        pc += 2
    elif op == 0x22:    # push(getchar())
        npush += 1
        pc += 1
    elif op == 0x23:    # ld imm
        cur_imm[code[pc+1]] = code[pc+2]
        pc += 3
    elif op == 0x24:    # mov d, s -> reg[d]=reg[s]
        cur_ops.append(('mov', code[pc+1], code[pc+2]))
        pc += 3
    elif op in (0x25, 0x26, 0x27):  # and/or/xor d,a,b
        cur_ops.append(({0x25:'and',0x26:'or',0x27:'xor'}[op], code[pc+1], code[pc+2], code[pc+3]))
        pc += 4
    elif op == 0x28:    # pop -> reg0
        flush()
        segs.append((npush - 1 - len([s for s in segs]), {}))  # placeholder, fix below
        pc += 1
    elif op == 0x29:    # push reg
        pc += 2
    else:
        print('unknown op %02x at %d' % (op, pc)); sys.exit(1)
flush()

# recompute input indices: pops occur in LIFO order relative to pushes
# rebuild properly: track push counter and pop counter
segs2 = []
pending_imm = {}
pending_ops = []
push_i = 0
pop_i = 0
pc = 0
while pc < len(code):
    op = code[pc]
    if op == 0x20:
        pending_ops.append(('halt',)); pc += 1; break
    elif op == 0x21:
        pc += 2
    elif op == 0x22:
        push_i += 1; pc += 1
    elif op == 0x23:
        pending_imm[code[pc+1]] = code[pc+2]; pc += 3
    elif op == 0x24:
        pending_ops.append(('mov', code[pc+1], code[pc+2])); pc += 3
    elif op in (0x25, 0x26, 0x27):
        pending_ops.append(({0x25:'and',0x26:'or',0x27:'xor'}[op], code[pc+1], code[pc+2], code[pc+3])); pc += 4
    elif op == 0x28:
        segs2.append((push_i - 1 - pop_i, dict(pending_imm), list(pending_ops)))
        pop_i += 1
        pending_imm = {}; pending_ops = []
        pc += 1
    elif op == 0x29:
        pending_ops.append(('push', code[pc+1])); pc += 2
    else:
        raise Exception('bad')
tail_ops = list(pending_ops)

print('pushes:', push_i, 'segments:', len(segs2))

# For each segment, find all c in 0..255 such that every value OR'd into the accumulator is 0.
def run_seg(imm, ops, c):
    reg = dict(imm)
    reg[0] = c
    ok = True
    for o in ops:
        if o[0] == 'and':
            reg[o[1]] = reg.get(o[2], 0) & reg.get(o[3], 0)
        elif o[0] == 'or':
            reg[o[1]] = reg.get(o[2], 0) | reg.get(o[3], 0)
        elif o[0] == 'xor':
            reg[o[1]] = reg.get(o[2], 0) ^ reg.get(o[3], 0)
        elif o[0] == 'mov':
            reg[o[1]] = reg.get(o[2], 0)
    return reg

flag = {}
for idx, (inp_pos, imm, ops) in enumerate(segs2):
    cands = []
    for c in range(256):
        reg = run_seg(imm, ops, c)
        # every op writing accumulator (reg 7 here) must yield 0
        good = True
        for o in ops:
            if o[0] in ('and','or','xor') and o[1] == 7 and reg[7] != 0:
                good = False; break
        if good:
            cands.append(c)
    flag[inp_pos] = cands
    print('seg %02d inp[%02d]: %s  imm=%s' % (idx, inp_pos, [hex(x) for x in cands[:8]], {k: hex(v) for k,v in sorted(imm.items())}))

print()
n = max(flag)+1
out = []
for i in range(n):
    cs = flag.get(i, [])
    out.append(chr(cs[0]) if len(cs) == 1 else '?')
print('FLAG:', ''.join(out))
