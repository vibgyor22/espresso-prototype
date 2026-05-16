"""
Espresso Protocol CLI Mascot — asymmetrical pixel creature for terminal display.

A minimalist, alien-like mascot with asymmetrical eyes, angled legs, and coffee-colored
pixel aesthetics. Renders with ANSI 256-color support and multiple animation states
(idle, happy, alert, processing).

Usage:
    from espresso.mascot import print_mascot, get_mascot_art

    # Print to terminal with colors
    print_mascot("idle")           # default idle state
    print_mascot("happy")          # happy variant
    print_mascot("alert")          # alert variant
    print_mascot("processing", frame=0)  # processing animation frame 0-3

    # Get raw ASCII without colors
    art = get_mascot_art("idle", colored=False)
    print(art)
"""

from __future__ import annotations


# ANSI 256-color codes (coffee palette)
COLORS = {
    "dark_brown":    "\033[38;5;94m",      # #6F4E37 — primary dark brown
    "medium_brown":  "\033[38;5;137m",     # #8B6F47 — medium brown
    "tan":           "\033[38;5;180m",     # #D2B48C — tan/light
    "light_tan":     "\033[38;5;224m",     # cream-tan
    "outline":       "\033[38;5;52m",      # very dark brown
    "reset":         "\033[0m",
}


# ─────────────────────────────────────────────────────────────────────────────
# MASCOT DESIGNS (8-10 lines tall, ~24-32 chars wide)
# ─────────────────────────────────────────────────────────────────────────────

MASCOT_IDLE = """\
      ▓▓▓░
     ▓▒░░░▓
     ▓●  ◯▓
     ▓░▀▀░▓
     ▓▒░░░▓
    ▓░   ░░
   ░░  ░  ░░
  ░░      ░
 ░        ░░
"""

MASCOT_HAPPY = """\
      ▓▓▓░
     ▓▒░░░▓
     ▓●  ◯▓
     ▓░╭──▓
     ▓▒░░░▓
    ▓░   ░░
   ░░  ░  ░░
  ░░      ░
 ░        ░░
"""

MASCOT_ALERT = """\
      ▓▓▓░
     ▓▒░░░▓
     ▓◉  ◯▓
     ▓░▲▲░▓
     ▓▒░░░▓
    ▓░   ░░
   ░░░░░░░░░
  ░░       ░
 ░        ░░
"""

# Processing animation frames (4 states showing loader pattern)
MASCOT_PROCESSING = [
    # Frame 0: left leg forward
    """\
      ▓▓▓░
     ▓▒░░░▓
     ▓◐  ◑▓
     ▓░▁▁░▓
     ▓▒░░░▓
    ▓░ ░ ░░
   ░░░    ░░
  ░░       ░
 ░        ░░
""",
    # Frame 1: right leg forward
    """\
      ▓▓▓░
     ▓▒░░░▓
     ▓◐  ◑▓
     ▓░▁▁░▓
     ▓▒░░░▓
    ▓░  ░ ░
   ░░  ░░░░░
  ░░       ░
 ░        ░░
""",
    # Frame 2: both legs
    """\
      ▓▓▓░
     ▓▒░░░▓
     ▓◑  ◐▓
     ▓░▂▂░▓
     ▓▒░░░▓
    ▓░ ░ ░░
   ░░░ ░ ░░░
  ░░       ░
 ░        ░░
""",
    # Frame 3: processing pulse
    """\
      ▓▓▓░
     ▓▒░░░▓
     ▓◑  ◐▓
     ▓░──░▓
     ▓▒░░░▓
    ▓░   ░░
   ░░  ░  ░░
  ░░░░░░░░░
 ░        ░░
""",
]


def colorize_mascot(art: str, color_scheme: str = "default") -> str:
    """
    Apply ANSI color codes to mascot ASCII art.

    Args:
        art: Raw ASCII art string
        color_scheme: "default" (dark/med/tan), "vibrant" (saturated browns), "minimal" (single color)

    Returns:
        ASCII art with ANSI color codes embedded
    """
    if color_scheme == "minimal":
        # Single dark brown for entire mascot
        lines = art.split("\n")
        colored_lines = [COLORS["dark_brown"] + line + COLORS["reset"] for line in lines]
        return "\n".join(colored_lines)

    # Default: gradient from dark → tan
    # Map: ▓ = dark, ▒ = medium, ░ = light
    art = art.replace("▓", COLORS["dark_brown"] + "▓" + COLORS["reset"])
    art = art.replace("▒", COLORS["medium_brown"] + "▒" + COLORS["reset"])
    art = art.replace("░", COLORS["tan"] + "░" + COLORS["reset"])

    # Eyes: asymmetrical
    art = art.replace("●", COLORS["dark_brown"] + "●" + COLORS["reset"])  # filled eye
    art = art.replace("◯", COLORS["tan"] + "◯" + COLORS["reset"])          # hollow eye
    art = art.replace("◐", COLORS["medium_brown"] + "◐" + COLORS["reset"])
    art = art.replace("◑", COLORS["medium_brown"] + "◑" + COLORS["reset"])
    art = art.replace("◉", COLORS["dark_brown"] + "◉" + COLORS["reset"])

    # Mouth expressions
    art = art.replace("▀▀", COLORS["tan"] + "▀▀" + COLORS["reset"])
    art = art.replace("─", COLORS["medium_brown"] + "─" + COLORS["reset"])
    art = art.replace("╭─", COLORS["tan"] + "╭─" + COLORS["reset"])
    art = art.replace("▁▁", COLORS["tan"] + "▁▁" + COLORS["reset"])
    art = art.replace("▲▲", COLORS["dark_brown"] + "▲▲" + COLORS["reset"])
    art = art.replace("▂▂", COLORS["tan"] + "▂▂" + COLORS["reset"])
    art = art.replace("──", COLORS["medium_brown"] + "──" + COLORS["reset"])

    return art


