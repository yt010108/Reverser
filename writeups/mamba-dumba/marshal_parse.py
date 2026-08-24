import ast, sys, types, dis

src = open('/challenge/input/chall.py').read()
start = src.index("b'")
end = src.index("'))", start)
blob = ast.literal_eval(src[start:end+2])
data = blob

pos = 0
refs = []

def rb(n):
    global pos
    b = data[pos:pos+n]
    pos += n
    return b

def ri():
    return int.from_bytes(rb(4), 'little')

def rd():
    global pos
    t = data[pos]; pos += 1
    flag = bool(t & 0x80)
    t = chr(t & 0x7f)
    idx = len(refs)
    if flag:
        refs.append(None)  # reserve slot

    if t == 'N': o = None
    elif t == 'F': o = False
    elif t == 'T': o = True
    elif t == 'i': o = ri()
    elif t == 's':
        n = ri(); o = bytes(rb(n))
    elif t in ('z','Z','a','A'):
        n = data[pos]; pos += 1
        o = rb(n).decode('utf-8')
    elif t == 'u':
        n = ri(); o = rb(n).decode('utf-8')
    elif t == 'r':
        o = refs[ri()]
    elif t in ('(', ')'):
        if t == '(':
            n = ri()
        else:
            n = data[pos]; pos += 1
        items = [rd() for _ in range(n)]
        o = tuple(items)
    elif t == 'c':
        argcount = ri(); posonly = ri(); kwonly = ri()
        stacksize = ri(); flags = ri()
        code = rd()
        consts = rd()
        names = rd()
        localsplus = rd()
        kinds = rd()
        filename = rd(); name = rd(); qualname = rd()
        firstlineno = ri()
        linetable = rd(); exctab = rd()
        o = dict(kind='code', argcount=argcount, posonly=posonly,
                 kwonly=kwonly, stacksize=stacksize, flags=flags,
                 code=code, consts=consts, names=names,
                 localsplus=localsplus, kinds=kinds,
                 filename=filename, name=name, qualname=qualname,
                 firstlineno=firstlineno, linetable=linetable, exctab=exctab)
    else:
        raise ValueError(f'unknown marshal type {t!r} at {pos-1}')
    if flag:
        refs[idx] = o
    return o

top = rd()

def build(d):
    lp = d['localsplus']; kinds = d['kinds']
    assert len(lp) == len(kinds)
    varnames, cellvars, freevars = [], [], []
    for nm, k in zip(lp, kinds):
        if k == 0: varnames.append(nm)
        elif k == 5: cellvars.append(nm)
        else: freevars.append(nm)
    consts = tuple(build(c) if isinstance(c, dict) else c for c in d['consts'])
    return types.CodeType(
        d['argcount'], d['posonly'], d['kwonly'], len(varnames),
        d['stacksize'], d['flags'], d['code'], consts, d['names'],
        tuple(varnames), d['filename'], d['name'], d['qualname'],
        d['firstlineno'], d['linetable'].decode('latin1'),
        d['exctab'].decode('latin1'), freevars=tuple(freevars),
        cellvars=tuple(cellvars))

code = build(top)
print('=== module ===')
dis.dis(code)
print()
for c in top['consts']:
    if isinstance(c, dict):
        print(f"=== {c['name']} ===")
        print('consts:', [x for x in c['consts'] if not isinstance(x, dict)])
        print('localsplus:', c['localsplus'])
        print('kinds:', list(c['kinds']))
        dis.dis(build(c))
