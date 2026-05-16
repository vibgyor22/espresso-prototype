"""
Espresso Protocol Mascot — geometric, friendly, brown.

A small hexagonal sprite with a sparkle accent. Inspired by Claude Code's
sparkle motif but with its own identity: rounded-corner crystal body,
asymmetric eyes, warm clay smile, splayed little feet.

Design:
       ✦         <- sparkle accent (Claude-inspired, but ours)
      ╭─╮        <- rounded crown
     ╱   ╲       <- widening shoulders
    │ ● ● │      <- big friendly eyes
    │  ⌣  │      <- gentle smile
     ╲   ╱       <- narrowing hips
      ╰─╯        <- rounded base
      ╱ ╲        <- splayed feet

8 lines tall, 7 chars wide at the widest. Color palette is coffee-toned
(tan, walnut, gold accent, clay smile) — warm browns without being
literally coffee-themed.

Usage:
    from espresso.mascot import render_mascot, print_mascot, animate_loading

    print_mascot()               # idle (normal)
    print_mascot("blink")        # eyes closed
    print_mascot("wink")         # left eye closed
    print_mascot("happy")        # smiling with ^ ^ eyes
    print_mascot("alert")        # wide-eyed alert
    animate_loading(2.0)         # blinking loading loop
    s = render_mascot()          # colorized string
"""
from __future__ import annotations

import sys
import time

try:
    import colorama
    colorama.init(autoreset=False)
except ImportError:
    pass


# ── ANSI 256-color codes ──────────────────────────────────────────────────────
_OUTLINE = "\033[38;5;137m"   # warm medium brown — body outline
_DEEP    = "\033[38;5;94m"    # dark coffee — eyes
_GOLD    = "\033[38;5;220m"   # bright gold — sparkle ✦
_CLAY    = "\033[38;5;173m"   # warm clay/rose — smile (cuteness pop)
_DIM     = "\033[38;5;95m"    # muted plum — closed eyes
_BOLD    = "\033[1m"
_RESET   = "\033[0m"


# ── Mascot variants (8 lines, centered design) ────────────────────────────────
# Common scaffolding — eyes/mouth slot in via {L_EYE} {R_EYE} {MOUTH}

_TEMPLATE = (
    "       ✦",
    "      ╭─╮",
    "     ╱   ╲",
    "    │ {L_EYE} {R_EYE} │",
    "    │  {MOUTH}  │",
    "     ╲   ╱",
    "      ╰─╯",
    "      ╱ ╲",
)

_FACES = {
    "normal": {"L_EYE": "●", "R_EYE": "●", "MOUTH": "⌣"},
    "blink":  {"L_EYE": "-", "R_EYE": "-", "MOUTH": "⌣"},
    "wink":   {"L_EYE": "-", "R_EYE": "●", "MOUTH": "⌣"},
    "happy":  {"L_EYE": "^", "R_EYE": "^", "MOUTH": "◡"},
    "alert":  {"L_EYE": "◉", "R_EYE": "●", "MOUTH": "o"},
}


# ── Colorizer ─────────────────────────────────────────────────────────────────

def _colorize(line: str) -> str:
    """Apply per-character color codes to a raw mascot line."""
    out = ""
    for ch in line:
        if ch == "✦":
            out += _BOLD + _GOLD + ch + _RESET
        elif ch in "●◉":
            out += _BOLD + _DEEP + ch + _RESET
        elif ch in "⌣◡":
            out += _BOLD + _CLAY + ch + _RESET
        elif ch == "o":                       # alert mouth
            out += _BOLD + _CLAY + ch + _RESET
        elif ch in "-^":                       # closed / happy eyes
            out += _DIM + ch + _RESET
        elif ch in "╭╮╰╯─│╱╲":                # body outline
            out += _OUTLINE + ch + _RESET
        else:
            out += ch
    return out


# ── Public API ────────────────────────────────────────────────────────────────

def render_mascot(variant: str = "normal", colorized: bool = True) -> str:
    """
    Build the mascot as a multi-line string.

    Args:
        variant:   "normal" | "blink" | "wink" | "happy" | "alert"
        colorized: embed ANSI color codes when True

    Returns:
        Multi-line string ready to write to a terminal.
    """
    face = _FACES.get(variant, _FACES["normal"])
    lines = [row.format(**face) for row in _TEMPLATE]
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
    """Print the mascot to stdout with ANSI colors."""
    _write(render_mascot(variant, colorized=True))


def animate_loading(duration_seconds: float = 2.0,
                    text: str = "Espresso brewing…") -> None:
    """
    Blink-loop loading animation: normal → blink → normal → wink → repeat.
    Clears and redraws in place using ANSI cursor movement.
    """
    frames = ["normal", "blink", "normal", "wink"]
    n_lines = len(_TEMPLATE) + 1  # +1 for the label line
    start = time.time()
    idx = 0

    while time.time() - start < duration_seconds:
        if idx > 0:
            sys.stdout.write(f"\033[{n_lines}A\033[0J")
            sys.stdout.flush()
        _write(_BOLD + _GOLD + f"  ◆ {text}" + _RESET)
        _write(render_mascot(frames[idx % len(frames)], colorized=True))
        idx += 1
        time.sleep(0.35)
    print()


# ── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    div = "─" * 32
    for v in ("normal", "blink", "wink", "happy", "alert"):
        print(f"\n{div}\n  {v}\n{div}")
        print_mascot(v)
    print(f"\n{div}\n  animate_loading (2s)\n{div}")
    animate_loading(2.0)
