#!/usr/bin/env python3
# dungeon-in-1983 solver (Dreamhack Reversing C2)
# 사용법: python3 solver.py <host> <port>  (또는 로컬: prob 바이너리와 같은 dir에서)
import re, sys

def make_spell(v):
    # A=+1, B=x2, 시작은 A, 연속 A 금지 -> 그리디 역산으로 유일한 정규 형태
    ops = []
    while v > 1:
        if v % 2 == 0:
            ops.append('B'); v //= 2
        else:
            ops.append('A'); v -= 1
    return 'A' + ''.join(reversed(ops))

def spell_value(s):
    acc = 0
    for c in s:
        acc = acc + 1 if c == 'A' else acc * 2
    return acc

def stats_to_val(hp, str_, agi, vit, int_, end_, dex):
    # printf 인자 매핑: STR=b0, AGI=b1, VIT=b2, INT=b3, END=b4, DEX=b5, HP=b6..7(u16 LE)
    return str_ | (agi << 8) | (vit << 16) | (int_ << 24) | (end_ << 32) | (dex << 40) | (hp << 48)

PAT = re.compile(r'HP:\s*(\d+), STR:\s*(\d+), AGI:\s*(\d+), VIT:\s*(\d+), INT:\s*(\d+), END:\s*(\d+), DEX:\s*(\d+)')

def run_stdio(read_line, send):
    out = ""
    while True:
        line = read_line()
        if not line:
            break
        out += line
        m = PAT.search(line)
        if m:
            hp, s1, a, v, i2, e, d = map(int, m.groups())
            val = stats_to_val(hp, s1, a, v, i2, e, d)
            sp = make_spell(val)
            assert spell_value(sp) == val and 'AA' not in sp and sp[0] == 'A'
            send(sp + "\n")
        if 'dangerous to go alone' in out.split('\n')[-2] if len(out.split('\n')) > 1 else False:
            pass
    return out

if __name__ == '__main__':
    from pwn import remote, process, context
    context.log_level = 'error'
    io = remote(sys.argv[1], int(sys.argv[2])) if len(sys.argv) > 2 else process('./prob')
    buf = b''
    while True:
        try:
            line = io.recvline(timeout=3).decode(errors='replace')
        except Exception:
            break
        if not line:
            break
        print(line, end='')
        m = PAT.search(line)
        if m:
            hp, s1, a, v, i2, e, d = map(int, m.groups())
            val = stats_to_val(hp, s1, a, v, i2, e, d)
            io.sendline(make_spell(val).encode())
    try:
        rest = io.recvall(timeout=3).decode(errors='replace')
        print(rest)
    except Exception:
        pass

## Provenance

- Challenge ID: `dungeon-in-1983-de95d295`
- Final status: `unsolved`
- Solve elapsed: `396s`
