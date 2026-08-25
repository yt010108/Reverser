# Reverser

Pi 기반 리버싱 CTF 문제풀이 하네스.

문제를 가져오면 부모 Pi가 별도 Solver 프로세스에 풀이를 위임하고, 필요하면 Reviewer가 결과를 독립적으로 검증한다. 문제 분석과 바이너리 실행은 격리된 작업자에서 수행하며 Windows 호스트에서는 문제 바이너리를 실행하지 않는다.

## 구조

```text
Reverser/
├── AGENTS.md
├── .pi/
│   ├── agents/
│   │   ├── solver.md
│   │   └── reviewer.md
│   └── extensions/
│       └── ctf.ts
├── code/
│   └── ctf_harness/
├── docker/
├── memory/
│   └── techniques/
├── runs/
│   └── <challenge_id>/
│       ├── progress.md
│       ├── original/
│       ├── work/
│       ├── output/
│       └── reports/
└── writeups/
'''

각 문제의 상태는 runs/<challenge_id>/progress.md에 저장한다. 대화 세션은 상태 저장소로 사용하지 않는다.

처리 흐름
문제 가져오기
→ Solver
→ 필요 시 Reviewer
→ 비공개 결과 저장
→ 플래그를 제거한 공개 write-up 생성

부모 Pi는 문제를 직접 풀지 않는다.

Solver와 Reviewer는 각각 별도 Pi 프로세스에서 실행하며 독립된 컨텍스트를 사용한다.

분석 환경

지원 범위:

x86 Linux ELF
amd64 Linux ELF
PE 정적 분석

작업자:

Profile	용도
core	file, strings, binutils, radare2 등 정적 분석
dynamic	GDB, strace, ltrace, Frida 기반 ELF 동적 분석
ghidra	관심 함수 디컴파일
angr	필요한 경우 심볼릭 실행

Linux ELF 실행이 필요한 경우 격리된 작업자에서만 실행한다.

PE는 실행하지 않는다.

문제 바이너리는 Windows 호스트에서 실행하지 않는다.

문제 데이터

각 문제의 데이터는 다음 디렉터리에 저장한다.

runs/<challenge_id>/

구조:

runs/<challenge_id>/
├── progress.md
├── original/
├── work/
├── output/
└── reports/

progress.md는 해당 문제의 현재 상태와 실행 기록을 저장한다.

runs/에는 다음과 같은 비공개 데이터가 포함될 수 있다.

원본 문제 파일
실제 플래그
분석 결과
실행 로그
비공개 write-up
Reviewer 보고서

runs/의 내용은 Git에 커밋하지 않는다.

문제 간 메모리

다른 문제의 runs/<challenge_id>/ 내용을 직접 읽어 풀이에 사용하지 않는다.

문제 간에 공유할 수 있는 정보는 ctf_learn을 통해 저장된 일반화된 풀이 기법뿐이다.

ctf_learn
→ memory/techniques/
→ ctf_solution_search

ctf_solution_search를 사용하지 않고 memory/techniques/를 직접 읽어 다른 문제의 기법을 가져오지 않는다.

풀이 기법에는 실제 플래그, 문제 고유 주소, 문제 고유 문자열, 원본 바이너리 내용처럼 해당 문제에 종속된 정보를 저장하지 않는다.

Research 단계

활성 문제의 공개 풀이, 플래그 또는 해설은 검색하지 않는다.

처음에는 현재 문제와 로컬 분석 도구만 사용한다.

설정된 direct-solve 시간이 지난 문제 또는 미해결 문제에서만 ctf_solution_search를 통해 저장된 로컬 풀이 기법을 검색할 수 있다.

브라우저

CTF 사이트 탐색은 ctf_browser를 사용한다.

ctf_browser에서는 Playwright의 page와 context API를 사용한다.

로그인이 필요한 경우 열린 브라우저에서 사용자가 직접 로그인한다.

다운로드한 문제 파일은 하네스로 가져온 뒤 분석한다.

실행

기본 작업자 빌드:

docker compose -f .\docker\compose.yaml build core dynamic

Pi 실행:

pi

필요한 경우 추가 작업자를 빌드한다.

docker compose -f .\docker\compose.yaml build ghidra
docker compose -f .\docker\compose.yaml build angr
직접 CLI
$env:PYTHONPATH="$PWD\code"

py -3 -m ctf_harness.cli doctor
py -3 -m ctf_harness.cli list
py -3 -m ctf_harness.cli status CHALLENGE_ID
py -3 -m ctf_harness.cli dashboard
결과

실제 플래그와 비공개 풀이 내용은 runs/에만 저장한다.

공개 write-up은 writeups/에 저장하며 실제 플래그를 포함하지 않는다.

플래그는 사이트에 자동 제출하지 않는다.