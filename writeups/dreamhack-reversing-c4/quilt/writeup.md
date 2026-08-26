# quilt — Dreamhack Reversing C4 (SOLVED)

## 아티팩트
- `quilt` : x86-64 ELF PIE, stripped
- `quilt.bmp` : 512x512 24bit BMP (플래그가 인코딩된 결과물)

## 분석 요약
`main`(0x12e9):
1. 192바이트(0xc0)를 `/dev/urandom`에서 읽고, 추가로 1바이트 시드를 읽는다.
2. `buf[seed % (0xc0 - strlen(argv[1]))]` 위치에 argv[1](플래그)을 strncpy → 플래그가 랜덤 버퍼 임의 위치에 삽입됨.
3. `enc(0x167e)` : 3바이트(b0<<16|b1<<8|b2) → 6비트 4개(base64와 동일한 비트 분해, 알파벳 없이 값 자체 사용) = 256개의 6비트 값.
4. `render(0x17a3)` : 16x16 타일 그리드, 각 타일은 32x32px 단색. 6비트 값이 `.rodata 0x2020`의 64색 팔레트(3바이트 RGB ×64) 인덱스. 홀수 타일 행(row)은 좌우 반전(`col -> 15-col`)으로 배치. BMP는 아래->위 순서로 기록.

## 복호화
1. 팔레트: ELF 파일 오프셋 0x2020에서 192바이트(64색).
2. BMP에서 각 32x32 타일 중심 색상을 추출해 팔레트 인덱스(=6비트 값)로 역매핑.
3. BMP 하단 업(row order) 보정(fy = H-1-y), 홀수 타일 행은 열 반전 해제.
4. 6비트 4개씩 묶어 24비트 재조립 → 원본 192바이트 복원 → 플래그 문자열 검출.

주의: 초판 디코더에서 (j,idx) 쌍을 전역 정렬해 행 경계가 섞여 garbage가 나왔음. 행 단위 배치가 정답.

## 스크립트
```python
import struct
elf=open('quilt','rb').read()
pal=[tuple(elf[0x2020+i*3:0x2020+i*3+3]) for i in range(64)]
bmp=open('quilt.bmp','rb').read()
off=struct.unpack('<I',bmp[10:14])[0]; W,H=struct.unpack('<ii',bmp[18:26]); rs=W*3
def px(x,y):
    o=off+(H-1-y)*rs+x*3
    return tuple(bmp[o:o+3])
six=[0]*256
for br in range(16):
    for c in range(16):
        idx=pal.index(px(c*32+16,br*32+16))
        j=(15-c) if br%2 else c
        six[br*16+j]=idx
data=bytearray()
for k in range(0,256,4):
    u=six[k]<<18|six[k+1]<<12|six[k+2]<<6|six[k+3]
    data+=bytes([(u>>16)&0xff,(u>>8)&0xff,u&0xff])
```

## 플래그
[FLAG REDACTED] — `reverser_record_flag`에 기록됨 (공개 write-up에는 미포함)
