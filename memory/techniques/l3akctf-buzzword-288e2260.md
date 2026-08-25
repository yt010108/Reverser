# L3akCTF Buzzword — 분석 기록 (미완료)

## 바이너리
- buzzword: x86-64 정적 링크 stripped ELF (No PIE, 0x400000), GFNI(`gf2p8affineinvqb`) 사용
- model.bin: 21336B = 42x42 int32 행렬 3개(126 row) + 잉여 1 row

## main 흐름 (0x402fa5)
1. `ptrace(PTRACE_TRACEME)` (0x403018 call 0x477f50)
2. `printf("Input: ")` → `fgets(buf, 0x32, stdin)` — 최대 49바이트
3. buf를 int[50] 배열(-0x7140)로 변환(부호확장), 난독화된 다항식 인덱스 루프
4. fopen("model.bin","rb") 후 fread로 42x42 int32 블록 3개를 버퍼 오프셋
   0 / 0x1b90 / 0x3720 에 로드 (stride 0xa8)
5. 거대한 난독화 연산(흩어진 basic block + `0f 0d` 안티디스어셈):
   - gf2p8affineinvqb xmm0,xmm1(상수 0x0102040810204080) = GF(2^8) 바이트별 곱셈 역원
   - pext 0x55555555/0xaaaaaaa 비트 인터리브
   - model 행렬 원소와 입력 파생 값을 조합해 테이블/출력 버퍼 생성
6. `printf("Output: %s\n", out_buf)` (fmt @ 0x4d4025)
7. 체크 (0x456f09): `Σ_{k=0..49} (int16)out[k]² <= 0x7f` 이면 puts("Correct")

## 관찰된 동작 (GFNI 소프트웨어 에뮬레이션 패치 후)
- 입력 `\x03\n` → `Output: \xcc\xab\x8e\xef\x84[9\r\xfb`, exit 255 (Correct 아님)
- 일부 입력('A' 등)은 실행 시간이 수 분 초과 (데이터 의존적 루프)

## 수행한 우회
1. ptrace(TRACEME) → xor eax,eax 패치
2. GFNI 미지원 CPU용 SSE2 스텁(1.2KB) 작성:
   - gmul(시프트-가산 GF 곱) + red4(0x11b 축소) + x^254 역원
   - 316개 gfni 사이트(모두 `66 0f 3a cf c1 00`)를 `call stub` 으로 교체
   - 스텁 배치: .text 끝~.rodata 사이 RX 패딩(0x4d3500) — NOP 슬레드는
     fall-through 실행되므로 사용 불가
   - rax/flags/xmm1..7 보존 필수

## 남은 과제
- 모델 변환(F: 입력→출력 버퍼)의 수학적 구조 규명 및 역변환/제약축소
- 목표: 출력이 Σc²≤127 (사실상 전부 0 또는 미소값)이 되는 입력 도출
- 대안: angr로 심볼릭 실행 (단, gfni 에뮬레이션 훅 필요)

## 산출물
- /challenge/output/stub.bin (SSE2 GF 역원 스텁)
- 패치 스크립트 요령은 본 문서 기술

## Provenance

- Challenge ID: `l3ak-ctf-buzzword-288e2260`
- Final status: `researching`
- Solve elapsed: `6459s`
