# rev-basic-8 (Dreamhack Reversing C1)

## 개요
- 파일: chall8.exe (PE32+ x64, MSVC 릴리즈)

## 분석
검증 함수 (0x140001000), 21바이트(0x15) 루프 — 모듈러 곱셈:
```c
int check(char *input) {
    for (int i = 0; i < 0x15; i++) {
        if ((input[i] * 0xfb) & 0xff != enc[i]) return 0;
    }
    return 1;
}
```
- 역산: 251의 mod 256 역수는 51 (`251*51 = 12801 ≡ 1 (mod 256)`).
- `input[i] = (enc[i] * 51) & 0xff`

## 결과
- 입력값: Did_y0u_brute_force? (20자 + NUL)
- verify: True
- 플래그: [FLAG REDACTED] (로컬 기록 완료, 사이트 미제출)
