alpha = bytes.fromhex("48434d51282826201b590505 21eefc".replace(" ",""))
beta = [0xa1,0xa4,0xd2,0xc0,0xd3,0xa5,0x92,0xcd,0x9e,0xa4,0xd3,0xcb,0x9c,0x60,0x9b]
gamma = bytes.fromhex("d3c06bee6bea6dee5d08dcdc8390")

# synergy_table from .rodata @0x4020a0
table_hex = (
"665e9e1022f67d0dd5aace920c51152c"
"12b105becda01fad63c20325488543e0"
"b78b540e89c6ff32f0bd423bf139741b"
"4c942034dfafba6a6d5752e246e5fda4"
"bcf9cfc4fa60b081f85a07fc296168b8"
"2d3f76d64fd2ddb95853eb7262a728ee"
"7abf5d4ddc65b36bf5d306786f2ac0ca"
"243eeac9b208ae70d88331971e908400"
"14de1c967f8dfb798f18a34b41feda16"
"1137c39f02a1697b7ed0a5e3e4303599"
"9d5cec4a2b5650c1ed80e75b49d1a90b"
"1d591738c59a86c7db6e4ee955d713c8"
"8e198ae1f4820a36ef40d9272144751a"
"26d4870195719823453a2eab7733a27c"
"6c3d09f747cbb4bbf3a664f2733ccc93"
"04b667e82f0f88b5e69c8cac5fa8919b")
table = bytes.fromhex(table_hex)

s = bytearray(44)
for i in range(15):
    s[i] = alpha[i] ^ ((7*i + 42) & 0xff)
for j in range(15):
    s[15+j] = (beta[j] - s[14+j]) & 0xff
for j in range(14):
    cands = [c for c in range(256) if table[c] == gamma[j]]
    s[30+j] = cands[0]
    print(j, [hex(c) for c in cands])

print(len(s), repr(bytes(s)))
print("check:", all(table[s[30+j]] == gamma[j] for j in range(14)))
