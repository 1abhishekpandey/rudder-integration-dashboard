"""Terminal helper utilities for hyperlinks and text styling."""

import os

# Detect terminals that render OSC 8 hyperlinks as clickable text.
# In unsupported terminals we print the URL in parentheses instead.
_TERM = os.environ.get("TERM_PROGRAM", "")
_SUPPORTS_HYPERLINKS = (
    _TERM in ("iTerm.app", "WezTerm", "Hyper")
    or os.environ.get("KITTY_WINDOW_ID") is not None
    or os.environ.get("VTE_VERSION") is not None       # GNOME Terminal / Tilix
    or os.environ.get("WT_SESSION") is not None        # Windows Terminal
)


def link(text: str, url: str) -> str:
    """Render a hyperlink.

    - Terminals that support OSC 8: clickable underlined text.
    - Other terminals: plain text followed by the URL in dim parentheses.
    """
    if _SUPPORTS_HYPERLINKS:
        return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"
    return f"{text} {dim(f'({url})')}"


def bold(s: str) -> str: return f"\033[1m{s}\033[0m"
def dim(s: str)  -> str: return f"\033[2m{s}\033[0m"
