# boss-rush (Dreamhack Reversing C5) — Write-up

## Triage
- `main`: x86-64 ELF PIE, stripped, C++ (libstdc++), Full RELRO/canary/NX.
- Strings: boss names Grullak/Zevrak/Morgath/Thragor/Velkor/Xalvros/Krynnach, "Big Slime", RTTI `9FinalBoss`, `6Player`, `6Object`.
- Reads file `flag` at runtime -> flag is NOT embedded; printed only after winning.

## Game structure (Ghidra, base 0x100000)
- `FUN_00102aa4` (init): Player(hp=50, dmg=10, potions=1), 8 Bosses(hp=50, dmg=5), FinalBoss "Big Slime"(hp=50, dmg=1).
  - Object layout: vptr@0x0, hp@0x8, dmg@0xc, name(std::string)@0x10, byte flags @0x30 (defeated / player: potions), FinalBoss phase byte @0x31.
- `FUN_00103a5a` (game loop): menu 1=start, 2=load password, 3=exit. Fight loop; all 8 defeated (`FUN_00103750`) -> stage 8 -> Big Slime; winning prints `flag` file line.
- Vtables: Boss/Player attack slot -> `FUN_00102712` (normal hit). FinalBoss vtable @0x8b98 -> `FUN_00102a08`:
  - toggles phase byte each turn; even phase: "casted shadow word!" sets PLAYER HP := 1; odd phase: normal attack (dmg 1).
- Consequence: vs Big Slime need a potion before every other turn; 5 attacks => exactly **4 potions** required. Player starts with 1 potion and cannot beat 8 bosses normally -> must use menu option 2 ("Enter password to resume").

## Password parser `FUN_00103038`
- Reads 5 lines (rows[0..4]); each length 5, chars 'O'/'X' else "No cheating!" exit(-1).
- Row order `{0,4,3,1,2}`; row index 2 (3rd line) = potion row: exactly one 'O', its column = potion count.
- Bitmask v (20 bits): t=0..3, j=0..4: bit (j+5t) set iff rows[order[t]][j]=='O'.
- m = ror20(v, potions). Constraint pairs (lo,hi): (15,11),(5,3),(6,4),(17,18),(7,16),(0,14),(10,19),(9,13)
  - require bit(lo) != bit(hi). Boss i defeated iff bit(hi_i) set; hi bits {11,3,4,18,16,14,19,13} must all be 1, lo bits all 0.

## Winning input (brute-forced over 32^4 grids x 5 potion counts; 16 valid solutions)
```
2                 <- menu: Enter password to resume
OXOOX             <- rows[0]
OOOOX             <- rows[1]
XXXXO             <- rows[2]: potion count = 4 (column 4)
XXOXX             <- rows[3]
OOOOX             <- rows[4]
1 2 1 2 1 2 1 2 1 <- final boss turns: Attack/Potion alternating
```

Verified end-to-end in the dynamic worker with a dummy `flag` file:
Big Slime defeated! -> "You have conquered the dungeon! Get the flag: <contents of ./flag>".

## Note on the actual flag
The real flag string lives in the `flag` file next to the binary on the challenge
server and is read via std::ifstream("flag") only after the final boss dies.
No platform URL/server was attached to this run (`platform_url` empty), so the
real flag could not be captured locally; feeding the above stdin transcript to
the server instance prints it.
