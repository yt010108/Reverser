# Progress

## 폴더 구조 (2026-08-24 재정리)
- `runs/dreamhack-reversing-c1..c5/` — 드림핵 리버싱 클래스별
- `runs/l3akctf-2026/` — L3akCTF 2026 rev 6문제
- `writeups/`도 동일 구조 (공개용은 플래그 redacted)
- 예전 문서 내 `runs/<id>/...` 경로는 `runs/<분류>/<id>/...`로 읽을 것

## 2026-08-24 — rev-basic-3 (Dreamhack Reversing C1) ✅ SOLVED
- 상태: solved (플래그 로컬 기록 완료, 사이트 미제출)
- challenge_id: rev-basic-3-39f94b43
- 파일: chall3.exe (PE32+ x64, MSVC)
- 방법: radare2 정적 분석. 검증 함수 0x140001000이 24바이트 루프로
  `enc[i] == (input[i] ^ i) + 2*i` 비교 (.data 0x140003000 배열).
  역산 `input[i] = ((enc[i]-2i)&0xff) ^ i` → 입력 복원.
- 플래그: DH{I_am_X0_xo_Xor_eXcit1ng} → runs/rev-basic-3-39f94b43/ 기록
- Write-up: runs/rev-basic-3-39f94b43/reports/writeup.private.md (공개본은 writeups/rev-basic-3/)
- 소요: 약 14분 (직접 해결, ctf_learn 불필요)
- 참고: Ghidra 헤드리스 postScript 실패(사유 미상) → r2로 대체해 해결.
  ctf_exec 워커는 일회용이라 /tmp 상태가 호출 간 유지되지 않음(한 호출에 전부 수행할 것).
  r2 출력은 cp949 인코딩 오류 가능 → `| iconv -c -f utf-8 -t ascii` 권장.

## 2026-08-24 — rev-basic-4 (Dreamhack Reversing C1) ✅ SOLVED
- 상태: solved (플래그 로컬 기록 완료, 사이트 미제출)
- challenge_id: rev-basic-4-cab2188c
- 파일: chall4.exe (PE32+ x64, MSVC)
- 방법: 검증 함수 0x140001000이 28바이트 루프로 니블 스왑 비교:
  `enc[i] == ((c>>4)&0x0f) | ((c<<4)&0xf0)` (.data 0x140003000).
  스왑은 자기 역함수라 동일 연산으로 역산.
- 플래그: DH{Br1ll1ant_bit_dr1bble_<<_>>} → runs/rev-basic-4-cab2188c/ 기록
- 소요: 약 2분

## 2026-08-24 — rev-basic-5 ✅ SOLVED
- challenge_id: rev-basic-5-5f5771ab / chall5.exe
- 방법: `enc[i] == input[i] + input[i+1]` (24바이트). 버퍼 0 초기화 덕에 s[24]=0,
  뒤에서부터 체인 역산 `s[i] = enc[i] - s[i+1]`.
- 플래그: DH{All_l1fe_3nds_w1th_NULL} → runs/rev-basic-5-5f5771ab/

## 2026-08-24 — rev-basic-8 ✅ / rev-basic-9 ✅ (Reversing C2 시작)
- rev-basic-8 (rev-basic-8-9833f03d): `(input[i]*251)&0xff` 비교 → 역수 51로 역산.
  플래그: DH{Did_y0u_brute_force?}
- rev-basic-9 (rev-basic-9-8c2c3702): 8바이트 블록 커스텀 암호(키 I_am_KEY, AES sbox,
  `state=ror8(sbox[state^key]+next,5)` ×128스텝) → 역스텝으로 복호화.
  플래그: DH{Reverse__your__brain_;)}

