# [Project] Reverser 제작: 가설 검증 루프와 비동기 Reviewer 구현 - 3

2편에서는 Reverser의 피드백 구조를 다시 살펴봤다.

Solver가 처음 세운 가설을 계속 붙잡는 문제, 분석 명령 실패와 전체 풀이 실패가 섞이는 문제, 플래그 후보와 실제 실행 근거가 연결되지 않는 문제를 정리했다. 이를 해결하기 위해 observation, fact, dead-end, Fresh Solver까지 여러 구조를 고려했다.

실제 구현 단계에서는 범위를 다시 줄였다.

에이전트 상태를 많이 나누면 정보는 잘 남지만, 같은 내용을 여러 필드에 중복해 저장하게 된다. 모델이 그 상태를 모두 관리하려면 프롬프트와 도구도 커진다.

그래서 3편의 구현 목표를 다음 네 가지로 정했다.

- Parent Pi는 Solver를 기다리지 않는다.
- Solver는 한 번에 하나의 반증 가능한 가설만 검증한다.
- 플래그는 성공한 실행 근거와 함께 저장한다.
- Reviewer는 풀이 중이 아니라 Solver 종료 후에 독립적으로 검토하고 Write-up을 작성한다.

이 글에서는 이 네 가지를 현재 코드에 어떻게 반영했는지 정리한다.

---

## 1. Parent Pi를 Solver의 대기 루프에서 빼냈다

초기 구조에서는 Parent Pi가 자식 Solver Pi를 실행한 뒤 종료할 때까지 `await`했다.

이 구조는 단순하지만 Solver가 오래 걸리면 Parent도 명령을 받지 못한다. 문제 여러 개를 가져오거나 다른 상태를 확인하는 작업과도 맞지 않았다.

현재 `reverser_solve`는 Orca 서브 터미널을 나눈 뒤 그 안에서 별도 Pi 프로세스를 시작한다.

```text
Parent Pi
   │
   ├─ reverser_solve(challenge_id)
   │       └─ Orca 터미널에 Solver Pi spawn
   │
   └─ 즉시 반환 → 다음 명령 수신
```

첫 Solver는 Parent 오른쪽에 열고, 추가 Solver는 오른쪽 영역에 쌓이도록 했다. 저장해 둔 Orca terminal handle이 닫힌 터미널을 가리키면 Parent 기준 분할을 한 번 다시 시도한다.

Solver의 긴 대화와 도구 출력은 Parent 컨텍스트로 복사하지 않는다. Parent가 받는 것은 시작 응답과 완료 메시지뿐이다.

---

## 2. 주기적 조회 대신 JSON 변경 이벤트를 사용했다

Parent가 Solver 상태를 2초마다 확인하는 구조는 추가하지 않았다.

각 문제 폴더에 `solver.json`을 두고, Solver 시작과 종료 시에만 원자적으로 교체한다.

```json
{
  "challenge_id": "rev-example-1234abcd",
  "status": "running",
  "terminal": "ORCA_TERMINAL_ID",
  "result": null
}
```

풀이가 끝나면 `status`는 `done`, `result`는 `solved`, `unsolved`, `failed` 중 하나가 된다.

Parent의 Pi Extension은 `fs.watch`로 해당 폴더를 감시한다. 파일 변경 이벤트가 오면 JSON을 한 번 읽고, `done`일 때만 follow-up 큐에 메시지를 넣는다.

```text
[Solver] rev-example-1234abcd 완료 · solved
```

이 구조에서는 상태가 바뀌지 않으면 아무 작업도 하지 않는다. 주기적 조회를 위한 Coordinator나 event bus도 필요하지 않았다.

---

## 3. Solver 흐름을 정찰, 가설, 검증으로 나눴다

기존 Solver prompt는 사용할 도구와 추천 순서를 설명했지만, 가설을 언제 세우고 언제 버릴지를 강제하지 않았다.

현재 흐름은 세 단계다.

```text
초기 정찰
  ↓ entry point → main 계열 경로 확인
flag 관련 후보 기록
  ↓
가설 하나 제안
  ↓
선언한 범위만 검증
  ├─ confirmed
  ├─ rejected
  └─ inconclusive
       ↓
  다음 가설 제안
```

