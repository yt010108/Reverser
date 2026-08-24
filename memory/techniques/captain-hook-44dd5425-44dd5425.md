# captain-hook-44dd5425 — 풀이 노트 (미완결, 연구 결과)

## 검증된 핵심 사실 (Unicorn 에뮬레이션으로 X=0..9000 범위 100% 일치 확인)

1. **프로그램 구조**
   - WinMain(0x140015fc0) → WndProc(FUN_140016200) → 프레임 함수 FUN_140016360
   - WndProc: WM_RBUTTONUP(0x202)마다 InvalidateRect → WM_PAINT(0xf)에서 FUN_140016360 1회 실행.
     즉 **우클릭 1번 = 니블 1개 표시**, 총 0x4800=18432회 필요 ("Patch Me!" 힌트).
   - 종료 조건: 카운터 X == varB*2 (varB=0x2400) → MessageBox "End" 후 ExitProcess.
   - 타이틀 문자열: "Patch Me! C411 5t4ck? Flag is "

2. **암호화 버퍼**: .rdata 0x14001f3f0 (파일 오프셋 0x1e1f0), 길이 0x2400바이트.
   프레임마다 원본에서 S=min((((X+1)/2 &~3)+4), 0x2400) 바이트 복사 후 복호화.
   - 키스트림 K[64]: K[i] = LCG(i+1), LCG: v=(v*0x10dd) mod 0x6fffffff, 시드 0x7a69
   - 각 dword c (c<S/4): mix(c) = ~(0x5841384F-(c^0x2b)) if c&1 else (0x5841384F-(c^0x2b))
     K[c%64] ^= mix(c) 누적 → 유효키 cum(c) = K_init[c%64] ^ mix(c%64) ^ mix(c%64+64) ^ ... ^ mix(c)
   - buf4[c] ^= cum(c) (단 c >= (X/2)>>2 인 것만 — 화면 위치 dword가 항상 복호화됨)

3. **표시**: nibble = buf[X/2] >> (X 홀짝에 따라 4/0) & 0xF → 16개 글리프 함수로 그림.
   글리프 매핑은 Ghidra 비교 체인으로 확정:
   8→140008dc0, 1→a2e0, 5→b650, 2→cb00, d→dfb0, a→f3f0, 9→108a0, f→11dd0,
   0→13210, e→147a0, 3→1240, (b→2760, 4→3c20, c→5060, 6→64b0, 7→7970 — 순서 동일 패턴)
   → **화면에 흐르는 전체 digit열 = dec.bin(9216B)의 hex 표기** (runs/…/work/digits.txt)

4. **dec.bin 내용 구조** (runs/…/work/dec.bin):
   - 0x88 채움 바이트가 다수. 앞 64B는 스파스 헤더, 64~8500B는 고엔트로피 데이터,
     **8617~9060B는 0x88로 구분된 문자열 유사 세그먼트들**, 이후 0x88 패딩.
   - 반복 템플릿 세그먼트: `91 f8 9e 5c 9c f2 5c ff 9e 96 5c 92 f5 fd 5c [WORD] 5c 94 21 5c 21 5c 28 56 9d 94 94`
     WORD가 6종 변함(길이 6,4,7,5,6 / 하나는 없음). 심볼 45종 → 치환성 인코딩으로 추정.

## 시도했으나 실패한 해석 (전부 재현 가능)
- 단일 XOR/ADD/SUB, affine(mod256, mod95), 비트반전+XOR, 델타(sub/xor prev),
  cp949/euc_kr/cp1252 등 코드페이지, UTF-16, x86 디스어셈블(32/64),
  영문 치환 hill-climbing(bigram), 클래스별 Caesar(lower/up/digit 분리 회전),
  아이콘 리소스(18개 — 두 그룹 완전 동일, 플래그 없음).
- 참고: 심볼 밴드 90–A9 / D1–EA / F0–FF 가 각각 a-z / A-Z / 0-9 크기와 일치하지만
  단일 오프셋(Caesar/affine)로는 영어가 나오지 않음. 커스텀 치환표 또는
  다른 2차 인코딩(예: 한국어 관련) 가능성 남음.

## 남은 가설
- dec.bin 중간부(64~8500)는 의도된 랜덤 패딩일 수 있고, 꼬리 문자열이 본 메시지.
- "C411 5t4ck?" 힌트는 우클릭 진행 방식(call stack 무관) 혹은 다른 의미 미확인.
- 꼬리 세그먼트의 실제 인코딩을 알아내면 플래그 문자열이 나올 것으로 판단.

## 산출물
- runs/captain-hook-44dd5425/work/emu.py : Unicorn 재구성 에뮬레이터(힘 256MB, run_frame(X))
- runs/captain-hook-44dd5425/work/dec.bin : 복호화 버퍼(9216B, emu와 X<=9000까지 일치 검증)
- runs/captain-hook-44dd5425/work/digits.txt : 화면 표시 digit 스트림(18432자)

## Provenance

- Challenge ID: `captain-hook-44dd5425`
- Final status: `researching`
- Solve elapsed: `2917s`
