# Call more functions (Dreamhack Reversing C3)

## 개요
- stripped amd64 PIE ELF. `main`은 64바이트 입력(`%65s`, strlen==0x40)을 받아 검증 함수 `fcn.00001311`의 반환값이 0이면 `[FLAG REDACTED]` 출력.

## VM 구조
전역 변수: 스택 버퍼 0x50a0, SP 0x508c, 에러 플래그 0x5088, 입력 버퍼 0x5040.

- `fcn.1236(v)`: push v (`buf[sp]=v; sp++`)
- `fcn.1257()`: top = input[top] (입력 인덱스 로드)
- `fcn.1290()`: top을 pop해 새 top과 XOR (**1개 소비**)
- `fcn.12cb()`: top을 pop하며 새 top과 비교, 다르면 err|=1 (**1개 소비**)

`fcn.1311`은 이 함수들을 총 319회 호출( push 128 / load 64 / xor 63 / cmp 64 )하는 직선 코드이며 마지막에 누적 XOR 값 == 0 비교 후 err 플래그 반환.

## 풀이
1. radare2로 check 함수 전체 disasm 덤프.
2. Python 파서로 op 시퀀스 추출 후 심볼릭 실행: 각 스택 값 = (입력 바이트 인덱스 집합, 상수), xor/cmp는 각각 top 1개만 소비함에 유의 (처음 2개 소비로 착각해 언더플로 발생 → 수정).
3. cmp마다 "입력 바이트들의 XOR ^ 상수 == 0" 제약. 512비트 GF(2) 가우시안 소거 → rank 512/512, 유일해.
4. dynamic 프로필에서 실제 실행으로 검증 통과.

## 결과
- 입력(=플래그 내용): 64자 hex 문자열 (기록된 플래그 참고)
- 검증 출력: `Correct! The flag is [FLAG REDACTED]`

## 산출물
- output/check.asm : fcn.1311 전체 disasm
- solve2.py : 파서 + GF(2) 솔버 (worker /tmp/solve2.py, 본 문서와 동일 로직)
