# Honest (Dreamhack Reversing C3)

## 개요
- amd64 Linux PIE ELF, not stripped (`main`).
- `./main <flag>`: argv[1] 길이가 정확히 0x40(64)이어야 하고, 각 문자를 순서대로 검사해 모두 통과하면 `Correct! Flag is [FLAG REDACTED]` 출력.

## 구조
- 전역 `counter`(초기 0)와 `correct`(초기 1) 플래그.
- `main`: `strlen(argv[1]) != 0x40`이면 correct=0. `argv[1][counter++]`를 `calculate()`에 넣고 결과가 상수(0xbd)와 같은지 비교, 틀리면 correct=0. `counter > 0x3f`이면 종료, 아니면 다음 verify 함수 호출.
- `verify_func_0` ~ `verify_func_62` (63개): main과 동일한 패턴 — counter번째 문자를 `calculate()` 후 각자 고유한 상수와 비교하고, 난독화된 순서로 다음 verify 함수를 꼬리호출. main → f2 → f1 → ... 체인 순서는 함수 번호와 무관하게 섞여 있음.
- 총 main 포함 64단계 = 64문자 검사.

## calculate() (바이트 단위 전단사 함수)
```
x ^= 0x3c
x = rol(x, 2)
x = (5*x + 0x7d) & 0xff
x = ror(x, 3) ^ 0xb2
x = rol(x, 4)
x = (3*x - 0x2f) & 0xff
x = rol(x, 1) ^ 0xd4
return bit_reverse(x)
```
모든 연산이 mod-256 전단사이므로 역변환 가능(또는 256개 전수조사).

## 풀이
1. objdump로 각 verify_func의 `cmp $imm,%al` 목표값과 `call verify_func_*` 체인을 파싱해 인덱스별 목표값 복원.
2. calculate를 Python으로 재구현, 256 입력에 대한 역매핑 생성. 각 목표값의 printable preimage가 유일함을 확인.
3. 재구현한 검증 로직으로 64자 전부 통과 확인.

## 결과
- flag 내부 값: 64자리 hex 문자열 (기록된 플래그 참조)
- 최종 플래그 형식: `[FLAG REDACTED]`
