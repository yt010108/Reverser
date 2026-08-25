# L3ak CTF — Drippy Adventures (rev) 미해결 노트

## 문제
- Unity 게임 리버싱. 제공 아티팩트: `Assembly-CSharp.dll`(95KB, .NET 4.x Mono 어셈블리), `drippy.readme`.
- "Help Drip escape his predicament, and perhaps find some drip along the way!"

## 접근 방법 (도구 없는 환경)
- ilspycmd/mono/dnfile 미설치 → 파이썬으로 ECMA-335 메타데이터 파서 + IL 디스어셈블러 직접 작성.
- 주의점: Constant 테이블 컬럼 순서는 Type(1)+Pad(1)+**Parent(coded)**+Value(blob) — Parent가 먼저다.
- u1b(1바이트+패드) 폭 누락 시 이후 모든 테이블이 어긋난다.

## 분석 결과 (전부 소거)
- #US 215개 문자열 = ldstr 215개와 일치. flag/l3ak 키워드 없음.
- FieldRVA 6개 블롭 = UnitySourceGeneratedAssemblyMonoScriptTypes 데이터.
- IL 242 메서드: Player(이동/카메라/착용), Bowtie/Crown/Shoes/SuitPickup, WaterDeathFogZone,
  WaterReflection, FancyChandelier, Readme — 순수 게임 로직.
- 암호화/Base64/String(char[])/InitializeArray 플래그 패턴 없음. PE 오버레이 없음. ManifestResource 없음.

## 추정 정답 경로
- 게임을 실제로 실행해 특정 조건(모든 drip 수집 또는 은신처 도달) 달성 시 플래그 노출로 추정.
- 씬/에셋이 포함된 원본 빌드가 필요하며, 스크립트 DLL 단독으로는 플래그 복원 불가.

## 재사용 팁
- Unity Assembly-CSharp.dll 분석 시: 1) #US 덤프 2) FieldRVA 블롭 3) Constant 테이블
  4) IL 전수에서 crypto/encoding API grep — 이 네 가지로 플래그 유무를 빠르게 판별 가능.

## Provenance

- Challenge ID: `l3ak-ctf-drippy-adventures-f4f19ab3`
- Final status: `unsolved`
- Solve elapsed: `2027s`