정찰 단계에서는 가설을 만들지 않는다. 파일 형식과 보호 기법을 확인한 뒤 실제 분석 run으로 entry point에서 main 계열 함수까지 따라가고 입력, 비교, 성공 문자열, 의심 함수를 본다. Ghidra, GDB, angr를 순서대로 모두 실행하지 않고 현재 질문에 필요한 도구만 고른다.

그 결과에서 flag 검증 또는 생성과 관련된 후보를 `reverser_recon`에 저장한다. 후보와 정찰에는 모두 성공한 run 근거가 필요하다.

```json
{
  "entry_point": "0x401000",
  "main": "0x401120",
  "evidence_runs": [2],
  "flag_candidates": [
    {
      "target": "check_flag",
      "reason": "성공 문자열 출력 직전에 호출된다",
      "evidence_runs": [2]
    }
  ]
}
```

recon 전에는 가설을 만들 수 없고, recon 후에는 가설 없이 분석 명령을 더 실행할 수 없다. 정찰이 끝나면 후보 하나를 target으로 `reverser_hypothesis`에 저장한다.

```json
{
  "id": "h1",
  "target": "check_flag",
  "parent_id": null,
  "claim": "입력의 각 바이트를 0x37과 XOR한다",
  "test": "세 입력의 runtime trace와 예측값을 비교한다",
  "falsifier": "trace의 변환 결과가 예측값과 다르다",
  "exhaustion": "16바이트 전체를 확인한다",
  "status": "testing",
  "evidence_runs": []
}
```

`claim`만 있으면 모델은 자신이 올바른 지지 증거만 찾기 쉽다. 그래서 가설을 제안할 때 `test`, `falsifier`, `exhaustion`을 모두 필수로 받는다.

- `test`: 무엇을 실행해 확인할지
- `falsifier`: 어떤 결과가 나오면 가설을 버릴지
- `exhaustion`: 어디까지 확인하면 해당 가설의 검사가 끝나는지

가설은 `parent_id`로 트리를 이룬다. non-rejected 가설을 구체화하면 child, 같은 단계의 대안은 sibling이다. rejected 노드 아래에는 child를 만들 수 없고 한 번에 `testing` 노드는 하나뿐이다. 이 트리는 `progress.md`에서 바로 볼 수 있다.

활성 가설이 있으면 `reverser_exec`에 해당 `hypothesis_id`를 넣어야 한다. 다른 ID를 넣거나 아예 넣지 않으면 Harness가 명령을 거부한다.

검증을 마칠 때도 실제 tool run을 지정해야 한다. 해당 run이 다른 가설에 연결된 것이면 상태를 바꿀 수 없다.

가설 단계는 별도 필드로 중복 저장하지 않는다.

- recon 기록 전이면 `recon`
- `testing` 가설이 있으면 `verify`
- recon이 있고 활성 가설이 없으면 `hypothesize`

이렇게 가설 이력에서 현재 단계를 계산해 상태 중복을 줄였다.

---

## 4. 가설 생성과 검증의 역할을 모델 단위로 나눴다

가설을 세우는 일과 정해진 범위를 검사하는 일은 성격이 다르다.

가설 생성은 여러 관찰을 연결해 가능성을 정렬해야 한다. 반면 검증은 선언된 테스트와 종료 범위를 따르는 작업에 가깝다.

그래서 하나의 Solver Pi 컨텍스트를 유지하면서 단계에 따라 모델을 교체하도록 했다.

```text
Parent에서 상속한 Planner 모델
  ↓ 초기 정찰과 가설 제안
검증 모델
  ↓ 선언된 범위 검사
Planner 모델로 복귀
  ↓ 결과 해석과 다음 가설
```

`reverser_hypothesis(action="propose")`가 성공하면 Pi의 `setModel`로 검증 모델에 전환한다. `resolve`가 성공하면 기존 모델과 thinking level을 복원한다.

현재 기본 검증 모델은 Luna지만 Workflow는 특정 모델에 의존하지 않도록 분리했다. 나중에 확장 설정에서 다른 모델로 교체할 수 있다.

새 Solver를 매번 시작하지 않은 이유는 컨텍스트 비용 때문이다. 검증이 끝날 때마다 새 Pi에 모든 로그를 다시 넘기면 입력 토큰이 계속 늘어난다. 같은 컨텍스트에서 모델만 바꾸면 정찰 결과를 복사하지 않고도 역할을 나눌 수 있다.

