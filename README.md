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

Pi는 문제 URL이나 로컬 파일을 받아 문제를 가져온 뒤, 풀이를 별도 Solver Pi에 위임한다. 플래그 제출과 작업자 네트워크는 없다.

```text
부모: 가져오기 → Solver: triage·풀이·Write-up → Reviewer: 검증·개선 피드백
```

Solver와 Reviewer는 각각 별도 Pi 프로세스에서 실행되므로 부모 Pi에 긴 풀이 컨텍스트가 누적되지 않는다. 현재 모델과 thinking 설정을 상속하고, 대화 세션은 저장하지 않으며 진행 상태와 결과는 `runs/<CHALLENGE_ID>/`에만 남긴다.

Pi TUI는 자식의 사고 과정이나 명령 출력 전문을 가져오지 않고 작업 종류와 경과시간만 보여준다. 10초 이상 실행되는 작업은 진행 시간을 주기적으로 갱신한다.

```text
[Solver] core · radare2 정적 분석 · 실행 중 · 18.2초
[Solver] ghidra · Ghidra 관심 함수 디컴파일 · 완료 · 26.9초
[Reviewer] Write-up 저장 · 완료 · 0.4초
```

30분은 강제 종료 시간이 아니라 `researching` 단계로 넘어가는 기준이다. Solver 종료 후 해결·미해결·30분 초과 문제만 새 Reviewer가 검토한다. 쉬운 문제는 메모리에 넣지 않고, 30분 이상 걸렸거나 미해결인 문제의 핵심 기법만 `memory/techniques/`에 저장한다.

## Playwright 브라우저

Pi 확장은 공식 Node Playwright를 직접 사용한다. 설치는 한 번만 하면 된다.

```powershell
$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD="1"
npm install
```

Pi의 `ctf_browser`에는 Playwright의 `page`와 `context`가 그대로 전달된다. 별도 브라우저 헬퍼는 없다.

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

반드시 `waitForEvent`와 클릭을 같이 기다린다. `ctf_browser`는 이렇게 `await`된 오류를 도구 오류로 반환한다.

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
ctf-ghidra /challenge/input/chall /challenge/output/decompile.c main check_flag 0x401230
```

첫 호출은 분석 프로젝트를 `/challenge/work/ghidra-project/`에 저장하고, 다음 호출부터는 분석을 다시 하지 않고 그 프로젝트를 재사용한다. 함수를 생략하면 `main`/entry 계열만 우선 출력하며, `--all`은 전체 함수가 필요할 때만 사용한다.

## 문제 결과

```text
runs/<CHALLENGE_ID>/
├── progress.md
├── original/
├── work/
├── output/
└── reports/
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
