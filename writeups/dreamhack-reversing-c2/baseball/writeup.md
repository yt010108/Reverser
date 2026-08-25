# baseball — Dreamhack Reversing C2

## 개요
- 파일: `baseball` (ELF x86-64 PIE, stripped), `text_in.txt`, `text_out.txt`, `flag_out.txt`
- 사용법 문자열: `Usage : ./baseball <table filename> <input filename>`

## 분석
`main` (0x154d):
1. 테이블 파일을 열어 크기가 정확히 0x40(64)바이트인지 검사("Invalid table") 후 전역 버퍼 0x4040에 64바이트 로드 → 커스텀 base64 치환 테이블.
2. 입력 파일을 읽어 `fcn.00001289(buf, len)` 호출, 결과를 `%s`로 출력.

`fcn.00001289`: 표준 base64 인코더와 비트 연산이 동일하되, 각 6비트 값의 문자 조회를 `table[0x4040]`에서 수행. 패딩은 `'='`. 즉 **커스텀 알파벳 base64**.

테이블 파일은 미제공 → known-plaintext 공격으로 복구.

## 풀이
1. `text_in.txt`(149 bytes)를 표준 base64로 인코딩 (200 chars, 패딩 1개).
2. `text_out.txt`와 위치별 대응: `table[std_index(std_b64[i])] = text_out[i]`.
3. 64개 중 53개 인덱스가 복구됨 (충돌 없음). 미매핑 인덱스: 0,3,10,14,31,40,42,49,58,59,62.
4. 복구된 알파벳으로 `flag_out.txt` 디코딩 → 플래그 문구 획득.
5. 검증: 후보 평문을 표준 base64 인코딩 후, 매핑된 모든 테이블 항목과 암호문이 일치함을 확인.

## 결과
- flag_out 평문: `[FLAG REDACTED]`
- 상태: solved (플래그는 ctf_record_flag로 로컬 기록만 함)

## 검증 노트 (reviewer)
flag_out 암호문 중 위치 13(A, idx 0), 15·37(D, idx 3), 29(+, idx 62)은 복구되지 않은
테이블 슬롯을 사용하지만, 기본 디코딩 결과가 이 바이트들(9–11 "now", 22 "4", 27–28 "ks")을
포함해 완전한 영어로 나온다는 점이 결정적이다. 참값이 달랐다면 해당 바이트들이 깨져
문장이 성립하지 않으므로, 읽을 수 있는 디코딩 결과가 유일하게 일관된 해석이다.
추가로 매핑된 53개 슬롯 전수와의 순방향 일치 검증(verify.py)도 통과했다.
