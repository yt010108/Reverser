# rev-basic-3 (Dreamhack Reversing C1)

## 개요
- 파일: chall3.exe (PE32+ x64 콘솔, 11KB, MSVC 릴리즈 빌드)
- 입력을 받아 Correct/Wrong을 출력하는 전형적인 basic 시리즈.

## 분석
`main` (0x140001120):
1. `printf("Input : ")`
2. `scanf("%256s", buf)` — buf는 0x100바이트 스택 버퍼
3. 검증 함수 0x140001000(buf) 호출, 반환값이 1이면 Correct

검증 함수 (0x140001000) 의사코드:
```c
int check(char *input) {
    for (int i = 0; i < 0x18; i++) {          // 24바이트 (NUL 포함)
        if (enc[i] != (unsigned char)(input[i] ^ i) + 2 * i)
            return 0;
    }
    return 1;
}
```
- `enc`는 .data 섹션 0x140003000에 위치한 상수 배열.
- enc[23] = 0x45 → input[23]은 NUL이어야 하므로 정답 문자열 길이는 23.

역산: `input[i] = ((enc[i] - 2*i) & 0xff) ^ i`

## 데이터
enc = 49 60 67 74 63 67 42 66 80 78 69 69 7b 99 6d 88 68 94 9f 8d 4d a5 9d 45

## 풀이 스크립트
```python
enc = bytes.fromhex("4960677463674266807869697b996d8868949f8d4da59d45")
flag = bytes(((enc[i] - 2*i) & 0xff) ^ i for i in range(24))
print(flag.decode())
```

## 결과
- 입력값: I_am_X0_xo_Xor_eXcit1ng
- 플래그: [FLAG REDACTED] (로컬 기록 완료, 사이트 미제출)
