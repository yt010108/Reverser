# rev-basic-4 (Dreamhack Reversing C1)

## 개요
- 파일: chall4.exe (PE32+ x64 콘솔, MSVC 릴리즈)
- rev-basic-3과 동일한 골격, 검증 변환만 다름.

## 분석
검증 함수 (0x140001000), 28바이트(0x1c) 루프:
```c
int check(char *input) {
    for (int i = 0; i < 0x1c; i++) {
        unsigned char t = ((input[i] >> 4) & 0x0f) | ((input[i] << 4) & 0xf0); // 니블 스왑
        if (enc[i] != t) return 0;
    }
    return 1;
}
```
- enc는 .data 0x140003000: `24 27 13 c6 c6 13 16 e6 47 f5 26 96 47 f5 46 27 13 26 26 c6 56 f5 c3 c3 f5 e3 e3 00`
- 니블 스왑은 자기 역함수 → 역산도 동일 연산.

## 풀이 스크립트
```python
enc = bytes.fromhex("242713c6c61316e647f5269647f54627132626c656f5c3c3f5e3e300")
out = bytes((((c & 0x0f) << 4) | (c >> 4)) for c in enc)
print(out.decode())
```

## 결과
- 입력값: Br1ll1ant_bit_dr1bble_<<_>> (27자 + NUL, forward 검증 통과)
- 플래그: [FLAG REDACTED] (로컬 기록 완료, 사이트 미제출)
