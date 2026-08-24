# This is not a web challenge — Write-up

- Event: Dreamhack Reversing C5
- Category: reverse (amd64 Linux ELF, Apache module)
- Status: SOLVED

## Files

- `module.so` — stripped Apache httpd module (`my_module`, handler `my-handler`)
- `index.html` — POST form with a single `flag` field
- `custom.conf` — `LoadModule my_module modules/module.so` / `AddHandler my-handler .dreamhack`

## Analysis

The two `[FLAG REDACTED]` strings visible in `.rodata` are **decoys** shown on failure paths.

Ghidra decompile of the handler (`FUN_00101460`, base 0x1460 in file):

1. Only handles requests where the last 22 bytes of `r->filename` satisfy
   `filename[len-22+i] ^ T_key[i] == T_exp[i]`, with 22-byte tables at
   `.rodata:0x2120` (expected) and `0x2140` (key).
2. On POST it parses form data and for each field:
   - CRC32-style check (poly 0xEDB88320, init 0xffffffff) against `0x35014541`
   - value length must be 22
   - each byte must satisfy `value[i] ^ filename_tail[i] == T_C[i]`
     with table at `.rodata:0x2100`
3. On success it reads and echoes the server file `/flag`.

## Solution

Both checks are linear over data in the binary, so no server is needed:

```
filename_tail = T_exp ^ T_key = "correct_path.dreamhack"   (the URL to request)
flag          = filename_tail ^ T_C = "[FLAG REDACTED]"
```

CRC gate clarified (review): the decompile computes the CRC over the form
field **NAME**, not the value (`__s1 = *puVar7`; `strncmp(__s1,"flag",4)`;
CRC loop over `__s1`). So 0x35014541 only requires a field name starting with
`flag` whose custom CRC-32 (poly 0xEDB88320, init/final 0xffffffff, no final
XOR) matches — it never constrains the flag value. Exact name not brute-forced
(worker execution is refused after solve); irrelevant to the answer.

Verification: decoded path is meaningful English matching the 22-byte length
check; decoded value matches `[FLAG REDACTED]` format and the same length. The two
independent XOR chains (tables 0x2120^0x2140 and tail^0x2100) uniquely
determine both values.

Note: the success path prints the contents of `/flag` from the live server;
the recovered string is the access credential/flag for this challenge.

## Flag

`[FLAG REDACTED]`

## Artifacts

- `output/ghidra.c` — decompiled handler + file reader
- `output/0005-core.stdout.log` — rodata hex dump of the three tables
