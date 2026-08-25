# rev-basic-6 (Dreamhack Reversing C1)

## 개요
- 파일: chall6.exe (PE32+ x64, MSVC 릴리즈)

## 분석
검증 함수 (0x140001000), 18바이트 루프 — S박스 치환 비교:
```c
int check(char *input) {
    for (int i = 0; i < 0x12; i++) {
        if (sbox[(unsigned char)input[i]] != enc[i]) return 0;
    }
    return 1;
}
```
- sbox: .data 0x140003020, 256바이트 — AES S-box (63 7c 77 7b f2 ... 로 시작)
- enc: .data 0x140003000, 18바이트

역산: `input[i] = inv_sbox[enc[i]]` (S-box 역테이블 생성 후 조회)

## 결과
- 입력값: Replac3_the_w0rld (17자 + NUL)
- verify: True
- 플래그: [FLAG REDACTED] (로컬 기록 완료, 사이트 미제출)
