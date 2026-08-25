# dungeon-in-1983 (Dreamhack Reversing C2)

## 개요
- prob: Linux x64 PIE (stripped), 10스테이지 몬스터 게임, Timeout 5s
- 서버에서 동적으로 플래그 출력 (`./flag` 읽음) → 실제 플래그는 원격 접속 필요

## 분석
- 각 스테이지마다 /dev/urandom에서 8바이트 읽어 몬스터 struct(이름 16B + u64 값)에 저장
- fcn.138d: `[INFO] HP, STR, AGI, VIT, INT, END, DEX` 출력. printf 인자 매핑:
  - HP = bytes[6..7] (u16 LE), STR=b0, AGI=b1, VIT=b2, INT=b3, END=b4, DEX=b5
  - → 출력된 스탯으로 목표 u64 값 완전 복원 가능
- fcn.1407 (스펠 검증): 문자열을 숫자로 변환
  - 'A': acc += 1 (연속 A면 exit), 'B': acc <<= 1, 시작은 반드시 A
  - 최종 acc가 몬스터의 랜덤 u64와 같으면 승리 (qword 비교)
- 10스테이지 클리어 시 ./flag 내용 출력

## 풀이
그리디 역산으로 스펠 생성: v>1 동안 짝수→'B'(v/=2), 홀수→'A'(v-=1), 앞에 'A' 붙임.
이 형태는 시작 A + 연속 A 없음 조건을 자동 만족.

solver.py 실행 결과 (로컬, 더미 flag): STAGE 10 클리어 후 플래그 출력 확인.
원격: `python3 solver.py <host> <port>` (워커 네트워크 제한으로 로컬 검증만 수행)

## 상태
- 솔버 완성 및 로컬 검증 통과. 실제 플래그는 Dreamhack 서버에서 획득 필요.
