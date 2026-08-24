# Technique: BST-walk token stream decoding (Dreamhack "Weird Forest"류)

- 인코더: 각 문자 c → v=(ord(c)^k)를 signed char로 변환, BST 삽입 경로를 이모지 토큰으로 출력
  (P=insert / D=left / E=right / C=duplicate-hit). 시뮬레이터 검증법:
  임의 텍스트 + 모든 k(0..255)로 encode(text,k) == 바이너리 출력 비교.
  signed char 변환 여부가 당락을 가름. 이 모델은 완전 일치로 검증됨.

- **함정 0 (신규): k는 실행마다 달라진다.** 바이너리가 런타임에(ASLR 유래 추정) k를 정하므로
  워커A에서 구한 "샘플의 참 k"는 워커B에서 무효. 검증 파이프라인은 반드시
  같은 프로세스/컨테이너 안에서 (1) 샘플 스트림 생성 → (2) 매칭 k 탐색 → (3) 그 k로 솔버 검증
  순서로 수행할 것. k↔k^128 동치류 존재(동일 스트림 생성 관찰됨).

- 디코딩 구조: C(duplicate)-종결 세그먼트는 트리/k 주어지면 문자 유일 결정.
  P(insert) 세그먼트만 자유도. 예: 1308토큰 → 195문자 중 P 68개만 분기점.

- 함정 1: 같은 (BST canonical rank-shape, phase) 상태를 공유하는 서로 다른 디코딩이 매우 많음.
  빔서치 상태당 best-1만 유지하면 참 해가 소실됨(수백 개 유효 해 중 원문 부재 사례 확인).
  → 상태당 top-K(K≥5) 보존 또는 전체 열거 + 메모이제이션 필요.

- 함정 2: 순수 열거 DFS도 27자 샘플에서 완주 불가(15분+ 초과). 195자는 기하급수.
  LM 가이던스 없는 전수 탐색은 비현실적. 잘못된 k 하나를 수백만 스텝 소진하지 말 것.

- 함정 3: 미검증 솔버의 "해 없음"은 무효. 빔/NFA 구현은 반드시 샘플 exact 복원을
  먼저 통과시킨 뒤 타깃에 적용. 여러 버전이 샘플에서 0솔루션/즉사로 실패한 채 종료됨.

## Provenance

- Challenge ID: `weird-forest-71530e37`
- Final status: `researching`
- Solve elapsed: `18101s`
