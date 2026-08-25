# Learn: Packer 언팩 + XTEA 정적키 + 패킷 핸들러 Unicorn 에뮬레이션

## 문제
L3akCTF Yet Another Chat (x86 PE, 3 sections, EP 0x4438d0). 패커로 sec1(0x401000)이 언팩 영역, pcap은 4바이트 BE 길이 + 16바이트 랜덤 헤더( RC5 키) + XTEA/RC5 이중 암호 페이로드.

## 핵심 기법

### 1. Unicorn 언팩
- PE 헤더 파싱해 `imgbase & ~0xffff` 에 `sizeImg+0x300000` 맵, sec1~sec3 로드.
- `hook_code`로 `0x401000 <= EIP < 0x424000` 첫 진입을 OEP로 간주해 덤프. `invalid-mem` 후킹으로 500k 스텝 후 sec1 덤프해도 strings 노출로 검증.
- 패커의 `call 0x43fxxx` 스택 쿠키 검사는 `E8` 타겟이 `0x401000` 범위 밖이면 NOP 5바이트 패치로 무력화.

### 2. XTEA 정적키 추출
- 패턴 `c7 44 24 XX imm32` 에서 `disp 0x18/0x1c/0x20/0x24` imm이 `eb da 20 75 / de 70 e3 10 / e0 4b 46 7b / 75 8c 6d 04` 4개.
- 함수 내 `be 20 37 ef c6` (mov esi, 0xc6ef3720) 및 `81 c6 47 86 c8 61` (-DELTA) 로 XTEA decrypt 식별 ( BE word 로딩).

### 3. 패킷 핸들러 직접 에뮬레이션 (RC5 재구현 회피)
- XTEA(0x401370/0x401c43)와 RC5 루프가 인라인된 핸들러(0x401144 부근)를 찾아, `packet_buf`, `len`, `out_buf`를 스택에 세팅해 Unicorn으로 직접 호출.
- 파이썬 RC5 재구현 대신 바이너리 로직을 그대로 실행하므로 엔디안/S 인덱스 오류 방지, 1회 실행으로 `L3AK{` 존재 여부 즉시 검증.

### 4. PCAP 재조립
- LINKTYPE_NULL(4바이트) → IP → TCP, `seq` 정렬 후 `>I` 길이 파싱. `tshark -o tcp.desegment_tcp_streams:true` 로 대체 가능.

## 재사용 포인트
- 고엔트로피 PE(>7.9) + EP가 sec2(0x24000)에 있으면 패커 의심, sec1 덤프가 핵심.
- 두 번째 암호가 `P=0xb7e15163` 없이 `rol 3`/`ror`로만 보일 때, 핸들러 인라인 RC5일 확률 높음 → 재구현보다 에뮬레이션이 빠름.
- 헤더 16바이트가 키로 쓰이고 페이로드가 8바이트 배수면 XTEA+RC5 이중 암호 의심.

## 실패 교훈
- `0xc40` vs `0xc43`/`0x370` 오프셋 혼동, `0x4019e0` 단일 패치로 S=0 유지 → 전체 `E8` 패치 필요.

## Provenance

- Challenge ID: `l3ak-ctf-yet-another-chat-302c752d`
- Final status: `researching`
- Solve elapsed: `21718s`
