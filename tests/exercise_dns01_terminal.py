"""Exercise actual dialog UI in a PTY; requires pexpect and pyte."""

import os
import time
from pathlib import Path

import pexpect
import pyte

out = Path("terminal-evidence")
out.mkdir(exist_ok=True)


def start(mode, cols):
    child = pexpect.spawn(
        "python3",
        ["tests/dns01_terminal_fixture.py", mode],
        encoding="utf-8",
        dimensions=(24, cols),
        env={**os.environ, "TERM": "xterm"},
        timeout=10,
    )
    screen = pyte.Screen(cols, 24)
    stream = pyte.Stream(screen)
    return child, screen, stream


def capture(child, screen, stream, name):
    end = time.monotonic() + 0.8
    while time.monotonic() < end:
        try:
            stream.feed(child.read_nonblocking(65536, timeout=0.1))
        except (pexpect.TIMEOUT, pexpect.EOF):
            pass
    text = "\n".join(screen.display)
    (out / (name + ".txt")).write_text(text + "\n")
    return text


for cols in (60, 80, 120):
    child, screen, stream = start("cloudflare", cols)
    assert "API token" in capture(child, screen, stream, f"{cols}-method")
    child.send("\r")
    text = capture(child, screen, stream, f"{cols}-token")
    assert "API token:" in text and "Zone ID:" in text
    child.send("dummy-private-token")
    child.send("\x1bOB")
    child.send("a" * 32)
    text = capture(child, screen, stream, f"{cols}-masked")
    assert "dummy-private-token" not in text
    child.send("\t\r")
    child.expect("SAVED")
    child.expect("VALID")
    child.expect(pexpect.EOF)
    child.close()
    assert child.exitstatus == 0

    child, screen, stream = start("generic", cols)
    capture(child, screen, stream, f"{cols}-instructions")
    child.send("\r")
    text = capture(child, screen, stream, f"{cols}-editor")
    assert "key0:" in text
    child.send("\x1b[6~" * 8)
    text = capture(child, screen, stream, f"{cols}-scrolled")
    assert "key59:" in text
    child.send("\t\r")
    child.expect("SAVED")
    child.expect("VALID")
    child.expect(pexpect.EOF)
    child.close()
    assert child.exitstatus == 0
print(
    "Actual terminal save, masking and scrolling passed at 60/80/120 columns."
)
