# wasm-rev-for-beginners-48766e18 — Write-up

- Event: Dreamhack Reversing C5
- Category: reverse (WebAssembly / Rust wasm-bindgen)
- Status: SOLVED
- Flag candidate recorded via `ctf_record_flag` (value redacted here).

## Files

- `challenge_bg.wasm` — Rust (1.74.1, walrus/wasm-bindgen) module exporting `check(flag)`
- `challenge.js`, `index.html` — JS glue; input is passed to `check()`, which calls
  browser `alert()` with "Correct!" or "Wrong..."

## Analysis

No wabt/node in the core container, so radare2 was used for disassembly:

```
r2 -q -c 'e scr.color=0; e asm.bytes=false; s 0x1a2e; af; pdf' challenge_bg.wasm
```

Exported `check` at vaddr 0x1a2e (389 bytes). Reconstructed logic:

1. Input length must be exactly **68** (`get_local 1 == 68` guard).
2. Loop i = 0..67: `buf1[i] = key[i] ^ input[i]`, key at linear address **0x100000**.
3. Second loop over a fresh 68-byte alloc: `buf2[i] = (buf1[i] * 13 + 37) & 0xff`.
4. Byte-wise comparison loop of `buf2[i]` against the table at **0x100044**
   (constant `1048644` in the disassembly); mismatch counter compared with 68,
   then `select(1048712 /* Wrong... */, 1048720 /* Correct! */)` and alert.

Data section layout (single segment @0x100000, len 748):
key[68] @0x100000, target[68] @0x100044, "Wrong..." @0x100088, "Correct!" @0x100090.

## Inversion

Both steps are bijective on bytes:
- XOR is trivially invertible.
- x -> 13x + 37 mod 256 is invertible since gcd(13,256)=1; inverse multiplier is
  13^-1 mod 256 = 197.

So: `input[i] = ((target[i] - 37) * 197 mod 256) ^ key[i]`

The result is mathematically the unique preimage; it decodes to
`[FLAG REDACTED]` with total length 68, confirming the derivation.

Solver script: `runs/wasm-rev-for-beginners-48766e18/work/solve.py`
(parses the data section directly from the wasm binary and prints the flag).
