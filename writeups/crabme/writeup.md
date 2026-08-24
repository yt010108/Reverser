# CrabME (Dreamhack Reversing C3)

## 개요
- Rust(크랩)로 작성된 64비트 PIE ELF, not stripped.
- 핵심 함수: `chal::main`(0x7dc0), `chal::flagchecker`(0x8030), `chal::hex_to_u32_vec`(0x7cc0).

## 로직
1. stdin에서 한 줄을 읽고 trim 후 길이가 정확히 64여야 하며, 모든 문자가 `[a-f0-9]`여야 한다.
2. `hex_to_u32_vec`: 64개의 hex 문자를 2글자씩 잘라 u32(radix 16) 32개로 변환.
3. `flagchecker`:
   - `.rodata` 0x49000에 32개의 u32 기대값 테이블.
   - 각 입력 값 v(≤0xff)에 대해 아래 변환 결과가 테이블과 일치해야 함:

     ```
     G = ((((v>>1)&1) | ((v<<3)&8)) + (v&4)*4)
         | ((v>>2)&2) | ((v<<3)&0x80);
     G = (G + (v&0x20)*2) | ((v>>4)&4) | ((v>>2)&0x20);
     out = ((G ^ 0x63) + 0x22) & 0xff
     ```

   - 덧셈 항들이 OR 비트와 서로 겹치지 않아 전체는 바이트 단위 비트 치환
     (in b0..b7 → out: b1,b3,b6,b0,b2,b7,b5,b4) 후 XOR 0x63, ADD 0x22.

## 풀이
- 테이블 128바이트를 파일 오프셋 0x49000에서 읽어 0..255 브루트포스로 역산.
- 각 위치마다 유일한 해가 나옴 → 입력 hex 문자열 확정.
- 동적 실행으로 검증: `🦀 input: Correct! flag is [FLAG REDACTED]` 출력 확인.

## 플래그
`[FLAG REDACTED]`

- 입력 hex 문자열이 곧 플래그 본문. 바이너리가 직접 `🦀 input: Correct! flag is [FLAG REDACTED]`로 출력해 동적으로 확정.

## 산출물
- output/ghidra.txt : 주요 함수 디컴파일
- output/0011-dynamic.stdout.log : 검증 실행 결과(xxd)
