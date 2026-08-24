# carta — Dreamhack Reversing C4 (solved)

## 개요
- amd64 Linux ELF PIE, stripped. 16×16 카드 짝맞추기 게임.
- 값 0..127이 각 2장씩 256장, `/dev/urandom`에서 읽은 시드 1바이트로 셔플.
- 모든 짝을 맞추고 trial 횟수가 128 이하(`trials < 0x81`)여야 플래그 지급 → 단 한 번도 실패 없는 완벽 플레이 필요.

## 취약점
1. `Stage %hhu` 프롬프트가 **셔플에 사용되는 초기 시드를 그대로 출력**한다.
2. 셔플 PRNG는 결정적 8비트 LFSR: `b = s & 1; s >>= 1; if (b) s ^= 0xb8`.
3. 셔플은 256회 스왑이며 각 스왑은 LFSR을 2회 진행해 좌표 `(s&0xf, s>>4)` 두 쌍을 얻는다.

→ 시드만 알면 최종 보드를 완전히 재현할 수 있다.

## 풀이 절차
1. Ghidra로 `main`(0x17b3), 셔플(0x132b), LFSR(0x12ee), 픽 함수(0x14a9) 디컴파일.
2. Python으로 보드 재현: 행마다 값 v가 연속 2장씩 배치 후 LFSR 스왑 256회.
3. 값 → 좌표 매핑 생성 후, 값 0..127 순서대로 같은 값을 가진 두 좌표를 한 trial에 입력.
   - 각 trial은 `scanf("%d %d")` 두 번(행 열, 행 열).
4. 정확히 128 trial 만에 "Game Cleared! Trials: 128" → 조건 충족 → 플래그 출력.

## 실행 결과 (격리 워커, 로컬 flag 파일)
```
Game Cleared! Trials: 128
Perfect Gamer! Get the Flag: [FLAG REDACTED]
```

## 아티팩트
- `runs/carta-0fb09bff/work/solve.py` — pwntools 솔버
- 실제 서버 플래그는 원격 인스턴스의 flag 파일로 결정됨(로컬 검증은 testflag).

## 비고
- Ghidra 헤드리스 스크립트는 함수 이름 대신 **PIE 로드 주소(0x100000 기준)** 를 받아야 했다 (`0x1017b3` 등). 결과는 `/challenge/work/OUTPUT`에 저장됨.
