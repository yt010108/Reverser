# [Project] Reverser 제작: Pi 기반 리버싱 CTF Harness - 1

CTF 리버싱 문제를 풀다 보면 비슷한 작업을 계속 반복하게 된다.

문제 파일을 내려받고 `file`, `strings`, `checksec`로 기본 정보를 확인한다. 그다음 radare2나 Ghidra로 코드를 살펴보고, 필요하면 GDB로 실행 흐름을 확인하거나 angr로 조건을 풀어본다. 문제를 해결한 뒤에는 분석 과정과 Write-up도 다시 정리해야 한다.

이 과정을 조금 더 일관되게 진행하고 싶어서 **Reverser**라는 프로젝트를 만들고 있다.

GitHub: [https://github.com/yt010108/Reverser](https://github.com/yt010108/Reverser)

Reverser의 목표는 AI에게 바이너리를 던진 뒤 단순히 “풀어줘”라고 요청하는 것이 아니다.

내가 만들고 싶은 것은 다음 조건을 만족하는 리버싱 작업 환경이다.

- Pi가 문제 풀이 흐름을 관리한다.
- 실제 바이너리 분석은 격리된 Docker 환경에서 실행한다.
- 문제별 명령과 분석 결과를 다시 확인할 수 있게 저장한다.
- 해결 과정은 별도의 Reviewer가 다시 검토한다.
- 어려운 문제에서 얻은 기법만 다음 문제에 재사용한다.

이번 글에서는 Reverser의 전체 구조와 현재까지 구현한 흐름을 정리한다.

---

## 1. 왜 Skill이 아니라 Harness인가

처음에는 리버싱 기법을 정리한 Skill만 만들어도 어느 정도 자동화가 가능하다고 생각했다.

예를 들어 다음과 같은 지침을 Skill에 넣을 수 있다.

- ELF라면 `checksec`, `readelf`, `rabin2`를 먼저 확인한다.
- 문자열 비교 함수와 입력 검증 함수를 우선 분석한다.
- 정적 분석으로 부족하면 GDB를 사용한다.
- 조건이 복잡하면 angr를 검토한다.

하지만 Skill은 에이전트에게 작업 방법을 알려주는 역할에 가깝다. 문제 파일을 어디에 저장할지, 바이너리를 어느 환경에서 실행할지, 어떤 명령을 실행했는지, 중간 결과를 어떻게 남길지는 별도로 관리해야 한다.

그래서 Reverser는 Skill보다 조금 더 넓은 **Harness** 형태로 구성했다.

Harness는 에이전트가 문제를 풀 수 있도록 프롬프트, 도구, 실행 환경, 상태 저장과 검토 과정을 하나의 흐름으로 연결하는 역할을 한다.

---

## 2. 전체 구조

현재 Reverser의 핵심 구조는 다음과 같다.

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

여기서 Pi는 분석 방향을 결정하고, Python Harness는 실제 명령 실행과 상태 저장을 담당한다. 바이너리를 직접 다루는 명령은 Docker Worker 안에서 실행된다.

핵심은 **에이전트의 판단과 바이너리 실행 환경을 분리한 것**이다.

---

## 3. Parent Pi, Solver, Reviewer

Reverser에서는 하나의 Pi가 문제 가져오기부터 분석, 검토까지 전부 수행하지 않는다.

```text
Parent Pi
   │
   ├── Solver
   │     └── 문제 분석과 풀이
   │
   └── Reviewer
         └── 풀이 검증과 개선점 정리
```

Parent Pi는 전체 흐름만 관리한다. 실제 문제 풀이는 별도의 Solver Pi 프로세스가 담당한다.

Solver가 문제를 해결했거나 더 진행하기 어렵다고 판단하면 새로운 Reviewer가 실행된다. Reviewer는 Solver의 긴 대화 전체를 이어받지 않고, 문제 폴더에 저장된 진행 상태와 분석 결과를 다시 읽는다.

이렇게 분리한 이유는 다음과 같다.

첫 번째는 부모 대화에 문제 풀이 과정 전체가 계속 쌓이는 것을 막기 위해서다.

두 번째는 풀이를 만든 에이전트와 풀이를 검증하는 에이전트를 분리하기 위해서다. 같은 에이전트가 자신의 풀이를 바로 검토하면 처음 세운 잘못된 가정을 그대로 유지할 가능성이 있다.

자식 에이전트가 사용할 수 있는 도구도 제한했다. Solver나 Reviewer가 다시 브라우저를 열거나 다른 에이전트를 계속 생성하지 못하고, 현재 문제 분석에 필요한 도구만 사용할 수 있다.

---

## 4. Pi와 Python Harness 연결

Pi와 프로젝트를 연결하는 파일은 다음과 같다.

```text
.pi/extensions/ctf.ts
```

이 Extension은 Pi에 CTF 전용 도구를 등록한다.

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

Pi가 분석 명령을 요청하면 바로 Docker 명령을 조합하지 않는다.

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

중간에 Python Harness를 두어 실행 정책과 문제 상태를 한곳에서 관리한다.

---

## 5. 문제를 가져오면 먼저 Triage한다

문제를 가져왔다고 바로 자유 분석을 시작하지 않는다. 먼저 core Worker에서 triage를 수행한다.

```text
Import
  ↓
Triage
  ↓
Solving
```

Triage에서는 다음과 같은 기본 정보를 수집한다.

- 파일 종류
- ELF 또는 PE 여부
- 아키텍처
- 32비트 또는 64비트 여부
- 기본 문자열과 섹션 정보
- 이후 사용할 분석 프로필

이 결과는 문제 폴더에 저장된다. 이후 Solver는 같은 정보를 다시 확인하기보다 triage 결과를 기준으로 분석 방향을 정할 수 있다.

---

## 6. Docker를 이용한 분석 환경 격리

CTF에서 받은 바이너리를 호스트에서 바로 실행하는 것은 피하고 싶었다.

그래서 실제 분석 명령은 Docker Worker 안에서만 실행하도록 구성했다. 기본 실행 제한은 다음과 같다.

```text
--network none
--read-only
--cap-drop ALL
--security-opt no-new-privileges
--pids-limit
--memory
--cpus
```

Worker는 기본적으로 네트워크를 사용할 수 없고, 컨테이너 파일 시스템도 read-only다.

문제 파일은 다음과 같이 나누어 마운트한다.

```text
/challenge/input   원본 파일, read-only
/challenge/work    분석 스크립트와 임시 작업
/challenge/output  명령 결과와 생성 파일
```

동적 분석 Worker에만 GDB 사용에 필요한 `SYS_PTRACE` 권한을 추가한다.

즉 전체 흐름은 다음과 같다.

```text
AI가 분석 명령 결정
        ↓
Docker 안에서만 실행
        ↓
stdout, stderr, 생성 파일 저장
```

---

## 7. 역할별 Docker Worker

모든 리버싱 도구를 하나의 거대한 이미지에 넣지 않고 역할별로 나누었다.

| Worker | 주요 용도 |
|---|---|
| `core` | file, strings, binutils, radare2, LIEF, Capstone |
| `dynamic` | GDB, strace, ltrace, Frida |
| `ghidra` | Ghidra Headless 분석 |
| `angr` | Symbolic Execution |

기본 흐름은 다음 순서를 우선한다.

```text
core
  ↓
dynamic
  ↓
ghidra
  ↓
angr
```

항상 네 Worker를 전부 실행하는 것은 아니다.

간단한 문제는 strings와 radare2만으로 해결할 수 있다. Ghidra는 관심 함수가 좁혀졌을 때 필요한 함수만 디컴파일한다. angr도 조건식이 복잡하고 심볼릭 실행이 실제로 도움이 될 때만 사용한다.

이미지 크기와 분석 시간을 줄이고, 에이전트가 무조건 무거운 도구부터 실행하는 것을 막기 위한 구조다.

---

## 8. 문제별 작업 공간과 progress.md

문제를 가져오면 다음 구조의 작업 공간이 생성된다.

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

분석 명령을 실행하면 결과가 다음과 같이 순서대로 남는다.

```text
output/
├── 0001-triage.stdout.log
├── 0001-triage.stderr.log
├── 0002-core.stdout.log
├── 0002-core.stderr.log
└── ...
```

Pi 프로세스를 종료하더라도 문제 파일과 진행 기록은 run 폴더에 남는다. 나중에 같은 문제를 다시 열었을 때 이전에 실행한 명령과 결과를 확인할 수 있다.

---

## 9. 처음 30분은 직접 분석한다

Reverser에서는 문제를 가져오자마자 공개 Write-up을 검색하지 않는다.

```text
Triage
  ↓
직접 분석
  ↓
30분 경과
  ↓
Research 허용
```

30분은 Solver를 강제로 종료하는 제한 시간이 아니다. 공개 풀이와 저장된 Technique Memory를 참고할 수 있게 되는 기준이다.

쉽게 풀 수 있는 문제까지 외부 풀이에 의존하지 않고, 직접 분석하는 시간을 확보하기 위해 넣은 정책이다.

---

## 10. Technique Memory

리버싱 문제에서는 비슷한 패턴이 반복된다.

- XOR 기반 입력 검증
- table lookup
- custom VM
- anti-debug
- bit rotation
- opaque predicate
- symbolic execution이 필요한 조건식

이런 기법을 다음 문제에서 다시 활용할 수 있도록 `memory/techniques/`에 Markdown 카드로 저장한다.

하지만 모든 문제를 Memory에 넣지는 않는다.

저장 대상은 다음과 같다.

- 30분 이상 걸린 문제
- 해결하지 못한 문제
- 다른 문제에서도 재사용할 수 있는 분석 기법이 나온 문제

쉽게 해결한 문제의 긴 풀이까지 계속 저장하면 Memory가 커지고 검색 결과도 흐려질 수 있다. 그래서 문제 전체 Write-up보다 다시 사용할 수 있는 핵심 기법만 남긴다.

검색은 SQLite FTS5를 사용한다. 별도의 벡터 데이터베이스를 추가하지 않고, 현재 필요한 수준에서 단순하게 구성했다.

---

## 11. 공개용과 비공개 Write-up 분리

Write-up은 두 종류로 나눈다.

```text
Private
  실제 분석 기록
  실제 플래그 포함 가능

Public
  플래그 제거
  Git에 올릴 수 있는 형태
```

비공개 Write-up은 run 폴더에 저장하고, Git에 올릴 공개 버전은 `writeups/`에 따로 생성한다.

공개 버전에서는 기록된 플래그와 flag 형태의 값을 제거한다. 풀이 과정에서 만든 Python이나 Shell 스크립트는 함께 정리할 수 있다.

플래그 자체보다 어떤 로직을 확인했고 어떻게 검증했는지가 Write-up에 남도록 하는 것이 목적이다.

---

## 12. 현재 전체 Workflow

현재 Reverser의 전체 흐름은 다음과 같다.

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

결국 현재 구조는 다음 다섯 부분으로 정리할 수 있다.

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

## 13. 만들고 나서 보인 한계

처음에는 Solver와 Reviewer를 분리하면 피드백 구조가 어느 정도 완성된다고 생각했다.

하지만 실제 구조를 다시 살펴보니 Reviewer는 Solver가 끝난 뒤에만 실행된다. Solver가 같은 가설과 명령을 반복해도 중간에 이를 감지하지 못한다. 플래그 후보가 실제 명령 출력에서 나온 값인지 강제하는 장치도 부족하다.

즉 현재 Reverser에는 **풀이 후 검토**는 있지만, 풀이 도중 막힘을 감지하고 전략을 바꾸는 **실시간 피드백 루프**는 아직 없다.

그래서 다음 글에서는 공개된 CTF 하네스들을 비교해 다음 내용을 정리할 예정이다.

- 다른 CTF 에이전트는 안 풀리는 문제를 어떻게 처리하는가
- 같은 실패를 반복하지 않기 위해 무엇을 기록하는가
- 플래그가 실제 실행 결과라는 것을 어떻게 검증하는가
- 현재 구조를 복잡하게 만들지 않고 어떤 부분만 가져올 것인가

2편에서는 `ctf-skills`, EnIGMA, D-CIPHER, CAI, Muteki를 비교하고 Reverser의 피드백 루프를 다시 설계해본다.

