#!/usr/bin/env python3
"""Solver for Typing Game Goes Hard.

Replicates the custom 8x16-bit Mersenne-Twister-like PRNG, recovers the
16-bit seed from the 10 visible EASY-round words, then predicts the
REDACTED HARD-round words.
"""
import subprocess
import sys

DICT = sys.argv[1] if len(sys.argv) > 1 else "dictionary.txt"


def gen_indices(seed, n):
    st = [seed & 0xFFFF]
    for i in range(1, 8):
        prev = st[-1]
        st.append((((prev ^ (prev >> 14)) * 0x6C07) + i) & 0xFFFF)
    ctr = 8
    out = []
    for _ in range(n):
        if ctr > 7:
            for i in range(8):
                y = (st[i] & 0x8000) | (st[(i + 1) % 8] & 0x7FFF)
                v = y >> 1
                if y & 1:
                    v ^= 0x9908
                st[i] = st[(i + 4) % 8] ^ v
            ctr = 0
        w = st[ctr]
        ctr += 1
        a = w & 15
        b = (w >> 4) & 15
        c = (w >> 8) & 15
        d = (w >> 12) & 15
        n0 = (3 * a + 5 * b + 7 * c + 2 * d) % 16
        n1 = (4 * a + 7 * b + 6 * c + 3 * d) % 16
        n2 = (2 * a + 3 * b + 5 * c + 4 * d) % 16
        n3 = (5 * a + 6 * b + 2 * c + 7 * d) % 16
        out.append(n0 | (n1 << 4) | (n2 << 8) | (n3 << 12))
    return out


words = open(DICT).read().split()
NWORDS = len(words)
print(f"[+] dictionary: {NWORDS} words")

p = subprocess.Popen(
    ["./chall"], stdin=subprocess.PIPE, stdout=subprocess.PIPE
)

answers = []
observed = []
for i in range(20):
    buf = b""
    while not buf.endswith(b"> "):
        ch = p.stdout.read(1)
        if not ch:
            print("[!] EOF while waiting for prompt")
            sys.exit(1)
        buf += ch
    text = buf.decode(errors="replace")
    shown = ""
    if "possible: " in text:
        tail = text.split("Type this word as soon as possible: ", 1)[1]
        shown = tail.rsplit("\n", 1)[0]
    if i < 10:
        mode = "EASY"
        observed.append(shown)
        ans = shown  # echo back what we see
    else:
        mode = "HARD"
        ans = predicted[i - 10]
    print(f"[{mode}] {i}: shown={shown!r} -> {ans!r}")
    p.stdin.write((ans + "\n").encode())
    p.stdin.flush()
    if i == 9:
        # brute force the 16-bit seed from observed EASY words
        cands = []
        for seed in range(65536):
            idxs = gen_indices(seed, 10)
            ok = True
            for j, idx in enumerate(idxs):
                want = words[idx] if idx < NWORDS else ""
                if want != observed[j]:
                    ok = False
                    break
            if ok:
                cands.append(seed)
        print(f"[+] seed candidates: {cands}")
        if not cands:
            print("[!] no seed found")
            sys.exit(1)
        predicted = [
            words[x] if x < NWORDS else ""
            for x in gen_indices(cands[0], 20)[10:]
        ]

out = p.stdout.read().decode(errors="replace")
print(out)
