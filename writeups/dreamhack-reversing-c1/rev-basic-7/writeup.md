# rev-basic-7 (Dreamhack Reversing C1)

## 개요
- 파일: chall7.exe (PE32+ x64, MSVC 릴리즈)

## 분석
검증 함수 (0x140001000), 31바이트(0x1f) 루프 — 비트 회전 + XOR:
```c
int check(char *input) {
    for (int i = 0; i < 0x1f; i++) {
        if ((rol8(input[i], i & 7) ^ i) != enc[i]) return 0;
    }
    return 1;
}
```
- rol al, cl (8비트 좌회전, cl = i & 7) 후 i로 XOR.
- 역산: `input[i] = ror8(enc[i] ^ i, i & 7)`.

## 결과
- 입력값: Roll_the_left!_Roll_the_right! (30자 + NUL)
- verify: True
- 플래그: [FLAG REDACTED] (로컬 기록 완료, 사이트 미제출)
