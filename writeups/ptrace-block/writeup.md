# ptrace_block (Dreamhack Reversing C4) — solved

## 요약
- `prob`: stripped amd64 ELF PIE. `main`이 `%255s`로 입력받아 AES-128-CBC(IV=0)로 암호화해 `./out.txt`(256B)에 기록. 제공된 `out.txt`가 플래그의 암호문.
- 키는 `.data:0x4010`의 16바이트 정적 시드에서 생성자 2개가 변형:
  - ctor1(0x12c9): `srand(time(0))`, 4096회 루프에서 `acc *= rand() * ptrace(PTRACE_TRACEME)` 결과. 미디버깅 실행 시 첫 TRACEME 성공(반환 0) → acc=0. 이후 `for i in 0..14: key[i+1] += key[i] + acc`.
  - ctor2(0x1392): `srand(rand()); r = rand(); for i in 0..15: key[i] ^= (byte)r`.
- 런타임 결과 공간은 (acc 하위 1바이트, r 하위 1바이트) = 최대 65,536개 키로 완전 열거 가능.

## 함정
- 파일의 정적 시드(`41 28 19 4e a5 7c a4 ...`)와 실제 out.txt 생성 당시 값이 다름: 인덱스 6이 파일에선 `a4`, 생성 환경에선 `a1`(재빌드/패치 흔적). LD_PRELOAD 후크로 실측한 키와 대조해 발견.
- 검증 방법: 워커에서 바이너리를 알려진 평문과 함께 실행하고 `AES_set_encrypt_key`를 후킹해 실제 키 덤프 → 모델 불일치 확인 → 시드 바이트 보정.

## 풀이
- 보정된 시드 `41 28 19 4e a5 7c a1 41 13 cf 88 ac 2a f0 b7 da`로 (a, x) 전수조사 AES-CBC 복호화.
- 적중: a=0, x=0x4b, key=`0a22c99b3ebad998adfe76a25848f1df`.

## 플래그
[FLAG REDACTED]

## 산출물
- output/0001~0022 로그 (triage, radare2, 동적 검증, 후크, 브루트포스)
