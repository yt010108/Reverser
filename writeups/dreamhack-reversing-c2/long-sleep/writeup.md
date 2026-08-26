# Long Sleep (Dreamhack Reversing C2) — Write-up

## 대상
- `original/prob`: ELF 64-bit PIE, x86-64, stripped, 14464 bytes
  sha256 `7e2484650c1055b3d3bfba21c27ca064ead63bb415254b5418ff1e84c5edfa61`
- Full RELRO / canary / NX / PIE

## 핵심 구조
- `main` (0x1367): `gen_flag(buf)` 호출 후 `[FLAG REDACTED]`.
- 생성기 `fcn.00001411`:
  - 전역 `[0x4030] == 1` 검사(아니면 exit(0)).
  - 문자열 `"I will evolve into SUPER FLAG!!!!"`(33바이트)을 자체 해시로 다이제스트 → 플래그 본문.
- 해시: 표준 SHA-256 구조(IV 동일, 메시지 스케줄/압축 함수 동일)이되 **K 상수 64개가 일부 변조됨** (예: K[0] 428a2f98→418a2fa8, K[1] 71374491→51374492, K[61] a4506ceb→a4506cbb 등).
- Anti-dynamic ("Long Sleep"):
  - 생성자 `entry.init1`이 무결성 검사: main(0x1367)부터 0x1000바이트를 위 해시로 계산해 내장 다이제스트와 비교, 실패 시 에러 출력 후 exit(-1). 성공 시 `[0x4030]=1`.
  - 압축 루프 내부에서 매 라운드 `[0x4030]!=0`이면 `fcn.000014d2` 호출 → raw `syscall nanosleep(0x23)`으로 요청마다 대기 시간이 **2배씩 증가**. 그대로 실행하면 사실상 종료 불가.
  - 패치도 무결성 검사 때문에 불가(.text 전체가 해시 범위).

## 풀이
실행하지 않고 알고리즘을 정적으로 재구현:

1. r2로 0x1552(SHA-256 transform), 0x19f5(init), 0x1a73(update), 0x1b14(final) 디스어셈블.
   - Σ0=ror2^ror13^ror22(rol10과 동일), Σ1=ror6^ror11^ror25(rol7과 동일) → 표준과 동일.
   - 메시지 스케줄도 표준(s0/s1 회전 상수 동일).
   - 유일한 차이: K 테이블(0x20c0, 64워드) 값 변조. IV는 표준.
2. Python으로 커스텀 K를 사용한 SHA-256 재구현 (`runs/<id>/work/solve.py`, 워커 /tmp/solve.py).
3. 검증: 바이너리에서 0x1367+0x1000 바이트를 해시해 내장 다이제스트
   `7f5712e2fe953b16 40bef27a2df821c7 698449eda6f904c6 7502ef1a49aa869e`(LE qword 4개)와 비교 → **일치**.
   이것으로 재구현(패딩 포함)과 변조된 K 추출이 모두 정확함을 확인.
4. `"I will evolve into SUPER FLAG!!!!"`의 다이제스트를 hex 인코딩한 것이 플래그 본문.

## 결과
플래그는 로컬에만 기록(`reverser_record_flag` 완료). 형식: `[FLAG REDACTED]`.

## 산출물
- runs/long-sleep-6ec393f3/work/writeup.md (본 문서)
- 워커 /tmp/solve.py — 재구현 + 검증 스크립트 (output/0011-core.stdout.log에 결과)
