# ezmix — Dreamhack Reversing C2 (solved)

## 아티팩트
- `main`: stripped amd64 ELF PIE (VM 인터프리터)
- `program.bin` (514B): VM 바이트코드, 2바이트 명령어 (opcode, operand) 257개
- `output.bin` (36B): 플래그를 program.bin 으로 암호화한 결과

## 분석
- `main`: argv[1] 파일을 0x400 바이트 읽어 `fcn.136c(buf, size, out)` 호출 후 결과를 argv[2]에 기록.
- `fcn.136c` (VM 루프): i를 2씩 증가시키며 op=prog[i], imm=prog[i+1]
  - op 1/2/3 → `fcn.1301(func, imm, buf, len)`
  - op 4 → "Insert your string: " 출력 후 fgets로 입력받아 len 저장
  - 그 외 → "Error!" 후 exit(1)
- `fcn.1301(func, c, buf, len)`: 모든 바이트에 `buf[j] = func(buf[j], c)` 적용
- 연산 함수:
  - 0x1289: `(x + c) & 0xff` (ADD)
  - 0x12a7: `x ^ c` (XOR)
  - 0x12c2: `((x >> c) | (x << (8-c))) & 0xff`, c&7 (ROR)

## 풀이
output.bin에 프로그램 연산을 역순으로 역적용: ADD→SUB, XOR→XOR, ROR→ROL.

```python
for o,p in reversed(ops):
    for j in range(len(data)):
        if o==1: data[j]=(data[j]-p)&0xff
        elif o==2: data[j]^=p
        else: data[j]=rol(data[j],p)
```

## 결과
플래그 획득 (36바이트, output.bin 길이와 일치). 값은 Git-ignored 상태에만 기록됨 (`ctf_record_flag`).
