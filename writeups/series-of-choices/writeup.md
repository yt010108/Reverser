# Series of Choices — Dreamhack Reversing C5

## 대상
- `main`: ELF 64-bit PIE, stripped, C++ (Ubuntu 11.4.0), 256,224 bytes

## 정적 분석 (radare2)
- `main` @ `0x1340`: setvbuf 2회 → `dfs(0)` 호출 (`0x3c350`) → `"[FLAG REDACTED]"` 출력.
  - counter는 전역 `qword [0x3f1a0]`, 그래프는 전역 vector @ `[0x3f1b0]`/`[0x3f1b8]`.
- `dfs(int idx)` @ `0x3c350`:
  ```
  if (idx < 0 || idx >= nodes.size()) exit(1);
  Node& nd = nodes[idx];            // 32바이트: int value; pad; vector<int> children;
  if (nd.value == 50) { counter++; return; }
  for (int c : nd.children) {
      if (nd.value >= nodes[c].value) exit(1);   // 값이 반드시 증가 (DAG 보장)
      dfs(c);
  }
  ```
- 즉, 노드 0에서 시작해 value==50인 노드(51개 존재)에 도달하는 서로 다른 경로의 개수를 세는 순수 재귀 DFS. 경로 수가 지수적으로 많아 직접 실행은 사실상 종료되지 않음(10초 타임아웃 확인).

## 동적 추출 (gdb)
- `starti` 후 `/proc/pid/maps`에서 base 획득 → `break *(base+0x3c350)` → 전역 vector begin/end(`[base+0x3f1a0]` 아님, `+0x3f1b0/+0x3f1b8`)를 읽어 32바이트 노드 배열과 각 노드의 children vector<int>(+0x18 오프셋까지)를 순회 덤프.
- 결과: 노드 1,326개, 엣지 21,749개, value 범위 0..50, value==50 노드 51개, 모든 엣지에서 값 순증(사이클 없음).

## 계산
- 메모이제이션 DP: `ways(v) = 1 (val==50)` else `sum(ways(child))`.
- exact 경로 수 = [REDACTED: 52자리 정수, 2^64 초과].
- 바이너리는 `add qword [counter], 1`을 경로마다 수행하므로 64비트 wrap: printed = exact mod 2^64 = **[REDACTED]**.

## 플래그
`[FLAG REDACTED]` (로컬 기록만, 미제출)

## 산출물
- `output/graph.txt` — 덤프된 그래프 (첫 줄: 노드 수, 이후 `value child...`)
