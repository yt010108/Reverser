# rev-basic-5 (Dreamhack Reversing C1)

## 개요
- 파일: chall5.exe (PE32+ x64, MSVC 릴리즈)

## 분석
검증 함수 (0x140001000), 24바이트 루프 — 인접 두 바이트의 합 비교:
```c
int check(char *input) {
    for (int i = 0; i < 0x18; i++) {
        if ((unsigned char)(input[i] + input[i+1]) != enc[i]) return 0;
    }
    return 1;
}
```
- enc (.data 0x140003000): ad d8 cb cb 9d 97 cb c4 92 a1 d2 d7 d2 d6 a8 a5 dc c7 ad a3 a1 98 4c 00
- 버퍼는 main에서 memset으로 전부 0 → input[24]=0 보장.
- 체인 역산: `s[i+1] = enc[i] - s[i]`, 끝에서부터 `s[i] = enc[i] - s[i+1]` (s[24]=0).

## 풀이 스크립트
```python
enc = bytes.fromhex("add8cbcb9d97cbc492a1d2d7d2d6a8a5dcc7ada3a1984c00")
s = [0]*25
for i in range(23, -1, -1):
    s[i] = (enc[i] - s[i+1]) & 0xff
print(bytes(s[:23]).decode())
```
주의: 검증 시 s에 s[24]=0까지 포함해야 IndexError가 나지 않음.

## 결과
- 입력값: All_l1fe_3nds_w1th_NULL (23자)
- forward 재계산 verify: True
- 플래그: [FLAG REDACTED] (로컬 기록 완료, 사이트 미제출)
