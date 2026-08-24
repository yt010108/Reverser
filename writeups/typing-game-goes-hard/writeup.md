# Typing Game Goes Hard (Dreamhack Reversing C3)

## Result
Solved. Local run prints `You won! flag is ...` (local `./flag` contains the placeholder test flag; real flag comes from the server copy of this binary).

## Binary
- stripped amd64 PIE ELF, Full RELRO/canary/NX.
- Reads 65536 words from `./dictionary.txt` into a table at `.bss+0x4060`, 64-byte slots (`fscanf("%s")`).
- Seeds a custom PRNG from `/dev/urandom` (4 bytes, low 16 bits used).
- Two rounds (EASY then HARD), 10 words each. EASY shows the word; HARD shows `[REDACTED]`.
- Every prompt requires `difftime(now, game_start) <= 90.0` (double at .rodata+0x2168) and exact strcmp.

## PRNG (reversed & validated against live process)
State: 8 x uint16 at `.bss+0x404060`; counter dword at `.bss+0x4010`.

Seed init:
```
st[0] = seed16
st[i] = ((st[i-1] ^ (st[i-1] >> 14)) * 0x6C07 + i) & 0xFFFF   for i=1..7
counter = 8
```

Twist (MT19937-style, in-place):
```
for i in 0..7:
    y = (st[i] & 0x8000) | (st[(i+1)%8] & 0x7FFF)
    v = y >> 1
    if y & 1: v ^= 0x9908
    st[i] = st[(i+4)%8] ^ v
counter = 0
```

next(): if counter > 7 -> twist; w = st[counter++]. Nibbles a,b,c,d of w, output index:
```
n0 = (3a + 5b + 7c + 2d) % 16
n1 = (4a + 7b + 6c + 3d) % 16
n2 = (2a + 3b + 5c + 4d) % 16
n3 = (5a + 6b + 4c + 7d) % 16     # NOTE: coefficient 4 for c (easy to misread as 2)
idx = n0 | n1<<4 | n2<<8 | n3<<12
target = dictionary[idx]
```
Dictionary has exactly 65536 words, so every index maps to a word.

## Solution
1. Play the EASY round by echoing the shown words.
2. After round 1, brute force all 65536 seeds offline; the observed 10 words uniquely identify seed 22053 (in our run).
3. Generate indices 10..19 from the recovered seed and type those words blind through the HARD round.
4. All within the 90-second wall clock limit - trivially fast via pipes since stdio is unbuffered.

## Verification method
Static analysis with radare2; model discrepancies resolved empirically by running the binary under gdb inside the worker:
- dumped post-seed state to fix the seeding recurrence,
- called the twist / next functions directly with controlled state memory to collect 60 transform samples (solved the nibble coefficients mod 16 exactly) and 20 twist samples (confirmed the MT-style twist).

Solver script: `runs/typing-game-goes-hard-dd0e2a4b/work/solve.py` (mirrored inline in tool run 0020).
