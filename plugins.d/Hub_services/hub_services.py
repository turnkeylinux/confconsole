"""Link Hub services, manage app email, or configure custom SMTP."""
import json
import os
import shutil
import subprocess
import textwrap

TITLE = "TurnKey Hub services"
HELPER = "/usr/lib/inithooks/bin/turnkey-hub"
CONNECT = "/usr/lib/inithooks/bin/hubservices.py"
TEXT = (
    "Link this appliance to your Hub account to manage app email delivery, dynamic DNS,"
    " backups and migration, and security announcements.\n\n"
    "A free account includes app email delivery and a tklapp.com hostname with dynamic DNS."
)


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


def custom():
    columns = shutil.get_terminal_size((80, 24)).columns
    field_width = max(15, min(42, columns - 23))
    values = ["", "587", "", ""]
    while True:
        fields = [(label, row, 0, value, row, 11, field_width, 255, 1 if label == "Password" else 0)
                  for row, (label, value) in enumerate(zip(("SMTP host", "Port", "Username", "Password"), values), 1)]
        code, entered = console._wrapper(
            "mixedform", "Enter your SMTP provider's settings. An authenticated, encrypted connection is required.",
            fields, height=0, width=0, form_height=4, title="Custom SMTP",
            ok_label="Connect", cancel_label="Back", insecure=True,
        )
        if code != "ok":
            return
        host, port, username, password = entered
        try:
            port = int(port)
            if not host or not username or not password or not 1 <= port <= 65535:
                raise ValueError()
        except ValueError:
            values = [host, str(port), username, ""]
            message("Check SMTP settings", "Enter the host, username, password and a port from 1 to 65535. Port 587 uses STARTTLS; port 465 uses implicit TLS.")
            continue
        console.infobox("Checking the encrypted SMTP connection and applying settings...")
        result = invoke("configure", "--stdin", payload={"smtp": {"host": host, "port": port, "username": username}, "password": password})
        if show(result):
            message("SMTP connected", "Your appliance now uses this SMTP relay. Use Send test email to check delivery.")
        return


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
            text += "\n\nChoose Link to Hub to authorize this appliance again."
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
        default = ("Sync", "Refresh Hub services") if linked and current.get("mode") == "hub" and current.get("mail_preference") != "manual" else ("Hub", "Use Hub email" if linked else "Link to TurnKey Hub")
        choices = [default, ("Custom", "Use another SMTP provider")]
        if linked:
            choices.append(("Reconnect", "Reconnect to Hub"))
        if current.get("status") not in ("disconnected", "error"):
            choices[1:1] = [("Status", "Check connection status")]
            if current.get("host"):
                choices[2:2] = [("Test", "Send test email")]
            choices.append(("Reset mail", "Restore previous mail settings"))
        code, choice = choose(TITLE, TEXT, choices)
        if code != "ok":
            return
        if choice == "Sync":
            status(invoke("sync"))
        elif choice == "Reconnect":
            connect()
        elif choice == "Hub":
            if current.get("connection_status") == "linked":
                result = invoke("use-hub")
                if show(result):
                    if result.get("services", {}).get("mail", {}).get("enabled") is False:
                        text = "Email is disabled in the Hub. Enable it in this appliance's Hub settings."
                    elif result.get("mode") == "hub" and result.get("status") == "ready":
                        text = "Hub email is configured. Use Send test email to check delivery."
                    else:
                        text = "Hub email is selected. Check connection status for verification or setup details."
                    message("Use Hub email", text)
            else:
                connect()
        elif choice == "Custom":
            custom()
        elif choice == "Status":
            status()
        elif choice == "Test":
            code, recipient = console.inputbox("Send test email", "Recipient email address:")
            if code == "ok" and recipient:
                result = invoke("test", "--recipient", recipient)
                if show(result):
                    message(TITLE, result["message"])
        elif choice == "Reset mail":
            if console.yesno("Restore the mail settings that were in place before this connection? Your Hub link, dynamic DNS and backup access will stay configured.", autosize=True) == "ok":
                result = invoke("reset-mail")
                if show(result):
                    message(TITLE, "Previous mail settings restored. Your Hub link and dynamic DNS are unchanged. To revoke this appliance credential, open its settings in the Hub.")
    finally:
        console.width, console.height = width, height
