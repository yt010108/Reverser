# BrunnerCTF 2026 — Decompile (vault)

## 개요
- amd64 Linux ELF (PIE, not stripped), 5문항 온보딩 볼트.
- 각 문항의 정답 비교는 `main`에 하드코딩되어 있고, 마지막에 답을 조합해 플래그를 printf로 출력.

## 풀이
1. Ghidra 디컴파일(`ctf-ghidra ... main ask wrong`)로 `main` 전체 확보. 정답은 모두 `main` 안:
   - Q1 password: strcmp와 `"Pl4nt3xt_p455w0rd_1s_bu551ng"`
   - Q2 staplers: strtol != 0xfef → **4079**
   - Q3 asset tag: strtol != 0x2a → **0x2a**
   - Q4 mug letter: 첫 바이트 == 'B'
   - Q5 budget: 입력*2 == 0x5dc(1500) → **750**
2. 검증 실행 시 컨테이너 glibc 2.36 < 요구 2.38 (`__isoc23_strtol`)이라 로드 실패 → ELF 패치로 해결:
   - `.dynstr`에서 `__isoc23_strtol` → `strtol`로 교체(길이 유지, NUL 패딩)
   - `.gnu.version`에서 해당 심볼 버전 인덱스를 GLIBC_2.2.5 인덱스로 변경
   - `.gnu.version_r`의 GLIBC_2.38 vernaux 엔트리를 기존 GLIBC_2.2.5 엔트리(hash/name)로 복사
3. 패치본 실행: `printf 'Pl4nt3xt_p455w0rd_1s_bu551ng\n0xfef\n0x2a\nB\n750\n' | ./vault`
   → 프로그램이 직접 플래그 출력으로 검증 완료.

## 플래그
`[FLAG REDACTED]` (비공개)

## 산출물
- output/ghidra_main.txt : Ghidra 디컴파일(main/ask/wrong)
- output/0012-dynamic.stdout.log : 검증 실행 로그
