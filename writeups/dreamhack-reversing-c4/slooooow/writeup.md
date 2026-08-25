# Slooooow (Dreamhack Reversing C4) — write-up

## 대상
- `original/main`: stripped amd64 PIE ELF, OpenSSL 3 (`EVP_sha256`, `EVP_Digest*`) 링크.

## 분석
- `main` (0x1594): setvbuf 초기화 → 배너 출력 → 정렬 함수 `f(0, 99999)` (0x138b) → 해시 함수 (0x14a9).
- 배열: `.data` vaddr 0x4020 (파일 오프셋 0x3020), 크기 0x61a80 = 400,000 바이트 = `uint32_t[100000]`.
- 비교 함수 (0x1313): 32비트 키 변환 후 unsigned 비교.
  - `K(a) = (a<<22) | ((a<<6)&0x3f0000) | ((a>>9)&0xff80) | (a>>25)`
  - 입력 비트 24는 무시되고 결과 비트 15는 항상 0 (비단사, 충돌 가능).
- 정렬 함수 `f(i,j)` (0x138b):
  - `if K(A[i]) > K(A[j]) swap`
  - `m = (j-i+1)/3` — 매직 넘버 0x55555556 = 3으로 나누는 코드 (처음엔 /2로 착각).
  - 재귀 `f(i,j-m); f(i+m,j); f(i,j-m)` → 전형적인 Stooge Sort.
  - T(n)=3T(2n/3)+O(1)=Θ(n^2.71), n=100k면 직접 실행 불가 ("master theorem" 배너가 힌트).
  - 실제로 dynamic 워커에서 7200초 실행해도 완료되지 않음을 확인.

## 풀이
Stooge Sort는 올바른 정렬이므로 최종 상태는 "K 기준 오름차순 정렬"과 동일.
- 데이터의 100,000개 값에 대해 K 중복이 0개 → 동률 처리 모호성 없음.
- 소규모 슬라이스(길이 ~150)로 정확한 Stooge 시뮬레이션을 수행해 key 정렬 결과와 일치함을 검증.
- Python으로 `arr.sort(key=K)` 후 `sha256(struct.pack('<100000I', ...))` 계산.

## 플래그
`[FLAG REDACTED]`
