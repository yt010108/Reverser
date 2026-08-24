# bitvm — Dreamhack Reversing C4 (solved)

## Files
- `chall` — stripped amd64 ELF PIE VM interpreter (Full RELRO, canary, NX)
- `command` — 2472-byte VM bytecode program

## Analysis
`chall <command_file>` loads the file into `code[]` at 0x4040 (max 0x1388 bytes) and runs a
dispatch-loop interpreter (`run()` at 0x1341). PC at 0x6768, byte registers `r[0..]` on stack
frame, operand/data stack at 0x53e0 with SP at 0x676c.

Opcodes:
- `0x20 ' '` HALT — returns r[0]; main prints "Correct!!!" iff return == 0
  (`test al,al; jne -> "Wrong."`, .rodata 0x2047="Correct!!!", 0x2052="Wrong.")
- `0x21 !` putchar(code[pc++])
- `0x22 "` push(getchar())
- `0x23 #` r[imm] = imm   (operands: dst, value)
- `0x24 $` r[d] = r[s]
- `0x25 %` r[d] = r[a] & r[b]
- `0x26 &` r[d] = r[a] | r[b]
- `0x27 '` r[d] = r[a] ^ r[b]
- `0x28 (` r[0] = pop()
- `0x29 )` push(r[n])

## Program structure
The bytecode prints two banner strings, then issues **68 `"` (getchar) pushes**, then 68
check blocks in LIFO order (first popped char = input[67]). Byte layout per block:
`#k1 #k2 #k3 (` **then** the check ops, i.e. `[imm][pop][ops]`. Each block for constants
k1,k2,k3:

```
# 1 k1 ; # 2 k2 ; # 3 k3 ; (        ; r0 = c
% 4 0 1            ; t = c & k1
' 5 2 4 ; & 7 5 7  ; acc |= t ^ k2      -> requires (c & k1) == k2
& 4 0 1            ; u = c | k1
' 5 3 4 ; & 7 5 7  ; acc |= u ^ k3      -> requires (c | k1) == k3
```

Tail: last block's ops, then `$ 0 7` (acc -> r0), HALT. Success ⇔ every term OR'd into
the accumulator is 0.

Note (parser quirk): because ops follow their own pop, an entry recorded *at* pop N holds
block N's constants but block N-1's ops. Since every block shares the identical op
template, substituting block N's constants reproduces exactly block N's constraint, so the
per-segment brute force is still correct for input[0..66]. Block 1's constraint
(k1=0xf3,k2=0x71,k3=0xff) has the unique solution c=(k2&k1)|(k3&~k1)=0x7d='}' for
input[67]; solve.py left that slot ambiguous (its seg 00 had no ops), filled as '}'.

`(c & k1) == k2 && (c | k1) == k3` pins all 8 bits of c:
bits under mask k1 come from k2, bits under ~k1 from k3 → unique solution per char.

## Solving
Parsed the bytecode into per-pop segments (`runs/.../work/solve.py`), brute-forced
c ∈ [0,256) per segment requiring all acc-contributions zero — each yields exactly one
candidate for input[0..66], plus '}' for input[67] from block 1 as above.

Verified by sequentially re-emulating the actual bytecode (run #10) with the recovered
input: every accumulator contribution stays 0 and final r7=0, halt returns 0 →
"Correct!!!" (main @0x16c9: `test al,al; jne Wrong.`). Cross-checked opcode semantics
against the disassembly handlers.

## Flag (redacted in public copy)
`[FLAG REDACTED]` — 68 bytes total.
