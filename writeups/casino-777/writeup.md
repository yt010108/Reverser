# Casino-777 (Dreamhack Reversing C4) — casino-777-da203cdd

## 상태
- 결론: 풀이 검증 완료(로컬). 잭팟 조건 달성 시 프로그램이 `flag` 파일을 읽어 출력.
- 바이너리: stripped amd64 ELF PIE, Full RELRO/Canary/NX.
- 실제 플래그 값은 서버 측 `flag` 파일에 있으며 로컬 마운트에는 없음 → 더미 플래그로 읽기까지 확인.

## 프로그램 로직
- 메뉴 1 (generate, 0x1337): 슬롯 10개 생성. 각 길이 = 0x4080 dword 배열값+1 = {73,83,89,97,103,79,101,127,131,137} (모두 서로소). 94자 charset에서 랜덤 채움. 슬롯에 '7'이 없으면 랜덤 위치 하나를 강제로 '7'로 → 모든 슬롯은 '7'을 최소 1개 포함.
- 메뉴 2 (rotate, 0x14c4): long long n 입력. 각 슬롯을 buf[(s+j)%len]=data[j] 방식(오른쪽 s칸 회전, s = n mod len)으로 회전하고 memcpy로 되돌림 → 누적 회전 합이 유지됨. 회전 후 10개 슬롯의 첫 글자가 모두 '7'이면 잭팟 → open("flag") 후 read/puts.
- 주의: n은 %lld로 받지만 div는 unsigned 64비트 → 유효값 u = n의 2의보수 비트패턴 (scanf 범위 [-2^63,2^63) 전체 커버).

## 풀이 (시간 기반 CRT)
1. u=1로 반복 회전하며 전역 스텝 t에서 각 슬롯 표시 문자 관찰. 슬롯 i는 t ≡ τ (mod mᵢ)일 때 obs[i][τ] 표시.
2. 최대 137스텝이면 모든 슬롯의 전체 주기 내용 관찰 완료. '7'이 나오는 시간 잔여집합 Tᵢ 확보.
3. CRT(모듈러 서로소, M = ∏mᵢ ≈ 9.8e19 > 2^64): 조합 DFS로 t* ∈ (t_cur, 2^62) 해 탐색. 평균 |Tᵢ|≈1.7이라 조합 수백 개 → 대부분 세대에서 해 존재. 없으면 메뉴 1로 재생성.
4. 마지막 회전 v = t* - t_cur 전송 → 모든 슬롯 첫 글자 '7' → 잭팟 → flag 출력.

## 구현 노트
- 자식 프로세스 stdout 파이프는 os.read(fd, 4096) bulk read 필수. byte-by-byte read(1)은 하네스에서 극단적으로 느려 타임아웃처럼 보임.
- 프롬프트 "> "는 scanf 이전에 출력되므로 동기화는 "Result:" 기준으로.
- 검증 스크립트: /tmp/solve.py (worker는 일회용, 미산출). 재현은 위 알고리즘대로.

## 산출물
- output/0019-dynamic.stdout.log: 로컬 잭팟 성공 로그 (attempt 1 ok=True).
