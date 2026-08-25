# My_First_Game_v0.1 — Write-up (Dreamhack Reversing C5)

## 요약
- 파일: `WindowsProject1.exe` (PE32+ x64, D3D9/D3DX + DirectInput GUI 게임), `background.png`
- 플래그는 문자열로 존재하지 않고, **68개의 3D 메시 지오메트리가 각각 글자 하나**를 이룬다.
- 게임은 각 메시를 x = 인덱스 위치에 나란히 렌더링하므로, 정적 버텍스 버퍼를 덤프해 레스터화하면 플래그를 읽을 수 있다. 실행 불필요.

## 분석
1. Ghidra 디컴파일 (`FUN_140001000` = WinMain, `FUN_140001900` = 초기화, `FUN_140001520` = 렌더 루프):
   - `D3DXCreateMeshFVF(NumIndices=0x140003520[i], NumVertices=0x140003410[i], FVF=0x142)` 을 68번(0x44) 호출.
   - 버텍스 버퍼 원본: `.data:0x1400068F0`, 인덱스 버퍼: `.data:0x14001AE10`.
   - FVF 0x142 = XYZ | DIFFUSE | TEX1 → 버텍스 24바이트 (float x,y,z; DWORD diffuse; float u,v).
   - 렌더 루프에서 `movd xmm3, ebx`(루프 카운터) → `D3DXMatrixTranslation(m, i, 0, 0)`: 메시 i가 월드 x=i에 그려짐 → **읽기 순서 = 메시 인덱스 순서**.
2. PE 파싱으로 정적 버텍스/인덱스 배열 추출 (RVA→파일 오프셋, ImageBase 0x140000000).
   - 정점 총 3468개, X좌표는 전부 0(평면 글리프), Y/Z는 폰트 아웃라인.
3. 각 메시를 (Y up, Z right) 평면에서 삼각형 래스터화 → ASCII 아트로 글자 판독.
   - 정점 데이터 MD5로 중복 그룹화: 20종 유니크 글리프.
   - 절대 높이(baseline 0 기준)로 대소문자 구분: '{','}'만 h≈0.92, 소문자 o/e/a는 h≈0.57, 나머지 ≈0.73–0.77.

## 글리프 매핑 (대표 메시 인덱스, 총 20종)
0:'D' 1:'H' 2:'{' 3:'7' 4:'d' 5:'3' 6:'2' 7:'4' 8:'0' 9:'5'
10:'f' 11:'b' 12:'8' 14:'o' 16:'6' 28:'9' 34:'e' 36:'a' 47:'1' 67:'}'

- mesh 13은 mesh 4와 동일 글리프('d')의 중복이므로 대표 목록에서 제외.

- 혼동 포인트: mesh4='d'(오른쪽 기둥+왼쪽 bowl), mesh11='b', mesh9='5'(평평한 상단 바), mesh28='9'(아래 꼬리 좌측 컬), mesh16='6'(우상단에서 시작하는 호), mesh36='a'(오른쪽 세로 스트로크 연속성으로 '&'와 구별), mesh47='1'.

## 결과
인덱스 순으로 이어붙이면 68자 플래그(`runs/<id>/work/` 비공개 복사본 및 `output/flag.txt` 참조). 실제 값은 공개 문서에서 제거.

## 산출물
- `/challenge/output/mesh.pkl` — 파싱된 정점/인덱스
- `/challenge/output/flag.txt` — 플래그
- `/challenge/output/ghidra_main.c`, `render_ctx.asm` — 근거
