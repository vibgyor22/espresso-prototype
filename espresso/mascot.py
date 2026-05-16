"""
Espresso Protocol Mascot — block-filled, wide, compact.

Solid-block construction (like Claude Code's dense geometric style):
  ▄███████████▄     <- half-block top cap
  █  ●     ●  █     <- face with big eyes
  █  ═══════  █     <- wide smile bar
  ▀███████████▀     <- half-block bottom cap
  ▌           ▐     <- stubby feet

5 lines, 13 chars wide. Coffee brown body, gold eyes, amber mouth.
No tall columns, no outlines — solid filled blocks.

Usage:
    from espresso.mascot import render_mascot, print_mascot, animate_loading

    print_mascot()           # normal
    print_mascot("blink")    # blink
    print_mascot("happy")    # happy
    animate_loading(2.0)     # blinking loader
    s = render_mascot()      # returns colorized string
"""
from __future__ import annotations

import sys
import time

try:
    import colorama
    colorama.init(autoreset=False)
except ImportError:
    pass


# ── ANSI 256 color codes ─────────────────────────────────────────────────────
_BODY  = "\033[38;5;94m"    # dark coffee brown — body blocks █▄▀▌▐
_EYE   = "\033[38;5;220m"   # bright gold — eyes ● ◉
_MOUTH = "\033[38;5;136m"   # amber gold — mouth ═══════
_DIM   = "\033[38;5;241m"   # mid-grey — closed eyes ─
_BOLD  = "\033[1m"
_RESET = "\033[0m"


# ── Template rows (each exactly 15 chars with 2-space indent) ─────────────────
# {L} and {R} = 1 char each (eyes)
# {M} = 7 chars (mouth)

_ROWS = (
    "  ▄███████▄",
    "  █ {L}   {R} █",
    "  █   {M}   █",
    "  ▀███████▀",
)

_FACES: dict[str, dict[str, str]] = {
    "normal": {"L": "●", "R": "●", "M": "◡"},
    "blink":  {"L": "─", "R": "─", "M": "◡"},
    "wink":   {"L": "─", "R": "●", "M": "◡"},
    "happy":  {"L": "◉", "R": "◉", "M": "◡"},
    "alert":  {"L": "◉", "R": "●", "M": "─"},
}


# ── Colorizer ─────────────────────────────────────────────────────────────────

def _colorize(line: str) -> str:
    out = ""
    for ch in line:
        if ch in "█▄▀▌▐":
            out += _BODY + ch + _RESET
        elif ch in "●◉▲":
            out += _BOLD + _EYE + ch + _RESET
        elif ch == "═":
            out += _MOUTH + ch + _RESET
        elif ch == "─":                   # closed eye or flat mouth
            out += _DIM + ch + _RESET
        else:
            out += ch
    return out


# ── Public API ────────────────────────────────────────────────────────────────

def render_mascot(variant: str = "normal", colorized: bool = True) -> str:
    """
    Return the mascot as a multi-line string.

    Args:
        variant:   "normal" | "blink" | "wink" | "happy" | "alert"
        colorized: embed ANSI color codes when True
    """
    face = _FACES.get(variant, _FACES["normal"])
    lines = [row.format(L=face["L"], R=face["R"], M=face["M"]) for row in _ROWS]
    if colorized:
        lines = [_colorize(l) for l in lines]
    return "\n".join(lines)


def _write(text: str) -> None:
    buf = getattr(sys.stdout, "buffer", None)
    if buf is not None:
        buf.write((text + "\n").encode("utf-8", errors="replace"))
        buf.flush()
    else:
        sys.stdout.write(text + "\n")
        sys.stdout.flush()


def print_mascot(variant: str = "normal") -> None:
    """Print mascot to stdout with ANSI colors."""
    _write(render_mascot(variant, colorized=True))


def animate_loading(duration_seconds: float = 2.0,
                    text: str = "Espresso brewing…") -> None:
    """Blinking loading loop: normal → blink → normal → wink, in place."""
    frames = ["normal", "blink", "normal", "wink"]
    n = len(_ROWS) + 1          # mascot lines + label
    start = time.time()
    idx = 0
    while time.time() - start < duration_seconds:
        if idx > 0:
            sys.stdout.write(f"\033[{n}A\033[0J")
            sys.stdout.flush()
        _write(_BOLD + _MOUTH + f"  ◆ {text}" + _RESET)
        _write(render_mascot(frames[idx % len(frames)], colorized=True))
        idx += 1
        time.sleep(0.35)
    print()


# ── Demo ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    div = "─" * 28
    for v in ("normal", "blink", "wink", "happy", "alert"):
        print(f"\n{div}\n  {v}\n{div}")
        print_mascot(v)
    print(f"\n{div}\n  animate_loading 2s\n{div}")
    animate_loading(2.0)
