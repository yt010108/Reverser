import struct

M = 0xFFFFFFFF
Q = [
    0x50504b003750201, 0x38A0201E0070000, 0x200C000005040471,
    0x502047703F10201, 0x3CA020138050000, 0x120000050604A5,
    0x52F035602040401, 0x240030169020000, 0x100F000005040446,
    0x50704D702340301, 0x2C0030180D90000, 0xA01F000005050405,
    0x5C203DC02030401, 0x2070401BE020000, 0x8E1F0000050F0381,
    0x502045702190301, 0x3CD020160020000, 0x050000050504FC,
    0x50304F303CB0201, 0x2010401700E0000, 0xF7020000058703C8,
    0x5C6039A02030401, 0x3AD0201D4050000, 0xB20200000501047D,
]
code = b"".join(struct.pack("<Q", q) for q in Q) + b"\x00"


def run(key):
    """Emulate FUN_00101333."""
    pc = acc = dp = 0
    while True:
        if pc >= len(code):
            return True
        op = code[pc]; pc += 1
        if op == 0:
            return True
        elif op == 1:
            if dp > 15:
                return False
            acc = key[dp]; dp += 1
        elif op == 2:
            if pc >= len(code):
                return False
            acc = (acc + code[pc]) & M; pc += 1
        elif op == 3:
            if pc >= len(code):
                return False
            acc ^= code[pc]; pc += 1
        elif op == 4:
            if pc >= len(code):
                return False
            r = code[pc] & 0x1F; pc += 1
            if r:
                acc = ((acc << r) | (acc >> ((32 - r) & 31))) & M
        elif op == 5:
            if pc + 4 > len(code):
                return False
            b = code[pc:pc + 4]; pc += 4
            if acc != (b[0] << 24 | b[1] << 16 | b[2] << 8 | b[3]):
                return False
        else:
            return False


key = []
pc = 0
while pc < len(code) and code[pc] != 0:
    assert code[pc] == 1, hex(pc)
    pc += 1
    ops = []
    while code[pc] != 5:
        o = code[pc]; pc += 1
        ops.append((o, code[pc])); pc += 1
    pc += 1
    b = code[pc:pc + 4]; pc += 4
    v = b[0] << 24 | b[1] << 16 | b[2] << 8 | b[3]
    for o, imm in reversed(ops):
        if o == 2:
            v = (v - imm) & M
        elif o == 3:
            v ^= imm
        elif o == 4:
            r = imm & 0x1F
            if r:
                v = ((v >> r) | (v << ((32 - r) & 31))) & M
    key.append(v)

kb = bytes(key)
print("key hex:", kb.hex())
print("verify:", run(kb))
