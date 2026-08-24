# so what (Dreamhack Reversing C5) — private write-up

## Flag (검증됨)
```
[FLAG REDACTED]
```
입력(=플래그 본문): `20654ccdb7c43bd1ab398283f9895ac285e8c419c4c157db2f3f50de92599bd8`

## 구조
- `main`: 64자 hex 입력 검증 → `dlopen("lib/start.so")` → `dlsym(start, "f_"+input[0])` 호출, 인자 `input+1`.
- 각 lib의 `f_X`는: 자신의 dlopen 타깃 lib을 열고, `*ptr` 문자로 `dlsym(f_<char>)`, `ptr+1`로 재귀 호출. eax는 그대로 전파.
- 리프 함수는 `mov $0/1,%eax` 상수 반환. 리프-0 319개, **리프-1은 (`lib/219f2e3164.so`,`f_8`) 단 하나**.
- **분기 극성**: `test %eax,%eax; je → "Wrong!"`, eax!=0 → `printf("Flag is [FLAG REDACTED]", input)`.
  따라서 정답 = 64단계 후 정확히 리프-1에서 끝나는 경로.

## 풀이 절차
1. objdump로 각 lib의 f_X별 dlopen 문자열 파싱 → 그래프 (lib, f_char) → next-lib.
2. forward DP S[i] (레벨 i에서 도달 가능한 lib 집합, i≥2부터 20개로 수렴). 219f2e3164가 S[63]에 존재 확인.
3. backward prev[] 체인으로 c62..c0 복원, c63='8' 고정.
4. `./main` 실행 → "Flag is [FLAG REDACTED]" 확인.

## 시행착오 (솔버 세션)
- 초기 솔버는 eax==0을 성공으로 가정 → 319개 leaf-0 후보 전부 실패.
- main 디스어셈블리에서 je 타깃(146a)이 "Wrong!" 문자열(0x2081)임을 rodata 덤프와 대조해 극성 오류 확정.
- LD_DEBUG=libs로 dlopen 순서 일치 확인 → 모델 자체는 정확했음을 입증.

## 검증 로그
- output/0047: LD_DEBUG 체인 일치
- output/0050: main rodata ("Flag is [FLAG REDACTED]" @0x2071, "Wrong!" @0x2081)
- output/0056: 최종 입력 실행 성공