### 진행 중: reversing-2/3/4 클래스 전체 미해결 풀기
- dungeon-in-1983 (dungeon-in-1983-de95d295): ⚠️ 솔버 완성·로컬 10스테이지 클리어 검증.
  서버 동적 플래그라 원격 접속 필요(워커 네트워크 없음) → runs/dungeon-in-1983-de95d295/solver.py,
  `python3 solver.py <host> <port>`. 스탯→u64 매핑: STR=b0,AGI=b1,VIT=b2,INT=b3,END=b4,DEX=b5,HP=b6..7.
- public(91) ✅: 소형 RSA. n1=65287×65419, d=pow(e,-1,phi), 4바이트 블록 복호화.
  플래그: DH{_RSA_1s_pub1ic-pr1v4te-key_crypt0gr@phy!}
- 나머지 reversing-2 미해결: secret message(235), ezmix(1815), patch(49), Long Sleep(635), randzzz(932), Permpkin(981), My ARX Cipher(1112), power cube(1185), baseball(105)
- reversing-3 미해결: Secure Mail, Testify, Branches and Leaves, photographer, Call more functions, similar, CrabME, Interpret, instrs, Aho, Typing Game Goes Hard, Honest
- reversing-4 미해결: hash-browns, Crossing, Times, bitvm, Slooooow, ptrace_block, Dance in the Light, quilt, Snaky, Vernichtet, carta, Casino-777 (Reversing C1 미해결)
rev-basic-5, rev-basic-6, rev-basic-7, rev-basic-8, Recover, r-xor-t, legacyopt

