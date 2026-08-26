# Solution note: BrunnerCTF 2026 "Lockdown mode" (EV3 .rbf bytecode)

## Status: UNSOLVED as of this attempt; reusable findings below.

## Challenge essence
- File `recovered.rbf` (1087 bytes) = custom/EV3-like bytecode ("LEGO" magic, but header deviates from lms2012 IMGHEADER).
- UI strings: "Enter access code:", "U/D:char  L/R:move", "ENTER:ok  BACK:quit", "ACCESS GRANTED", "ACCESS DENIED".
- Target: find the 36-char access code over charset "0123456789abcdef-" whose md5 equals the hash given in README (see challenge original/README.md). Wrap the code per the challenge flag format.

## Bytecode structure (verified from full hexdump)
- At 0x1C charset table: 17 entries of form [CC char slot] mapping chars to indices 0..16 ('-' -> 16). Chars as `81 xx` const8.
- At 0x84 expected table: 36 entries of form [CC val slot], position-indexed values:
  33 1d 85 85 6b 3b 0d 95 9b 85 8b 8b 95 1d 03 33 95 3b 3b 85 8b 23 33 13 13 6b 3b 0d 33 03 a5 7b 85 7b 23 03
  (all odd bytes). Value-slot grammar: bare below 0x80 = addr, 81 = const8, 80 = inline nul-string, 84 = special op/blob.
- Display calls: `84 05 01 x y [80 str]` draws at screen coords; `84 13 00 00 00` = clear/fill; `84 00` = refresh/update.
- Button dispatch at about 0x269: chain of `83 01 btn 42 42 42` + `82 imm16` conditional jump-past (btn ids 1..6).
- `82 imm16` = JMP rel16 signed (PROVEN: 0x43B `82 4d fd` lands on instruction boundary 0x18B).
- Validation loop regions: about 0x2A0-0x310 and 0x330-0x3E8; ops with unknown arities: 30, 40, 41, C1, C8, CC, 83.

## Dead ends (do NOT retry)
All assuming standard GUID dashes at positions 8,13,18,23 unless noted:
- Stateless affine/xor/add/sub transforms without multiplication (incl. mod 17/251/255/239/241 variants) - dash-position contradictions.
- Post-state chains storing v=h where h_next = A*h+c or (h+c)*A - contradicts equal consecutive values at position pairs (2,3),(10,11),(17,18),(23,24).
- Pre-state chain: store v=h_p then update h_next = A*h_p + c_p - exhaustive A over Z256 by hand -> no survivor.
- Chain v(next) = (v + c)*A - intersection empty.
- CRC8 shift-chain - fails at first step.
- XOR/add keys from README-hash ASCII, "brunnerne", "brunnerctf" strings - invalid chars.

## Remaining promising approaches
1. Brute-force multiplicative families: v(p) = A*c + B*p + C mod 256; v(p) = A*(c + B*p + C) mod 256; PRNG keystream K(p) = A*K(prev)+C mod 256 with c = v xor K or v-K (additive & xor keystream versions partially hand-refuted via dash anchors; recheck programmatically).
2. Constraint-based disassembler: slot grammar known; use verified jump anchor (0x43B -> 0x18B), display-call anchors, button-dispatch boundaries to pin op arities; decode loop at 0x2A0-0x310 to read exact transform between typed char and expected-table value.
3. Consider that code may be 36 hex chars WITHOUT dashes (charset '-' possibly unused) when testing stateless mappings.

## Infrastructure gotcha encountered
When worker image local/reverser-core:0.1 is missing, triage fails -> all exec profiles refuse with "Run triage before free-form analysis". No workaround from inside the agent; must fix image availability first.

## Provenance

- Challenge ID: `brunnerctf-2026-lockdown-mode-1d207c5e`
- Final status: `unsolved`
- Solve elapsed: `35172s`
