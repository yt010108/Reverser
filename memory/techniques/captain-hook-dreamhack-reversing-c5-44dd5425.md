# captain-hook (Dreamhack Reversing C5) - 핵심 기법과 함정

## 구조
- PE32+ x64 GDI+ GUI. WM_PAINT 계열 함수(FUN_140016360)가 프레임마다
  .rdata 0x14001f3f0, 0x2400B 버퍼에서 니블 1개를 복호화해
  16개의 글리프 드로잉 함수 중 하나로 그린다.
- 전역 카운터 X는 DAT_140024888/140024890 이중 간접 포인터 배열로 난독화.
  X == 0x2400*2 가 되면 "End" MessageBox 후 종료 → 총 18432 프레임.

## 난독화 패턴 (재사용 가능)
- 로컬 변수/슬롯마다 "포인터 테이블 256개 + LCG(0x10dd mod 0x6fffffff) 기반
  XOR 키"로 이중 간접 접근. Ghidra 결과에서 슬롯 연산만 걸러내면
  실제 알고리즘은 단순하다:
  - S = min((((X+1)/2) & ~3) + 4, 0x2400)
  - buf = rdata[0:S] 복사, c = 0..S/4-1 루프
  - r = 0x5841384F - (c ^ 0x2b), c 홀수면 ~r
  - keyidx = c % (S>>2)  → 루프 범위상 항상 keyidx == c
  - J[keyidx] ^= r 다음, c >= ((X/2)>>2)일 때 buf_dw(c) ^= J[keyidx]
  - J는 시드 0x7a69에서 advance-then-store로 채운 **256개** LCG 테이블

## 함정 (이번에 틀린 부분)
1. 키 테이블을 64개로 잘못 읽고 "J[c%64]에 mix 누적" 모델을 세움.
   c<64에서는 우연히 같은 값이 나와 소규모 검증(X=0..9, dword 0~1)을 통과.
   → **모델 검증은 서로 다른 코드 경로/큰 인덱스를 반드시 포함**할 것
   (dword c>=64, 즉 X>=512 구간에서 emu와 대조).
2. Unicorn 에뮬은 malloc 누수로 수백 프레임 만에 heap exhausted.
   프레임 단위 실행 시 free를 주소 재사용으로 처리하거나
   프로세스를 자주 새로 만들 것.
3. 에뮬 중 MEMFAULT(널 참조)를 zero-page 매핑으로 덮으면 의미가 바뀔 수
   있으므로 원인 rip를 먼저 확인.

## 정답 모델
dec_dw(c) = dw(c) ^ K[(c % 256) + 1] ^ mix(c),
K[i] = 0x7a69에서 *0x10dd mod 0x6fffffff를 i+1회 적용한 값,
mix(c) = 0x5841384F - (c ^ 0x2b) (c 홀수면 ~r).
데이터 오프셋 0x2400B 전체를 이 식으로 복호화한 뒤 ASCII/플래그 검색.

## Provenance

- Challenge ID: `captain-hook-44dd5425`
- Final status: `unsolved`
- Solve elapsed: `2917s`
