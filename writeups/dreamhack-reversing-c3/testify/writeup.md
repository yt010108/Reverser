# Testify (Dreamhack Reversing C3) — write-up

## Challenge

`chal` (amd64 ELF PIE, full RELRO, canary, NX) + `chal.c`. Source/binary are
consistent (verified by disassembling `go`, `gen_fail`, `testify`,
`generate_testify`).

## Program logic

- `FLAG` is a compile-time literal in `.rodata`. In the shipped copy it is the
  placeholder `"real flag is [0-9a-f]{64}. Have a nice day!"`; on the Dreamhack
  server it contains `[FLAG REDACTED]` (see unused `FLAG_HEADER` /
  `FLAG_FOOTER` macros). **No real flag bytes exist in the provided binary**
  (checked `.rodata`/`.data` hex dumps).
- Each round you supply up to 256 patterns (max 15 usable chars each: buffer
  0x10, NUL appended at `[detect]`). The program builds an Aho–Corasick trie,
  builds fail links (`gen_fail`) and scans `FLAG` (`testify`):
  - prints `pure!` if any pattern occurs as substring of `FLAG`
  - otherwise `fail...`
- `main` loops rounds forever ("Try Again? [Y/n]").

=> The program is a **1-bit substring-membership oracle over the embedded flag
string**. The intended solve is oracle-based extraction of the flag text.

## Extraction algorithm (~4 queries per character)

1. Seed the known prefix `DH{`.
2. To determine the next character, binary-search the alphabet `[0-9a-f]`
   (16 symbols): one round submits the pattern set `{window + c}` for half of
   the remaining candidates, where `window` = last 13 known chars (patterns
   must stay ≤14 bytes because of the 0x10 read + NUL).
   - `pure!` → next char is in that half; recurse.
   - ~log2(16)=4 rounds per character ⇒ ≈260 rounds for 64 chars.
3. Stop at `}` / after 64 body characters.

A 13-char random-hex window occurs essentially uniquely in the target, so
false positives from matches elsewhere in the string are negligible.

## Protocol pitfalls (verified dynamically)

- stdin is unbuffered (`setvbuf(stdin,0,2,0)`); `scanf("%d")` leaves the
  newline in stdio pushback, so the raw `read(0,...)` sees only fresh input.
  Each pattern line must be sent as ONE write while the prompt is awaited,
  otherwise two lines get merged into one pattern (piped-input tests all said
  `fail...` for this reason until sends were separated/synchronized).
- Answer `Y` each round to keep querying.

## Validation without the server

Compiled a twin from the given `chal.c` with `FLAG` replaced by a random
secret `[FLAG REDACTED]`, ran `work/extract.py` against it:

```
RESULT: [FLAG REDACTED]
secret: [FLAG REDACTED]   # exact match
```

## Tooling

`work/extract.py --prog ./chal` or `--host H --port P` recovers the full flag
from any instance of this binary. Point it at the live Dreamhack service to
obtain the real flag.

## Blocker for this environment

The imported challenge has no reachable service (`platform_url` empty;
workers run networkless), and the local binary embeds only the placeholder
string. The extraction script is proven correct on a twin binary, but the
actual flag value cannot be determined offline.
