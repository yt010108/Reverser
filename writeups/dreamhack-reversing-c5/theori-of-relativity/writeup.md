# Theori of Relativity — Write-up (Dreamhack Reversing C5)

## 개요
- 파일: `relativity` (x86-64 PIE ELF, stripped, Full RELRO)
- 핵심 트릭: **커스텀 relocation 섹션 `.rela.tivity`가 런타임에 자기 자신을 패치**하며
  `.data`에 검증용 키 문자열을 동적으로 생성한다.

## 구조 분석

### 1) 로더가 `.rela.tivity`를 처리한다
`DT_RELA = 0x628`, `DT_RELASZ = 9864` → `.rela.dyn`(11개) + `.rela.tivity`(400개) = 411 엔트리 전부를
ld.so가 순서대로 처리한다. 즉 `.rela.tivity`는 장식이 아니라 실제로 적용되는 relocation이다.

### 2) self-patching 체인
`.rela.tivity`의 PC32 relocation들은 오프셋이 **테이블 자신(0x730~0x2ca8) 내부**를 가리킨다.
4엔트리 = 1그룹 × 100그룹이며, 각 그룹은 뒤쪽의 아직 처리 전인 `R_X86_64_NONE` 엔트리의 3개 필드를 덮어써
새로운 활성 PC32 reloc으로 변신시킨다:

```
entry[3].r_offset ← 0x6020   entry[3].type ← PC32   entry[3].addend ← 0x6054
→ ld.so가 entry[3]을 처리할 때: mem[0x6020] = 0x6054 - 0x6020 = 0x34 (키 첫 바이트!)
```

다음 그룹은 `mem[0x6021]`, `mem[0x6022]` … 순서로 4바이트씩 겹쳐 쓰면서
한 바이트씩 키 문자열을 만들고, 마지막 write의 상위 3바이트 0이 NUL 종료를 담당한다.
결과: 0x6020에 64바이트 키가 생성된다.

정적 디스어셈블리만 보면 `.data`의 `whp_O3+%...`(더미)가 키처럼 보이므로,
파일에 있는 값을 그대로 쓰면 절대 통과하지 못한다.

### 3) init_array 반디버깅
- `init_array = [frame_dummy, f1@0x3189, f2@0x31d9]`
- `f1`: `ptrace(PTRACE_TRACEME)` 실패(추적 중)면 `key[0] += 1`, 정상이면 `-1`.
- `f2`: 세 함수(func1/func2/checker) 본문을 첫 RET까지 스캔해 `byte + 0x34 == 0`
  (즉 0xCC int3)를 발견하면 `key[0] += 2` 후 즉시 종료(최종 보정 생략).
  끝까지 못 찾으면 루프 탈출 후 `key[0] -= 2` 실행(0x3272–0x327c, 단 한 번).
  → **정상 실행 net -2**, BP 설치 시 net +2. (초기 풀이의 "net 0"은 오류 —
  0004 디스어셈블리상 `83 e8 02` 한 번뿐이며 0x3189–0x3383 범위에 0xCC 바이트 없음)
- "Congrats! Flag is [FLAG REDACTED] ...if you didn't cheat!" — 정상 실행(-1, -2)일 때만 올바른 키가 만들어진다.

### 4) 검증 함수 (0x3298)
`check(key_ptr=0x6020, input)`:
```
for j = 0.. :
    e = (j*j + key[j]) & 0xff
    if e == 0: require popcnt(input[j]) == 0 (둘 다 NUL에서 종료)
    elif j 홀수: popcnt(input[j] ^ e) == 0  → input[j] == e
    else:       popcnt(input[j] - e) == 0  → input[j] == e (mod 256)
```
즉 정답 입력 = `(j*j + key[j]) & 0xff` (e==0까지).

## 풀이
ld.so 재현 시뮬레이션: 메모리 이미지 위에서 411개 reloc을 순서대로 적용(중간에 패치된
엔트리 필드를 다시 읽음), 이후 정상 실행 init 효과 `key[0] -= 1`(f1, 비추적) 및
`key[0] -= 2`(f2, BP 미발견)를 적용하고 마지막으로 디코딩.

> **검토 정정(reviewer)**: 초기 풀이는 f2를 net 0으로 잘못 가정해 첫 문자를 '3'(0x33)으로
> 복원했다. 디스어셈블리 재검증 결과 정상 실행 f2는 -2를 적용하므로 키[0] = 0x34−1−2 =
> 0x31('1')이며, 체커(i=0 짝수 분기 popcnt(e−c))도 '1'만 통과한다('3'은 0xfe≠0으로 실패).
> 격리 워커 실행 검증은 세션 게이트로 불가하여 정적 분석으로 확정.

```python
for i in range(9864//24):
    off, info, add = 현재 메모리에서 엔트리 읽기
    if info&0xffffffff == 2: mem[off:off+4] = (add-off)&0xffffffff
mem[0x6020] -= 1
flag_input = bytes((j*j+k)&0xff for j,k in enumerate(key) until k_j makes 0)
```

생성된 키 64바이트(key[0]=0x31) → 입력:
`1d459fbdd85803e8223c2a11604dac728aceaffbc454aedce56b1a8d4e063360`

## 플래그
`[FLAG REDACTED]` (로컬 기록 완료, 미제출)

※ 초기 기록값 `[FLAG REDACTED]`은 f2 순효과 오분석(net 0 가정)으로 인한 오답 후보였음.

## 아티팩트
- 시뮬레이션 스크립트/로그: `output/0008-core.stdout.log` (tool_runs #8)
