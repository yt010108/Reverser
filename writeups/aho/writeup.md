# Aho (Dreamhack Reversing C3) — solved

## 요약
- `main`(amd64 ELF PIE, stripped)은 13자 답을 `scanf("%13s")`로 입력받아 검사하고, 통과 시 `flag` 파일을 읽어 출력한다.
- 검사 로직은 Aho-Corasick 오토마타:
  - 알파벳 10자 `"aehinrstuw"`(0x46b0), 각 문자가 이 알파벳에 없으면 "Impossible character"로 즉시 종료.
  - 상태 테이블: `.data` 0x4020부터 8바이트 구조체 배열 `{int32 next_state; int32 pattern_id}` — `idx = state*10 + j`.
  - `pattern_id >= 0`이면 `mask |= 1 << pattern_id`, 상태는 항상 `next_state`로 전이.
  - 13자 소비 후 `mask == 0xf`이면 Correct → flag 파일 출력.

## 풀이
1. radare2로 main 디스어셈블 → 오토마타 구조와 테이블 베이스(0x4020/0x4024) 파악.
2. 워커에서 Python으로 ELF를 직접 파싱해 테이블 추출: 상태 20개, 패턴 id 0..7.
3. 완전탐색 DFS는 10^13으로 시간 초과 → DP(위치 × 상태 × mask ≤ 14×20×16)로 전환.
4. 역추적 결과 조건을 만족하는 해 `[FLAG REDACTED]` 획득.
   - 주의: DP가 (상태, mask) 키별로 백포인터 1개만 저장하므로 "유일"은 증명되지 않음 — 적어도 하나의 유효해임은 동적 실행(`Correct!`)으로 확정.
   - "this is answerr" 형태의 문장. 패턴 4종(bits 0..3)은 모두 매칭되고 4..7번 패턴은 매칭되면 안 됨(마스크가 정확히 0xf).
5. 격리 dynamic 워커에서 실행 검증: `Correct!` 및 플래그 파일 내용 출력 확인.
   - 로컬 flag 파일은 `[FLAG REDACTED]`(더미). 실제 플래그는 라이브 서비스의 flag 파일에서 출력됨.

## 산출물
- output/solve2.py : 테이블 추출 + DP 솔버
- output/0006-core.stdout.log : 유일 해 발견 로그
- output/0007-dynamic.stdout.log : 실행 검증 로그

## 정답 입력
`[FLAG REDACTED]`
