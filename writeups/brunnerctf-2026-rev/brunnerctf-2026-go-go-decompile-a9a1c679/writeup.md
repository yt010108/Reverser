# BrunnerCTF 2026 — Go Go Decompile (rev)

## 개요
- 바이너리: `go_go_budgetmaster` (Go 1.26.2, amd64 Linux ELF, static, not stripped, debug info 포함)
- 목표: 라이선스 키(플래그) 복구

## 분석
1. `nm`으로 확인하면 `main` 패키지에는 `main.main`(0x4a1f80) 하나만 존재 → 모든 로직이 `main.main`에 인라인됨.
2. Ghidra headless로 `main.main` 디컴파일 (`output/ghidra_main.c`):
   - 프롬프트 출력
   - 하드코딩된 base64 문자열 로드: `&DAT_004cc9e8`, 길이 0x28(40바이트)
   - `bufio.Scanner`로 한 줄 입력
   - `base64.StdEncoding.Decode`로 상수를 디코딩한 뒤 사용자 입력과 길이/내용 비교(`memequal`)
   - 일치 시 "Correct!" 문자열 출력
3. `.rodata`에서 vaddr 0x4cc9e8의 40바이트를 직접 읽어 base64 상수 획득:
   - `YnJ1bm5lcntnMF9kM2MwbXAxbDNkX2cwX2Jycn0=`
   - 디코드 결과가 플래그.

## 검증
격리 dynamic 워커에서 실행:
```
$ echo '<flag>' | ./go_go_budgetmaster
Go Go License? Correct!
This is way better than Excel!
```

## 아티팩트
- `output/ghidra_main.c` — main.main 디컴파일
- `output/0006-core.stdout.log` — 상수 추출/디코드
- `output/0008-dynamic.stdout.log` — Correct! 확인

## 플래그
비공개 write-up 참조 (플래그 값은 이 문서에서 제거됨)
