# Testify (Dreamhack Reversing C3) - solution note

## Key idea

The binary is an Aho-Corasick automaton over a compile-time FLAG literal.
Each interactive round accepts up to 256 patterns (<=14 usable bytes each,
0x10 read buffer + NUL) and answers exactly one bit: "pure!" if any pattern
occurs as a substring of FLAG, else "fail...". Rounds loop forever.

=> It is a 1-bit substring-membership oracle; extract FLAG character by
character from the live service.

## Extraction

- Seed the known prefix (header chars, e.g. D H open-brace).
- Next char via binary search over the 16 hex symbols: one round tests
  patterns {window + c} for half the remaining candidates, window = last 13
  known chars. About 4 rounds per char, ~260 rounds total for 64 body chars.
- A 13-char random-hex window is unique in practice, so no false positives.

## Protocol pitfalls

- stdin is unbuffered; scanf percent-d leaves newline in stdio pushback, so
  raw read() only sees fresh input. Send the "amount" line first, then await
  each "input i: " prompt and send each pattern as ONE write (merged writes
  make two lines become one pattern - all queries then return fail...).
- Answer Y after each verdict to continue rounds.

## Validation

Compiled chal.c with FLAG replaced by a random 64-hex-char secret wrapped in
the flag header/footer; extractor (work/extract.py) recovered it
byte-for-byte. Script supports --prog for local process or --host/--port for
remote service. Point at the Dreamhack server to obtain the real flag. The
offline copy embeds only a placeholder sentence (verified .rodata).

## Provenance

- Challenge ID: `testify-4c01a64b`
- Final status: `unsolved`
- Solve elapsed: `468s`
