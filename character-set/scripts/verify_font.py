#!/usr/bin/env python3
"""Self-consistency checks on the transcribed character set.

Importable by emit-font.py, or run directly to print the results:

    python3 verify_font.py
"""
import json
from pathlib import Path

BUILD = Path(__file__).resolve().parent.parent / "build"


def mirror(byte):
    """reflect a 5-dot row left to right"""
    return int(f"{byte:05b}"[::-1], 2)


def checks(g):
    """(description, passed) for each check, in reporting order"""
    return [
        ("arrow up 0x30 is the vertical mirror of arrow down 0x31",
         g[0x30] == g[0x31][::-1]),
        ("arrow left 0x32 is the horizontal mirror of arrow right 0x33",
         [mirror(b) for b in g[0x32]] == g[0x33]),
        ("'(' 0x1F is the horizontal mirror of ')' 0x2F",
         [mirror(b) for b in g[0x1F]] == g[0x2F]),
        ("solid block 0x1E is all 35 dots set",
         all(b == 0x1F for b in g[0x1E])),
        ("BLANK 0x0F and BACKGROUND 0x2E are all dots clear",
         all(b == 0 for b in g[0x0F] + g[0x2E])),
        ("every byte fits in 5 bits",
         all(b < 32 for gl in g for b in gl)),
    ]


def closest_calls(n=6):
    """the dots whose sample sat nearest the ink/blank threshold.

    A dot decodes as set when its sample window is more than half ink. Values
    near 0.5 are the ones a small change in the fit would flip, so they are
    where a transcription error would hide. Anything below about 0.3 or above
    0.7 is a comfortable call.
    """
    path = BUILD / "font-margins.json"
    if not path.exists():
        return []
    m = json.loads(path.read_text())
    return sorted(m, key=lambda d: abs(d[3] - 0.5))[:n]


def superset_failures(fig_a, fig_b):
    """codes where 3(a) has a dot 3(b) lacks -- 3(b) only ever adds dots"""
    return [i for i in range(64)
            if any((fig_a[i][r] & ~fig_b[i][r]) & 0x1F for r in range(7))]


def main():
    raw = json.loads((BUILD / "font-raw.json").read_text())
    a, b = raw["a"], raw["b"]
    for label, ok in checks(a):
        print(f"  [{'PASS' if ok else 'FAIL'}]  {label}")
    fails = superset_failures(a, b)
    print(f"\n  3(b) superset check: {64 - len(fails)}/64 pass; "
          f"misaligned in 3(b): {', '.join(f'0x{i:02X}' for i in fails) or 'none'}")
    ink = sum(bin(x).count("1") for gl in a for x in gl)
    print(f"  {ink} dots set out of 2240 ({ink / 2240 * 100:.1f}%)")
    cc = closest_calls()
    if cc:
        print("\n  closest calls (sample fill; 0.5 is the ink/blank threshold):")
        for code, r, c, fill in cc:
            print(f"    0x{code:02X} row {r} col {c}  fill={fill:.2f}"
                  f"  -> {'set' if fill > 0.5 else 'clear'}")


if __name__ == "__main__":
    main()
