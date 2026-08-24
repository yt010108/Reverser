#!/usr/bin/env python3
"""carta solver - Dreamhack Reversing C4.

Stage 값 = /dev/urandom에서 읽은 초기 시드 1바이트가 그대로 출력된다.
셔플은 이 시드로 구동되는 LFSR(s>>=1, lsb면 ^0xb8)을 512회 진행하며
256번의 스왑에 (s&0xf, s>>4) 좌표쌍을 사용하므로 보드 전체를 재현할 수 있다.
값 0..127이 각 2장씩이므로 시뮬레이션 결과대로 짝을 맞추면
정확히 128 trial 만에 클리어(trials <= 0x80 조건 충족)한다.
"""
from pwn import *

context.log_level = 'info'


def adv(s):
    b = s & 1
    s >>= 1
    if b:
        s ^= 0xb8
    return s


def build_board(seed):
    board = []
    v = 0
    for r in range(16):
        row = []
        for _ in range(8):
            row.append(v)
            row.append(v)
            v += 1
        board.append(row)
    s = seed
    for _ in range(256):
        s1 = s
        c1 = s1 >> 4
        s = adv(s)
        s2 = s
        c2 = s2 >> 4
        s = adv(s)
        r1, cc1 = s1 & 0xf, c1
        r2, cc2 = s2 & 0xf, c2
        board[r1][cc1], board[r2][cc2] = board[r2][cc2], board[r1][cc1]
    return board


def main():
    import os
    os.makedirs('/tmp/carta', exist_ok=True)
    for f in ('main', 'flag'):
        import shutil
        shutil.copy(f'/challenge/input/{f}', f'/tmp/carta/{f}')
    os.chmod('/tmp/carta/main', 0o755)

    p = process(['./main'], cwd='/tmp/carta')
    p.recvuntil(b'[carta]\n')
    line = p.recvline().decode()
    seed = int(line.split()[1])
    log.info('seed(stage) = %d', seed)

    board = build_board(seed)
    pos = {}
    for r in range(16):
        for c in range(16):
            pos.setdefault(board[r][c], []).append((r, c))
    assert len(pos) == 128 and all(len(v) == 2 for v in pos.values()), 'simulation mismatch'

    for val in range(128):
        (r1, c1), (r2, c2) = pos[val]
        p.recvuntil(b'pick: ')
        p.sendline(b'%d %d' % (r1, c1))
        p.recvuntil(b'pick: ')
        p.sendline(b'%d %d' % (r2, c2))

    rest = p.recvall(timeout=10).decode(errors='replace')
    print(rest)


if __name__ == '__main__':
    main()
