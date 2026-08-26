# L3AK CTF 2026 — "What Who" (rev, amd64)

## 요약
`whatwho`(stripped PIE ELF)는 12바이트 명령어(op,a,b,c,imm64)를 해석하는 자체 VM 인터프리터.
`vault.wwc`에서 암호화된 바이트코드(262 instrs)와 데이터(762B)를 복호화해 실행한다.
6개의 질문에 정답을 입력하면 FLAG 게이트(op 0xe1, mask==0x3f && idx==7)를 통과하고
`WHATWHO_FLAG` 환경변수(또는 서버 값)를 출력한다. nonce(`WHATWHO_NONCE`)마다 Q4~Q6 답이 달라진다.

검증 환경: `WHATWHO_NONCE=0123456789ABCDEF`

## 최종 답변 시퀀스 (nonce=0x0123456789ABCDEF)
1. `slop`
2. `slop_slop_slop!!`
3. `EESSEENNEEEEEESSEESSEESSWWSSEESSWWSSEESSWWWWWWNNWWNNWWSSWWNNWWNNEENNWWNNEEEEEENNEESSSSWWWWSSEEEEEENNNN`
4. `2347727620915961940`
5. `0f1b54eadb90271e`
6. `cc5e42fcde3381f38fd61e51578ff02e`

실제 바이너리에서 `[answer 1..6 accepted]` → `Both faces agree. Here is your flag: <FLAG>` 확인.

## vault 복호화
헤더: count=262 instrs @0x40, dlen=762, key=@0x18.
키스트림: x = splitmix-like(((i+1)*C1 ^ key ^ magic)); magic 코드=`_VEICARDI`, 데이터=`V_LEDGER`.
plain[i] = (rotl8(c^xorval, r) - s) & 0xff, r=((i*3)+magic_lo+key_lo)&7,
s=(i*29+(magic>>8)+(key>>16))&0xff.

## VM 구조
- 레지스터 페이스(face 0)와 스택 페이스(face 1), op 0x0c/0xfa로 전환(SWITCH는 sp==0일 때만).
- 주요 함정: op **0xa7은 face0에서 MOVri(R[a]=imm)** — NOP이 아님. Q3 시작값(r1=0 인덱스, r2=18 시작 위치)을 여기서 설정.
- LDINSTSEED(0xca) = NONCE 그대로(accept 후에도 불변!). LDSEED(0x31)는 별도 progseed(nonce 유도값; nonce=0x0123...ABCDEF일 때 0xce5c709b68ba4897).
- S_ROTL(0x97) = **64비트** rotate-left(shift&63). S_ROL8(0xd5)만 8비트.
- UNPACK(0xa3) = BE64, PACK(0x75) = LE64.

## 각 문제
1. **Q1**: 32비트 체크섬 역산 → `slop`.
2. **Q2**: 바이트 단위 체인 역산(D1..D4 테이블, t=((m^r2)+D1)&0xff 형태의 순방향을 거꾸로) → `slop_slop_slop!!`. 최종 r2=0x90.
3. **Q3 미로**: 입력 102글자 전부 이동(N=-17,E=+1,S=+17,W=-1), 시작 위치 18(MOVri로 설정!), 목표 0x60,
   셀 데이터 d[0x129+p]==1만 통과, 정확히 102보. DP로 경로 산출.
4. **Q4**: splitmix64류 PRNG 137회 반복 후 결과와 일치하는 십진수 → 에뮬레이터가 계산.
5. **Q5**: 같은 PRNG 변형 → 16 hex.
6. **Q6 Feistel**: 16바이트 hex 입력을 BE64 hi/lo로 분해, 10라운드:
   F_i = rotl64((lo^T1_i)+instseed, sh_i) ^ (lo*T2_i) + progseed^(i*0xc2b2ae3d27d4eb4f)
   new_hi=lo, new_lo=hi^F. 최종 hi==r2, lo==r3 검사.
   T1@d+0x250+8i, T2@d+0x2a0+8i(LE64), sh=d[0x2f0+i].
   **역산 시 F(i, 현재 hi)** 를 사용해야 함(현재 hi == 이전 라운드의 lo).

## 디버깅 포인트
- gdb 루프 헤드 BP(base+0x1ed0): pc=rsp+0x6748, face=rsp+0x6750, regs=rsp+0x38, vmstack=rsp+0x78,
  sp=rsp+0x678, mem=rsp+0x680(데이터 @mem+0x2000). BP는 명령 실행 **전** 상태를 보여줌.
- 스택 중간값 덤프(pc 210/215/224/232)로 ROTL이 64비트임과 곱셈 상수 0xc2b2ae3d27d4eb4f를 확정.

## 도구
`output/solve.py` — vault 복호화 + 완전 VM 에뮬레이터 + 온더플라이 답변 생성.
`output/answers.txt` — 위 6개 답변.
