# BrunnerCTF 2026 — KPWhy (rev, Easy-Medium)

## 개요
`kpiman`은 44바이트(0x2c) 사원 ID를 입력받아 세 단계 검사를 모두 통과하면
"Productivity: 100%"와 함께 프로모션 코드(= 플래그)로 입력값을 그대로 출력한다.

## 분석 (amd64 ELF, not stripped)
- `main`: `fgets` → `strcspn`으로 개행 제거 후 `strlen(buf) == 0x2c(44)` 확인,
  세 함수 결과 합이 3이면 통과.
- `calculateSynergy` (i = 0..14): `buf[i] ^ ((7*i + 42) & 0xff) == kpi_alpha[i]`
- `measureVelocity` (i = 15..29): `buf[i] + buf[i-1] == kpi_beta[i-15]`
  (`kpi_beta`는 int 배열, 앞 구간의 마지막 문자 `buf[14]`가 체인의 시드)
- `assessAlignment` (i = 30..43): `synergy_table[buf[i]] == kpi_gamma[i-30]`
  (256바이트 치환 테이블 역탐색)

데이터 위치: `kpi_alpha` @0x402020, `kpi_beta` @0x402040, `kpi_gamma` @0x402080,
`synergy_table` @0x4020a0 (.rodata).

## 풀이
세 구간 모두 순차적으로 유일하게 복호화된다:
1. `s[i] = alpha[i] ^ ((7*i+42)&0xff)` → "brunner{..."
2. `s[j] = beta[j-15] - s[j-1]` (s[14]='p'에서 시작)
3. 테이블 역탐색: 각 gamma 바이트에 대해 유니크한 원문 문자 존재

`solve.py`로 복구한 ID를 격리 워커에서 실행하여 "Productivity: 100%" 확인.

## 결과
플래그는 상태 기록에만 저장됨(`ctf_record_flag`). 공개 write-up에는 미포함.
형식: `[FLAG REDACTED]`
