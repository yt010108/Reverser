# rev-basic-9 (Dreamhack Reversing C2)

## 개요
- 파일: chall9.exe (PE32+ x64, MSVC) — 8바이트 블록 단위 커스텀 암호

## 분석
check(input):
- `(strlen+1) % 8 == 0` 여야 함 (len ≡ 7 mod 8)
- 입력을 8바이트 블록 단위로 fcn.1400010a0로 변환(제자리)
- `memcmp(input, enc, 25)` → len=23, enc[24]=0

블록 암호 (fcn.1400010a0):
- 키 "I_am_KEY\0" (스택 복사, key[j] = j&7 인덱스 사용)
- S-box: AES S-box (0x140004020)
- 초기 state = blk[0], 16라운드 × 8스텝 = 128스텝:
```
nxt  = blk[(j+1)&7]
state = ror8((sbox[state ^ key[j&7]] + nxt) & 0xff, 5)
blk[(j+1)&7] = state
```
- 암호문(enc, 0x140004000, 25B): 7e7d9a8b252dd53d032b3898279f4fbc2a79007dc42a4f58 00

역산 (각 스텝을 거꾸로):
- step j 이후 state는 blk[(j+1)&7]에, step j-1의 state는 blk[j&7]에 저장돼 있음
- `n_old = rol8(s_j, 5) - sbox[s_prev ^ key[j&7]]`, blk[(j+1)&7] = n_old
- j=127→0 순서로 복원하면 원본 블록 복구됨 (pos 0은 backward j=7에서 원복)

재암호화 verify: True

## 결과
- 입력값: Reverse__your__brain_;) (23자)
- 플래그: [FLAG REDACTED] (로컬 기록 완료, 사이트 미제출)
