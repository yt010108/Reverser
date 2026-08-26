# L3ak CTF "Omega" - solver notes (unsolved: environment blocker)

## Status summary
- Challenge: custom-VM job executor (`executor`, x86-64 ELF) that loads signed `PRX` jobs.
- Goal on remote: read `/challenge/flag.txt`. Flag exists only server-side; harness has no network and platform_url is empty -> real flag not obtainable offline.
- Full attack chain reconstructed and implemented in `runs/l3ak-ctf-omega-a70a7e3f/work/exploit.py`; local validation blocked because worker image `local/reverser-core:0.1` was unavailable during this attempt (triage/exec all rejected).

## Reversed facts (from Ghidra logs output/0014/0016/0018/0007 + prior 51 runs)

### File format PRX v1 (loader FUN_00102940, run from FUN_001035c0)
```
off 0x00  magic "PRX\0"
off 0x04  version byte (=1), [5]=n_phdr, [6]=flags(bit0: reg28=*[0x0C])
off 0x08  entry point (u32)          <-- NOT covered by MAC
off 0x0C  init value for reg28       <-- NOT covered by MAC
off 0x10  MAC = SHA256(SECRET || file[0x30:])   (32 bytes)
off 0x30  payload: n_phdr * {off u32, vaddr u32, filesz u32, memsz u32} then segments
          filesz == 0xffffffff means "load until EOF"
```
echo jobs: seg1 code off 0x50 va 0x400000 len 0x220; seg2 data off 0x270 va 0x401000 filesz 0xFFFFFFFF memsz 0x3A0.

### Execution flow (main FUN_001015c0)
1. SECRET from env or fallback file; hex-decoded (FUN_00103660).
2. fork+pipe: child dup2(pipe->stdin), runs EMBEDDED verifier PRX (executor .data @VA 0x104500, 0xA80 bytes, file offset 0x4500).
3. Parent writes over pipe: u32 secret_len, secret, u32 payload_len(=size-0x30), payload bytes, 32-byte expected MAC.
4. Child exit 0 => "[+] Verified", then parent runs the job PRX in the same VM.

### MAC construction (confirmed empirically, run 22)
MAC_local == sha256(bytes.fromhex('00112233445566778899aabbccddeeff') + file[0x30:]) exactly -> classic secret-prefixed SHA256 -> length extension works.

### VM (FUN_00101c60), MIPS-O32-flavored but scrambled encodings
word stored little-endian; op=(w>>11)&0x3f, rs=(w>>22)&0x1f, rt=(w>>6)&0x1f, rd=(w>>17)&0x1f, funct=w&0x3f
imm16 = bits[17..21]<<11 | bits[27..31]<<6 | bits[0..5]; sign-ext for arith (op 53=addiu/li), zero-ext for logical (ori=op28, xori=15, andi=13); lui=op30 (rt=imm<<16)
R-type group op6 functs: addu 0x23/0x31 (rd!=0 required), sub 4/0x1d, mult 8, multu 0xc, div 0xb, divu 0x33, slt 0x10, sltu 0x1c, nor 0x17, srlv 0x18, srav 0x19, mfhi 0x1a, mthi 0x22, mtlo 0x1e, mflo 0x36, jalr 0x30, jr 0x29, syscall 0x11, sll/srl/sra shamt 0x3a/0x1f/0x2d, and 0x32, or 0x3b, xor 0x37
I-type: lw 8, lh 10, sb 0x11, sh 0x31, sw 0x21, lwl/lwr 0xe/0x27(FUN_00101a50), swl/swr 0x18/0x3e(FUN_00101b80), lbu 0x34, lb 0x3c, beq 4, bne 0x30, blez 0x12, bgtz... , addiu 0x1c? (case 0x1c shown as ORI-like zero-ext), lui 0x1e, j/jal via case 0x2/0x3?; branch target PC+4+imm*4; J-target reassembles from scattered fields.
Memory: paged, page table at state+0x90, reads of unmapped pages return 0, writes auto-allocate. regs r0-r31 at +0x00..0x7C, HI +0x88, LO +0x8C, PC +0x80/nPC +0x84, halted +0xA4, exit code +0xA8.

### Syscalls (FUN_001031c0) - NO SANDBOX
4001 exit(a0&0xff); 4003 read(a0 fd, a1 vm_buf, a2 n); 4004 write(a0 fd, a1 vm_buf, a2 n);
4005 open(path string at a0, flags mapped from a1, mode a2); 4006 close; 4019 lseek.
=> any signed job can open/read/write arbitrary host files as the executor user.

## Attack chain (exploit.py implements it)
1. Take echo.remote.prx (valid MAC under unknown remote SECRET, same layout/len as local).
2. glue = SHA256 padding for message length SECRET_LEN + 1504; extension = shellcode + path string.
3. new_MAC = SHA256_extend(old_digest, internal_len=SECRET_LEN+1504+len(glue), append=ext) -- no secret needed, only its LENGTH (brute-forceable remotely; each guess is one connection).
4. Write header unchanged except entry(0x08)=vaddr of appended code; keep original MAC slot replaced by extended digest.
5. Loader's filesz=0xFFFFFFFF segment slurps appended bytes into VM RAM at 0x401000+(file_off-0x270); PC starts inside our code.
6. Shellcode (straight-line, no branches): open("/challenge/flag.txt") -> read(fd,buf,512) -> write(1,buf,n) -> exit(0), buf at 0x500000.

Expected remote result: flag contents echoed back by the job runner.

## Validation plan (blocked)
Local tests prepared in exploit.py main(): secrets of length 16/32/47 with decoy files under /tmp plus a wrong-length negative control. All must print their decoy through the executor. Requires /challenge/input/* mounts and executable worker (image currently unavailable).

## Provenance

- Challenge ID: `l3ak-ctf-omega-a70a7e3f`
- Final status: `unsolved`
- Solve elapsed: `97965s`
