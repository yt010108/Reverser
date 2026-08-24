import re, sys

lines = open('/challenge/output/check.asm', encoding='utf-8', errors='replace').read().splitlines()

# parse ops inside fcn.1311
ops = []  # ('push', val) | ('load',) | ('xor',) | ('cmp',)
pending_edi = None
for ln in lines:
    m = re.match(r'\s+0x([0-9a-f]+)\s+(.*)', ln)
    if not m:
        continue
    addr = int(m.group(1), 16)
    if not (0x1311 <= addr <= 0x1f99):
        continue
    ins = m.group(2)
    me = re.match(r'mov edi, (0x[0-9a-f]+|\d+)', ins)
    if me:
        pending_edi = int(me.group(1), 0)
        continue
    mc = re.search(r'call (fcn\.[0-9a-f]+)', ins)
    if mc:
        f = mc.group(1)
        if f == 'fcn.00001236':
            ops.append(('push', pending_edi))
        elif f == 'fcn.00001257':
            ops.append(('load',))
        elif f == 'fcn.00001290':
            ops.append(('xor',))
        elif f == 'fcn.000012cb':
            ops.append(('cmp',))
        else:
            raise Exception('unknown call ' + f + ' at %x' % addr)

print('ops:', len(ops))

N = 64  # input length
# symbolic value: (bitmatrix rows?) simpler: represent as tuple (frozenset_of_byte_idx, const)
def combine(a, b):
    s = set(a[0]) ^ set(b[0])
    return (frozenset(s), a[1] ^ b[1])

stack = []
constraints = []  # list of ((setA,constA),(setB,constB)) meaning A^constA == B^constB
maxidx = -1
for op in ops:
    if op[0] == 'push':
        stack.append((frozenset(), op[1]))
    elif op[0] == 'load':
        v = stack[-1]
        assert not v[0], 'load with symbolic index'
        idx = v[1]
        maxidx = max(maxidx, idx)
        stack[-1] = (frozenset([idx]), 0)
    elif op[0] == 'xor':
        b = stack.pop(); a = stack.pop()
        stack.append(combine(a, b))
    elif op[0] == 'cmp':
        b = stack.pop(); a = stack.pop()
        constraints.append((a, b))
print('constraints:', len(constraints), 'max input idx:', maxidx)

# Build GF(2) system: vars [FLAG REDACTED] for byte i bit b.
# Equation per constraint per bit: XOR of var bits = rhs bit
rows = []
for a, b in constraints:
    vars_set = sorted(set(a[0]) | set(b[0]))
    const = a[1] ^ b[1]
    # A ^ constA == B ^ constB  =>  A ^ B == constA ^ constB
    # A is sum over its set... but careful: A's "value" = XOR of input bytes in set? No!
    # Actually load replaces value with input[idx]; values on stack are single input bytes or constants,
    # xor combines them. So value = XOR of selected input bytes ^ const. Correct.
    for bit in range(8):
        row = [0] * (N * 8)
        for i in vars_set:
            row[i * 8 + bit] = 1
        rows.append((row, (const >> bit) & 1))

nvars = N * 8
# Gaussian elimination
pivots = {}
mat = [r[:] for r in rows]
rank = 0
for r in mat:
    pass
pivot_row_of_col = {}
list_rows = [[c for c in r[0]] + [r[1]] for r in rows]
row_idx = 0
col = 0
nrows = len(list_rows)
r = 0
for col in range(nvars):
    piv = None
    for i in range(r, nrows):
        if list_rows[i][col]:
            piv = i; break
    if piv is None:
        continue
    list_rows[r], list_rows[piv] = list_rows[piv], list_rows[r]
    for i in range(nrows):
        if i != r and list_rows[i][col]:
            for j in range(col, nvars + 1):
                list_rows[i][j] ^= list_rows[r][j]
    pivot_row_of_col[col] = r
    r += 1
# consistency
for i in range(r, nrows):
    if all(v == 0 for v in list_rows[i][:nvars]) and list_rows[i][nvars] == 1:
        print('INCONSISTENT'); sys.exit(1)
print('rank:', r, 'of', nvars)

sol = [0] * nvars
free_cols = [c for c in range(nvars) if c not in pivot_row_of_col]
print('free cols (byte.bit):', [(c // 8, c % 8) for c in free_cols])
for col in range(nvars):
    if col in pivot_row_of_col:
        sol[col] = list_rows[pivot_row_of_col[col]][nvars]

out = bytes(sum(sol[i*8+b] << b for b in range(8)) for i in range(N))
print(repr(out))
