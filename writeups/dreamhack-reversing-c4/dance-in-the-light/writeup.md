# Dance in the Light — write-up

## 문제
- `main`: ELF 64-bit PIE (stripped). 사용법: `main [input_mp3_file] [output_filename] [flag]`
- `output.mp3`: 인코더가 플래그를 숨겨놓은 MPEG-2 Layer III (32 kbps, mono) 파일.

## 분석

### main (0x1180)
```
for each flag char c:
    for bit_idx in 0..7:            # LSB first
        fcn_1380(fin, fout, (c >> bit_idx) & 1)
남은 프레임 동안 bit=0 으로 계속 호출
```

### fcn_1380 (0x1380) — MP3 프레임 1개 처리
1. 4바이트 헤더 검증: sync(0xFFE..), MPEG version 2/3, Layer III, protection bit=1, bitrate idx != 15, samplerate idx != 3.
2. 테이블:
   - `0x4020`: samplerate [44100, 48000, 32000], MPEG2면 >>1 (22050/24000/16000)
   - `0x4040`: bitrate 테이블, index = `(version^3)*15 + bitrate_idx` → v1/v2 Layer III bitrate(kbps) 나열
3. base_size = samples * bitrate * 125 / sr_adj (MPEG2 samples=576, MPEG1=1152), framesize = base + 원본 padding 비트.
4. body(framesize-4 바이트) 전체를 XOR → fold(x^=x>>4; x^=x>>2; x^=x>>1; &1) = 패리티 p.
5. **p != data_bit 이면 출력 헤더의 padding bit(bit0 of byte2)를 1로 설정** 후 헤더+body 기록.

즉 각 프레임이 `bit = parity(body) XOR declared_padding_bit` 을 1비트씩 운반. 단, encoder는 body를 재구성하지 않으므로 flip 시 선언된 크기(base+1)와 실제 물리 크기(base+원본pad)가 어긋난다.

## 디코딩
1. 물리 프레임 길이는 104 또는 105(base=104, 입력 mp3의 원본 padding에 따라).
2. 역방향 DP로 "다음 헤더가 valid한 체인"을 최대화하는 길이(104/105)를 선택하며 전체 파일(6257프레임, 653793B) 정확히 소진.
3. 각 프레임에서 `bit = parity(전체 body bytes) XOR header_padding_bit`, 문자당 LSB-first 8비트.

## 결과
```
[FLAG REDACTED]
```

검증: 역방향 DP(best[0]=6257)로 6257프레임이 653793바이트 전체를 정확히 소진하며,
플래그 뒤는 0 패딩 비트(출력에서 '.'로 표시)라 깨끗하게 종료된다.

## 교훈
- XOR 루프 범위(`rbx` ~ `rbx+fsz-5`)를 잘못 읽어 마지막 바이트 제외로 오해 → 실제론 body 전체.
- 테이블 인덱스 `rdi = v'*15 + br`를 `br*16 + v'*15`로 오해 (shl/sub/add 조합 재확인 필요).
- decoder가 자기 output을 못 읽는 구조(선언 크기 vs 물리 크기 불일치) → 체인 validity 기반 탐색으로 해결.
