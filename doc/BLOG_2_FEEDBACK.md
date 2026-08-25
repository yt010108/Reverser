# [Project] Reverser 제작: 리버싱 Agent의 실패를 줄이는 피드백 루프 설계 - 2

1편에서는 Pi, Python Harness, Docker Worker를 연결해 리버싱 CTF 문제를 분석하는 Reverser의 기본 구조를 정리했다.

1편: [Reverser 제작: Pi 기반 리버싱 CTF Harness - 1](https://yt5246.tistory.com/142)

현재 구조에는 문제 가져오기, triage, 격리 분석, Solver와 Reviewer 분리, Write-up 생성, Technique Memory까지 들어가 있다. 처음에는 이 정도면 피드백 구조도 갖췄다고 생각했다.

```text
Solver가 문제를 풂
        ↓
Reviewer가 결과를 검토함
        ↓
어려웠던 기법을 Memory에 저장함
```

코드를 다시 읽고 나니 중요한 빈틈이 보였다.

Reviewer는 Solver가 끝난 뒤에만 실행된다. Solver가 같은 명령이나 잘못된 가설을 반복해도 풀이 도중에는 이를 감지하지 못한다. 플래그 후보를 기록할 때도 그 값이 실제 명령 출력에서 나온 것인지 강제하지 않는다.

Reverser에는 사후 검토는 있지만 문제를 푸는 도중 작동하는 피드백 루프는 부족했다.

이번 글에서는 공개된 CTF 하네스와 리버싱 Agent 연구를 함께 살펴본다.

- 안 풀리는 문제를 어떻게 감지하는가
- 관찰 결과를 언제 확인된 사실로 인정하는가
- 실패한 접근을 어떻게 기록하는가
- 가설을 어떤 조건에서 버리는가
- 새로운 에이전트에 어떤 정보만 전달하는가
- 플래그가 실제 실행 결과인지 어떻게 검증하는가
- 어떤 기능은 Reverser에 넣지 않는 것이 좋은가

비교 대상은 `ctf-skills`, EnIGMA, D-CIPHER, CAI, Muteki다. 여기에 [당신의 AI Agent가 CTF 문제를 못 푸는 이유: 리버싱 편](https://h4c.team/posts/49)과 관련 연구에서 다룬 관찰 오류, 컨텍스트 손실, 확인 편향 문제를 Reverser의 설계에 대입했다.

먼저 분명히 해둘 점이 있다. 이 글에서 설명하는 `Observation Gate`, 반증 조건, 실행 결과 검증, 막힘 감지는 아직 구현되지 않았다. 현재 코드의 동작과 앞으로 바꿀 설계를 구분해서 적었으며, 실제 구현 과정과 변경 전후 테스트는 3편에서 다룰 예정이다.

---

## 1. 현재 Reverser의 피드백 구조

현재 Solver와 Reviewer는 각각 별도의 Pi 프로세스로 실행된다.

```text
Parent Pi
   │
   ├── Solver
   │     └── 문제 풀이
   │
   └── Reviewer
         └── 풀이 검증과 개선점 작성
```

역할을 나눈 덕분에 얻은 것이 있다.

- 부모 Pi의 컨텍스트가 문제 풀이로 가득 차지 않는다.
- 풀이한 에이전트와 검토하는 에이전트가 분리된다.
- Reviewer는 더 빠른 풀이와 놓친 단서를 독립적으로 확인한다.
- 어려운 문제에서 얻은 기법은 Memory에 남긴다.

문제는 Reviewer가 움직이는 시점이다. 문제 해결, 미해결 기록 또는 30분 경과 이후에야 실행된다.

Solver가 30분 동안 잘못된 방향으로 가더라도 중간에 다음과 같은 판단을 해주는 계층은 없다.

```text
이 명령은 이미 실행했다.
이 가설은 앞의 결과에서 반증됐다.
최근 여러 명령에서 새로운 정보가 나오지 않았다.
현재 컨텍스트를 정리하고 다른 전략으로 바꿔야 한다.
```

다른 프로젝트가 이 구간을 어떻게 처리하는지부터 살펴봤다.

---

## 2. ctf-skills가 막혔을 때 방향을 바꾸는 법

[ctf-skills](https://github.com/ljagiello/ctf-skills)는 CTF 분야별 지식을 Agent Skill 형태로 정리한 프로젝트다.

web, pwn, crypto, reverse, forensics 등 카테고리별 Skill이 있다. `solve-challenge`는 문제를 먼저 분류한 뒤 적절한 Skill로 연결한다.

막혔을 때 따를 지침도 구체적이다.

- 처음 세운 가정을 다시 확인한다.
- 문제가 한 가지 카테고리인지 다시 판단한다.
- 다른 분야의 Skill을 함께 사용한다.
- 놓친 파일, 포트, 주석과 메타데이터를 다시 확인한다.
- 복잡한 공격보다 더 단순한 경로가 있는지 찾는다.

자세한 흐름은 [`solve-challenge/SKILL.md`](https://github.com/ljagiello/ctf-skills/blob/main/solve-challenge/SKILL.md)에 정리돼 있다.

이 프로젝트의 중심은 실행 하네스가 아니라 지식과 작업 지침이다. 같은 명령을 몇 번 반복했는지, 비용을 얼마나 썼는지, 어떤 접근이 실패했는지를 runtime에서 강제하지는 않는다.

둘을 나란히 놓으면 이렇다.

```text
ctf-skills
  강점: 넓은 분야 지식, 카테고리 전환, 다양한 기법

Reverser
  강점: Docker 격리, 상태 저장, 플래그 보호, Reviewer
```

모든 Skill과 도구를 Reverser에 가져올 필요는 없었다. triage 결과에 맞는 리버싱 체크리스트만 골라 쓰기로 했다.

---

## 3. EnIGMA가 실제 도구 사용을 강조하는 이유

[EnIGMA](https://github.com/SWE-agent/SWE-agent/releases/tag/v0.7.0)는 SWE-agent에 CTF 문제 해결 기능을 추가한 연구 프로젝트다.

눈에 띈 부분은 GDB와 원격 연결처럼 상태를 유지하는 Interactive Agent Tools다. 긴 명령 출력은 summarizer로 줄여 에이전트에 다시 전달한다.

[EnIGMA 논문](https://arxiv.org/abs/2409.16165)에서는 `soliloquizing`이라는 현상도 설명한다.

모델이 실제 환경과 충분히 상호작용하지 않은 채, 도구로 확인하지 않은 관찰 결과를 스스로 만들어내는 현상이다.

예를 들어 GDB를 실제로 실행하지 않고 다음과 같이 생각하는 경우다.

```text
아마 이 주소에서 비교가 수행될 것이다.
레지스터에는 특정 값이 들어 있을 것이다.
따라서 입력은 이 값일 것이다.
```

이런 추론이 언제나 틀리지는 않는다. 다만 실제 실행 결과가 없으면 잘못된 가정이 계속 이어지기 쉽다.

EnIGMA가 주는 핵심 피드백은 단순하다.

> 모델의 설명보다 실제 도구의 observation을 중심으로 다음 행동을 결정해야 한다.

Reverser도 모든 명령의 stdout과 stderr를 저장하지만 그 결과로 어떤 사실을 검증했는지는 구조적으로 남기지 않는다.

Interactive GDB부터 추가하지는 않기로 했다. 먼저 보완할 항목은 아래와 같다.

- 실제 명령 출력과 확인된 사실을 연결한다.
- 긴 출력 전체를 다음 Solver에 넘기지 않고 핵심 결과를 요약한다.
- GDB 명령은 우선 batch script로 재현 가능하게 실행한다.
- 상태 유지가 반드시 필요한 문제가 확인되면 그때 persistent GDB를 추가한다.

---

## 4. D-CIPHER의 Planner와 새로운 Executor

[D-CIPHER](https://github.com/NYU-LLM-CTF/nyuctf_agents)는 Planner와 여러 Executor를 분리한다.

Planner는 전체 문제 해결 방향을 관리하고 Executor는 작은 작업 하나를 새로운 컨텍스트에서 수행한다.

```text
Planner
   ↓
작은 분석 작업 생성
   ↓
Fresh Executor
   ↓
실행 결과와 요약 반환
   ↓
Planner가 다음 작업 결정
```

한 Executor가 실패해도 결과는 Planner로 돌아간다. Planner는 같은 작업을 그대로 반복하지 않고 새로운 작업을 만든다.

공개된 [`agent.py`](https://github.com/NYU-LLM-CTF/nyuctf_agents/blob/main/nyuctf_multiagent/agent.py)를 보면 최대 round와 최대 비용을 제한하고 종료 사유도 구분한다.

```text
solved
giveup
cost
planner_rounds
error
unknown
```

Executor가 정상적인 작업 요약을 반환하지 못하면 한 번 더 요약을 요청한다. 그래도 실패하면 호출을 이어가지 않고 오류나 빈 결과로 처리한다.

Planner–Executor 전체는 Reverser에 비해 규모가 크다. 그래도 두 가지는 가져올 가치가 있다.

- Solver가 막혔을 때 기존 대화를 그대로 이어가지 않고 새 Solver를 실행한다.
- 새 Solver에는 전체 로그가 아니라 확인된 사실, 실패한 접근, 다음 전략만 전달한다.

새로운 agent 계층을 여러 개 만드는 대신 현재 Solver를 필요할 때 한 번 교체하는 구조만 추가하면 된다.

---

## 5. CAI의 중간 조향 방식

[CAI](https://github.com/aliasrobotics/cai)는 CTF만을 위한 프로젝트라기보다 범용 사이버보안 에이전트 프레임워크다.

Agent, Tool, Handoff, Guardrail, Human-in-the-loop 등으로 여러 보안 에이전트를 연결한다. 다음 에이전트는 LLM이 선택하거나 코드에 정한 순서대로 실행한다. [CAI multi-agent 문서](https://aliasrobotics.github.io/cai/multi_agent/)

CAI에서 눈여겨본 부분은 운영자가 중간에 개입하는 방식이다.

- 현재 대화 기록 확인
- 긴 컨텍스트 압축
- 대화 저장과 다시 불러오기
- 모델과 에이전트 변경
- 최대 turn과 비용 제한
- 실행 중단 후 새로운 지시 전달

현재 Reverser도 Solver 취소를 지원한다. 그러나 사용자의 한 줄 피드백을 상태에 남겨 새로운 Solver로 이어주는 흐름은 빠져 있다.

CAI의 전체 handoff, tracing, agent registry를 가져오면 프로젝트가 너무 커진다. CAI 저장소도 2026년 8월 archive되어 현재는 설계 참고 자료로 보는 편이 맞다.

Reverser에는 이 정도면 충분하다.

```text
현재 Solver 중단
      ↓
사용자의 짧은 방향 수정 저장
      ↓
Fresh Solver 실행
```

---

## 6. Muteki가 실패한 길을 기록하는 법

[Muteki](https://github.com/FishCodeTech/muteki)는 Pi, Codex, Claude, Cursor, OpenCode 등 여러 CLI 에이전트를 같은 CTF 문제에 투입하는 프로젝트다.

여러 Worker는 SQLite 기반의 blackboard를 공유한다. 자세한 구조는 [Muteki 동작 원리](https://github.com/FishCodeTech/muteki/blob/main/docs/%E5%B7%A5%E4%BD%9C%E5%8E%9F%E7%90%86.md)에 정리돼 있다.

blackboard에는 다음 데이터가 저장된다.

```text
Facts
Intents
Dead-ends
Flags
PoCs
```

가장 눈에 들어온 항목은 `Dead-end`다.

어떤 접근이 실패했다는 사실도 다른 Worker와 공유할 데이터로 취급한다. 새 Worker는 작업 전에 기존 dead-end를 읽고 같은 접근을 반복하지 않는다.

플래그 검증 기준도 구체적이다.

모델이 플래그라고 주장하는 것만으로는 부족하다. 해당 문자열이 실제 명령 출력에 그대로 존재해야 최종 플래그로 인정한다.

```text
모델이 flag 후보 발견
        ↓
실제 명령 출력 확인
        ↓
같은 문자열 존재
        ↓
Flag Gate 통과
```

Muteki의 전체 구조를 Reverser에 적용할 필요는 없다. 여러 모델, 다수 Worker, 2초 단위 Coordinator, intent claim, event bus는 현재 프로젝트의 규모와 맞지 않는다.

아래 두 가지면 지금 드러난 문제를 직접 다룰 수 있다.

- 실패한 접근을 `dead_ends`로 기록한다.
- 플래그를 실제 실행 결과와 연결한다.

---

## 7. 비교하며 확인한 Reverser의 장점

비교를 마치고 나니 부족한 부분만큼 현재 구조를 유지할 이유도 또렷해졌다.

### 7.1 명령마다 새 Worker를 사용한다

Reverser는 분석 명령마다 새로운 Docker Worker를 띄운 뒤 작업이 끝나면 폐기한다.

이전 명령에서 만들어진 프로세스나 환경 변경이 다음 명령에 남지 않는다. 분석 명령을 다시 실행하기도 쉽다.

### 7.2 브라우저와 바이너리 실행을 분리했다

로그인이 필요한 CTF 사이트는 Parent Pi의 Playwright browser에서 접근한다. 문제 바이너리를 실행하는 Docker Worker에는 네트워크가 없다.

웹 로그인 환경과 신뢰할 수 없는 바이너리 실행 환경을 같은 곳에 섞지 않는다.

### 7.3 실제 플래그는 Git에 올리지 않는다

실제 플래그와 비공개 Write-up은 `runs/`에 보관한다. 공개 Write-up에는 플래그를 제거한다.

연구용 benchmark agent보다 개인 CTF 풀이와 Git 관리에 직접 맞춘 부분이다.

### 7.4 공개 풀이는 검색하지 않는다

단순히 solve rate만 높이는 것보다 직접 분석과 학습을 우선한다.

활성 문제의 외부 풀이는 검색하지 않는다. Technique Memory는 30분이 지난 문제와 미해결 문제에서만 사용한다.

### 7.5 전체 구조가 작다

Reverser의 orchestration은 Pi Extension 하나와 Solver, Reviewer prompt로 구성된다. 여기에 Python Harness와 네 종류의 Docker Worker가 연결된다.

거대한 Coordinator와 event system이 없어도 전체 흐름이 한눈에 보인다.

---

## 8. 현재 코드에서 발견한 문제

비교 과정에서는 현재 코드 자체의 문제도 몇 가지 드러났다.

### 8.1 분석 명령 실패와 문제 풀이 실패가 섞여 있다

현재 구현에서는 분석 명령 하나의 non-zero 종료가 전체 상태를 `failed`로 바꿀 가능성이 있다.

CTF 분석에서는 다음과 같은 실패가 흔하다.

- `grep` 결과가 없음
- 잘못된 함수 주소 확인
- 디버거에서 예상과 다른 분기
- 테스트 스크립트의 검증 실패

이런 결과는 전체 풀이 실패가 아니라 새로운 observation으로 봐야 한다.

개별 명령 결과는 명령 기록에만 남겨야 한다. run의 `failed` 상태는 Docker나 Pi 실행 자체가 중단됐을 때만 사용한다.

### 8.2 Solver 종료 상태가 모호하다

Solver 프로세스가 정상 종료해도 문제 상태가 계속 `solving`이라면 실제 풀이가 끝난 상태는 아니다.

종료 상태는 아래처럼 분명히 구분할 필요가 있다.

```text
solved
unsolved
failed
```

### 8.3 플래그 후보와 실행 증거가 연결되지 않는다

현재는 플래그 문자열을 기록하면 바로 `solved` 상태가 된다.

앞으로는 성공한 명령 출력에 같은 문자열이 존재할 때만 기록한다. 이것만으로 정답을 검증할 수는 없지만, 적어도 실행 결과에서 나온 값이라는 provenance는 확인할 수 있다.

### 8.4 30분 외의 실행 예산이 없다

30분은 로컬 Technique Memory 검색을 허용하는 기준이지 실행 예산이 아니다. Solver 전체의 최대 turn, 도구 호출 수와 비용에는 별도 제한이 없다.

같은 작업을 오래 반복하지 않게 하려면 최소한 아래 값이 필요하다.

- 최대 agent turn
- 최대 tool run
- 최대 전체 실행 시간
- 종료 사유

---

## 9. 리버싱 Agent의 실패 조건

프로젝트 비교만으로는 리버싱 특유의 실패를 충분히 설명하기 어려웠다. H4C 글에서 정리한 실패 원인은 다섯 가지로 좁혀진다.

- 정적 분석 결과와 실제 실행 흐름이 다르다.
- 여러 함수에 흩어진 단서가 컨텍스트에서 빠진다.
- 설명은 만들지만 실행 가능한 입력이나 solver를 만들지 못한다.
- 처음 세운 가설을 반박하는 결과가 나와도 버리지 않는다.
- Decompiler 출력을 정답처럼 믿는다.

[Towards LLM-Resistant Software Protection](https://www.ndss-symposium.org/wp-content/uploads/bar2026-58.pdf)은 리버싱 과정을 Observe–Comprehend–Plan으로 나누고 보호 기법을 Concealment, Complication, Misdirection으로 구분했다. 연구진이 세 Agent에게 풀게 한 대상은 2025년 CTF의 x86-64 Linux ELF 24개였다. 이 실험에서는 training bias, over-trust, context limitation, plan persistence가 반복됐다.

Reverser의 현재 작업도 같은 세 단계로 펼칠 수 있다.

```text
Observe     Docker Worker의 stdout / stderr와 artifact
Comprehend  Solver가 로그를 해석하고 progress.md에 상태 저장
Plan        다음 profile과 분석 명령 선택
```

Observe 단계의 원본 로그는 이미 남는다. 빈틈은 Comprehend 단계에 있다. `progress.md`에는 tool run이 저장되지만 Decompiler에서 본 내용과 여러 실행 결과로 확인한 사실을 구분하지 않는다.

분석 도구가 많아도 첫 관찰이 틀리면 뒤의 추론까지 어긋난다. Decompiler가 보여준 의사 코드는 출발점이지 ground truth가 아니다. 어셈블리와 runtime trace가 다른 결과를 보여주면 앞의 해석부터 고쳐야 한다.

---

## 10. Reverser에 추가할 최소 피드백 데이터

Muteki의 기록 방식은 참고하되 별도의 blackboard와 event DB까지 만들 생각은 없다. 현재 사용 중인 `progress.md`에 관찰의 출처와 검증 상태를 추가하는 정도면 충분하다.

```json
{
  "observations": [
    {
      "text": "Decompiler shows check_flag calls verify",
      "source_run": 4,
      "source_kind": "decompiler",
      "status": "provisional"
    }
  ],
  "facts": [
    {
      "text": "argv[1] reaches compare at 0x4012d0",
      "evidence_runs": [6, 8],
      "status": "confirmed"
    }
  ],
  "hypotheses": [
    {
      "text": "입력은 0x37과 XOR된다",
      "test": "세 입력으로 solver 결과와 runtime trace 비교",
      "falsifier": "trace의 변환 바이트가 예측값과 다름",
      "status": "testing"
    }
  ],
  "dead_ends": [
    {
      "text": "UPX unpack 시도",
      "reason": "packed binary가 아님",
      "evidence_run": 3
    }
  ],
  "analysis_path": {
    "input": "argv[1]",
    "transforms": ["sub_401180"],
    "sink": "memcmp@0x4012d0",
    "unknown_edges": ["global table initialization"]
  },
  "exit_reason": null
}
```

위 값은 저장 형태를 설명하기 위한 예시다.

명령 출력에서 본 내용은 바로 fact에 넣지 않는다. 먼저 observation으로 저장한다. `source_kind`는 `static`, `decompiler`, `assembly`, `runtime`, `solver` 정도만 사용한다.

처음 발견한 observation은 `provisional`이다. 다른 분석 경로에서 같은 내용을 확인하면 `confirmed`로 올리고 반대 증거가 나오면 `contradicted`로 바꾼다. confidence 점수는 넣지 않는다. 모델이 근거 없이 0.8을 붙여도 증거가 늘어나는 것은 아니기 때문이다. 어떤 run이 뒷받침하거나 반박했는지만 남긴다.

여러 함수에 흩어진 로직은 `analysis_path`로 짧게 연결한다. [ReCopilot](https://arxiv.org/abs/2505.16366)은 변수 데이터 흐름과 call graph를 함께 사용해 함수 이름 복원과 type inference 성능을 13% 개선했다고 보고했다.

ReCopilot 전체나 별도의 graph database를 추가하지는 않는다. 입력이 어디서 들어오고 어떤 변환을 거쳐 어디서 비교되는지만 적는다. 연결하지 못한 구간은 `unknown_edges`에 남긴다. Fresh Solver는 긴 대화 대신 이 경로와 관련 로그부터 읽는다.

모든 명령에 장문의 요약을 붙일 필요도 없다. 새로운 사실이 확인되거나 가설이 반증되거나 분석 전략이 바뀔 때만 `progress.md`를 갱신한다.

---

## 11. 반증 조건과 막힘 감지

가설에는 내용과 상태만 적지 않고 `test`와 `falsifier`를 함께 붙인다. 무엇을 실행해 확인할지와 어떤 결과가 나오면 가설을 버릴지를 먼저 정하는 방식이다.

[Failing to Falsify](https://arxiv.org/abs/2604.02485)는 규칙 추론 과제에서 11개 LLM의 확인 편향을 조사했다. 반례를 찾으라는 지시를 주자 평균 규칙 발견률이 42%에서 56%로 높아졌다. 리버싱 성능을 직접 측정한 연구는 아니지만 가설마다 반증 조건을 적는 설계에는 참고할 만하다.

실행 결과가 falsifier와 맞으면 기존 가설을 조용히 덮어쓰지 않는다. 상태를 `rejected`로 바꾸고 `dead_ends`에 근거 run을 남긴다. 막힘을 감지할 때는 같은 명령을 반복했는지뿐 아니라 이미 반증된 가설을 다시 사용했는지도 확인한다.

현재는 30분이라는 시간 하나만 보고 Research 단계로 전환한다. 앞으로는 시간과 별개로 새로운 정보가 생겼는지도 확인하려고 한다.

막힘의 신호로 삼을 조건은 다음과 같다.

- 같은 명령을 두 번 이상 반복한다.
- 최근 5개 분석 명령에서 새로운 fact가 없다.
- 비슷한 출력과 같은 exit code가 반복된다.
- 도구를 사용하지 않고 같은 결론만 반복한다.

첫 번째 감지에서는 현재 Solver에게 이미 실패한 접근을 알려준다.

두 번째 감지에서는 기존 Solver를 계속 실행하지 않는다. Reviewer가 현재 상태를 짧게 정리한다.

```text
Solver 실행
   ↓
새로운 증거가 있는가?
   │
   ├── Yes → 계속 분석
   │
   └── No
        ↓
   반복 접근 경고
        ↓
   다시 막힘
        ↓
   Fresh Reviewer
        ↓
   다음 전략 1~3개 정리
        ↓
   Fresh Solver로 한 번 재시도
```

새 Solver에는 이전 Pi 대화 전체를 넘기지 않는다.

아래 정보만 전달한다.

- 검증된 사실
- 현재 가설
- 실패한 접근
- 관련 로그와 artifact 경로
- Reviewer가 제안한 다음 전략

이렇게 하면 컨텍스트 사용량이 줄고 같은 실패를 반복할 가능성도 낮아진다.

도구 전환도 정해진 순서보다 실패 원인에 맞춰 결정한다.

```text
정적 결과와 실행이 다름     → runtime trace / memory dump
함수 사이 연결이 끊김       → xref / call graph / data flow
Decompiler 해석이 불확실함  → assembly와 branch 비교
로직은 알지만 답이 없음     → solver / keygen / test harness
가설이 반복됨               → counterexample test / Fresh Reviewer
```

모든 문제에 Ghidra, GDB, angr를 차례로 실행하지 않는다. 현재 observation을 확인하거나 반박하는 데 필요한 도구만 선택한다.

---

## 12. 설명이 아니라 실행 결과로 끝낸다

Agent가 검증 함수를 정확히 설명했다고 해서 문제를 푼 것은 아니다. 후보 입력, keygen, patch, emulator 가운데 하나는 실제 바이너리에서 확인해야 한다.

[CrackMeBench](https://arxiv.org/abs/2605.10597)는 외부의 실행 가능한 oracle로 제출물을 판정한다. 네트워크가 차단된 Linux Docker에서 원본 실행 파일을 사용하며 모델의 설명이 아니라 프로그램이 받아들인 입력과 생성 artifact를 평가한다.

Reverser의 최소 Result Gate는 실행 결과 provenance를 확인하는 정도로 구성한다.

```json
{
  "candidate": "[REDACTED]",
  "verification_command": "./chall \"$CANDIDATE\"",
  "evidence_run": 12,
  "exit_code": 0,
  "accepted": true,
  "artifact_sha256": "..."
}
```

현재 `record_flag`는 문자열만 기록해도 상태를 `solved`로 바꾼다. 구현할 Result Gate에서는 성공한 Docker Worker run의 출력에 같은 문자열이 있어야 한다. 별도 검증 상태는 저장하지 않고 기존 `flags`와 `tool_runs`만 사용한다.

문제에 자동 판정기가 없다면 로컬 실행만으로 정답을 완전히 보장하지 못할 수도 있다. 이 경우 Reviewer가 검증 방법과 남은 제한을 함께 기록한다.

---

## 13. Reviewer의 피드백을 다음 문제에 반영하기

현재 Reviewer는 아래 내용을 작성한다.

- 풀이가 실제 로직과 맞는지
- 불필요하게 오래 걸린 부분
- 놓친 단서
- 더 빠른 명령이나 도구
- 다음 문제에서 재사용할 기법

Reviewer가 새 도구를 추천했다고 바로 Dockerfile에 설치하지는 않는다. 한 문제에서만 쓸 도구인 경우가 있고 이미지 크기와 공급망 관리 비용도 계속 늘어나기 때문이다.

대신 아래 기준을 적용하려고 한다.

```text
서로 다른 문제에서 같은 도구가 2회 이상 제안됨
        +
기존 방식보다 빠르다는 실행 근거가 있음
        ↓
사용자가 Dockerfile 추가 여부 결정
```

모델이 제안한 내용을 곧바로 적용하는 것은 자가 개선이라 보기 어렵다. 여러 문제에서 효과가 반복해서 확인된 변경만 반영하는 편이 더 안전하다.

---

## 14. 3편에서 구현하고 검증할 순서

현재 코드에는 이 설계가 아직 들어가 있지 않다. 3편에서는 아래 순서로 실제 구현을 진행할 예정이다.

1. 분석 명령의 non-zero 종료와 전체 run의 `failed` 상태를 분리한다.
2. `solved`, `unsolved`, `failed`를 구분하고 `failed`의 종료 사유를 기록한다.
3. `record_flag`에 실행 증거를 요구하는 Result Gate를 추가한다.
4. `progress.md`에 observations, facts, hypotheses, dead_ends, analysis_path를 저장한다.
5. 가설의 test와 falsifier를 기록하고 반증된 가설을 dead-end로 옮긴다.
6. 새 증거가 없는 상태를 감지해 Fresh Reviewer와 Fresh Solver로 한 번 전환한다.

변경 효과는 비공개 리버싱 문제 8~15개로 회귀 테스트한다. 단순 문자열 비교, 여러 함수에 흩어진 검증 로직, runtime에서 복호화되는 로직을 섞는다.

solve rate만 보면 틀린 후보를 자신 있게 제출하는 문제를 놓칠 수 있다. 아래 값도 함께 확인한다.

- 검증된 결과의 비율
- 첫 confirmed fact까지 걸린 시간
- contradicted observation 수
- 반복 명령 수와 전체 tool run
- Solver에 전달한 컨텍스트 크기
- Fresh Solver 전환 전후의 새 증거 수

아직 구현과 실험 전이므로 이 글에는 개선 수치를 적지 않는다. 같은 문제와 예산으로 변경 전후를 비교하고 로그까지 다시 확인한 뒤 결과를 기록한다.

---

## 15. 추가하지 않을 기능

다른 프로젝트를 조사하다 보면 넣고 싶은 기능이 계속 생긴다. 그래도 아래 기능은 현재 Reverser에 추가하지 않는 편이 낫다고 판단했다.

- 여러 모델을 동시에 실행하는 swarm
- 2초마다 동작하는 Coordinator
- 별도의 JSONL event bus
- ReCopilot 모델 전체와 별도의 graph database
- IDA나 GDB의 상시 세션
- 모델이 임의로 정한 confidence 점수
- 서버 기반 실시간 dashboard
- OpenTelemetry 전체 tracing
- vector database와 embedding memory
- 모델 추천에 따른 자동 도구 설치
- 자동 CTF flag 제출
- 모든 CTF 분야와 도구의 한 번에 통합

지금 필요한 일은 에이전트와 저장소를 늘리는 게 아니다. 이미 실행한 분석에서 무엇을 배웠고 무엇이 틀렸는지 정확히 남겨야 한다.

---

## 16. 최종적으로 바꿀 피드백 루프

최종적으로 만들고 싶은 흐름은 아래와 같다.

```text
Triage
  ↓
Observation 저장
  ↓
Observation Gate
  ├─ provisional → assembly / runtime 확인
  ├─ contradicted → 기존 해석 수정
  └─ confirmed   → Fact
  ↓
Analysis Path 갱신
  ↓
Hypothesis + Test + Falsifier
  ↓
Docker 실행
  ├─ 반증됨  → Dead-end
  ├─ 새 증거 → 계속 분석
  └─ 후보 발견
       ↓
Executable Result Gate
  ├─ 통과 → Solved
  └─ 실패 → 가설 갱신

새 증거가 없는 상태가 반복됨
  ↓
Fresh Reviewer가 사실과 dead-end 요약
  ↓
Fresh Solver로 한 번 재시도
  ↓
30분 이후라면 풀이 검색 허용
```

Reviewer를 계속 추가하는 것이 핵심은 아니다.

핵심은 observation을 바로 사실로 믿지 않고 반증 가능한 가설과 실제 실행 결과를 다음 판단에 연결하는 것이다. 증거가 늘지 않을 때만 새로운 컨텍스트로 전략을 바꾼다.

---

## 17. 마무리

다른 CTF 하네스와 리버싱 Agent 연구를 함께 살펴보니 Reverser의 빈틈은 여섯 가지로 정리됐다.

- 관찰과 확인된 사실을 구분하지 않는다.
- 실패한 접근과 반증된 가설을 기억하지 않는다.
- 막힘을 30분이라는 시간으로만 판단한다.
- 플래그 후보와 실제 실행 증거가 연결되지 않는다.
- Solver의 종료 사유와 실행 예산이 명확하지 않다.
- 새 Solver에 넘길 컨텍스트의 범위가 정해져 있지 않다.

반대로 Docker 격리, 명령별 새 Worker, 브라우저와 바이너리 실행 환경 분리, 플래그 보호, 30분 동안의 직접 분석 정책은 그대로 유지한다. 피드백 루프를 추가하려고 현재 장점을 버릴 이유는 없다.

새로 필요한 데이터는 아래와 같다.

```text
Observations
Facts
Hypotheses + Test + Falsifier
Dead-ends
Analysis Path
Flag Evidence
Exit Reason
```

이 데이터는 별도의 거대한 blackboard가 아니라 기존 `progress.md`와 stdout, stderr 로그에 연결한다. 새 증거가 없을 때만 Fresh Reviewer가 상태를 정리하고 Fresh Solver로 한 번 전환한다.

여기까지는 설계다. 현재 코드에는 Observation Gate, falsifier, Result Gate, 막힘 감지가 구현되어 있지 않다. 3편에서는 이 설계를 실제 코드에 적용하고 같은 문제와 예산으로 변경 전후를 비교할 예정이다.

Reverser의 목표는 가장 많은 에이전트를 실행하는 하네스가 아니다. 문제를 풀며 얻은 관찰, 실제 증거, 실패를 다음 판단에 연결하고 그 과정을 나중에 다시 확인하는 작은 리버싱 작업 환경을 만드는 것이다.
