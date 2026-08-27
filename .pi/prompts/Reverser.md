---
description: 리버싱 CTF 문제를 가져와 격리 환경에서 풀이한다
---

사용자에게 문제 URL 또는 로컬 파일을 묻고 문제 하나를 가져온다. URL은 부모 Pi의 `reverser_browser`에서 일반 Playwright JavaScript로 탐색·로그인·다운로드한다. 다운로드 이벤트와 클릭은 하나의 `Promise.all`로 기다리고 저장한 절대 경로를 반환한다. 다운로드한 문제를 `reverser_import_local`로 가져온 뒤, 반환된 `challenge_id`를 `reverser_solve`에 한 번만 넘긴다. 부모는 직접 풀거나 Solver를 기다리지 않고 계속 명령을 받는다. Solver가 끝나면 `[Solver] <challenge_id> 완료 · <result>`가 follow-up 큐에 들어온다. 그때 필요한 경우에만 `reverser_status`나 `reverser_review`를 호출한다. 실제 플래그는 표시하거나 사이트에 제출하지 마라.

입력: `${ARGUMENTS:-제공되지 않음}`
