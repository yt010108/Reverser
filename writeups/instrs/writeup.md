# instrs (Dreamhack Reversing C3)

## 개요
- ELF 64-bit PIE, stripped, amd64 (`original/prob`, sha256 93977887...)
- 문자열: "Enter Your Program", "Result: %d", "./flag", "Good, get the flag: %s", "No Hack!", "Machine Time Ended"

## 분석
### main (0x151d)
1. `read(0, 0x4050, 8)` — 사용자 프로그램 8바이트 (VM 명령어)
2. `memset(0x4060, 0, 8)` — 테이프 8셀 초기화, 포인터 p(0x4070)=0, PC(0x406c)=0
3. VM 실행 함수 `fcn.0000136d` 호출 → 반환값이 `0x1869f`(99999) 초과면 `./flag` 읽어 출력

### VM (fcn.0000136d)
- 상태: prog[8]@0x4050, tape[8]@0x4060 (byte 셀), ptr p@dword 0x4070 (0..7 clamp), pc@dword 0x406c (0..7 clamp)
- 매 스텝 counter(var_8h)++ 하고 `prog[pc]` 실행:
  - `'+'`: tape[p]++, `'-'`: tape[p]--
  - `'a'`: tape[p] != 0 이면 pc=0 으로 점프(PC 자동증가 생략)
  - `'l'`: p-- (음수면 0), `'r'`: p++ (7 초과면 7)
  - `'e'`: 종료, 지금까지의 스텝 수 반환
  - 그 외(`b,c,d,f,g,h,i,j,k,m` 등): "No Hack!" 후 exit(-1)
- 명령 실행 후 pc++ (pc>7이면 7 유지 → 무한루프 주의, alarm(5)에 걸림)

## 풀이
스텝 수를 99999 넘기면서 `'e'`로 정상 종료하는 중첩 루프 구성.
셀은 byte라 0에서 `-` 하면 255가 되고 256회 후 다시 0으로 wrap됨을 이용.

```
PC0 'r' : p=1
PC1 '-' : cell1--
PC2 'a' : cell1 != 0 -> PC0   (내부 루프 256회 x 3스텝 = 768)
PC3 'l' : p=0
PC4 '-' : cell0--
PC5 'a' : cell0 != 0 -> PC0   (외부 루프 256회, 매번 내부 루프 재실행)
PC6 'e' : 종료
PC7 'n'
```

프로그램 입력: `r-al-aen`
실측 결과: `Result: 196624` → 플래그 출력 확인 (로컬 더미 flag 파일로 검증).

## 아티팩트
- 검증 로그: runs/instrs-38315461/output/0008-dynamic.stdout.log

## 플래그
서버 접속 정보가 없어 로컬 더미 플래그로 검증만 수행. 실제 제출 답안은 입력 프로그램 **r-al-aen** (플래그는 서버에서 위 프로그램 입력 시 출력).
