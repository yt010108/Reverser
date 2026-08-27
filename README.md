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
└── runs/[EVENT/]<CHALLENGE_ID>/ # 원본과 분석 결과, Git 제외
```

전체 `ctf-skills` 저장소는 복사하지 않는다. 필요한 흐름은 로컬 Pi 스킬에만 두며 참고 원본은 [ljagiello/ctf-skills](https://github.com/ljagiello/ctf-skills)다.

## 실행

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
Parent: 가져오기 → Orca Solver: entry 정찰 → flag 후보 → 가설 트리 → 검증 → flag 저장
                 ← [Solver] 완료
                 → Orca Reviewer: 근거 검토 → Write-up
                 ← [Reviewer] 완료
```

`reverser_solve`는 현재 모델과 thinking을 상속한 Solver Pi를 Orca 서브 터미널에서 시작하며 종료를 기다리지 않는다. 첫 Solver는 Parent 오른쪽에, 추가 Solver는 오른쪽 아래로 쌓인다. 마지막 터미널이 닫혔으면 Parent 기준 분할을 한 번 재시도한다.

Solver의 긴 풀이 컨텍스트와 출력은 Parent에 들어오지 않는다. 플래그와 근거 run을 저장하고 종료하면 같은 Orca 터미널에서 새 컨텍스트의 Reviewer가 자동으로 시작된다. Parent에는 각 단계의 완료 메시지만 전달된다.

```text
[Solver] CHALLENGE_ID 완료 · solved
[Reviewer] CHALLENGE_ID 완료 · writeup.md
```

### Solver 가설 루프

Solver는 가설 없이 entry point에서 main 계열 함수까지 먼저 분석하고, 입력·비교·성공 경로에서 flag 검증 또는 생성 후보를 `recon`에 기록한다. 이후 후보 하나를 target으로 골라 한 번에 하나의 가설만 검증한다. 가설에는 주장, 검사 방법, 반증 조건, 유한한 검사 범위를 기록한다. 가설을 세운 모델과 검증 모델을 교체하며, 검증 모델은 확장에서 교체할 수 있다. 현재 기본값은 Luna다.

가설은 `parent_id`로 트리를 이룬다. 확인되거나 불확실한 가설을 구체화할 때는 child, 대안은 sibling으로 두며 rejected 노드 아래에는 child를 만들 수 없다. 검증 명령은 활성 `hypothesis_id`를 포함해야 하고, 결과는 `confirmed`, `rejected`, `inconclusive` 중 하나와 실제 run 근거로 마감한다.

`progress.md`에 recon, flag 후보, 가설 트리와 검증 run을 저장해 사용자가 바로 확인할 수 있다. Solver의 파일 도구는 `reverser_status`가 반환한 `workspace`만 보도록 프롬프트에서 제한한다. 이는 행동 지침이며 강제 샌드박스는 아니다.

30분은 강제 종료 시간이 아니라 로컬 기법을 검색하는 `researching` 단계로 넘어가는 기준이다. Reviewer는 풀이 중에 개입하지 않고 `solved`, `unsolved`, `failed` 후에만 실행된다. 쉬운 문제는 메모리에 넣지 않고, 30분 이상 걸렸거나 미해결인 문제의 핵심 기법만 `memory/techniques/`에 저장한다.

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

플래그 저장이나 미해결 기록이 끝나면 `solver.json`을 `done`으로 바꾼다. Reviewer도 같은 형식의 `reviewer.json`을 사용한다. Parent는 두 JSON을 `fs.watch`로 감시하므로 주기적인 조회를 하지 않는다.

### 로컬 목록

`reverser_list`는 Parent가 바로 읽을 수 있게 `project`, `events`, `challenges`를 하나의 JSON 객체로 반환한다.

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
├── reviewer.json
├── original/
├── work/
├── output/
└── reports/
```

event가 있으면 문제는 `runs/<EVENT>/<CHALLENGE_ID>/`, 없으면 `runs/<CHALLENGE_ID>/`에 저장한다. 실제 플래그, 실행 로그, 가설 이력, Reviewer Write-up을 포함한 모든 문제 결과는 Git에서 제외된 `runs/`에만 남는다.

## 직접 CLI

```powershell
$env:PYTHONPATH="$PWD\code"
py -3 -m reverser_harness.cli doctor
py -3 -m reverser_harness.cli import-local --title rev1 --file C:\Downloads\rev1
py -3 -m reverser_harness.cli list
py -3 -m reverser_harness.cli status CHALLENGE_ID
py -3 -m reverser_harness.cli recon CHALLENGE_ID --entry-point "0x401000" --main "0x401120" --evidence-run 2 --candidates-json '[{"target":"check_flag","reason":"success 경로 직전 호출","evidence_runs":[2]}]'
py -3 -m reverser_harness.cli hypothesis CHALLENGE_ID propose --target "check_flag" --claim "..." --test "..." --falsifier "..." --exhaustion "..."
py -3 -m reverser_harness.cli exec CHALLENGE_ID --profile core --command "..." --hypothesis h1
py -3 -m reverser_harness.cli hypothesis CHALLENGE_ID resolve --hypothesis-id h1 --outcome rejected --evidence-run 1 --observation "..."
py -3 -m reverser_harness.cli solution-search CHALLENGE_ID "xor validation loop"
py -3 -m reverser_harness.cli dashboard
```

## 대시보드

`reverser_dashboard` 또는 `dashboard` 명령은 서버를 띄우지 않고 `runs/dashboard.html`을 생성한다.

## 테스트

```powershell
$env:PYTHONPATH="$PWD\code"
py -3 -m unittest discover -s tests -v
docker compose -f .\docker\compose.yaml config --quiet
```
