# photographer (Dreamhack Reversing C3)

## 개요
- `prob`: stripped amd64 C++ PIE ELF. `flag.bmp`를 읽어 바이트 단위 변형 후 `flag.bmp.enc`로 저장.
- `flag.bmp.enc`: 6,220,854 bytes (원본과 동일 크기).

## 분석
`main`(0x24fb):
1. `srand(0xbeef)` — 시드가 고정이므로 rand 시퀀스 완전 결정론적.
2. `flag.bmp` 전체를 `ifstream` + `istreambuf_iterator`로 `vector<char>`에 적재.
3. 각 바이트 `i`에 대해 `i % 3` 스위치 (바이트당 `rand()` 정확히 1회 호출):
   - case 0: `enc = rol8((ror8(b,7) + rand()) & 0xff, 4)`
   - case 1: `enc = ror8(b, rand() % 8)`
   - case 2: `enc = ((rand() ^ b) - 0x18) & 0xff`
4. 결과를 `flag.bmp.enc`에 write.

보조 함수:
- `fcn.0x2489(x, n)`: ROR8 — `(x >> n) | (x << (8-n))`
- `fcn.0x24c2(x, n)`: ROL8 — `(x << n) | (x >> (8-n))`

## 풀이
glibc `rand()` TYPE_3(가법적 피드백)를 Python으로 재구현(시드 0xbeef, 344 엔트리 초기화 후 출력 시작, `r[i] = r[i-31] + r[i-3]`, 출력은 `>> 1`). 같은 시퀀스를 사용해 역연산:

- case 0: `b = rol8((ror8(enc,4) - rand()) & 0xff, 7)`
- case 1: `b = rol8(enc, rand() % 8)`
- case 2: `b = ((enc + 0x18) & 0xff) ^ rand()`

검증: 복호화 결과 첫 바이트 `BM`, `bfSize == 6220854`로 정상 BMP.

## 주의점
- glibc rand 초기화에서 인덱스 34~343 채움 구간을 출력으로 반환하면 시퀀스가 어긋남(첫 시도 실패 원인). 채움 후 인덱스 344부터 출력.
- 워커는 매 실행 새 컨테이너라 `/tmp` 파일이 유지되지 않음 — 스크립트는 한 명령 안에서 실행.

## 결과
BMP 이미지에 플래그가 렌더링되어 있음. 플래그는 상태에 기록함(`reverser_record_flag`).
