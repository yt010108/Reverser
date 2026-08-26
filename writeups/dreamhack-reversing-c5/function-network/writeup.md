# Function Network — Write-up (Dreamhack Reversing C5)

## 개요
- 바이너리: stripped amd64 PIE ELF (`original/chal`, sha256 10088b59...)
- 입력 64바이트를 받아 "함수 네트워크" 10,000회 변환 후 상수 64바이트와 memcmp.
- 플래그 = 올바른 입력. `[FLAG REDACTED]` 형태.

## 구조 분석 (core / r2, objdump)
1. `main` (0x704f): read(0, buf, 0x41) → 개행 제거 → strlen == 0x40 요구.
   buf를 s2(스택 64B)로 복사 후 i=0..9999 루프:
   - 테이블 `.data:0xb020`의 struct {int64 fn; int64 off1; int64 off2;} (24B × 10000)
   - `dispatch(fn, &s2+off1, &s2+off2)` 호출 → 마지막에 `memcmp(s2, 0x459a0, 0x40)`.
   - .data는 vaddr = fileoff + 0x1000 이므로 테이블/타깃을 파일에서 직접 추출 가능.

2. 디스패치 트리: 진입 0x1209에서 각 노드가 `v & 3`으로 4갈래 선택 후 `v >>= 2`를 재귀 전달.
   깊이 약 32레벨, 총 125개 디스패처 + 4개 리프 연산 함수:
   - 0x6f4c add : tmp=*p+*q; *q=*p; *p=tmp  → Feistel (p', q') = (p+q, p)
   - 0x6f8f xor : 동일 구조, p^q
   - 0x6fd0 sub : p-q
   - 0x7017 swap: 단순 교환
   모두 가역.

## 검증 (dynamic / gdb)
- 리프 4곳에 bp 걸어 실제 실행 시퀀스(op, rsi, rdx) 덤프 후 Python 모델과 대조.
- 디스패처 분기 순서는 **call 명령 주소 순서**(== 실행 순서)가 (v&3)==0,1,2,else.
  (예: 0x6c50은 else 분기가 0x6fd0(sub).)
  단, 이것만 고쳐선 부족했다 — 주소 정렬에서 주소 순서로 바꾼 뒤에도 check:False였고(run #25),
  결정적 원인은 **sub 역변환 공식**: 올바른 inverse는 t=s[q]; s[q]=(t-s[p]) mod 256; s[p]=t.
  이전 버전들의 (s[p]-t)/(s[p]+t) 계열은 단위 roundtrip 테스트(#28)로 걸러냈다.
- 참고: gdb 트레이스 대조(#23)는 9999/10000 op만 수집되고 첫 항목부터 불일치해
  모델 오류로 판단하고 중단했다. 동적 대조보다 "fwd∘bwd == id" 단위 테스트가 더 빠른 검증이었다.
- 최종 증명: 복원 입력을 실제 바이너리에 입력 → "Yes, the flag is [FLAG REDACTED]" 출력(#30).

## 솔버
solve4.py: 테이블/디스패치 그래프 추출(call 명령 주소 순 정렬) → 각 엔트리 리프 op 결정
→ target(0x459a0)에서 역방향 10,000 스텝으로 입력 복원.
검증: (1) 난수 상태 fwd(bwd(x))==x && bwd(fwd(x))==x, (2) fwd(inp)==target,
(3) 실제 바이너리 통과.

복원 입력(=플래그 내용): 64자리 hex 문자열 — `reverser_record_flag`에 저장됨
(공개 문서에는 미포함). 실제 바이너리에 입력 시
"Yes, the flag is [FLAG REDACTED]" 출력으로 검증 완료.

## 산출물
- solver 스크립트는 tool_runs 로그(output/*.log)에 포함 (solve4.py 최종본).
