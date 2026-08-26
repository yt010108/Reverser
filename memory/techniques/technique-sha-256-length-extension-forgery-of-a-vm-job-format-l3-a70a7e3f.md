# Technique: SHA-256 length-extension forgery of a VM job format (L3ak "Omega")

Reusable pattern when an executor loads "signed" jobs and the MAC is
SHA256(SECRET ‖ payload) with the secret as PREFIX:

1. Confirm MAC construction empirically with the known local secret before
   assuming anything (sha256(secret + file[0x30:]) matched exactly here).
2. Length extension needs only the SECRET LENGTH, not the secret:
   - glue = b"\x80" + zeros + be64((secret_len+payload_len)*8)
   - new_mac = extend(old_digest, orig_len = secret_len + payload_len + len(glue),
     append = ext)
   PITFALL (cost us a review cycle): orig_len must INCLUDE len(glue) if glue is
   part of the hashed message. Forgetting it yields MACs that always fail.
3. Look for header fields OUTSIDE the hashed region — entry point at 0x08 was
   unhashed, so PC can be pointed straight into appended data.
4. Look for "load until EOF" segment semantics (filesz == 0xffffffff in this
   PRX loader): appended bytes silently land in VM RAM at linear vaddr.
5. If the VM has unsandboxed syscalls (open/read/write), straight-line shellcode
   (no branches) avoids having to reverse branch encodings: open(flag)->read->
   write(1,...)->exit.
6. Validate hand-assembled instructions against REAL instructions from a working
   sample decoded with the custom field layout — standard MIPS assemblers are
   useless for scrambled ISAs. Also verify R-type/I-type quirks (rd≠0 required,
   scattered imm bits [17..21]<<11|[27..31]<<6|[0..5], zero- vs sign-extended).
7. When testing forged files, ACTUALLY redirect the entry point; otherwise runs
   "passing verification" prove nothing about your code (we executed zero padding
   and got SIGILL-looking rc=132).
8. Brute-force the unknown remote secret length remotely (one connection per
   guess); first "[+] Verified" identifies L.

Environment notes: worker exec may be gated behind triage; stale blockers can
hide that execution was actually available (check tool_runs logs first).

## Provenance

- Challenge ID: `l3ak-ctf-omega-a70a7e3f`
- Final status: `unsolved`
- Solve elapsed: `97965s`
