# hash-browns (Dreamhack Reversing C4)

## Triage
- `original/hash-browns`: stripped amd64 PIE ELF, dynamically linked, 18648 bytes.
- Imports: printf, read, strchr, memcmp — classic "check input" challenge.

## Analysis (radare2 + Ghidra)
`main` @ 0x22b9:
1. Stores 9 target digests inline as pairs of `movabs` immediates on the stack
   (stride 0x10, i.e. sixteen bytes per block).
2. Reads up to 0x100 bytes from stdin, strips the newline via `strchr`.
3. Loops `i = 0..8`: for each 3-byte block of the input
   - `fcn.00001209(ctx)` — init: state = MD5 IV (0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476)
   - `fcn.0000125c(ctx, buf+3*i, 3)` — update (standard Merkle-Damgård buffering)
   - `fcn.000013e7(ctx)` — finalize (0x38/0x78 padding split, LE digest at ctx+0x58)
   - `memcmp(ctx+0x58, targets[i], 16)`

`fcn.000015b3` is the compression function: all standard MD5 round constants,
message schedule and shift amounts. The hash is plain **MD5**.

Key detail: the target qwords are stored to memory as little-endian immediates,
so each 16-byte target is `struct.pack('<QQ', lo, hi)`.

## Solve
The check is fully block-independent (each 3-byte chunk hashed separately),
so brute-force printable 3-byte preimages per block (~95^3, instant in Python):

| # | target (LE hex)        | preimage |
|---|------------------------|----------|
| 0 | 2bd06839093a5dfeae2e86c267a30aba | DH{ |
| 1 | 4f60269eda2aea8b2452cf6dc9416f2e | m-d |
| 2 | f3759b94d21bd97fa6f372608eedb105 | -5_ |
| 3 | 117688d4c64540c9954db9f66ddf439d | 1s_ |
| 4 | 808dc08a3ca8a8b96484517603e8786d | vu1 |
| 5 | d0c223200fa2810e86f1899de6ea412e | n-e |
| 6 | fde5a3d21d835c42ec0041dcbb8d7882 | r-4 |
| 7 | 20dd01398dee0f6d83d7e5410a2ae8eb | b1e |
| 8 | 06e5724b4126fa2a4d111dc2e948180d | ~!} |

Concatenation verified by piping into the binary in the isolated dynamic worker:

```
Input : Correct! Flag is <FLAG>
```

## Flag
See private note; redacted here.
