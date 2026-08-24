# wasm-rev-for-beginners-48766e18 solver
# Parses the data section of challenge_bg.wasm and inverts the check() transform.
#
# check() logic (Rust -> wasm-bindgen, export at 0x1a2e, 389 bytes):
#   1. input length must be 68
#   2. buf1[i] = key[i] ^ input[i]        (key @ 0x100000)
#   3. buf2[i] = (buf1[i] * 13 + 37) & 0xff
#   4. compare buf2 against target table @ 0x100044 (68 bytes)
#      "Wrong..." @ 0x100088, "Correct!" @ 0x100090
# Inverse: input[i] = ((target[i] - 37) * inv13 mod 256) ^ key[i], inv13 = 197

data = open('/challenge/input/challenge_bg.wasm', 'rb').read()

def uread(b, i):
    r = s = 0
    while True:
        x = b[i]; i += 1; r |= (x & 0x7f) << s; s += 7
        if not x & 0x80:
            return r, i

def sread(b, i):
    r = s = 0
    while True:
        x = b[i]; i += 1; r |= (x & 0x7f) << s; s += 7
        if not x & 0x80:
            if s < 64 and x & 0x40:
                r -= 1 << s
            return r, i

i = 8  # skip magic + version
mem = {}
while i < len(data):
    sid = data[i]; i += 1
    size, i = uread(data, i)
    body = data[i:i + size]
    if sid == 11:  # data section
        j = 0
        n, j = uread(body, j)
        for _ in range(n):
            _, j = uread(body, j)          # memidx flag
            assert body[j] == 0x41          # i32.const
            addr, j = sread(body, j + 1)
            assert body[j] == 0x0b; j += 1  # end
            ln, j = uread(body, j)
            seg = body[j:j + ln]; j += ln
            for k, byte in enumerate(seg):
                mem[addr + k] = byte
    i += size

key = bytes(mem[0x100000 + k] for k in range(68))
target = bytes(mem[0x100044 + k] for k in range(68))

inv13 = pow(13, -1, 256)  # 197
flag = bytes((((t - 37) * inv13) & 0xff) ^ k for t, k in zip(target, key))
print(flag.decode())
assert len(flag) == 68 and flag.startswith(b'[FLAG REDACTED]')
