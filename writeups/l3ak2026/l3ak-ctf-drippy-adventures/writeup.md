# Write-up (private) — L3ak CTF Drippy Adventures

**상태: 미해결 (플래그 미획득)**

## 요약
L3akCTF 2026 rev. Unity 게임의 `Assembly-CSharp.dll`(.NET 4.x, PE32)만 제공됨.
"Help Drip escape his predicament, and perhaps find some drip along the way!"

## 분석
- 환경에 .NET 디컴파일러가 없어 자체 ECMA-335 파서/IL 디스어셈블러를 작성해 전체 메타데이터와 242개 메서드 IL을 덤프.
- 확인 영역: #Strings/#US 힙, FieldRVA 정적 블롭(Unity MonoScriptTypes 메타데이터), Constant 테이블,
  전체 IL(Player/Pickup/FogZone/Chandelier 클래스), PE 오버레이·리소스·ManifestResource.
- 결과: 플래그 문자열·암호화 루틴·인코딩된 데이터 전무. 모든 코드는 순수 게임 로직(이동, 카메라, 의상 수집, 물 안개 사망 존 등).

## 결론
플래그는 게임 빌드 실행 중(전체 drip 수집 또는 숨겨진 장소 도달 등)에 노출되는 것으로 추정.
씬/에셋이 없는 스크립트 DLL 단독으로는 정적으로 복원 불가 → v1 정적 분석 범위에서 해결 불가로 종료.

## FLAG
(미획득)
