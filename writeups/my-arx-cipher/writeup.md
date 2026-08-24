# My ARX Cipher (Dreamhack Reversing C2)

## 아티팩트
- `encryptor` — stripped amd64 ELF PIE (Full RELRO, canary, NX)
- `flag.enc` — 72바이트 암호문
- `key` — 12바이트 ASCII: "SuP3RSaFeK3Y"

## 분석
Ghidra 디컴파일로 구조 파악:

- `main` (0x1495): `encryptor <key_file> <input> <output>`
- `read_key` (0x1229): 키 파일에서 `fread(buf, 2, 6)` → u16 서브키 6개 (LE)
- `encrypt_file` (0x1381): 입력을 4바이트씩 읽어(부분 블록은 zero-pad) 라운드 함수 적용 후 그대로 기록
- `rounds` (0x129f): 블록 = 두 개의 u16 LE (x=lo, y=hi), 라운드 r=0..2:
  - `y_next = ((rotl16(x,7) + y) & 0xffff) ^ k[2r]`
  - `x_next = rotl16(y,7) ^ k[2r+1]`

## 복호화
ARX만으로 구성되어 완전 가역:

```
y_prev = rotr16(x_next XOR k[2r+1], 7)
x_prev = rotr16(((y_next XOR k[2r]) - y_prev) AND 0xffff, 7)
```

r=2→0 역순 적용. 서브키는 "SuP3RSaFeK3Y"를 `<6H`(LE) 언패킹.

## 검증
복호화 결과(플레인텍스트 + 후행 `\n\x00\x00\x00`)를 원본 바이너리로 재암호화 → `flag.enc`와 바이트 일치(`cmp` MATCH).

## 플래그
(비공개 — `ctf_record_flag`에 기록됨)

## 산출물
- `output/ghidra.c` — 디컴파일
- `output/decrypt.py` — 복호화 스크립트
