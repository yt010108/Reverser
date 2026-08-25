# GFNI(GF2P8AFFINEINVQB) 난독화 우회 — 교훈 (buzzword, 108분 미해결)

## 핵심 기법/실수
1. `gf2p8affineinvqb xmm0, xmm1, imm8`은 **src 바이트를 GF(2) 8×8 행렬로 보고 그 역행렬을
   적용하는 비트 어파인**이다. 필드 곱셈 역원이 아니다. xmm1=비트반전 항등행렬
   (0x0102040810204080)이면 결과는 **바이트별 bit-reverse(선형)** → 전체 체크를
   선형대수(GF(2) 소거/역변환)로 풀 수 있다. ISA 의미를 구현 전에 먼저 확정할 것.
2. CPU가 지원 명령을 에뮬레이션해야 하면: 손작성 SSE2 스텁 대신 C 함수
   `__m128i f(__m128i,__m128i)`를 `-Os -ffreestanding -fno-stack-protector -nostdlib`
   로 컴파일해 .text만 objcopy로 추출해 붙인다(System V: 인자/반환 모두 xmm).
   반드시 Python 참조 구현과 256² 전수 단위테스트 후 사용.
3. 정적 패턴(`66 0f 3a cf c1 00`)으로 명령 교체 시 섹션/세그먼트(RX) 필터와
   배치 영역 미사용 확인 필수. .text 중간 겹쳐쓰기 → SIGSEGV@rip=0.
   실행 가능한 빈 패딩(.text 끝~.rodata 사이 RX gap)이 안전.
4. 스텁은 rax/rflags/xmm(callee-saved 아닌 것도 사이트 문맥상) 보존 + pushfq/popfq 필요.
5. 데이터 의존 실행시간(입력 따라 수 분)이면 전수 탐색 불가 → 구조(선형성) 규명이 정석.

## 재사용
- GFNI 계열(affine/aesencvaes 등) 난독화 만나면: ① cpuinfo 확인 ② xmm 피연산자 덤프로
  실제 연산 확인 ③ 선형이면 Python 재구현+선형대수, 아니면 C-ABI 스텁+단위테스트.

## Provenance

- Challenge ID: `l3ak-ctf-buzzword-288e2260`
- Final status: `unsolved`
- Solve elapsed: `6481s`
