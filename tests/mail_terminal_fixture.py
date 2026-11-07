"""Real dialog widgets with fixture responses; no services or files changed."""
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import confconsole

spec = importlib.util.spec_from_file_location("mail_relay", ROOT / "plugins.d/Mail_Relaying/mail_relay.py")
wizard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wizard)
wizard.HELPER = __file__
wizard.console = confconsole.Console("TurnKey app email QA", width=min(65, __import__("shutil").get_terminal_size().columns - 4), height=0)
wizard.console.console.add_persistent_args(["--ascii-lines"])
mode = sys.argv[1]
polls = 0


def invoke(*args, payload=None):
    global polls
    if args[0] == "status":
        if mode == "disconnected":
            return {"status": "disconnected"}
        return {"status": "revoked" if mode == "revoked" else "ready", "domain": "sample.tklapp.com", "host": "smtp.example"}
    if args[:2] == ("connect", "--start"):
        return {"verification_uri": "https://hub.turnkeylinux.org/link", "user_code": "ABCD&1234"}
    if args[:2] == ("connect", "--poll"):
        polls += 1
        if mode in ("denied", "expired"):
            return {"status": mode}
        if mode == "error":
            return {"status": "error", "message": "The Hub is temporarily unavailable. Try again shortly."}
        if mode == "pending" and polls == 1:
            return {"status": "pending"}
        return {"status": "ready", "domain": "sample.tklapp.com"}
    if args[0] == "configure":
        assert payload["password"] == "fixture-private-password"
        return {"status": "ready"}
    if args[0] == "test":
        return {"status": "queued", "message": "Test message accepted by the local mail queue. Check the recipient inbox for delivery."}
    if args[0] == "reset-mail":
        return {"status": "disconnected"}
    raise AssertionError(args)


wizard.invoke = invoke
if mode in ("disconnected", "connected", "reset"):
    wizard.run()
elif mode == "revoked":
    wizard.status()
elif mode == "reconnect":
    wizard.run()
elif mode == "custom":
    wizard.custom()
else:
    wizard.connect()
print("FINISHED")
