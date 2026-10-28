# CTF Reverse

Pi와 네트워크 없는 Docker 작업자로 제공된 리버싱 CTF 문제를 분석하는 최소 하네스다. v1은 x86/amd64 Linux ELF와 PE 정적 분석만 지원하며 플래그를 제출하지 않는다. 활성 문제의 공개 풀이는 검색하지 않고, triage 이후 30분이 지나도 미해결일 때만 저장된 로컬 풀이 방법을 검색한다.

## 구조

```text
Reverser/
├── AGENTS.md
├── README.md
├── .pi/                 # /Reverser와 reverser_* 도구
├── code/reverser_harness/    # 가져오기, 분석, 저장, write-up, 메모리
├── docker/              # core, dynamic, ghidra, angr 작업자
├── memory/techniques/   # 승인된 재사용 기법
├── tests/
├── writeups/            # 플래그가 제거된 공개 write-up
└── runs/[EVENT/]<CHALLENGE_ID>/ # 원본과 분석 결과, Git 제외
```

전체 `ctf-skills` 저장소는 복사하지 않는다. 필요한 흐름은 로컬 Pi 스킬에만 두며 참고 원본은 [ljagiello/ctf-skills](https://github.com/ljagiello/ctf-skills)다.

## 실행

### Docker 웹 작업실

Docker Desktop을 켜고 아래처럼 실행한다. 웹의 LLM 설정에서 `ChatGPT OAuth`를 선택하고 `ChatGPT로 로그인`을 누르면 브라우저에서 연결할 수 있다. 기존 Pi 로그인을 쓰려면 `docker/.env.example`을 참고해 `docker/.env`에 `REVERSER_PI_AUTH_SOURCE`를 지정한다. API 키 방식도 모델 설정에서 선택할 수 있다.

```powershell
docker compose -f docker/compose.yaml build core dynamic web
docker compose -f docker/compose.yaml up -d web
```

웹 주소는 [http://127.0.0.1:18880](http://127.0.0.1:18880)이다. 파일과 설명을 등록하고 풀이를 시작하면 정찰 뒤 플래너가 의도를 만들고, 의도별 작업자가 격리 Docker 작업자에서 분석한다. 세션 탭에서 메인 에이전트·플래너·작업자·시스템 기록을 확인하고, 탐색 경로에서 의도·사실·가설·후보를 볼 수 있다. 작업은 일시정지·재개할 수 있고 후보는 별도 검증 실행을 거쳐야 해결로 표시된다. 플래그 자동 제출은 하지 않는다.

`새 작업`에서 공개 문제 URL을 입력하고 `사이트에서 읽기`를 누르면 제목·설명·첨부파일 후보가 채워진다. 내용을 고치고 가져올 파일을 선택한 뒤 문제를 만든다. 로그인이나 자바스크립트가 필요한 페이지는 설명과 파일을 직접 입력한다.

인증 설정과 원본·분석 파일은 기존 `.private/web/`, `runs/`에 남고 Git에서 제외된다. 세션 활동과 작업 상태는 Docker의 `reverser_state` 볼륨에 저장된다. 웹 서버는 로컬 주소에만 열리며 Docker 소켓으로 네트워크 없는 격리 작업자를 띄운다.
ChatGPT OAuth 연결이 만료되면 LLM 설정의 `ChatGPT 다시 연결`을 누른다. 기존 Pi 로그인 방식에 `다시 로그인 필요`가 보이면 호스트 터미널에서 `pi`를 열고 `/login`으로 OpenAI Codex에 다시 로그인한다.

### Pi 터미널

```powershell
cd C:\Users\ytyt\Desktop\security\Reverser
docker compose -f .\docker\compose.yaml build core dynamic
pi
```

Pi에서:

```text
/Reverser
```

Parent Pi는 문제 URL이나 로컬 파일을 가져온 뒤 풀이를 별도 Solver Pi에 위임하고 즉시 다시 명령을 받는다. 플래그 제출과 작업자 네트워크는 없다. 확장 코드를 바꿘으면 실행 중인 Pi에서 `/reload`로 다시 읽는다.

```text
Parent: 가져오기 → Orca Solver: 정찰 → 가설 → 검증 → Write-up
                 ← [Solver] 완료 메시지
                 → 필요할 때 Reviewer 호출
```

`reverser_solve`는 현재 모델과 thinking을 상속한 Solver Pi를 Orca 서브 터미널에서 시작하며 종료를 기다리지 않는다. 첫 Solver는 Parent 오른쪽에, 추가 Solver는 오른쪽 아래로 쌓인다. 마지막 터미널이 닫혔으면 Parent 기준 분할을 한 번 재시도한다.

Solver의 긴 풀이 컨텍스트와 출력은 Parent에 들어오지 않는다. 진행 상태와 결과는 `runs/<CHALLENGE_ID>/`에 남고, 완료 시 Parent의 follow-up 큐에 다음 한 줄만 전달된다.

```text
[Solver] CHALLENGE_ID 완료 · solved
```

### Solver 가설 루프

Solver는 초기 정찰 후 한 번에 하나의 가설만 다룬다. 가설에는 주장, 검사 방법, 반증 조건, 유한한 검사 범위, 정찰 근거 `basis_run`을 기록한다. 이전 가설을 구체화하면 `parent_id`로 연결하고, 반증된 가설 아래에는 새 가설을 만들 수 없다. 가설 제안과 검증에는 상속한 모델과 thinking 설정을 그대로 사용한다.

검증 명령은 활성 `hypothesis_id`를 포함해야 하고, 결과는 `confirmed`, `rejected`, `inconclusive` 중 하나와 실제 run 근거로 마감한다. 마감 후 다음 가설을 세운다. 횟수 제한은 없다.

`progress.md`에 현재 단계, 활성 가설, 검증 run, 종료된 가설 이력을 저장해 사용자가 바로 확인할 수 있다. Solver의 파일 도구는 `reverser_status`가 반환한 `workspace`만 보도록 프롬프트에서 제한한다. 이는 행동 지침이며 강제 샌드박스는 아니다.

30분은 강제 종료 시간이 아니라 로컬 기법을 검색하는 `researching` 단계로 넘어가는 기준이다. `reverser_review`는 완료 메시지 뒤 필요할 때 별도로 호출하며, 풀이 중인 30분 이내 문제는 검토하지 않는다. 쉬운 문제는 메모리에 넣지 않고, 30분 이상 걸렸거나 미해결인 문제의 핵심 기법만 `memory/techniques/`에 저장한다.

### Solver 완료 알림

Solver를 시작하면 문제 폴더의 `solver.json`을 다음처럼 기록한다.

```json
{
  "challenge_id": "CHALLENGE_ID",
  "status": "running",
  "terminal": "ORCA_TERMINAL_ID",
  "result": null
}
```

Write-up 저장이나 미해결 기록이 끝나면 `status`를 `done`으로, `result`를 `solved`, `local_verified`, `unsolved`, `failed` 중 하나로 바꾼다. `local_verified`는 입력·키가 로컬에서 검증됐지만 실제 플래그는 얻지 못한 상태다. JSON은 임시 파일을 원자적으로 교체해 기록한다. Parent는 해당 폴더를 `fs.watch`로 감시한다.

## Playwright 브라우저

Pi 확장은 공식 Node Playwright를 직접 사용한다. 설치는 한 번만 하면 된다.

```powershell
$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD="1"
npm install
```

Pi의 `reverser_browser`에는 Playwright의 `page`와 `context`가 그대로 전달된다. 별도 브라우저 헬퍼는 없다.

```javascript
await page.goto("https://ctf.example/challenges");
return await page.locator("body").innerText();
```

클릭, 입력, 새 탭, 네트워크 응답, 스크린샷, 다운로드 등 Playwright API를 그대로 사용할 수 있다. 브라우저는 Pi 실행 중 계속 열려 있고 세션은 `.private/playwright-profile/`에 저장된다. 로그인 화면이면 열린 브라우저에서 사용자가 직접 로그인한 뒤 Pi에게 계속하라고 하면 된다.

```javascript
await page.getByRole("link", { name: "Reversing" }).click();
return await page.locator("body").innerText();
```

다운로드 파일은 `.private/browser-downloads/`에 저장하고 `reverser_import_local`로 가져온다.

```javascript
const [download] = await Promise.all([
  page.waitForEvent("download"),
  page.getByText("다운로드").click(),
]);
const path = `${downloadsDir}/${download.suggestedFilename()}`;
await download.saveAs(path);
return path;
```

반드시 `waitForEvent`와 클릭을 같이 기다린다. `reverser_browser`는 이렇게 `await`된 오류를 도구 오류로 반환한다.

## 작업자

| 이미지 | 역할 | 실행 여부 |
|---|---|---|
| `core` | file, strings, binutils, radare2, LIEF/Capstone | 정적 분석 |
| `dynamic` | GDB, strace, ltrace, Frida | Linux ELF 실행 |
| `ghidra` | headless 디컴파일 | 정적 분석 |
| `angr` | 심볼릭 실행 | 필요할 때만 |

`core`, `dynamic`부터 빌드하고 용량이 큰 `ghidra`, `angr`는 필요할 때 따로 빌드한다.

이미지는 이 프로젝트 전용 `local/yt010108-reverser-*` 태그를 쓴다. `doctor`의 `core_ready`가 false이면 core를 다시 빌드한다. 이전의 `local/reverser-core:0.1` 태그는 다른 프로젝트 이미지와 겹쳐 `reverser-triage: command not found`를 일으킬 수 있다.

```powershell
docker compose -f .\docker\compose.yaml build ghidra
docker compose -f .\docker\compose.yaml build angr
```

Ghidra는 매번 전체 함수를 디컴파일하지 않는다. 먼저 `core`의 radare2로 관심 함수나 주소를 좁힌 다음 Ghidra 작업자에서 다음과 같이 실행한다.

```bash
reverser-ghidra /challenge/input/chall /challenge/output/decompile.c main check_flag 0x401230
```

첫 호출은 분석 프로젝트를 `/challenge/work/ghidra-project/`에 저장하고, 다음 호출부터는 분석을 다시 하지 않고 그 프로젝트를 재사용한다. 함수를 생략하면 `main`/entry 계열만 우선 출력하며, `--all`은 전체 함수가 필요할 때만 사용한다.

## 문제 결과

```text
runs/[EVENT/]<CHALLENGE_ID>/
├── progress.md
├── solver.json
├── original/
├── work/
├── output/
└── reports/
```

event가 있으면 문제는 `runs/<EVENT>/<CHALLENGE_ID>/`, 없으면 `runs/<CHALLENGE_ID>/`에 저장한다. `progress.md`에 상태와 경과시간, 실행 기록, 가설 이력을 함께 저장한다. 새 결과와 비공개 write-up은 `runs/`에만 남는다. 기존 `writeups/`는 과거 공개본이다.

`reverser_record_flag`는 실제 플래그면 `kind=flag`, 로컬에서만 확인한 입력·키면 `kind=local_solution`을 요구한다. 둘 다 성공한 `evidence_run`에 연결되지만 후자는 `solved`가 되지 않는다. Reviewer는 완료된 문제에서도 `reverser_review_exec`으로 격리 재검증을 실행할 수 있다.

## 직접 CLI

```powershell
$env:PYTHONPATH="$PWD\code"
py -3 -m reverser_harness.cli doctor
py -3 -m reverser_harness.cli import-local --title rev1 --file C:\Downloads\rev1
py -3 -m reverser_harness.cli list
py -3 -m reverser_harness.cli status CHALLENGE_ID
py -3 -m reverser_harness.cli hypothesis CHALLENGE_ID propose --basis-run 1 --claim "..." --test "..." --falsifier "..." --exhaustion "..."
py -3 -m reverser_harness.cli exec CHALLENGE_ID --profile core --command "..." --hypothesis h1
py -3 -m reverser_harness.cli hypothesis CHALLENGE_ID resolve --hypothesis-id h1 --outcome rejected --evidence-run 2 --observation "..."
py -3 -m reverser_harness.cli flag CHALLENGE_ID --value "..." --evidence-run 3 --kind local_solution
py -3 -m reverser_harness.cli review-exec CHALLENGE_ID --profile dynamic --command "..."
py -3 -m reverser_harness.cli solution-search CHALLENGE_ID "xor validation loop"
```

## 테스트

```powershell
$env:PYTHONPATH="$PWD\code"
py -3 -m unittest discover -s tests -v
docker compose -f .\docker\compose.yaml config --quiet
```
