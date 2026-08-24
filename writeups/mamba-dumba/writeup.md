# Mamba Dumba (Dreamhack Reversing C5)

## 개요
`chall.py`는 `exec(marshal.loads(b'...'))`로 마셜 직렬화된 코드 오브젝트를 실행한다.
워커의 Python 3.12로는 `marshal.loads`가 실패(버전 불일치). 블롭 헤더(argcount/posonly/kwonly/nlocals 6-int 레이아웃, lnotab, qualname 부재)와 워드코드 구성으로 Python 3.9/3.10 형식임을 특정했다.

## 접근
1. 커스텀 marshal 파서(≤3.10 포맷: code/int/tuple/ref/string)를 작성해 consts/names/varnames/lnotab을 추출했다.
2. 바이트코드를 수동 디코드. 핵심은 중간 루프의 opcode `0x4e`(78) = **INPLACE_XOR** (클래식 오프코드 표)라는 점. 처음에 이것을 놓쳐 단순 가산 시프트 가설이 클래스 0/2에서 실패했고, 이것이 XOR 패스 존재를 확정하는 단서가 됐다.

## verify 알고리즘 (Python 3.9/3.10)
```python
def verify(a):
    b = '<charset>'
    for c in a:            # charset 검사
        if c not in b: return False
    d = bytearray(a.encode())
    for e in range(len(d)):            # pass1: add
        f = e % 3
        d[e] = (d[e] + [107,101,89][f]) % 256
    for g in range(len(d)):            # pass2: xor  (INPLACE_XOR, opcode 78)
        h = g % 3
        d[g] ^= [39,240,141][h]
    for i in range(len(d)):            # pass3: sub
        j = i % 3
        d[i] = (d[i] - [39,240,141][j]) % 256
    return d == bytearray(<57-byte target>)
```

## 역연산
`plain[i] = (((target[i] + S[i%3]) & 0xff) ^ X[i%3]) - A[i%3] (mod 256)`
- 순방향 재계산으로 target 57바이트 전체 일치 확인.
- accept 입력: `[FLAG REDACTED]`
- 서버는 이 입력 통과 시 `flag` 파일 내용을 플래그로 출력.

## 산출물
- runs/mamba-dumba-7c65c0ea/work/marshal_parse.py (marshal 파서 초안)
- output/0010-core.stdout.log (역연산 + 순방향 검증 성공 로그)
