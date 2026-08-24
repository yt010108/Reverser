#!/usr/bin/env python3
"""Testify solver: recover the embedded FLAG string via substring-oracle queries.

The binary builds an Aho-Corasick automaton from user-supplied patterns (max 256
patterns, <=15 bytes each) and answers exactly one bit per round:
    "pure!"  -> at least one pattern occurs in FLAG
    "fail..." -> none occurs
Rounds repeat indefinitely ("Try Again? [Y/n]").

Extraction: grow the known flag prefix left-to-right. To decide the next
character we binary-search the charset: one round tests the set
{window + c} for half of the remaining candidate characters, where
window is the last <=13 known characters (pattern length limit).
~log2(|charset|) rounds per character.

Usage:
  python3 extract.py --prog ./chal            # local process
  python3 extract.py --host H --port P        # remote service
"""
import argparse
import subprocess
import socket
import sys

CHARSET = "0123456789abcdef"          # flag body alphabet ([0-9a-f]{64})
SEED = "DH{"                          # known prefix (FLAG_HEADER)
MAXPAT = 14                           # safe pattern length (buffer is 0x10)


class LocalOracle:
    def __init__(self, prog):
        self.p = subprocess.Popen([prog], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE)

    def _read_until(self, token):
        buf = b""
        while not buf.endswith(token):
            ch = self.p.stdout.read(1)
            if not ch:
                raise EOFError(buf.decode(errors="replace"))
            buf += ch
        return buf

    def query(self, patterns):
        self._read_until(b"amount: ")
        self.p.stdin.write(str(len(patterns)).encode() + b"\n")
        self.p.stdin.flush()
        for i, pat in enumerate(patterns, 1):
            assert 1 <= len(pat) <= MAXPAT
            self._read_until(("input %d: " % i).encode())
            # single write => read(0,...,0x10) returns the whole line
            self.p.stdin.write(pat.encode() + b"\n")
            self.p.stdin.flush()
        ans = self._read_until(b"\n")
        self.p.stdin.write(b"Y\n")
        self.p.stdin.flush()
        return b"pure!" in ans


class RemoteOracle(LocalOracle):
    def __init__(self, host, port):
        self.s = socket.create_connection((host, port))
        self.f = self.s.makefile("rwb")

    def _read_until(self, token):
        buf = b""
        while not buf.endswith(token):
            ch = self.f.read(1)
            if not ch:
                raise EOFError(buf.decode(errors="replace"))
            buf += ch
        return buf

    def query(self, patterns):
        self._read_until(b"amount: ")
        self.f.write(str(len(patterns)).encode() + b"\n")
        self.f.flush()
        for i, pat in enumerate(patterns, 1):
            self._read_until(("input %d: " % i).encode())
            self.f.write(pat.encode() + b"\n")
            self.f.flush()
        ans = self._read_until(b"\n")
        self.f.write(b"Y\n")
        self.f.flush()
        return b"pure!" in ans


def ask(o, window, chars):
    """True if FLAG contains window+c for some c in chars."""
    pats = [(window + c)[-MAXPAT:] for c in chars]
    return o.query(pats)


def next_char(o, window, charset):
    cands = sorted(charset)
    while len(cands) > 1:
        mid = len(cands) // 2
        if ask(o, window, cands[:mid]):
            cands = cands[:mid]
        else:
            cands = cands[mid:]
    return cands[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prog")
    ap.add_argument("--host")
    ap.add_argument("--port", type=int)
    ap.add_argument("--length", type=int, default=64,
                    help="chars to recover after SEED")
    args = ap.parse_args()

    if args.prog:
        o = LocalOracle(args.prog)
    else:
        o = RemoteOracle(args.host, args.port)

    known = SEED
    for pos in range(args.length):
        window = known[-(MAXPAT - 1):]
        c = next_char(o, window, CHARSET)
        known += c
        print("[%2d] %s" % (pos + 1, known), flush=True)
        if c == "}":
            break
    print("RESULT:", known)


if __name__ == "__main__":
    main()
