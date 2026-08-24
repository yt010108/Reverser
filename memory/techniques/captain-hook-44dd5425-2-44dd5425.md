# captain-hook-44dd5425 — 검토 결과 (2차 리뷰 정정)

## 결론
- 1차 리뷰(review.md)의 "수정 모델"(K 256엔트리, c%256 랩핑)도 **틀렸다**.
- Ghidra 디컴파일(FUN_140016360) 재독해로 확정한 올바른 모델:

## 올바른 복호화 모델 (정적으로 확정)
1. 0x800(256*8B) 할당들은 전부 **포인터 난독화 셀 배열**이다.
   (`*cell = LCG값*0x30f9d1a13f72 ^ const` 로 채운 뒤 2패스 XOR로 실제 포인터 복원)
   1차 리뷰가 이것을 "키 테이블 256개"로 오독했다.
2. 실제 키스트림 배열은 `alloc(4 * (S>>2))` — NC = S>>2 = 2304 엔트리(풀 프레임 기준).
   매 프레임 시드 슬롯에 0x7a69 저장 후, `while (i < S>>2)` 루프에서
   **advance-then-store**(`k=k*0x10dd mod 0x6fffffff` 먼저, 저장 나중)로 전체를 채운다.
   → K[i] = 시드에서 i+1회 진행한 값.
3. 복호화 루프 (c < S>>2):
   ```
   keyidx   = c % (S>>2)            # 범위 안에서는 == c
   K[keyidx] ^= mix(c)              # mix(c) = 0x5841384F-(c^0x2b), c 홀수면 ~r
   out_dw(c) = dw(c) ^ K[keyidx]    # 갱신된 K 사용
   ```
   누적 없음, 64/256 랩핑 없음. **eff_key(c) = K[c] ^ mix(c)** (c < 2304).
4. 구모델(cum)과 c<64 에서 우연히 일치 → X=0..9 에뮬 검증과 헤더 256B는 유효,
   **byte 256 이후(dec.bin 대부분)는 전부 잘못 복호화된 값**이었다.
   꼬리 문자열 해석 실패의 원인은 인코딩이 아니라 키 모델 오류.

## 다음 실행용 스크립트 (검증 포함)
```python
import struct, re
blob = open('/challenge/input/CaptainHook.exe','rb').read()[0x1e1f0:0x1e1f0+0x2400]
NC = 0x2400//4
k = 0x7a69; Ks = []
for _ in range(NC):
    k = (k*0x10dd) % 0x6fffffff
    Ks.append(k & 0xFFFFFFFF)
def mix(c):
    r = (0x5841384F - (c^0x2b)) & 0xFFFFFFFF
    return (~r)&0xFFFFFFFF if c&1 else r
dw = lambda c: struct.unpack('<I', blob[4*c:4*c+4])[0]
dec = b''.join(struct.pack('<I', dw(c) ^ (Ks[c] ^ mix(c))) for c in range(NC))
print([(m.start(), m.group()) for m in re.finditer(rb'[ -~]{4,}', dec)][:50])
for kw in (b'DH{', b'flag', b'dream'): print(kw, dec.find(kw))
```
- 주의: 1차 리뷰 스크립트의 `K[c%256]`(256 사전계산 후 랩핑)은 c>=256 에서 오답.
  반드시 NC=2304 전체를 생성해 Ks[c]를 직접 쓴다.
- 검증: 새 프로세스에서 emu.run_frame(2000) 니블 vs 모델 니블(dword 250, c>=64라
  신구모델 판별점). 일치하면 모델 확정. run_frame 호출마다 새 프로세스(힘 고갈 방지).
- 참고: 종료 조건은 counter == 0x2400*2 = 18432 (전 니블 표시 후 "End" MessageBox).

## Provenance

- Challenge ID: `captain-hook-44dd5425`
- Final status: `unsolved`
- Solve elapsed: `2917s`
