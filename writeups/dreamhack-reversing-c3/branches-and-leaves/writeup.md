# Branches and Leaves (Dreamhack Reversing C3)

## 개요
- stripped PIE ELF x86-64, 2MB. .text는 509바이트뿐이고 나머지는 전부 .data(0x200060 바이트)에 들어 있다.
- `main`(0x10a0)은 `argv[1]`을 검증 함수(0x11e0)에 넣고 통과하면 그대로 `[FLAG REDACTED]`로 출력.

## 검증 함수 (0x11e0)
1. `strlen(input) == 0x40` (64자 hex) 아니면 `exit(1)`.
2. 4 hex 글자씩 16그룹으로 파싱해 16비트 값 생성.
3. 각 그룹마다 트리 탐색 16단계:
   - 노드 인덱스 `cur = 0`에서 시작
   - 매 단계 `bit = val & 1; val >>= 1` (LSB부터 소비)
   - `cur = tree[2*cur + bit]` — tree는 0x4060의 int32 배열
   - 중간 값이 -1이거나 > 0x3ffff면 실패
4. 16단계 후 최종 값이 expected 테이블(0x4020, int32 16개)과 일치해야 함.

즉 이름 그대로 이진 트리(branch)를 따라 내려가 잎(leaf)의 태그값이 expected와 같은 경로를 찾는 문제.

## 풀이
- .data 덤프: 파일 오프셋 0x3000 (vaddr 0x4000), expected = 0x4020, tree = 0x4060 (2^19개 int32).
- 루트(노드 0)에서 DFS로 깊이 16까지 유효한 모든 경로를 열거(-1/범위 백 제외), 마지막 값이 expected[i]인 경로의 비트열을 복원.
- 각 그룹마다 유일한 해가 존재. 비트는 LSB부터 소비되므로 `value = sum(bit_j << j)`, 16비트 값을 `%04x`로 이어붙임.

## 검증
- 체커 에뮬레이션으로 16그룹 전부 일치 확인.
- 격리 워커에서 실제 실행:
  `./main <64hex>` → `[FLAG REDACTED]` 출력 확인.

## 결과
- 입력(=플래그 내용): 64 hex 문자열 (플래그 기록은 상태 저장소 참조)