def get_mascot_art(state: str = "idle", frame: int = 0, colored: bool = True) -> str:
    """
    Get mascot ASCII art for a given state.

    Args:
        state: "idle", "happy", "alert", "processing"
        frame: for "processing" state, which animation frame (0-3)
        colored: whether to apply ANSI color codes

    Returns:
        ASCII art string, optionally with colors
    """
    if state == "idle":
        art = MASCOT_IDLE
    elif state == "happy":
        art = MASCOT_HAPPY
    elif state == "alert":
        art = MASCOT_ALERT
    elif state == "processing":
        art = MASCOT_PROCESSING[frame % len(MASCOT_PROCESSING)]
    else:
        art = MASCOT_IDLE

    if colored:
        art = colorize_mascot(art.strip())
    else:
        art = art.strip()

    return art


def print_mascot(state: str = "idle", frame: int = 0, indent: int = 0) -> None:
    """
    Print the mascot to stdout with colors.

    Args:
        state: "idle", "happy", "alert", "processing"
        frame: for "processing" state, which animation frame
        indent: number of spaces to indent the output
    """
    art = get_mascot_art(state, frame, colored=True)
    prefix = " " * indent
    for line in art.split("\n"):
        print(prefix + line)


def print_mascot_with_text(text: str, state: str = "idle") -> None:
    """
    Print mascot alongside text (side-by-side layout).

    Args:
        text: text to display on the right
        state: mascot state
    """
    art_lines = get_mascot_art(state, colored=True).split("\n")
    text_lines = text.split("\n")

    # Pad text lines to match art height
    while len(text_lines) < len(art_lines):
        text_lines.append("")

    for i, art_line in enumerate(art_lines):
        text_line = text_lines[i] if i < len(text_lines) else ""
        # Pad art line to fixed width (to align text)
        art_padded = art_line.ljust(35)  # adjust based on mascot width
        print(art_padded + "  " + text_line)


# ─────────────────────────────────────────────────────────────────────────────
# LOADING ANIMATION
# ─────────────────────────────────────────────────────────────────────────────

def animate_loading(duration_seconds: float = 2.0, text: str = "Espresso brewing…") -> None:
    """
    Animate the processing mascot for a loading screen.

    Args:
        duration_seconds: how long to animate
        text: status text to display
    """
    import time
    import sys

    start = time.time()
    frame = 0

    while time.time() - start < duration_seconds:
        # Clear line and print
        sys.stdout.write("\r")
        sys.stdout.flush()

        # Print mascot + text
        art = get_mascot_art("processing", frame=frame, colored=True)
        lines = art.split("\n")

        if frame == 0:
            # Print header on first frame
            print(f"\n{COLORS['dark_brown']}◆ {text}{COLORS['reset']}\n")

        print(lines[min(frame, len(lines) - 1)])

        frame = (frame + 1) % 4
        time.sleep(0.3)

    print()  # final newline


if __name__ == "__main__":
    # Demo: print all states
    print("\n" + "=" * 40)
    print("ESPRESSO PROTOCOL MASCOT GALLERY")
    print("=" * 40 + "\n")

    states = ["idle", "happy", "alert"]
    for state in states:
        print(f"\n[{state.upper()}]")
        print_mascot(state)

    print(f"\n[PROCESSING] Animation frame 0")
    print_mascot("processing", frame=0)

    print(f"\n[PROCESSING] Animation frame 2")
    print_mascot("processing", frame=2)

    # Side-by-side example
    print("\n" + "=" * 60)
    print("SIDE-BY-SIDE EXAMPLE")
    print("=" * 60 + "\n")
    print_mascot_with_text("Ready to analyze your data.\nAsk a question to begin.", state="happy")
