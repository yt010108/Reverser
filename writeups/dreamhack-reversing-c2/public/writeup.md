# public (Dreamhack Reversing C2)

## 개요
- public: Linux x64 ELF (RSA 암호화), out.txt(공개키), out.bin(암호문) 제공

## 분석
- n.txt에서 두 시드를 읽어 PRNG(fcn.12fe)로 p, q 생성 (p·q > 0xfcfcfcfc까지 반복)
- n1 = p*q, n2 = gcd(e, (p-1)(q-1))==1인 최소 e
- 플래그 4바이트씩 u32 블록으로 읽어 `c = pow(m, e, n1)` → u64 LE로 out.bin에 기록

## 풀이
- n1 = 4271010253 = 65287 × 65419 (trial division)
- phi = (p-1)(q-1), d = pow(201326609, -1, phi)
- 각 8바이트 LE 값 c에 대해 m = pow(c, d, n1) → 4바이트 LE 조립

## 결과
- 플래그: [FLAG REDACTED] (로컬 기록 완료, 사이트 미제출)
