# GDI+ 선분 그리기 플래그 복원 (patch 유형)

## 신호
- strings에서 `GdipDrawLineI`, `GdipCreatePen1` 임포트 + BeginPaint/EndPaint → 플래그가 선분 좌표 하드코딩으로 렌더링됨.
- WM_PAINT 핸들러가 글리프 함수들(x 오프셋, y 기준을 파라미터로 받음)과 래퍼를 호출.

## 핵심 기법
1. **r2 레지스터 슬루싱은 PE x64에서 불안정** — `pdfj`로 mov/lea/add 추적 시 Ghidra가 var_sp/arg 명명을 제멋대로 바꿔 실패율 높음. 곧바로 `reverser-ghidra <bin> <out> <함수주소...>`로 디컴파일하고 C 출력을 파싱할 것.
2. Ghidra 출력 파싱 요령:
   - 단순 대입(`var = 상수/식`)을 env로 수집, `param_2`=x오프셋/`param_3`=y기준으로 치환 후 eval.
   - `GdipDrawLineI(g, pen, x1, y1)` 호출 직전 stack args(local_XX/uStack_XX, 주소 내림차순 = x2, y2)를 페어링.
   - **함정**: `iVar3 = GdipDrawLineI(...)`의 반환값(status code)을 좌표 변수로 env에 넣지 말 것. `if (iVar3 != 0)` 패턴으로 구별 가능.
3. 전체 선분을 ASCII 그리드에 렌더링(문자 폭:세로 ≈ 2:1로 y를 2줄마다 출력). 장식/노이즈 선분(예: 고정 x=150에서 시작하는 방사형 선)은 필터.
4. 글자가 뒤집힌 중괄호 `{`/`}`로 나오면 팁(중간 돌기) 방향으로 실제 문자 판정 후 정규화.

## 적용 예
- Dreamhack Reversing "patch": WM_PAINT에서 12개 글리프 + 래퍼 선 25개 → 렌더 결과 플래그 복원.

## Provenance

- Challenge ID: `patch-08db38ac`
- Final status: `solved`
- Solve elapsed: `1980s`
