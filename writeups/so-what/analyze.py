import subprocess, glob, re, collections
def load_sections(so):
    out=subprocess.run(['readelf','-S','-W',so],capture_output=True,text=True).stdout
    secs=[]
    for line in out.splitlines():
        m=re.match(r'\s*\[\s*\d+\]\s+(\S+)\s+(\S+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)',line)
        if m:
            secs.append((m.group(1),int(m.group(3),16),int(m.group(5),16)))
    return secs
def make_getstr(so):
    data=[]
    for name,addr,size in load_sections(so):
        if size==0 or name.startswith('.note') or name.startswith('.gnu') or name.startswith('.debug'): continue
        r=subprocess.run(['objdump','-s','-j',name,so],capture_output=True,text=True)
        if r.returncode!=0: continue
        blob=bytearray(size); filled=False
        for line in r.stdout.splitlines():
            m=re.match(r'\s*([0-9a-f]+) ((?:[0-9a-f]{2,8} ){1,4})',line)
            if m:
                off=int(m.group(1),16)-addr
                b=bytes.fromhex(m.group(2).replace(' ',''))
                blob[off:off+len(b)]=b; filled=True
        if filled: data.append((addr,bytes(blob)))
    def getstr(a):
        for base,blob in data:
            if base<=a<base+len(blob):
                end=blob.find(b'\x00',a-base)
                return blob[a-base:end].decode('latin1')
        return None
    return getstr
def analyze(so):
    gs=make_getstr(so)
    out=subprocess.run(['objdump','-d','--no-show-raw-insn','-j','.text',so],capture_output=True,text=True).stdout
    funcs={}
    parts=re.split(r'\n(?=[0-9a-f]{4,16} <)',out)
    for part in parts:
        m=re.match(r'([0-9a-f]+) <([^>]+)>:',part)
        if not m or not re.fullmatch(r'f_.',m.group(2)): continue
        name=m.group(2)
        mnem=[]; dstr=None
        for ln in part.splitlines()[1:]:
            mm=re.match(r'\s*[0-9a-f]+:\t(.*)',ln)
            if not mm: continue
            ins=mm.group(1)
            cm=re.search(r'#\s*([0-9a-f]+)',ins)
            core=re.sub(r'\s+',' ',re.sub(r'<[^>]*>','',ins.split('#')[0]).strip())
            mnem.append(core)
            if cm and ('lea' in core) and dstr is None: dstr=gs(int(cm.group(1),16))
        funcs[name]=('\n'.join(mnem), dstr)
    return funcs
shapes=collections.defaultdict(list)
for so in sorted(glob.glob('lib/*.so'))+['lib/start.so']:
    fs=analyze(so)
    for n,(sig,s) in fs.items():
        shapes[sig].append((so,n,s))
print("distinct shapes:",len(shapes))
for k,v in sorted(shapes.items(), key=lambda x:-len(x[1])):
    print("COUNT",len(v),"ex",v[0][0],v[0][1])
    for ln in k.splitlines():
        if any(w in ln for w in ('call','cmp','ret','test')): print("   ",ln)
    print('---')