---

## 5. 플래그와 evidence run을 함께 저장한다

2편에서 가장 명확했던 문제는 플래그 provenance였다.

모델이 만든 문자열을 바로 플래그로 저장하면 설명은 그럴듯하지만 실제 프로그램에서 나온 값인지 확인할 수 없다.

`reverser_record_flag`는 다음 조건을 모두 확인한다.

- `evidence_run`이 존재한다.
- 해당 run의 exit code가 0이다.
- timeout된 run이 아니다.
- stdout과 stderr 중 하나에 같은 플래그 문자열이 있다.

조건을 통과하면 플래그와 run 번호를 `flag_evidence`에 함께 저장한다.

```json
{
  "flag_evidence": [
    {
      "flag": "CTF{...}",
      "evidence_run": 12
    }
  ]
}
```

이 검증은 사이트 제출과 같지 않다. 로컬 프로그램이 해당 값을 출력했다는 provenance를 보장하는 최소 gate다. 정답 로직 전체가 맞는지는 뒤에 시작되는 Reviewer가 다시 확인한다.

---

## 6. Solver는 풀이만 하고 Reviewer가 Write-up을 쓴다

초기에는 Solver가 플래그를 찾고 Write-up까지 작성했다. 그 뒤 Reviewer가 같은 Write-up을 다시 읽고 수정했다.

이 구조에서는 두 에이전트의 역할이 겹친다. Solver는 이미 긴 분석 컨텍스트를 갖고 있고, 그 상태에서 자신의 풀이를 설명하면 논리적 비약을 놓치기 쉽다.

현재 역할은 다음처럼 나뉜다.

```text
Solver
  ├─ 정찰
  ├─ 가설과 검증
  └─ flag + evidence_run 저장

Reviewer
  ├─ 플래그 근거 검토
  ├─ 가설과 결론 사이의 비약 검토
  ├─ 불필요하게 오래 걸린 분석 정리
  ├─ 놓친 단서와 재사용 기법 정리
  └─ Write-up 또는 review 작성
```

Solver가 끝나면 Parent의 watcher가 `solver.json` 변경을 받는다. 그 뒤 Orca의 `terminal wait --for tui-idle`로 Solver Pi가 종료하고 터미널이 빈 상태가 될 때까지 기다린다.

터미널이 비면 같은 터미널에 다음 명령을 보낸다.

```text
pi -p --no-session --append-system-prompt .pi/agents/reviewer.md ...
```

즉, 터미널은 재사용하지만 Pi 세션과 컨텍스트는 새로 시작한다. Reviewer의 상태는 `reviewer.json`에 별도로 기록한다.

```text
[Reviewer] rev-example-1234abcd 완료 · writeup.md
```

Reviewer가 완료되어도 Parent는 긴 검토 내용을 받지 않고 완료 메시지만 받는다.

---

## 7. 모든 문제 결과를 runs에만 남겼다

예전 Write-up 관리자는 두 파일을 만들었다.

- `runs/.../reports/writeup.private.md`
- `writeups/.../writeup.md`

공개본을 만들 때 알고 있는 플래그와 플래그 형태의 문자열을 제거했다. 하지만 현재 목표는 자동 공개가 아니라 로컬 분석과 검토다.

그래서 공개본 생성과 redaction 로직을 제거했다. 새로 생성하는 문제 결과는 모두 Git에서 제외된 `runs/`에만 남는다.

```text
runs/
└── [event/]<challenge_id>/
    ├── progress.md
    ├── solver.json
    ├── reviewer.json
    ├── original/
    ├── work/
    ├── output/
    └── reports/
        ├── writeup.md   # solved
        └── review.md    # unsolved / failed
```

`solved`면 Reviewer가 실제 플래그를 포함한 `writeup.md`를 작성한다. `unsolved` 또는 `failed`면 막힌 원인과 다음 가설을 `review.md`에 남긴다.

기존 `writeups/`에 있던 파일은 삭제하지 않았지만 새 Workflow는 그 경로에 파일을 추가하지 않는다.

---

## 8. Parent가 로컬 project와 event를 JSON으로 읽는다

event가 있는 문제는 `runs/<event>/<challenge_id>/`, event가 없는 문제는 `runs/<challenge_id>/`에 저장한다.