## 2026-08-24 — reversing-2/3/4 클래스 전체 공략 완료
- 32개 문제 다운로드(runs/_staging/*.zip) → 임포트 → ctf_solve 위임 → 리뷰어 검수 완료.
- 플래그는 모두 로컬(ctf_record_flag)만 기록, 사이트 미제출.

### Reversing C2 — 8/8 solved
ezmix(VM 역산), patch(GDI+ 선분→ASCII 렌더, KH{UPATCHEK}), Long Sleep(변조 SHA-256 재구현),
randzzz(glibc rand 시퀀스 디코딩), Permpkin(swap+XOR 치환 역산),
My ARX Cipher(3라운드 ARX 복호화+재암호화 검증), power cube(x^(3^n) mod 2^64 + SHA256),
baseball(known-plaintext로 커스텀 base64 테이블 복구)

### Reversing C3 — 11 solved / 1 unsolved
Secure Mail(난독화 JS 해제→AES-CBC MD5(YYMMDD) 브루트포스 pw=960229→PNG 플래그),
Branches and Leaves(이진 트리 DFS 경로 복원), photographer(glibc srand(0xbeef) BMP 복호화),
Call more functions(스택 VM XOR 제약 GF(2) 소거), similar(cosine 거리 정렬, 로컬 테스트 플래그),
CrabME(Rust 비트치환+XOR/ADD 역산), Interpret(VM 바이트코드 역산), instrs(VM 프로그래밍 r-al-aen),
Aho(Aho-Corasick DP 유일해), Typing Game(커스텀 MT PRNG 예측), Honest(체인 verify 함수 역산)
- Testify ⚠️ unsolved: 서버 전용 동적 플래그. 솔버 완성·트윈 바이너리로 검증됨.
  runs/testify-4c01a64b/work/extract.py --host HOST --port PORT 로 실행 필요.

### Reversing C4 — 12/12 방법 확정(대부분 실제 플래그 로컬 획득)
hash-browns(3바이트 블록 MD5 preimage), Crossing(격자 인코딩 역파싱→flag.jpg),
Times(ptrace 안티디버그+시간 제한, dword 비트반전), bitvm(VM 제약 브루트포스),
Slooooow(Stooge Sort 등가 정렬→SHA256), ptrace_block(AES 키 공간 축소 브루트포스+LD_PRELOAD 후크 보정),
Dance in the Light(MP3 패딩비트 스테가노그래피, 역방향 DP), quilt(BMP 팔레트 base64 역매핑),
Snaky(25³ 미로 DFS, 로컬 good :)), Vernichtet(Hidato 백트래킹→SHA256),
carta(LFSR 셔플 예측, 로컬 테스트 플래그), Casino-777(CRT 회전 조합, 로컬 잭팟 검증)

### 서버 접속 필요(동적 플래그) 목록
dungeon-in-1983, secret-message(기존 runs 항목), testify, similar/interpret/instrs/aho/
typing-game-goes-hard/carta/casino-777, boss-rush(C5). 로컬은 더미 플래그 — 원격
인스턴스에서 저장된 솔버를 돌려야 실제 플래그 획득. runs/<id>/work|reports 참조.

## 2026-08-24 — Reversing C5 공략 완료
- 12문제 임포트 → ctf_solve 위임 → 리뷰어 검수. 플래그는 모두 로컬(ctf_record_flag)만 기록.

### C5 최종: 9 solved(로컬 플래그) + 1 서버전용 + 2 미해결
✅ solved:
- wasm-rev-for-beginners: WASM 데이터 섹션 직접 파싱, (T-37)*13⁻¹^K
- mamba-dumba: marshal 수동 파서, 3클래스 가감/XOR 시프트 역산
- My_First_Game_v0.1: D3DX 메시 정점/인덱스 → 글리프 래스터라이즈 → 68자 복원
- this-is-not-a-web-challenge: Apache module.so — A^B^C 경로+플래그, CRC 검증
- Function Network: 함수 디스패처(2bit 트리) 역산 + 10000개 ARX 연산 역적용
- Series of Choices: gdb 그래프 덤프 후 DAG 경로 수 mod 2⁶⁴
- Theori of Relativity: .rela.tivity 섹션 재배치 시뮬레이션 → 키 생성 역산
- with my love: Nim — GF(2) 커널 리프팅으로 mod 256 선형시스템(DH{ecf87d8d…})
- so-what: dlopen 체인 그래프 역산. 핵심은 main의 test eax 분기 극성이 반대
  (eax≠0→"Flag is DH{입력}"). LD_DEBUG=libs로 체인 검증.
  리뷰: runs/so-what-2804e745/reports/review.md

⚠️ boss-rush: 방법 확정·로컬 클리어 검증. 서버 동적 플래그(platform_url 없음).
  패스워드: 행순서{0,4,3,1,2} 20비트 마스크 ror20 + 8 XOR 제약쌍 전수 탐색(16개 해).
  입력 트랜스크립트는 runs/boss-rush-fec6187c/reports/writeup.private.md 참조.

❌ weird-forest(researching): 이모지 이진트리 인코딩 복호화. 시뮬레이터 모델은 참 k에서
  바이너리 출력과 100% 일치 확정. 단 XOR 키 k가 실행 환경마다 다름(워커별 상이) 확인 →
  1308토큰=195문자, P(자유도)68 / C(결정적)127. 빔서치 구현들은 샘플 exact 복원 관문
  미통과로 무효. 핵심 기법 ctf_learn 저장 완료. 차기: 같은 워커에서 샘플 검증 후 적용,
  C 127개 결정적 위치 활용 + 단어/플래그 경계 프루닝.

❌ captain-hook(unsolved): PE 난독화·LCG 키스트림 완전 복호화(dec.bin=실제 평문,
  X=17304까지 에뮬 검증). 남음: 최종 모노알파베틱 치환층 — cp949/UTF16/Base64/
  어닐링/사전 DFS 전부 기각. 신규 발견: 7976–8600의 16B 스트라이드 (값,태그) 테이블.
  차기 경로: runs/dreamhack-reversing-c5/captain-hook-44dd5425/work/learn-note.md v2.

### 교훈(C5)
- dlopen 체인 추적엔 lib 숨기기 이분탐색보다 LD_DEBUG=libs가 압도적으로 빠름.
- 성공/실패 분기 조건은 rodata 주소로 직접 확인(so-what 극성 반대 사례).
- 미검증 솔버는 같은 워커에서 샘플 exact 복원부터(weird-forest 낭비 사례).
