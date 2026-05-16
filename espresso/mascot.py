"""
Espresso Protocol Mascot.

   ▄▄▄▄▄▄▄▄▄▄▄
   █  ▀   ▀  █   <- diamond eyes
   █▄▄▄▄▄▄▄▄▄█
   ▄█▀█████▀█▄
 ▄██  █████  ██▄  <- blocky arms
 ▀▀█  █████  █▀▀
   █▄▄█   █▄▄█   <- stubby legs

Usage:
    from espresso.mascot import print_mascot, render_mascot, animate_loading
"""
from __future__ import annotations
import sys
import time

try:
    import colorama
    colorama.init(autoreset=False)
except ImportError:
    pass

_BODY  = "\033[38;5;94m"    # dark coffee brown
_EYE   = "\033[38;5;220m"   # bright gold  — eye ▀ chars
_BOLD  = "\033[1m"
_RESET = "\033[0m"

# Each tuple: (eye_left, eye_right) — single chars
_EYES = {
    "normal":     ("▀", "▀"),
    "blink":      ("▁", "▁"),
    "wink":       ("▁", "▀"),
    "alert":      ("▲", "▀"),
    "processing": ("▀", "▁"),
}

_HEAD_TOP  = "   ▄▄▄▄▄▄▄▄▄▄▄"
_HEAD_BOT  = "   █▄▄▄▄▄▄▄▄▄█"
_BODY_TOP  = "   ▄█▀█████▀█▄"
_ARM_MID   = " ▄██  █████  ██▄"
_ARM_BOT   = " ▀▀█  █████  █▀▀"
_LEGS      = "   █▄▄█   █▄▄█"


def _eye_line(l: str, r: str) -> str:
    return f"   █  {l}   {r}  █"


def _colorize(lines: list[str], eye_idx: int) -> list[str]:
    out = []
    for i, line in enumerate(lines):
        result = ""
        for ch in line:
            if ch in "█▄":
                result += _BODY + ch + _RESET
            elif ch == "▀":
                result += (_BOLD + _EYE if i == eye_idx else _BODY) + ch + _RESET
            elif ch in "▁▲":          # closed / alert eye chars
                result += _BODY + ch + _RESET
            else:
                result += ch
        out.append(result)
    return out


def render_mascot(variant: str = "normal", colorized: bool = True) -> str:
    el, er = _EYES.get(variant, _EYES["normal"])
    raw = [
        _HEAD_TOP,
        _eye_line(el, er),
        _HEAD_BOT,
        _BODY_TOP,
        _ARM_MID,
        _ARM_BOT,
        _LEGS,
    ]
    if colorized:
        raw = _colorize(raw, eye_idx=1)
    return "\n".join(raw)


def _write(text: str) -> None:
    buf = getattr(sys.stdout, "buffer", None)
    if buf:
        buf.write((text + "\n").encode("utf-8", errors="replace"))
        buf.flush()
    else:
        sys.stdout.write(text + "\n")
        sys.stdout.flush()


def print_mascot(variant: str = "normal") -> None:
    _write(render_mascot(variant, colorized=True))


def animate_loading(duration_seconds: float = 2.0,
                    text: str = "Espresso brewing…") -> None:
    frames = ["normal", "blink", "normal", "wink"]
    n = 8   # 7 art lines + 1 label
    start = time.time()
    idx = 0
    while time.time() - start < duration_seconds:
        if idx > 0:
            sys.stdout.write(f"\033[{n}A\033[0J")
            sys.stdout.flush()
        _write(_BOLD + _EYE + f"  ◆ {text}" + _RESET)
        _write(render_mascot(frames[idx % len(frames)], colorized=True))
        idx += 1
        time.sleep(0.35)
    print()


if __name__ == "__main__":
    for v in ("normal", "blink", "wink", "alert", "processing"):
        print(f"\n[{v}]")
        print_mascot(v)
