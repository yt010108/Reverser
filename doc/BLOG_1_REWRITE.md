# [Project] Reverser 제작: Pi 기반 리버싱 CTF Harness - 1

AI가 발전하면서 CTF처럼 시간이 제한되어 있는 문제 풀이에서는 AI 사용이 필수적이다. 또한 AI가 발전하면서 Agent를 통한 문제 풀이가 일반적이다.
codex를 사용한 문제 풀이를 진행하다 보면 쉬운 문제는 가볍게 잘 풀리지만 어려운 문제로 갈수록 시간과 비용이 많이 든다.
게다가 agent를 사용하면 사용자가 개입할 수 있는 부분은 처음 문제 설명과 로그로 사용자가 부분적으로 개입 가능하다.
codex로 사용할 경우에는 문제 입력과 skill을 통해서 문제 풀이를 하곤 했다.

하지만 codex는 물론 잘 만든 하네스이고 리버싱 문제를 잘 풀지만 못 푸는 문제도 있으며 문제 풀이에서 사용자가 입력 가능한 skill과 입력만으로는 한계가 느껴졌다.
그래서 PI Agent를 통한 하네스를 만들어 문제를 풀수록 잘 풀리는 Agent를 만들고 싶었으며 Agent feedback 루프 및 오케스트레이션을 통해서 이걸 구현하고 싶었다.

따라서 Reverser라는 프로젝트를 만들고 있다.

