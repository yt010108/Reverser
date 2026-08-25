# Interpret — solution

## Summary
Stripped x86-64 PIE ELF. main reads a 32-hex-char string (16 bytes), builds a VM state
(FUN_001012a9) containing:
- acc (u32), pc (u32)
- code blob: 24 qword literals + zero terminator = 193 bytes
- data region = the 16-byte key
Then FUN_00101333 interprets the bytecode:

| op | meaning |
|----|---------|
| 0  | halt -> success |
| 1  | acc = key[dp++] |
| 2  | acc += imm8 |
| 3  | acc ^= imm8 |
| 4  | acc = rol32(acc, imm8 & 31) (FUN_00101289) |
| 5  | require acc == big-endian u32 of next 4 bytes, else fail |

Each of the 16 blocks is `load key[i]; add/xor/rol ops; compare`. Inverting each block's
op chain recovers the key byte directly.

## Key
1a2948231febe838343e580772d48f77

Verified against the real binary: prints "Correct! Here is your flag:" and dumps ./flag.

## Reproduce
python3 solve_vm.py  # prints key hex and verifies via built-in emulator
