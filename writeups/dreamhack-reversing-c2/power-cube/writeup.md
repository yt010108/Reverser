# power cube (Dreamhack Reversing C2)

## 개요
- `chall`: stripped amd64 PIE ELF, OpenSSL libcrypto SHA256 사용.
- 플래그 형식: `[FLAG REDACTED]` (SHA256 hex 64자).

## 분석
`main` (@0x1288):
1. 카운터(i)를 0으로 초기화하고, `i <= 0x456beefcafebabd` 동안 `fcn.00001259`를 호출(총 `0x456beefcafebabd + 1 = 0x456beefcafebabe`회).
2. `fcn.00001259` (@0x1259): 전역 `qword [0x4010]`(초기값 `0xdeadbeefdeadbeef`)을 세제곱해 다시 저장 — `x = x*x*x mod 2^64`.
3. 루프 종료 후 `SHA256(&x, 8, out)` — 리틀엔디안 8바이트 최종값 해시.
4. `fcn.000011a9`가 32바이트 다이제스트를 hex 문자열로 변환해 `printf("... [FLAG REDACTED]\n", hex)`.

즉 실제 계산은 `v = 0xdeadbeefdeadbeef`, `0x456beefcafebabe`번 반복 세제곱 → `SHA256(v.to_bytes(8,'little'))`.

## 풀이
- 원본은 루프가 약 4.95e18회라 직접 실행 불가 → 수학으로 치환.
- v는 홀수이므로 gcd(v, 2^64)=1, Carmichael λ(2^64)=2^62. 지수를 `e = pow(3, n, 2^62)`로 줄인 뒤 `v = pow(x0, e, 2^64)`.

```python
import hashlib
M = 1 << 64
n = 0x456beefcafebabe
e = pow(3, n, 1 << 62)
v = pow(0xdeadbeefdeadbeef, e, M)
print('[FLAG REDACTED]' % hashlib.sha256(v.to_bytes(8, 'little')).hexdigest())
```

## 검증
- dynamic 워커에서 루프 한계 상수(파일 오프셋 0x12be의 LE immediate)를 9로 패치해 10회 반복 버전을 실행.
- 실행 결과와 "10회 반복 세제곱 후 SHA256" 에뮬레이션 출력이 정확히 일치하는 것을 확인 → 알고리즘 해석 검증 완료.

## 결과
- 플래그: `ctf_record_flag`로 기록 완료 (본 문서에는 미포함).
- 상태: solved
