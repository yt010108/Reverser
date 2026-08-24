# Progress

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
