"""Render and exercise app email widgets in 60/80/120-column terminals."""
import os
from pathlib import Path
import sys
import time

import pexpect
import pyte

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "mail-terminal-evidence")
OUT.mkdir(parents=True, exist_ok=True)


def start(mode, cols):
    child = pexpect.spawn("python3", [str(ROOT / "tests/mail_terminal_fixture.py"), mode],
                          encoding="utf-8", dimensions=(24, cols), timeout=10,
                          env={**os.environ, "TERM": "linux", "NCURSES_NO_UTF8_ACS": "1"})
    screen = pyte.Screen(cols, 24)
    return child, screen, pyte.Stream(screen)


def capture(child, screen, stream, name):
    end = time.monotonic() + 0.35
    while time.monotonic() < end:
        try:
            stream.feed(child.read_nonblocking(65536, timeout=0.05))
        except (pexpect.TIMEOUT, pexpect.EOF):
            pass
    result = "\n".join(screen.display)
    (OUT / (name + ".txt")).write_text(result + "\n")
    assert "Terminal too small" not in result, result
    return result


def finish(child):
    child.send("\r")
    child.expect("FINISHED")
    child.expect(pexpect.EOF)
    child.close()
    assert child.exitstatus == 0


for cols in (60, 80, 120):
    for mode in ("disconnected", "connected"):
        child, screen, stream = start(mode, cols)
        text = capture(child, screen, stream, f"{cols}-{mode}-menu")
        assert "Link to TurnKey Hub" in text
        if mode == "disconnected":
            assert "Send test email" not in text
        else:
            assert "Send test email" in text
        child.send("\t\r")
        child.expect("FINISHED")
        child.expect(pexpect.EOF)
        child.close()
        assert child.exitstatus == 0
    for mode in ("ready", "pending", "expired", "denied", "error"):
        child, screen, stream = start(mode, cols)
        text = capture(child, screen, stream, f"{cols}-{mode}-approval")
        assert "ABCD&1234" in text and "Check browser approval" in text
        child.send("\r")
        text = capture(child, screen, stream, f"{cols}-{mode}-result")
        if mode == "pending":
            assert "Waiting for approval" in text
            child.send("\r")
            text = capture(child, screen, stream, f"{cols}-{mode}-connected")
        if mode in ("ready", "pending"):
            assert "sample.tklapp.com" in text and "Hub linked" in text
        elif mode == "error":
            assert "temporarily unavailable" in text
        else:
            assert mode in text and "again." in text
        finish(child)
    child, screen, stream = start("cancel", cols)
    text = capture(child, screen, stream, f"{cols}-cancel-approval")
    child.send("\x1b[B\r")
    child.expect("FINISHED")
    child.expect(pexpect.EOF)
    child.close()
    assert child.exitstatus == 0
    child, screen, stream = start("revoked", cols)
    text = capture(child, screen, stream, f"{cols}-revoked-status")
    assert "Connection revoked" in text and "authorize this appliance" in text
    finish(child)
    child, screen, stream = start("reconnect", cols)
    capture(child, screen, stream, f"{cols}-reconnect-menu")
    child.send("\r")
    text = capture(child, screen, stream, f"{cols}-reconnect-approval")
    assert "ABCD&1234" in text
    child.send("\r")
    text = capture(child, screen, stream, f"{cols}-reconnect-result")
    assert "Hub linked" in text
    finish(child)
    child, screen, stream = start("reset", cols)
    capture(child, screen, stream, f"{cols}-reset-menu")
    child.send("\x1b[B" * 4 + "\r")
    text = capture(child, screen, stream, f"{cols}-reset-confirmation")
    assert "Restore the mail settings" in text
    child.send("\r")
    text = capture(child, screen, stream, f"{cols}-reset-result")
    assert "Previous mail settings restored" in text and "unchanged" in text
    finish(child)
    child, screen, stream = start("custom", cols)
    text = capture(child, screen, stream, f"{cols}-custom-empty")
    assert "Password" in text and "SMTP host" in text
    child.send("smtp.example.net\x1b[B\x1b[Bfixture-user\x1b[Bfixture-private-password")
    text = capture(child, screen, stream, f"{cols}-custom-masked")
    assert "fixture-private-password" not in text
    child.send("\t\r")
    text = capture(child, screen, stream, f"{cols}-custom-connected")
    assert "SMTP connected" in text
    finish(child)
print("App email terminal paths passed at 60/80/120 columns.")
