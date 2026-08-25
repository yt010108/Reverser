# [Project] Reverser 제작: AI 리버싱 Agent의 실패 조건을 Harness에 반영하기 - 3

1편에서는 Reverser의 기본 구조를 만들었고 2편에서는 풀이 중 막힘을 감지하는 피드백 루프를 정리했다.

1편: [Reverser 제작: Pi 기반 리버싱 CTF Harness - 1](https://yt5246.tistory.com/142)

2편에서 추가하려던 데이터는 `Facts`, `Hypotheses`, `Dead-ends`, `Flag Evidence`였다. 실제 명령으로 확인한 내용과 실패한 접근을 남기면 같은 실수를 덜 반복한다고 봤다.

여기서 문제가 하나 더 생긴다. 기록한 fact가 처음부터 틀렸다면 어떻게 해야 할까.

[당신의 AI Agent가 CTF 문제를 못 푸는 이유: 리버싱 편](https://h4c.team/posts/49)을 읽으며 이 빈틈을 다시 들여다봤다. 글에서 찾은 원인은 도구 부족보다 관찰, 컨텍스트, 가설 검증에 가까웠다. 같은 기준으로 Reverser의 현재 구조를 살펴보고 단순한 사실 저장을 증거의 품질까지 따지는 흐름으로 바꾸려 한다.

---

## 1. 리버싱 Agent는 어디서 막히는가

H4C 글이 짚은 실패는 다섯 갈래로 묶인다.

- 정적 분석 결과와 실제 실행 흐름이 다르다.
- 여러 함수에 흩어진 단서가 컨텍스트에서 빠진다.
- 설명은 만들지만 실행 가능한 입력이나 solver를 만들지 못한다.
- 처음 세운 가설을 반박하는 결과가 나와도 버리지 않는다.
- Decompiler 출력을 정답처럼 믿는다.

관련 연구에서도 비슷한 문제가 드러난다. [Towards LLM-Resistant Software Protection](https://www.ndss-symposium.org/wp-content/uploads/bar2026-58.pdf)은 리버싱 과정을 Observe–Comprehend–Plan으로 나눴다. 보호 기법은 Concealment, Complication, Misdirection으로 구분했다.

연구진이 세 Agent에게 풀게 한 대상은 2025년 CTF의 x86-64 Linux ELF 24개였다. 이 실험에서 training bias, over-trust, context limitation, plan persistence가 반복됐다.

도구가 많아도 첫 관찰이 틀리면 뒤의 추론까지 어긋난다. Decompiler가 보여준 의사 코드는 출발점일 뿐 ground truth가 아니다. 어셈블리나 runtime trace가 다르게 말한다면 앞의 해석부터 고쳐야 한다.

---

## 2. 현재 Reverser에 대입해 보기

Reverser의 작업을 같은 세 단계로 펼쳐 봤다.

```text
Observe     Docker Worker의 stdout / stderr와 artifact
Comprehend  Solver가 로그를 해석하고 progress.md에 상태 저장
Plan        다음 profile과 분석 명령 선택
```

Observe 단계의 원본 로그는 이미 남는다. 빈틈은 Comprehend에 있다.

현재 `progress.md`는 tool run을 기록해도 관찰과 확인된 사실을 구별하지 않는다. Solver가 Decompiler 출력 하나를 사실로 받아들이면 다음 Solver와 Reviewer까지 같은 전제를 물려받는다.

코드에는 더 직접적인 문제도 있다. 분석 명령 하나가 non-zero로 끝나면 전체 상태가 `failed`로 바뀐다. 문자열 하나를 flag로 기록하면 별도의 실행 검증 없이 `solved`가 된다.

2편에서 이 두 문제를 고칠 계획을 세웠다. 3편에서는 저장할 증거의 등급까지 나누려 한다.

---

## 3. Observation과 Fact를 나눈다

명령 출력에서 본 내용은 바로 fact에 넣지 않는다. 먼저 observation으로 저장한다.

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
  ]
}
```

위 값은 저장 형태를 보여주는 예시다.

`source_kind`는 `static`, `decompiler`, `assembly`, `runtime`, `solver` 정도만 쓴다. 처음 발견한 observation은 `provisional`로 둔다.

다른 경로에서 같은 내용을 확인하면 `confirmed`로 올린다. 반대 증거를 찾으면 `contradicted`로 바뀐다.

confidence 점수는 빼기로 했다. 모델이 근거 없이 0.8을 붙여도 증거가 단단해지지는 않는다. 몇 번 run이 뒷받침했고 어느 run이 반박했는지만 남긴다.

---

## 4. 함수 목록 대신 분석 경로를 남긴다

리버싱 문제의 핵심 로직은 여러 함수에 흩어지기 쉽다. [ReCopilot](https://arxiv.org/abs/2505.16366)은 변수 데이터 흐름과 call graph를 함께 사용해 함수 이름 복원과 type inference 성능을 13% 개선했다고 보고했다.

ReCopilot 전체를 Reverser에 넣겠다는 뜻은 아니다. 별도의 graph database도 만들지 않는다. `progress.md`에는 확인이 끝난 분석 경로만 짧게 남긴다.

```json
{
  "analysis_path": {
    "input": "argv[1]",
    "transforms": ["sub_401180"],
    "sink": "memcmp@0x4012d0",
    "unknown_edges": ["global table initialization"]
  }
}
```

이 값 역시 예시다. 함수 전체를 요약하지 않고 입력 지점, 변환 구간, 마지막 비교 지점만 적는다.

잇지 못한 구간은 `unknown_edges`로 표시한다. Fresh Solver가 처음 읽을 내용도 긴 대화가 아니라 이 경로와 관련 로그다.

---

## 5. 가설과 함께 반증 조건을 적는다

2편의 `hypotheses`에는 가설 내용과 상태만 있었다. 여기에 `test`와 `falsifier`를 붙인다.

```json
{
  "text": "입력은 0x37과 XOR된다",
  "test": "세 입력으로 solver 결과와 runtime trace 비교",
  "falsifier": "trace의 변환 바이트가 예측값과 다름",
  "status": "testing"
}
```

[Failing to Falsify](https://arxiv.org/abs/2604.02485)는 규칙 추론 과제에서 11개 LLM의 확인 편향을 조사했다. 반례를 찾으라는 지시를 주자 평균 규칙 발견률이 42%에서 56%로 높아졌다.

리버싱 성능을 직접 잰 연구는 아니다. 그래도 가설마다 무엇이 나오면 포기할지 미리 적는 설계에는 참고할 만하다.

실행 결과가 falsifier와 맞으면 기존 가설을 조용히 덮어쓰지 않는다. 상태를 `rejected`로 바꾸고 `dead_ends`에 근거 run을 남긴다. 막힘을 감지할 때는 같은 명령을 반복했는지뿐 아니라 이미 반증된 가설을 다시 꺼냈는지도 살핀다.

---

## 6. 설명이 아니라 실행 결과로 끝낸다

Agent가 검증 함수를 정확히 설명해도 문제를 푼 것은 아니다. 후보 입력, keygen, patch, emulator 가운데 하나는 실제 바이너리에서 확인해야 한다.

[CrackMeBench](https://arxiv.org/abs/2605.10597)는 외부의 실행 가능한 oracle으로 제출물을 판정한다. 네트워크가 차단된 Linux Docker에서 원본 실행 파일을 쓴다. 평가 대상은 모델의 설명이 아니라 프로그램이 받아들인 입력과 생성 artifact다.

Reverser의 Result Gate에도 같은 원칙을 적용한다.

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

`record_flag`는 문자열만 받아서는 안 된다. Docker Worker에서 실행한 검증 명령, 결과를 저장한 run, 성공을 나타내는 출력이나 exit code를 함께 받아야 `solved`로 바뀐다. 문제에 자동 판정기가 없다면 정답을 완전히 보장하지 못한다는 제한도 Reviewer가 기록한다.

---

## 7. 실패 원인에 맞춰 도구를 바꾼다

모든 문제에 Ghidra, GDB, angr를 차례로 실행하면 비용만 늘어난다. 지금 어떤 증거가 모자란지 보고 다음 행동을 고르는 편이 낫다.

```text
정적 결과와 실행이 다름     → runtime trace / memory dump
함수 사이 연결이 끊김       → xref / call graph / data flow
Decompiler 해석이 불확실함  → assembly와 branch 비교
로직은 알지만 답이 없음     → solver / keygen / test harness
가설이 반복됨               → counterexample test / Fresh Reviewer
```

도구 이름보다 전환 조건이 먼저다. Reviewer도 새 도구부터 권하지 않는다. 현재 observation을 확인하거나 반박할 명령을 제안한다.

---

## 8. 바뀐 풀이 흐름

세 편의 내용을 합치면 Reverser의 풀이 흐름은 아래처럼 바뀐다.

```text
Triage
  ↓
Observation 저장
  ↓
Observation Gate
  ├─ provisional → assembly / runtime 확인
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
  ├─ 통과 → Solved → Reviewer
  └─ 실패 → 가설 갱신
```

구현 순서는 작게 잡는다. 먼저 observation과 fact를 나누고 hypothesis에 test와 falsifier를 붙인다.

그다음 `analysis_path`와 실행 증거를 저장한다. 마지막에는 Reviewer가 출처 없는 fact, 반증된 가설, 검증되지 않은 후보를 찾아내도록 바꾼다.

---

## 9. 무엇을 측정할 것인가

변경 효과는 비공개 리버싱 문제 8~15개로 회귀 테스트한다. 단순 문자열 비교, 여러 함수에 흩어진 검증 로직, runtime에서 복호화되는 로직을 섞는다.

solve rate만 보면 틀린 후보를 자신 있게 제출하는 문제를 놓친다. 검증된 결과 비율, 첫 confirmed fact까지 걸린 시간, contradicted observation 수, 반복 명령 수, 전체 tool run, Solver에 전달한 컨텍스트 크기도 함께 본다.

아직 구현과 실험 전이라 개선 수치는 적지 않는다. 같은 문제와 예산으로 변경 전후를 비교한 뒤 로그까지 다시 확인해야 결과를 기록할 수 있다.

---

## 10. 추가하지 않을 것

이번 조사에서도 큰 시스템을 통째로 가져오지는 않는다.

- ReCopilot 모델 전체
- IDA나 GDB의 상시 세션
- 별도의 graph database
- 여러 Agent를 동시에 돌리는 swarm
- 모델이 정한 confidence 점수
- 자동 flag 제출

현재 `progress.md`와 stdout, stderr 로그만으로도 관찰의 출처와 반증 과정을 잇는다. 실제 문제에서 부족함이 드러나기 전에는 저장소와 Agent 계층을 늘리지 않는다.

---

## 11. 마무리

2편에서는 사실, 가설, 실패한 접근을 남기려 했다. 3편에서는 기록의 양보다 fact로 승격되는 조건을 더 중요하게 본다.

Reverser는 Decompiler의 설명을 바로 믿지 않는다. 정적 분석, 어셈블리, runtime 결과가 어떻게 맞물리는지 확인한다. 가설에는 반증 조건을 붙이고 답은 원본 바이너리에서 직접 실행한다.

목표는 Agent에게 더 그럴듯한 설명을 시키는 데 있지 않다. 틀린 관찰을 오래 끌지 않고 실제 실행 결과를 보고 자기 해석을 고치는 것. 그런 작은 리버싱 Harness를 만들려 한다.
