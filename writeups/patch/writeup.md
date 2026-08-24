# patch — Dreamhack Reversing C2 (patch-08db38ac)

## 개요
- 파일: `Patch.exe` (PE32+ GUI, x64, 117,760 bytes)
- GDI+(`GdipDrawLineI`)만 사용해 WM_PAINT에서 선분들을 그리는 프로그램.
- 플래그는 화면에 텍스트로 그려지지 않고, 선분 좌표 하드코딩으로 렌더링됨.

## 구조
- `FUN_140002c40` (WM_PAINT 핸들러)가 다음을 호출:
  - `FUN_140002b80(g, ?, y1, x2, y2, color)` — 래퍼: (150, y1) → (x2, y2) 선 25개(좌측 방사형 노이즈/장식).
  - 글리프 함수 10종이 x 오프셋(param_2)과 y 기준(param_3=0x5a=90)을 받아 문자를 구성하는 선분들을 그림.

## 접근
1. triage strings에서 GDI+ 임포트 확인.
2. r2/radare2 + Ghidra 디컴파일로 각 함수의 `GdipDrawLineI(g, pen, x1, y1)` 호출과 스택 인자(x2=[rsp+0x20], y2=[rsp+0x28])를 추출.
   - Ghidra 출력에서 `local_XX`(XX가 큰 쪽 = 낮은 주소 = x2, 작은 쪽 = y2) 매핑 확인.
3. 파서로 전체 71개 호출의 좌표 복원 후 ASCII 그리드에 렌더링.
4. 래퍼 선분(x1==150)을 제외하고 글리프만 렌더링하면 문자가 읽힘.

## 복원된 문자 (x 순서)
x=40 K | 80 H | 115 } | 160 U | 200 P | 240 A | 280 T | 320 C | 360 H | 400 E | 440 K | 480 {

브레이스는 작성자가 좌우 반전으로 그려 넣었음(중간 팁 방향 확인). 정규화하면:

**플래그: [FLAG REDACTED]**

참고(대안 해석): 리터럴 나열은 `KH}[FLAG REDACTED]` 가능성도 있으나 중간 팁 방향상 `{`가 맞음.

## 산출물
- Ghidra 디컴파일: `/challenge/work/OUT2`
- 좌표 추출/렌더 스크립트 및 로그: `output/0017~0031-*` (runs 내부)