문제가 늘어나면 Parent가 모든 `progress.md`를 직접 읽는 방식은 비용이 커진다. 기존 `reverser_list`는 전체 상태를 반환해 출력도 컸다.

현재 `reverser_list`는 다음 형태의 compact JSON을 반환한다.

```json
{
  "project": {
    "name": "Reverser",
    "root": "C:/.../Reverser"
  },
  "events": ["Event A", "Event B"],
  "challenges": [
    {
      "challenge_id": "rev-example-1234abcd",
      "title": "Example",
      "event": "Event A",
      "status": "solved",
      "architecture": "x86_64",
      "bits": 64,
      "updated_at": "...",
      "elapsed_seconds": 120,
      "flag_count": 1
    }
  ]
}
```

Parent는 전체 폴더를 전수 검색하지 않고 이 목록에서 challenge ID를 고른 뒤 필요한 문제의 `reverser_status`만 읽는다.

---

## 9. Solver의 파일 범위는 prompt로 줄였다

Solver Pi는 Reverser 프로젝트 루트에서 실행되므로 기본 파일 도구만 보면 다른 문제와 프로젝트 코드도 읽을 수 있다.

파일 도구 자체에 강제 샌드박스를 추가하지는 않았다. 그 대신 `reverser_status`가 정확한 `workspace`를 반환하고 Solver prompt에서 다음 규칙을 지정한다.

- `read`, `write`, `edit`, `grep`, `find`, `ls`는 workspace 내부에만 사용한다.
- 다른 문제, `.pi`, 홈 디렉터리와 환경 파일을 보지 않는다.
- 바이너리는 호스트에서 실행하지 않는다.

이것은 안전 규칙이지 강제된 filesystem security boundary는 아니다. 현재 단계에서는 도구를 새로 감싸 코드를 늘리기보다 작업 범위를 명확하게 전달하는 방식을 선택했다.

---

## 10. 2편의 설계에서 의도적으로 뺀 것

2편에서는 아래 상태를 각각 나누는 구조를 고려했다.

- observations
- facts
- dead_ends
- analysis_path
- Fresh Reviewer
- Fresh Solver
- 반복 명령과 새 증거 감지
- 최대 turn과 tool run 예산

현재 구현에는 이 구조를 넣지 않았다.

가설의 `claim`, `test`, `falsifier`, `exhaustion`, `observation`, `evidence_runs`만으로도 어떤 전제를 검사했고 왜 버렸는지를 보존할 수 있다. 별도 observation과 fact를 함께 두면 같은 근거를 여러 곳에 동기화해야 한다.

막힘 감지도 일단 추가하지 않았다. 새 증거를 얻었는지 자동으로 판정하려면 상태 비교와 추가 요약 로직이 필요하다. 잘못된 감지는 정상적인 탐색을 중단시킬 수도 있다.

도구 사용 횟수 제한도 두지 않았다. 대신 한 가설의 검사 범위를 `exhaustion`에 명시해 검증이 무한히 늘어나지 않도록 했다.

이 선택은 2편의 설계가 틀렸다는 뜻이 아니다. 가설 이력으로 부족한 사례가 실제로 반복될 때 다음 상태를 추가하는 편이 작은 Harness를 유지하기 쉽다.

---

## 11. 테스트로 확인한 것

현재 테스트는 다음 행동을 확인한다.

- event가 있는 문제도 정확한 workspace를 반환한다.
- entry 정찰 run과 flag 후보 없이 가설을 만들 수 없다.
- 가설 target과 parent가 recon 및 기존 트리와 일치해야 한다.
- 활성 가설 ID 없이 검증 명령을 실행할 수 없다.
- 가설 검증 run이 다른 가설의 근거로 사용되지 않는다.
- 플래그가 실제 출력에 없으면 `solved`로 바뀌지 않는다.
- 개별 분석 명령의 non-zero exit가 전체 문제를 `failed`로 바꾸지 않는다.
- Solver와 Reviewer의 JSON 상태가 `running`과 `done`을 구분한다.
- solved Reviewer는 `writeup.md`, unsolved Reviewer는 `review.md`를 생성한다.
- public writeup 폴더를 새로 생성하지 않는다.
- Parent용 catalog가 project, event, challenge를 compact JSON으로 반환한다.
- Windows의 CP949 기본 출력에서도 CLI JSON을 UTF-8로 출력한다.
- Pi Extension이 오프라인 로드 검사를 통과한다.

