---
description: 리버싱 CTF 문제를 가져와 격리 환경에서 풀이한다
---

사용자에게 문제 URL 또는 로컬 파일을 묻고 문제 하나를 가져온다. URL은 부모 Pi의 `ctf_browser`에서 일반 Playwright JavaScript로 탐색·로그인·다운로드한다. 다운로드 이벤트와 클릭은 하나의 `Promise.all`로 기다리고 저장한 절대 경로를 반환한다. 다운로드한 문제를 `ctf_import_local`로 가져온 뒤, 반환된 `challenge_id`를 `ctf_solve`에 한 번만 넘긴다. 부모는 직접 풀이하거나 중간 `ctf_status`를 컨텍스트로 가져오지 않는다. `ctf_solve`는 별도 Pi 프로세스의 Solver에게 triage부터 Write-up까지 위임한다. 미해결·30분 초과 상태일 때만 또 다른 새 Pi 컨텍스트의 Reviewer를 자동 실행한다. 부모에게는 실제 플래그가 없는 Solver와 Reviewer의 짧은 요약만 반환된다. 활성 문제의 공개 풀이는 검색하지 않고 사이트에 플래그를 제출하지 마라.

입력: `${ARGUMENTS:-제공되지 않음}`
