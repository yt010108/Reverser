# randzzz — Dreamhack Reversing C2 (solved)

## Triage
- `chall`: ELF 64-bit PIE, not stripped, Full RELRO, NX, no canary.
- Symbols: `main`, `get_flag`; imports: `rand`, `sleep`, `scanf`, `printf`, `__ctype_b_loc`.

## Program logic
`main`:
1. `s = 0; s++; sleep(s); s += rand(); sleep(s); rand(); rand();`
   → no `srand()` call, so the glibc rand sequence is fixed (default seed 1):
   1804289383, 846930886, 1681692777, **1714636915 (%10 = 5)**, **1957747793 (%10 = 3)**, ...
2. `scanf("%d", &s)` — user input overwrites `s`.
3. Branch A: if `rand() % 10 == s` (needs **s = 5**) → decode 28-byte array
   (`0x386c2c39364c396c`, `0x30383338ac4c4c39`, `0x353330354ccccc34`, dword `0xcc6c37ac`)
   into out[0..27] via `get_flag(c, s)`.
4. Branch B: if a fresh `rand() % 10 == s` (needs **s = 3**) → decode 36-byte array
   (`0x01b323838330b1335`, `0x0b332323361b2333`, `0x23391b0b38370b13`,
   `0x3338353439333533`, dword `0x382b3936`) into out[28..63].
5. `printf("[FLAG REDACTED]", out)`.

`get_flag(c, s)`:
- digit: `d = (c*8) % 10; return d+40 if 7 < d <= 9 else d+50`
- else: `v = (c >> s) | (c << (8-s))` (32-bit signed ops on sign-extended char);
  `if (v < 0) v += 0x68`; low byte stored.

## Catch
`s` cannot be both 5 and 3 in one normal run, so each input only yields one half
(input 5 prints the first half; input 3 writes the second half but the printed
string starts at uninitialized out[0], so it prints `DH{}`).

## Solution
Two ways, both verified:
1. Static: reimplement `get_flag` in Python, decode halfA with s=5 and halfB with s=3, concatenate.
2. Dynamic: LD_PRELOAD a stub `sleep(3)` (the program sleeps ~1.8e9 seconds otherwise),
   run with input `5`, then under gdb break at `main+0x162` (before the second
   `cmp`) and `set {int}($rbp-0xc)=3` to force branch B as well.

Both produce the same full flag.

## Flag
Recorded via ctf_record_flag (64 hex chars inside DH{}). Not included in this public copy.
