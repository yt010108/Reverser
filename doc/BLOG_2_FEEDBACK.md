# [Project] Reverser 제작: 다른 CTF Harness와 비교하고 피드백 루프 다시 설계하기 - 2

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

이번 글에서는 공개된 CTF 하네스와 보안 에이전트 프로젝트를 비교하며 다섯 가지를 살펴본다.

- 안 풀리는 문제를 어떻게 감지하는가
- 실패한 접근을 어떻게 기록하는가
- 새로운 에이전트에 어떤 정보만 전달하는가
- 플래그가 실제 실행 결과인지 어떻게 검증하는가
- 어떤 기능은 Reverser에 넣지 않는 것이 좋은가

비교 대상은 `ctf-skills`, EnIGMA, D-CIPHER, CAI, Muteki다.

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

### 7.4 처음 30분은 공개 풀이를 검색하지 않는다

단순히 solve rate만 높이는 것보다 직접 분석과 학습을 우선한다.

외부 풀이와 Technique Memory는 30분이 지난 문제와 미해결 문제에서만 사용한다.

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
incomplete
```

### 8.3 플래그 후보와 실행 증거가 연결되지 않는다

현재는 플래그 문자열을 기록하면 바로 `solved` 상태가 된다.

앞으로는 그 값을 확인한 명령 출력도 함께 기록한다. 실제 출력에 같은 문자열이 존재할 때만 해결로 인정하는 것이 맞다.

### 8.4 30분 외의 실행 예산이 없다

30분은 공개 풀이 검색을 허용하는 기준이지 실행 예산이 아니다. Solver 전체의 최대 turn, 도구 호출 수와 비용에는 별도 제한이 없다.

같은 작업을 오래 반복하지 않게 하려면 최소한 아래 값이 필요하다.

- 최대 agent turn
- 최대 tool run
- 최대 전체 실행 시간
- 종료 사유

---

## 9. Reverser에 추가할 최소 피드백 데이터

Muteki의 기록 방식은 참고하되 별도의 blackboard와 event DB까지 만들 생각은 없다.

현재 사용 중인 `progress.md`의 내부 상태에는 네 가지 정도만 보태면 된다.

```json
{
  "facts": [
    {
      "text": "check_flag는 변환된 16바이트를 비교한다",
      "evidence_run": 7
    }
  ],
  "hypotheses": [
    {
      "text": "입력값을 0x37과 XOR한다",
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
  "exit_reason": null
}
```

모든 명령에 장문의 요약을 붙이지는 않는다. 새로운 사실이 확인되거나 가설이 반증되거나 분석 전략이 바뀔 때만 갱신하면 된다.

---

## 10. 안 풀리는 문제를 감지하는 기준

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

---

## 11. Reviewer의 피드백을 다음 문제에 반영하기

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

## 12. 추가하지 않을 기능

다른 프로젝트를 조사하다 보면 넣고 싶은 기능이 계속 생긴다. 그래도 아래 기능은 현재 Reverser에 추가하지 않는 편이 낫다고 판단했다.

- 여러 모델을 동시에 실행하는 swarm
- 2초마다 동작하는 Coordinator
- 별도의 JSONL event bus
- 서버 기반 실시간 dashboard
- OpenTelemetry 전체 tracing
- vector database와 embedding memory
- 모델 추천에 따른 자동 도구 설치
- 자동 CTF flag 제출
- 모든 CTF 분야와 도구의 한 번에 통합

지금 필요한 일은 에이전트와 저장소를 늘리는 게 아니다. 이미 실행한 분석에서 무엇을 배웠고 무엇이 틀렸는지 정확히 남겨야 한다.

---

## 13. 최종적으로 바꿀 피드백 루프

최종적으로 만들고 싶은 흐름은 아래와 같다.

```text
Solver가 분석 명령 실행
        ↓
실제 stdout / stderr 저장
        ↓
Fact / Hypothesis / Dead-end 갱신
        ↓
플래그 후보가 실제 출력에 있는가?
        │
        ├── Yes → 증거 검증 → Solved → Reviewer
        │
        └── No
             ↓
        새로운 정보가 있는가?
             │
             ├── Yes → 계속 분석
             │
             └── No → 막힘 감지
                        ↓
                  Fresh Reviewer
                        ↓
                  Fresh Solver 재시도
                        ↓
              30분 이후라면 풀이 검색 허용
```

Reviewer를 계속 추가하는 것이 핵심은 아니다.

실제 실행 결과에서 새로운 증거가 생겼는지 확인하고 증거가 늘지 않을 때만 새로운 컨텍스트로 전략을 바꾸는 것이 핵심이다.

---

## 14. 마무리

다른 CTF 하네스와 비교한 뒤 Reverser의 빈틈은 네 가지로 좁혀졌다.

- 실패한 접근을 기억하지 않는다.
- 막힘을 시간으로만 판단한다.
- 플래그와 실제 실행 증거가 연결되지 않는다.
- Solver의 종료 사유와 실행 예산이 명확하지 않다.

동시에 현재 구조를 유지할 이유도 확인했다.

- 바이너리는 네트워크가 차단된 Docker Worker에서만 실행한다.
- 명령마다 새로운 Worker를 사용한다.
- 브라우저 로그인과 바이너리 실행 환경을 분리한다.
- 실제 플래그와 비공개 Write-up을 Git에서 제외한다.
- 처음 30분은 공개 풀이보다 직접 분석을 우선한다.
- 전체 구조가 작아서 직접 확인하고 수정하기 쉽다.

다른 프로젝트의 구조를 그대로 복사하기보다 네 가지만 현재 구조에 추가하려고 한다.

```text
Facts
Hypotheses
Dead-ends
Flag Evidence
```

그리고 새 증거가 없을 때만 Reviewer와 fresh Solver를 한 번 사용한다.

Reverser의 목표는 가장 많은 에이전트를 실행하는 하네스가 아니다. 문제를 풀며 얻은 실제 증거와 실패를 다음 판단에 연결하고 그 과정을 나중에 다시 확인하는 작은 리버싱 작업 환경을 만드는 것이다.
