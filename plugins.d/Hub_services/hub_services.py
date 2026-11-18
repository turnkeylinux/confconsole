"""Manage the Hub connection and app email delivery."""
import json
import os
import shutil
import subprocess
import textwrap

TITLE = "TurnKey Hub services"
HELPER = "/usr/lib/inithooks/bin/turnkey-hub"
CONNECT = "/usr/lib/inithooks/bin/hubservices.py"
CONNECTED_TEXT = "Manage this server's Hub connection and app email delivery."
DISCONNECTED_TEXT = "Connect this server to the TurnKey Hub to use app email delivery."


def invoke(*arguments, payload=None):
    try:
        result = subprocess.run(
            [HELPER, *arguments, "--json"],
            input=json.dumps(payload) if payload is not None else None,
            capture_output=True, text=True, timeout=90,
        )
        response = json.loads(result.stdout)
        if not isinstance(response, dict):
            raise ValueError()
        if result.returncode and response.get("status") != "error":
            raise ValueError()
        return response
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {"status": "error", "message": "Hub services setup could not finish. Check that inithooks is up to date, then try again."}


def message(title, text):
    width, height = console.width, console.height
    terminal = shutil.get_terminal_size((80, 24))
    console.width = min(width, max(40, terminal.columns - 4))
    lines = sum(max(1, len(textwrap.wrap(line, max(20, console.width - 6))))
                for line in text.splitlines())
    console.height = min(terminal.lines - 2, lines + 6)
    try:
        return console.msgbox(title, text)
    finally:
        console.width, console.height = width, height


def choose(title, text, choices):
    height = console.height
    lines = sum(max(1, len(textwrap.wrap(line, max(20, console.width - 6))))
                for line in text.splitlines())
    console.height = min(shutil.get_terminal_size((80, 24)).lines - 2,
                         lines + len(choices) + 7)
    try:
        return console.menu(title, text, choices)
    finally:
        console.height = height


def show(result):
    if result.get("status") == "error":
        message(TITLE, result.get("message", "Hub services setup could not finish. Try again."))
        return False
    return True


def connect():
    # Confconsole already runs as root. Inherit the terminal for the shared UI
    # and let its existing dialogs handle approval, Skip and cancellation.
    try:
        result = subprocess.run([CONNECT, "--relink"], stderr=subprocess.PIPE, text=True)
    except OSError:
        result = None
    if result is None or result.returncode not in (0, 1, 130) or result.stderr:
        message(TITLE, "The Hub connection could not finish. Check the network and the inithooks package, then try Link to Hub again.")


def status(result=None):
    if result is None:
        result = invoke("status")
    if show(result):
        details = {"ready": "Connected", "pending": "Waiting for domain verification",
                   "linked": "Hub linked", "connecting": "Connection setup is pending", "disconnected": "Not connected",
                   "revoked": "Connection revoked", "suspended": "Sending suspended", "expired": "Authorization renewal is pending"}
        text = details.get(result.get("status"), "Check the connection in the Hub")
        if result.get("domain"):
            text += "\n\nSending domain: " + result["domain"]
        for service, state in result.get("services", {}).items():
            if service in ("mail", "backup"):
                text += "\n" + service.capitalize() + ": " + state.get("status", "pending").replace("_", " ")
        if result.get("message"):
            text += "\n\n" + result["message"]
        if result.get("status") in ("revoked", "expired"):
            text += "\n\nChoose Link to Hub to connect again."
        text += "\n\nManage Hub connections at https://hub.turnkeylinux.org/email/"
        message("Hub connection status" if result.get("connection_status") == "linked" else "Email connection status", text)


def run():
    if not os.path.isfile(HELPER):
        message(TITLE, "Update the inithooks package to link Hub services. Your existing settings are unchanged.")
        return
    width, height = console.width, console.height
    console.height = 0
    console.width = min(width, max(40, shutil.get_terminal_size((80, 24)).columns - 4))
    try:
        current = invoke("status", "--local")
        linked = current.get("connection_status") == "linked"
        choices = []
        if not linked:
            choices.append(("Hub", "Link to TurnKey Hub"))
        elif current.get("mode") != "hub" or current.get("mail_preference") == "manual":
            choices.append(("Hub", "Use Hub email"))
        if linked:
            choices.append(("Status", "Refresh connection status"))
        if current.get("status") not in ("disconnected", "error"):
            if current.get("host"):
                choices.append(("Test", "Send test email"))
        if linked:
            choices.append(("Reconnect", "Reconnect to Hub"))
        code, choice = choose(TITLE, CONNECTED_TEXT if linked else DISCONNECTED_TEXT, choices)
        if code != "ok":
            return
        if choice == "Reconnect":
            connect()
        elif choice == "Hub":
            if current.get("connection_status") == "linked":
                result = invoke("use-hub")
                if show(result):
                    if result.get("services", {}).get("mail", {}).get("enabled") is False:
                        text = "Email is disabled in the Hub. Enable it in Hub settings."
                    elif result.get("mode") == "hub" and result.get("status") == "ready":
                        text = "Hub email is configured. Use Send test email to check delivery."
                    else:
                        text = "Hub email is selected. Check connection status for verification or setup details."
                    message("Use Hub email", text)
            else:
                connect()
        elif choice == "Status":
            status()
        elif choice == "Test":
            code, recipient = console.inputbox("Send test email", "Recipient email address:")
            if code == "ok" and recipient:
                result = invoke("test", "--recipient", recipient)
                if show(result):
                    message(TITLE, result["message"])
    finally:
        console.width, console.height = width, height
