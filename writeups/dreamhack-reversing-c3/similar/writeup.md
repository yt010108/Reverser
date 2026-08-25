# similar — Dreamhack Reversing C3 (write-up)

## Triage
- `similar`: stripped amd64 PIE ELF, Full RELRO / canary / NX, linked against libm (`sqrt`).
- Strings: `/dev/urandom`, `Values:`, `%d: %d %d %d`, `Result?`, `Wrong...`, `./flag`, `Bingo! Flag: %s`, `TIMEOUT!`.
- Local `flag` file contains a placeholder value; real flag lives on the server.

## Program logic (main @ 0x1369)
1. Seeds `srand` with 4 bytes from `/dev/urandom`.
2. Generates 30 records `{ int a, b, c, id }` (stride 16) where `a,b,c = rand()%200 - 100` and `id = i` (0..29).
3. Prints each record as `"%d: %d %d %d"` → `id: a b c`.
4. `qsort(records, 30, 16, cmp)` with comparator at `0x17c8`.
5. Prints `Result?`, then reads 30 integers via `scanf("%d")`; the i-th answer must equal
   `sorted[i].id` (the original index of the record now at sorted position i). All 30 correct
   ⇒ prints the contents of `./flag`. A SIGALRM handler prints `TIMEOUT!`.

## Comparator (0x17c8) and similarity function (0x16a3)
- Similarity function takes one record's vector `(a,b,c)` and compares it to the constant
  vector `(1,1,1)`:

  ```
  d = 1.0 - dot(v, (1,1,1)) / (||v|| * sqrt(3))
    = 1 - (a+b+c) / (sqrt(a^2+b^2+c^2) * sqrt(3))
  ```

  i.e. **cosine distance to the diagonal direction (1,1,1)** — hence the title "similar".
- Comparator: if `eps > d1 - d2` (eps = double constant at 0x2070) the records are "equal"
  (returns 0); otherwise orders ascending by `d`.

So the required answer is: sort the 30 triples by cosine distance to `(1,1,1)` ascending and
type back their original indices in that order.

## Solver
Python script parses the printed lines, recomputes
`key = 1 - (a+b+c)/(sqrt(3)*sqrt(a*a+b*b+c*c))` in doubles, sorts ascending (stable, matching
glibc mergesort for epsilon-ties), and sends all 30 indices at once (alarm makes latency matter):

```python
order = sorted(recs, key=lambda r: 1-(r[1]+r[2]+r[3])/(math.sqrt(3)*math.sqrt(r[1]**2+r[2]**2+r[3]**2)))
p.communicate(' '.join(str(r[0]) for r in order) + '\n')
```

Verified in the dynamic worker: binary prints `Bingo! Flag: ...` with the local test flag.

## Result
Solved locally; candidate flag recorded via `ctf_record_flag` (server-side flag would be read
from the remote `./flag`).