현재 전체 Python 테스트 31개를 실행했고 30개가 통과했다. 한 개는 환경에 따라 skip된다.

아직 여러 비공개 리버싱 문제에 대한 변경 전후 solve rate를 측정하지는 않았다. 따라서 이 글에서 성능이 높아졌다고 단정하지 않는다. 현재 확인한 것은 Workflow가 의도한 상태 전이를 강제하고 근거를 남긴다는 점이다.

---

## 12. 현재 전체 Workflow

현재 Reverser의 전체 흐름은 다음과 같다.

```text
Parent Pi
  ├─ reverser_list로 project / event / challenge 확인
  ├─ Playwright로 문제 가져오기
  ├─ reverser_import_local
  └─ reverser_solve → 즉시 반환
                         │
Orca Solver Pi           │
  ├─ entry → main 정찰   │
  ├─ flag 후보 기록      │
  ├─ target 가설 제안    │
  ├─ 검증 모델로 전환   │
  ├─ hypothesis_id 검증 │
  ├─ 결과 기록 후 복귀   │
  ├─ 반증/불확실 → child/sibling 가설
  └─ flag + evidence_run 또는 미해결 사유
                         │
solver.json done         │
  └─ Parent에 [Solver] 완료
                         │
Orca Reviewer Pi 새 컨텍스트
  ├─ flag_evidence 검토
  ├─ 가설과 결론 검토
  ├─ 비효율과 놓친 단서 정리
  └─ writeup.md 또는 review.md
                         │
reviewer.json done       │
  └─ Parent에 [Reviewer] 완료
```

Parent는 Solver와 Reviewer를 기다리지 않는다. 에이전트의 대화를 복사하지도 않는다. 공유하는 것은 challenge ID와 `runs/`에 저장된 상태, 완료 메시지뿐이다.

---

## 13. 남은 한계

이번 구현으로 가설과 검증 사이의 규칙은 생겼지만, 문제 풀이 성능이 자동으로 향상되는 것은 아니다.

첫째, 가설 우선순위는 아직 하나의 Planner 모델이 판단한다. 여러 Planner가 각자 가설을 제안하고 순위를 합의하는 orchestration은 나중 범위다.

둘째, prompt로 지정한 workspace 범위는 보안 경계가 아니다. Solver에게 더 강한 격리가 필요하다면 파일 도구 자체를 challenge root 기준으로 감싸야 한다.

셋째, Reviewer가 작성한 피드백이 다음 문제의 성공률을 실제로 높였는지 확인하려면 반복 실험이 필요하다. 현재는 30분 이상 걸린 문제와 미해결 문제의 핵심 기법만 Memory에 남긴다.

넷째, Reviewer가 시작되기 전 Solver 터미널이 idle 상태가 되어야 한다. terminal handle이 사라지거나 기다림이 실패하면 Parent에 시작 실패 메시지를 보내지만 자동 복구 정책은 아직 단순하다.

이 한계들은 실제 문제 로그에서 반복될 때 하나씩 보완할 예정이다.

---

## 14. 마무리

2편에서는 Reverser에 필요한 피드백 데이터를 넓게 설계했다. 3편에서는 그중 가장 작은 단위로 강제할 수 있는 부분만 코드로 옮겼다.

현재 Solver는 임의로 명령을 늘려 가는 대신 반증 조건과 종료 범위가 있는 가설을 한 번에 하나씩 검증한다. 결과는 실제 run에 연결되고 플래그도 성공한 출력과 함께 저장된다.

Parent는 풀이를 기다리지 않고, Solver가 끝나면 새 컨텍스트의 Reviewer가 자동으로 근거를 다시 읽고 Write-up을 만든다. 모든 결과는 Git에서 제외된 `runs/`에만 남는다.

아직 Fresh Solver, 막힘 감지, observation/fact 분리는 없다. 대신 현재 Workflow는 작고, 상태 전이가 명확하고, 사용자가 `progress.md`에서 가설 이력을 바로 확인할 수 있다.

복잡한 자가 개선 시스템보다 먼저 필요했던 것은 에이전트가 무엇을 가정했고, 어떻게 확인했고, 왜 다음 가설로 넘어갔는지 남기는 최소 규칙이었다.
