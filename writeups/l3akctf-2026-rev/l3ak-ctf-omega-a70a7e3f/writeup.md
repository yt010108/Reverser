# Omega — L3akCTF 2026 rev (private write-up, contains exploit details)

## TL;DR
`executor` runs SHA256-authenticated custom-VM jobs. MAC = `SHA256(SECRET || payload)`
(secret-prefix construction) → **SHA-256 length extension** forges valid jobs without
the secret. The loader maps the data segment with `filesz=0xFFFFFFFF` (until EOF), so
bytes appended past EOF land in VM RAM, and the **entry point in the header is outside
the hashed region**, letting PC start inside attacker bytes. VM syscalls (open/read/
write/...) are unsandboxed → forged job prints `/challenge/flag.txt` to stdout.

## Components
- `executor`: stripped x86-64 PIE; main @0x15c0, loader @0x102940, VM step @0x101c60,
  syscalls @0x1031c0, embedded verifier PRX image at VA 0x104500 (file off 0x4500,
  0xA80 bytes) run by forked child over a pipe.
- `echo.local.prx` / `echo.remote.prx`: same 1552-byte job signed with local
  (`00112233445566778899aabbccddeeff`) vs unknown remote secret.

## PRX format (loader FUN_00102940)
| off | size | field |
|-----|------|-------|
| 0x00 | 4 | magic "PRX\0" |
| 0x04 | 1 | version (=1) |
| 0x05 | 1 | n_phdr |
| 0x06 | 1 | flags bit0 → reg28 = u32@0x0C |
| 0x08 | 4 | entry (u32, LE) ← **unhashed** |
| 0x0C | 4 | reg28 init value ← unhashed |
| 0x10 | 32 | MAC = SHA256(SECRET ‖ file[0x30:]) |
| 0x30 | … | phdrs {u32 off, u32 vaddr, u32 filesz, u32 memsz} ×n_phdr + segments |

echo jobs: code seg off 0x50 va 0x400000 filesz 0x220;
data seg off 0x270 va 0x401000 **filesz 0xFFFFFFFF** memsz 0x3A0.

Verified: `sha256(bytes.fromhex('00112233...') + file[0x30:]) == MAC_local`.

## Verification flow (main FUN_001015c0)
pipe+fork; child dup2(pipe→stdin) and interprets the embedded verifier PRX reading
`u32 secret_len | secret | u32 payload_len | payload | 32B expected_MAC`; exit 0 ⇒
"[+] Verified", parent then runs the submitted job in the same VM.

## VM ISA highlights (FUN_00101c60)
- Words little-endian; fields: op=(w>>11)&0x3f, rs=(w>>22)&0x1f, rt=(w>>6)&0x1f,
  rd=(w>>17)&0x1f, funct=w&0x3f.
- imm16 = bits[17..21]<<11 | bits[27..31]<<6 | bits[0..5]; sign-ext for arith
  (op 53 = li/addiu), zero-ext for logical (ori op 28, xori op 15, andi op 13);
  lui = op 30.
- R-type (op 6): addu funct 0x23/0x31 (needs rd≠0), sub 4/0x1d, or 0x3b, jr 0x29,
  jalr 0x30, syscall funct 0x11 (word 0x00003011).
- Syscall ABI: v0=num, a0/a1/a2 args, ret v0=result a3=err.
  4001 exit, 4003 read, 4004 write, **4005 open** (path string read from VM memory
  at a0, flags from a1), 4006 close, 4019 lseek. No path filtering whatsoever.
- Memory: paged via table at state+0x90; unmapped reads = 0, writes auto-allocate.

## Exploit (work/exploit.py)
For assumed secret length L:
1. glue = SHA-256 continuation padding for msg length L+1504.
2. ext = shellcode + b"/challenge/flag.txt\0"
   shellcode: lui/ori a0=path; a1=a2=0; v0=4005 syscall; save fd;
   buf=0x500000; read(fd,buf,512); write(1,buf,n); exit(0).
   Encoded with the scrambled encodings (see note/solution-note.md).
3. new_MAC = SHA256_length_extend(old_digest, orig_len=L+1504+len(glue),
   append=ext) — REVIEW FIX: orig_len must INCLUDE len(glue), because the
   verifier hashes SECRET‖payload‖glue‖ext (MAC covers file[0x30:] =
   payload+glue+ext). The original code passed L+1504 and would have
   produced a MAC that fails verification everywhere. Fixed in
   work/exploit.py (2026-08-26 review); never executed end-to-end.
4. Output file: original header with entry(0x08)=vaddr(ext)=0x401000+(1552+len(glue)-0x270),
   MAC slot = new_MAC; payload = orig_payload‖glue‖ext.
5. Loader loads glue+ext into VM RAM (filesz=-1 segment); PC enters shellcode;
   flag printed on stdout of the remote service.

Remote usage: try L = 1..64 until "[+] Verified" (each guess one connection).

## Validation status (review)
- Statically verified against decompilation: all shellcode encodings match real
  echo-job instructions (li op53, lui op30 imm<<16, syscall word 0x00003011 — run
  0046) and interpreter semantics in FUN_00101c60 (ori=op28 zero-ext scattered imm;
  addu op6/funct31 rd≠0) plus syscall handler FUN_001031c0 (open reads NUL-string
  from VM mem at a0, a1=0 → O_RDONLY; read/write copy via VM memory helpers;
  numbers 4001/4003/4004/4005 = 0xfa1/fa3/fa4/fa5).
- Loader FUN_00102940 confirmed: filesz==0xffffffff ⇒ filesz=filesize−off (slurps
  appended bytes); segment offsets are whole-file absolute; entry @0x08 unhashed.
- Earlier runs 48/49/51 forged jobs were NOT valid tests: they recomputed the MAC
  correctly ("[+] Verified") but never redirected the header entry point, so the
  crafted instructions never executed (rc=132 from executing zero padding).
- Runtime end-to-end self-test still not executed: reviewer-side reverser_exec is
  gated behind a triage step unavailable in the review context.

## Flag
Not obtained: flag lives only on the remote service (`/challenge/flag.txt`); harness
is offline (platform_url empty, workers networkless). No real flag candidate seen in
any run — nothing recorded via reverser_record_flag.
