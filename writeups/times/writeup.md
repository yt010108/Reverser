# Times (Dreamhack Reversing C4) — Write-up

## Triage
- `times`: ELF 64-bit PIE, x86-64, stripped, Full RELRO / canary / NX.
- Strings: "Not yet !!! Please wait more time.", "%s [registration code]", "Registration done !", "Registration failed.."

## Analysis
`.init_array`의 `_INIT_1` (0x17d0):
1. `time(0) < 0x71ca7800`이면 "Not yet !!!" 출력 후 exit — 2030년까지 실행 불가인 시간 제한.
2. `ptrace(PTRACE_TRACEME)` 결과 ret에 대해 `DAT_00104048 ^= ((short)ret + 1) * 0x4d2`.
   - 정상 실행: ret=0 → XOR 0x4d2 → 파일값 0x4d2가 0으로 변함(디버거 사용 시 키가 틀어짐).

`main` (argv[1] = registration code, 길이 n):
1. seed=time(0), srand, k=rand()+rand() → `fcn_13ad(k,4,buf16)` = **MD5**(커스텀 구현, K/시프트 테이블은 .rodata) → 16바이트 키스트림 ks.
2. 루프 A: i=0..n-1, `s[i] ^= ks[4i&15]; s[i] ^= ks[(4i+1)&15]; ...` — 실질적으로 각 바이트를 ks 전체 16바이트 XOR 값으로 변환.
3. 루프 B: j=0..n/2-1, word[j] ^= DAT_00104048 (정상 실행 시 0).
4. 다시 srand(time(0))로 같은 방식 MD5 키스트림 생성 후 루프 A 반복 → 같은 초 안이면 **자기 취소(XOR involution)**.
5. 루프 D: 각 dword를 `fcn_174a` = **32비트 비트 반전**.
6. `memcmp(s, target@0x4020, 41)`.

## Solve
정상 경로에서는 루프 A+C가 상쇄되고 워드 XOR도 0이므로:
`input = bitreverse32(target의 각 little-endian dword)`

target 41바이트 중 앞 40바이트(10 dwords)를 역변환하면 깔끔한 16진수 ASCII가 나옴:

```
660c4c86a62c1c9c1c661c2c9c6ca6cca66c6caca6a6864c2c46ec8cec468c9c4cecc6664c46864cd2
-> [FLAG REDACTED]
```

## 검증
- 시간 제한만 패치(`jg`→`jmp` at file offset 0x17e8)한 복사본을 격리 워커에서 실행.
- 위 40자 입력 → "Registration done !" 확인, 오염된 입력은 "Registration failed..".

## Flag
`[FLAG REDACTED]`
