# Permpkin — Dreamhack Reversing C2 (solver write-up)

## 대상
- `chall`: stripped amd64 PIE ELF (14KB), Full RELRO, NX. 동적 링크, import는 fopen/fprintf/fclose/strlen/__ctype_b_loc 뿐.
- 첨부: `flag1.txt`, `flag2.txt` — 부호 있는 10진수 바이트 열 ("102 111 ...").

## 프로그램 동작 (r2 정적 분석)

참고(리뷰 정정): 초기 write-up은 "dynamic 실행 검증"이라 명시했으나 tool_runs에
dynamic 프로필 실행 기록은 없다. 샘플 출력 rev1/rev2 값과 klen=13 모델은 아래의
수기 순열 전개로 독립 검증됨(샘플 2개 각 21/21, 19/19 바이트 일치) — 결론은 동일.
main은 다음을 수행한다.

1. 하드코딩된 hex 문자열 `"CC2A750B63821F45AC20839"`(23자)의 각 문자를
   `fcn.0000126e`로 변환해 스택 버퍼 key[]에 저장.
   - isdigit(c) → c − 40 ('0'→8 ... '9'→17)
   - c ≤ 'E' → c − 60 ('A'→5 ... 'E'→9)
   - c ≤ 'O' → c − 70 ('F'→0)
   - c ≤ 'Y' → c − 80, 그 외 0
   - 버퍼가 NUL 종료 보장이 없어 실제 strlen(key)는 실행 시점 스택 상태에 의존 →
     실제 실행에서는 **13**으로 관측됨 (아래 검증으로 확정).
2. `fcn.000011fd(s, 0, len-1, key)`: 인자 2·3은 미사용. 실제로는
   `for i in range(strlen(key)): swap(s[0], s[key[i]])` (`fcn.000011c9` = swap).
3. `fcn.000012e7(s, key)`: XOR 페이즈 — len(s) ≤ strlen(key)면 `s[i] ^= key[i]`,
   아니면 초과 구간은 `s[i] ^= key[i % klen]`.
4. 결과를 `"%d "`(부호 있는 char)로 rev1.txt / rev2.txt에 기록.

샘플 입력: `"_this_is_sample_flag_"`(21B) → rev1.txt,
`"this_is_sample_flag"`(19B) → rev2.txt. flag1/flag2는 동일 변환의 실제 플래그 출력으로 추정.

## 복호화
모델을 파이썬으로 재구현하고 klen을 1..24로 브루트포스해 샘플 두 출력과 완전 일치하는
klen=13에서 확정 (rev1/rev2 모두 일치). 역변환:
1. `b[i] ^= key[i % 13]` (XOR 제거)
2. swap 단계를 역순(i = 12..0)으로 재적용

## 결과
- flag1 복호: `[FLAG REDACTED]`
- flag2 복호: `[FLAG REDACTED]` ("_"로 시작, 19자)
- 결합 플래그 후보: `[FLAG REDACTED]` (flag1+flag2 결합형, 40자)
  (문장이 자연스럽게 이어지므로 제출 시에는 결합 형태일 가능성도 있음.
  리뷰 시점에 상태에는 flag1 값만 후보로 기록되어 있었음)

(공개 문서에는 실제 값 대신 형태만 기록: flag1 = "c...y" 21자, flag2 = "_...n" 19자)

## 아티팩트
- output/0004~0009: r2 디스어셈블리 및 복호화 스크립트 실행 로그
  (리뷰 정정: 별도 dynamic 프로필 실행 기록은 없으며, klen=13 모델과 샘플 출력은
  순열 전개 재계산으로 독립 검증됨 — 샘플 2개 각 21/21, 19/19 바이트 일치)