GitHub: [https://github.com/yt010108/Reverser](https://github.com/yt010108/Reverser)

Reverser의 목표는 AI에게 바이너리를 던지고 단순히 “풀어줘”라고 요청하는 데 있지 않다.

내가 원한 리버싱 작업 환경의 조건은 이렇다.

- Pi가 문제 풀이 흐름을 관리하고 오케스트레이션한다.
- 실제 바이너리 분석은 격리된 Docker 환경에서 실행한다.
- 문제별 명령과 분석 결과를 저장해 두고 다시 확인한다.
- 풀이가 끝난 뒤에는 별도의 Reviewer가 과정을 다시 검토한다.
- 어려운 문제에서 얻은 기법만 다음 문제에 재사용한다.

이번 글에서는 Reverser의 전체 구조와 지금까지 구현한 흐름을 정리한다.
---

## 1. 왜 Skill이 아니라 Harness인가

처음에는 리버싱 기법을 정리한 Skill만 있어도 어느 정도 자동화되리라 생각했다.
ctf-skills라는 https://github.com/ljagiello/ctf-skills 프로젝트를 통해 어느 정도 커버가 가능했다.


그런데 Skill은 에이전트에게 작업 방법을 알려주는 데 가깝다. skill을 통한 문제 풀이는 에이전트에게 문제를 파악하고 어떻게 접근하는지에 대한 가이드라인이다. 그리고 AI 모델은 이 가이드를 바탕으로 가설을 세우고 문제를 통해 검증한다. 이때 검증 과정이 올바르면 문제가 풀린다. 하지만 가설이 잘못되거나 하면 검증을 바탕으로 AI 모델은 새로운 가설을 세우고 그에 따른 검증을 반복해 문제를 풀게 된다.


물론 AI 모델이 발전할수록 가설은 점점 더 정확해지고 검증 프로세스 반복은 줄어들 것이다. 하지만 가설을 어떻게 세우고 검증 프로세스를 어떻게 진행하는지에 따라서 같은 모델을 사용하더라도 시간, 비용, 심지어 결과까지 달라진다. 시간과 비용은 보통 결국 토큰과 연관되어 있으며 많은 토큰을 사용할 수 있으면 AI가 가설을 세우고 검증하는 프로세스를 진행하는 시행 횟수가 많아질수록 문제 해결 가능성이 높아진다. 하지만 CTF에는 시간 제한이 있으며 토큰은 무제한이 아니다. 또한 AI가 사용할 수 있는 컨텍스트가 토큰에 따라 늘어나 결국 문제를 못 풀게 될 가능성이 높다.


따라서 Reverser의 범위를 Skill보다 넓혀 Harness 형태로 구성했다. 여기서 Harness는 문제 풀이에 필요한 프롬프트와 도구, 실행 환경, 상태 저장, 검토 과정을 한 흐름으로 묶는 구조를 뜻한다. Reverser는 PI를 통해서 오케스트레이션하고 가설과 검증 프로세스를 관리하고 문제 풀이 solver와 review를 통해서 자가 개선하는 에이전트를 구성하려 했다.

---


## 2. 왜 Pi를 선택했는가

Reverser에서 바꾸고 싶었던 것은 모델보다 Harness였다.

codex와 Claude Code는 범용 코딩 작업에 필요한 기능을 이미 많이 갖춘 큰 Harness다. 파일을 읽고 수정하거나 명령을 실행하고 여러 도구를 연결하기에는 편하다. 대신 Harness가 맡는 범위가 넓고 기본 Workflow도 이미 잡혀 있다.

Reverser는 범용 코딩 Agent를 하나 더 만들려는 프로젝트가 아니다. 문제를 가져오고 triage한 뒤 Solver에 넘기는 과정, 바이너리를 Docker에서 실행하는 과정, 새로운 Reviewer가 풀이를 다시 읽는 과정까지 직접 바꾸고 싶었다. Solver가 같은 가설을 반복할 때 이를 감지하고 새로운 전략으로 전환하는 피드백 루프도 Harness 안에 넣으려 했다.

큰 범용 Harness 위에 이 흐름을 덧붙이면 기존 기능과 Reverser의 정책이 섞인다. 어떤 판단을 모델이 했고 어떤 처리를 Harness가 했는지 추적하기도 어려워진다. 내가 필요했던 것은 기능이 많은 기반보다 필요한 기능만 직접 넣을 수 있는 작은 기반이었다.

[Pi](https://pi.dev/)는 minimal agent harness를 지향한다. sub-agent, plan mode, MCP, permission popup 같은 기능을 코어에 전부 넣지 않고 필요하면 Extension으로 추가한다. 기본 Harness가 작으니 프로젝트에 필요하지 않은 기능을 걷어낼 필요도 없다.

이 미니멀함이 Reverser에 더 적합했다. `.pi/extensions/ctf.ts`에서 CTF 전용 도구를 등록하고 Parent Pi, Solver, Reviewer의 역할을 직접 나눌 수 있다. 어떤 로그를 저장하고 언제 Solver를 끝내며 무엇을 Reviewer에 넘길지도 Reverser가 정한다.

결국 Pi를 선택한 이유는 가벼워서만은 아니다. 이미 완성된 범용 Workflow를 사용하는 것보다 작은 Harness 위에서 가설과 검증, 상태 저장, 피드백 루프를 직접 설계하기 쉬웠기 때문이다.

---

## 3. 전체 구조

앞에서 말한 가설과 검증을 한 흐름으로 관리하려고 각 역할을 나눴다. Reverser의 현재 구조를 펼치면 아래와 같다.

```text
사용자
  ↓
Parent Pi
  ↓
문제 Import
  ↓
Solver Pi
  ↓
Python Harness
  ↓
Docker Worker
  ↓
분석 결과 저장
  ↓
Reviewer Pi
  ↓
Write-up / Technique Memory
```

Pi는 분석 방향을 정하고 Python Harness는 명령 실행과 상태 저장을 맡는다. 바이너리를 직접 다루는 명령은 Docker Worker 안에서만 실행한다.

핵심은 에이전트의 판단과 바이너리 실행 환경을 분리하는 데 있다.

---

## 4. Parent Pi, Solver, Reviewer

전체 흐름을 나눌 때 가장 먼저 정한 원칙은 하나의 Pi에 문제 가져오기부터 분석, 검토까지 전부 맡기지 않는 것이었다.

```text
Parent Pi
   │
   ├── Solver
   │     └── 문제 분석과 풀이
   │
   └── Reviewer
         └── 풀이 검증과 개선점 정리
```

Parent Pi는 전체 흐름을 조율하고 실제 문제 풀이는 별도의 Solver Pi 프로세스가 맡는다.

Solver가 문제를 해결했거나 더 진행하기 어렵다고 판단하면 새로운 Reviewer가 실행된다. Reviewer는 Solver의 긴 대화 전체를 이어받지 않고 문제 폴더에 저장된 진행 상태와 분석 결과를 다시 읽는다.

이렇게 나누면 부모 대화에 문제 풀이 과정이 계속 쌓이지 않는다. 풀이를 만든 에이전트와 검증하는 에이전트도 자연스럽게 분리된다. 같은 에이전트가 자신의 풀이를 바로 검토하면 처음 세운 잘못된 가정을 그대로 끌고 갈 가능성이 있기 때문이다.

자식 에이전트의 도구도 제한했다. Solver나 Reviewer는 다시 브라우저를 열거나 다른 에이전트를 계속 생성하지 못하며 현재 문제 분석에 필요한 도구만 사용한다.

---

## 5. Pi와 Python Harness 연결

역할을 나눈 다음에는 Pi의 판단을 Python Harness와 연결해야 했다. Pi와 프로젝트를 잇는 파일은 아래 Extension이다.

```text
.pi/extensions/ctf.ts
```

이 Extension이 Pi에 CTF 전용 도구를 등록한다.

주요 기능은 다음과 같다.

- 문제 목록과 현재 상태 확인
- 기본 triage 실행
- 격리된 분석 명령 실행
- 플래그 후보 로컬 기록
- Write-up 저장
- 30분 이후 풀이 기법 검색
- 미해결 사유 기록
- Reviewer 실행
- 정적 HTML 대시보드 생성

Pi가 분석 명령을 요청하더라도 곧바로 Docker 명령을 조합하지는 않는다.

```text
Pi
  ↓
ctf_exec
  ↓
Python CLI
  ↓
Docker Worker
  ↓
결과 저장
```

중간의 Python Harness가 실행 정책과 문제 상태를 한곳에서 관리한다.

---

## 6. 문제를 가져오면 먼저 Triage한다

Pi와 Python Harness를 연결한 뒤 문제를 가져온다. Import 직후에는 자유 분석부터 시작하지 않고 core Worker에서 triage를 수행한다.

```text
Import
  ↓
Triage
  ↓
Solving
```

Triage에서 수집하는 기본 정보는 다음과 같다.

- 파일 종류
- ELF 또는 PE 여부
- 아키텍처
- 32비트 또는 64비트 여부
- 기본 문자열과 섹션 정보
- 이후 사용할 분석 프로필

결과는 문제 폴더에 남는다. 이후 Solver는 같은 정보를 매번 다시 확인하지 않고 triage 결과를 기준으로 분석 방향을 정한다.

---

## 7. Docker를 이용한 분석 환경 격리

Triage 다음부터는 실제 바이너리를 다뤄야 한다. CTF에서 받은 파일을 호스트에서 곧바로 실행하고 싶지는 않았다.

실제 분석 명령을 Docker Worker 안에서만 실행하도록 구성한 이유다. 기본 실행 제한은 다음과 같다.

```text
--network none
--read-only
--cap-drop ALL
--security-opt no-new-privileges
--pids-limit
--memory
--cpus
```

Worker는 기본적으로 네트워크를 쓰지 못하고 컨테이너 파일 시스템도 read-only다.

문제 파일은 용도에 따라 나누어 마운트한다.

```text
/challenge/input   원본 파일, read-only
/challenge/work    분석 스크립트와 임시 작업
/challenge/output  명령 결과와 생성 파일
```

동적 분석 Worker에만 GDB 사용에 필요한 `SYS_PTRACE` 권한을 추가한다.

전체 흐름은 다음과 같다.

```text
AI가 분석 명령 결정
        ↓
Docker 안에서만 실행
        ↓
stdout, stderr, 생성 파일 저장
```

---

## 8. 역할별 Docker Worker

실행 환경을 격리한 뒤에는 리버싱 도구도 역할별로 나눴다. 하나의 거대한 이미지에 전부 몰아넣지 않았다.

| Worker | 주요 용도 |
|---|---|
| `core` | file, strings, binutils, radare2, LIEF, Capstone |
| `dynamic` | GDB, strace, ltrace, Frida |
| `ghidra` | Ghidra Headless 분석 |
| `angr` | Symbolic Execution |

기본 분석 순서는 아래와 같다.

```text
core
  ↓
dynamic
  ↓
ghidra
  ↓
angr
```

네 Worker를 매번 전부 실행하지는 않는다.

간단한 문제라면 strings와 radare2만으로도 풀 수 있다. Ghidra는 관심 함수가 좁혀졌을 때 필요한 함수만 디컴파일한다. angr도 조건식이 복잡하고 심볼릭 실행이 실제로 도움이 될 때만 사용한다.

이 구성이 이미지 크기와 분석 시간을 줄이고 에이전트가 무거운 도구부터 무조건 실행하는 일도 막아준다.

---

## 9. 문제별 작업 공간과 progress.md

Worker가 만든 결과와 문제 상태는 문제별 작업 공간에 남긴다. 문제를 가져오면 아래 구조가 생긴다.

```text
runs/<challenge_id>/
├── progress.md
├── original/
├── work/
├── output/
└── reports/
```

각 폴더의 역할은 다음과 같다.

- `original/`: 원본 문제 파일
- `work/`: 풀이 스크립트와 분석 중간 파일
- `output/`: 명령의 stdout, stderr와 분석 결과
- `reports/`: 비공개 Write-up과 Reviewer 결과
- `progress.md`: 현재 상태와 명령 실행 이력

분석 명령의 결과는 실행 순서에 맞춰 남는다.

```text
output/
├── 0001-triage.stdout.log
├── 0001-triage.stderr.log
├── 0002-core.stdout.log
├── 0002-core.stderr.log
└── ...
```

Pi 프로세스를 종료해도 문제 파일과 진행 기록은 run 폴더에 남는다. 나중에 같은 문제를 다시 열면 이전 명령과 결과부터 확인한다.

---

## 10. 처음 30분은 직접 분석한다

분석 기록을 남기는 것과 별개로 외부 풀이를 찾는 시점도 정했다. Reverser에서는 문제를 가져오자마자 공개 Write-up을 검색하지 않는다.

```text
Triage
  ↓
직접 분석
  ↓
30분 경과
  ↓
Research 허용
```

이 30분은 Solver를 강제로 종료하는 제한 시간이 아니다. 저장된 Technique Memory 참고를 허용하는 기준일 뿐이며 활성 문제의 공개 풀이는 검색하지 않는다.

쉽게 풀리는 문제도 먼저 직접 분석할 시간을 확보하려고 넣은 정책이다.

---

## 11. Technique Memory

직접 분석하거나 Research 단계에서 확인한 기법 중에는 다음 문제에 다시 쓸 만한 것도 있다. 리버싱 문제에서는 비슷한 패턴이 반복된다.

- XOR 기반 입력 검증
- table lookup
- custom VM
- anti-debug
- bit rotation
- opaque predicate
- symbolic execution이 필요한 조건식

이런 기법은 다음 문제에서 다시 꺼내 쓰려고 `memory/techniques/`에 Markdown 카드로 저장한다.

다만 모든 문제를 Memory에 넣지는 않는다.

저장 대상은 다음과 같다.

- 30분 이상 걸린 문제
- 해결하지 못한 문제
- 다른 문제에도 재사용할 분석 기법이 나온 문제

쉽게 해결한 문제의 긴 풀이까지 쌓으면 Memory가 커지고 검색 결과도 흐려진다. 문제 전체 Write-up 대신 다시 쓸 핵심 기법만 남기는 이유다.

검색에는 SQLite FTS5를 쓴다. 별도의 벡터 데이터베이스는 추가하지 않고 지금 필요한 수준에 맞춰 단순하게 구성했다.

---

## 12. 공개용과 비공개 Write-up 분리

Technique Memory와 별도로 문제의 전체 풀이 과정은 Write-up에 남긴다. Write-up은 공개용과 비공개용으로 나눈다.

```text
Private
  실제 분석 기록
  실제 플래그 포함 가능

Public
  플래그 제거
  Git에 올릴 수 있는 형태
```

비공개 Write-up은 run 폴더에 저장하고 Git에 올릴 공개 버전은 `writeups/`에 따로 생성한다.

공개 버전에서는 기록된 플래그와 flag 형태의 값을 지운다. 풀이 과정에서 만든 Python이나 Shell 스크립트는 필요하면 함께 정리한다.

Write-up에는 플래그 자체보다 어떤 로직을 확인했고 어떻게 검증했는지를 남긴다.

---

## 13. 현재 전체 Workflow

여기까지 설명한 구성 요소를 하나의 Workflow로 이어 붙이면 아래와 같다.

```text
문제 가져오기
      ↓
자동 Triage
      ↓
Solver가 분석 전략 결정
      ↓
Docker Worker에서 명령 실행
      ↓
분석 명령과 결과 저장
      ↓
플래그 후보 검증 또는 미해결 기록
      ↓
새 Reviewer가 풀이 검토
      ↓
공개/비공개 Write-up 생성
      ↓
어려운 문제라면 Technique Memory 저장
```

현재 구조를 떠받치는 요소는 다섯 가지다.

```text
Pi Orchestration
+
Docker Isolation
+
CTF Harness
+
Solver / Reviewer
+
Technique Memory
```

---

## 14. 만들고 나서 보인 한계

처음에는 Solver와 Reviewer를 분리하면 문제를 풀수록 더 잘 푸는 Agent에 가까워진다고 생각했다. 실제 구조를 다시 살펴보니 둘을 나눈 것만으로는 부족했다.

Reviewer는 Solver가 끝난 뒤에만 실행된다. Solver가 같은 가설과 명령을 반복해도 중간에 이를 감지하지 못한다. 플래그 후보가 실제 명령 출력에서 나온 값인지 강제하는 장치도 부족하다.

현재 Reverser에는 풀이 후 검토는 있지만 풀이 도중 막힘을 감지하고 전략을 바꾸는 실시간 피드백 루프는 아직 없다.

다음 글에서는 공개된 CTF 하네스들을 비교하며 이 빈틈을 어떻게 메울지 정리할 예정이다.

- 다른 CTF 에이전트는 안 풀리는 문제를 어떻게 처리하는가
- 같은 실패를 반복하지 않기 위해 무엇을 기록하는가
- 플래그가 실제 실행 결과라는 것을 어떻게 검증하는가
- 현재 구조를 복잡하게 만들지 않고 어떤 부분만 가져올 것인가

2편에서는 `ctf-skills`, EnIGMA, D-CIPHER, CAI, Muteki를 비교하고 Reverser의 피드백 루프를 다시 설계한다.
