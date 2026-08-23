---
description: 리버싱 CTF 문제를 가져와 격리 환경에서 풀이한다
---

사용자에게 문제 URL 또는 로컬 파일을 묻고 문제 하나를 가져온다. URL은 `ctf_browser`에서 일반 Playwright JavaScript의 `page`와 `context`를 직접 사용해 탐색·클릭·입력·스크롤·다운로드한다. 로그인 화면이면 열린 브라우저에서 사용자가 직접 로그인한 뒤 계속한다. 다운로드한 문제를 `ctf_import_local`로 가져오고 `ctf_triage` 직후 승인 없이 바로 풀이한다. 최초 30분은 풀이 방법을 검색하지 않고 필요한 최소 Docker 작업자만 사용한다. `ctf_status`의 `research_due`가 true인데도 미해결이면 `ctf_solution_search`와 Playwright 공개 Write-up 조사로 전환한다. 플래그는 로컬에만 기록하고 제출하지 않는다. 해결 여부와 관계없이 Write-up을 남기고, 30분 이상 걸렸거나 미해결인 문제만 `ctf_learn`으로 풀이 방법을 저장한다.

입력: `${ARGUMENTS:-제공되지 않음}`
