# CTF Reverse

Pi와 네트워크 없는 Docker 작업자로 제공된 리버싱 CTF 문제를 분석하는 최소 하네스다. v1은 x86/amd64 Linux ELF와 PE 정적 분석만 지원하며 플래그를 제출하지 않는다. triage 이후 30분은 직접 풀고, 그 뒤에도 미해결일 때만 풀이 방법을 검색한다.

## 구조

```text
ctf/
├── AGENTS.md
├── README.md
├── .pi/                 # /ctf와 ctf_* 도구
├── code/ctf_harness/    # 가져오기, 분석, 저장, write-up, 메모리
├── docker/              # core, dynamic, ghidra, angr 작업자
├── memory/techniques/   # 승인된 재사용 기법
├── tests/
├── writeups/            # 플래그가 제거된 공개 write-up
└── runs/<CHALLENGE_ID>/ # 원본과 분석 결과, Git 제외
```

전체 `ctf-skills` 저장소는 복사하지 않는다. 필요한 흐름은 로컬 Pi 스킬에만 두며 참고 원본은 [ljagiello/ctf-skills](https://github.com/ljagiello/ctf-skills)다.

## 실행

```powershell
cd C:\Users\ytyt\Desktop\security\ctf
docker compose -f .\docker\compose.yaml build core dynamic
pi
```

Pi에서:

```text
/ctf
```

Pi는 문제 URL이나 로컬 파일을 받아 정적 triage를 수행한 뒤 승인창 없이 바로 풀이한다. 플래그 제출과 작업자 네트워크는 없다.

```text
가져오기 → triage → 30분 직접 풀이 → 미해결이면 풀이 방법 검색 → Write-up
```

30분은 강제 종료 시간이 아니라 `researching` 단계로 넘어가는 기준이다. `ctf_solution_search`는 저장된 어려운 문제 기법과 공개 웹 검색 결과를 함께 보여준다. 검색 결과와 링크의 내용은 신뢰하지 않는 참고자료로 취급한다. 쉬운 문제는 메모리에 넣지 않고, 30분 이상 걸렸거나 미해결인 문제의 핵심 기법만 `memory/techniques/`에 저장한다.

## Playwright 브라우저

Pi 확장은 공식 Node Playwright를 직접 사용한다. 설치는 한 번만 하면 된다.

```powershell
$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD="1"
npm install
```

Pi의 `ctf_browser`에는 Playwright의 `page`와 `context`가 그대로 전달된다. 별도 클릭 래퍼나 CTFd API 가정은 없다.

```javascript
await page.goto("https://ctf.example/challenges");
return await page.locator("body").innerText();
```

클릭, 입력, 새 탭, 네트워크 응답, 스크린샷, 다운로드 등 Playwright API를 그대로 사용할 수 있다. 브라우저는 Pi 실행 중 계속 열려 있고 세션은 `.private/playwright-profile/`에 저장된다. 로그인 화면이면 열린 브라우저에서 사용자가 직접 로그인한 뒤 Pi에게 계속하라고 하면 된다.

```javascript
await page.getByRole("link", { name: "Reversing" }).click();
return await page.locator("body").innerText();
```

다운로드 파일은 `.private/browser-downloads/`에 저장하고 `ctf_import_local`로 가져온다.

```javascript
const [download] = await Promise.all([
  page.waitForEvent("download"),
  page.getByText("다운로드").click(),
]);
const path = `${downloadsDir}/${download.suggestedFilename()}`;
await download.saveAs(path);
return path;
```

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

## 문제 결과

```text
runs/<CHALLENGE_ID>/
├── progress.md
├── original/
├── work/
├── output/
├── reports/
└── memory/
```

`progress.md`에 `solving`, `researching`, `solved`, `unsolved` 상태와 경과시간, 실행 기록을 함께 저장한다. 실제 플래그와 비공개 write-up은 `runs/`에만 남고, 플래그를 제거한 결과만 `writeups/`에 저장한다.

## 직접 CLI

```powershell
$env:PYTHONPATH="$PWD\code"
py -3 -m ctf_harness.cli doctor
py -3 -m ctf_harness.cli import-local --title rev1 --file C:\Downloads\rev1
py -3 -m ctf_harness.cli list
py -3 -m ctf_harness.cli status CHALLENGE_ID
py -3 -m ctf_harness.cli solution-search CHALLENGE_ID "xor validation loop"
py -3 -m ctf_harness.cli dashboard
```

## 대시보드

`ctf_dashboard` 또는 `dashboard` 명령은 서버를 띄우지 않고 루트의 `dashboard.html` 하나를 생성한다. 이 파일에는 실제 플래그가 들어가지 않으며 Git에서도 제외된다.

## 테스트

```powershell
$env:PYTHONPATH="$PWD\code"
py -3 -m unittest discover -s tests -v
docker compose -f .\docker\compose.yaml config --quiet
```
