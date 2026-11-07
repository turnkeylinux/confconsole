"""Link Hub app email and DNS, or configure custom SMTP."""
import json
import os
import shutil
import subprocess
import textwrap

TITLE = "App email"
HELPER = "/usr/lib/inithooks/bin/turnkey-mail"
TEXT = (
    "Link your appliance to TurnKey Hub for app email and dynamic DNS. A free account includes"
    " a tklapp.com hostname.\n\n"
    "Paid accounts can use a custom sending domain."
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
        return {"status": "error", "message": "Mail setup could not finish. Check that inithooks is up to date, then try again."}


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
        message(TITLE, result.get("message", "Mail setup could not finish. Try again."))
        return False
    return True


def connect():
    result = invoke("connect", "--start")
    if not show(result):
        return
    instructions = (
        "Open this address on your phone or computer:\n\n%s\n\n"
        "Link code: %s\n\nSign in or create a free Hub account and approve"
        " this appliance using the code. Then check the connection here."
    ) % (result["verification_uri"].split("?", 1)[0], result["user_code"])
    while True:
        code, choice = choose(
            "Link to TurnKey Hub", instructions,
            [("Check", "Check browser approval"), ("Back", "Keep current mail settings")],
        )
        if code != "ok" or choice != "Check":
            return
        result = invoke("connect", "--poll")
        if not show(result):
            return
        if result.get("domain"):
            connected_text = ("Your appliance is linked. App email and dynamic DNS are configured." if result.get("status") == "ready" else
                       "Your connection is saved. Messages will queue while the sending domain is verified.")
            message("Hub linked", "%s\n\nSending domain: %s\n\nUse Send test email to check delivery." % (connected_text, result["domain"]))
            return
        status = result.get("status")
        if status == "pending":
            instructions = "Waiting for approval in your browser.\n\n" + instructions.split("Waiting for approval in your browser.\n\n")[-1]
        else:
            message("Connection %s" % status,
                           "This connection request %s. Choose Link to Hub to start again. Your existing mail settings were kept." % status)
            return


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


def status():
    result = invoke("status")
    if show(result):
        details = {"ready": "Connected", "pending": "Waiting for domain verification",
                   "connecting": "Connection setup is pending", "disconnected": "Not connected",
                   "revoked": "Connection revoked", "suspended": "Sending suspended", "expired": "Authorization renewal is pending"}
        text = details.get(result.get("status"), "Check the connection in the Hub")
        if result.get("domain"):
            text += "\n\nSending domain: " + result["domain"]
        if result.get("message"):
            text += "\n\n" + result["message"]
        if result.get("status") in ("revoked", "expired"):
            text += "\n\nChoose Link to Hub to authorize this appliance again."
        text += "\n\nManage Hub connections at https://hub.turnkeylinux.org/email/"
        message("Email connection status", text)


def run():
    if not os.path.isfile(HELPER):
        message(TITLE, "Update the inithooks package to connect app email. Your existing mail settings are unchanged.")
        return
    width, height = console.width, console.height
    console.height = 0
    console.width = min(width, max(40, shutil.get_terminal_size((80, 24)).columns - 4))
    try:
        current = invoke("status", "--local")
        choices = [("Hub", "Link to TurnKey Hub"), ("Custom", "Use another SMTP provider")]
        if current.get("status") not in ("disconnected", "error"):
            choices[1:1] = [("Status", "Check connection status")]
            if current.get("host"):
                choices[2:2] = [("Test", "Send test email")]
            choices.append(("Reset mail", "Restore previous mail settings"))
        code, choice = choose(TITLE, TEXT, choices)
        if code != "ok":
            return
        if choice == "Hub":
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
            if console.yesno("Restore the mail settings that were in place before this connection? You can connect again later.", autosize=True) == "ok":
                result = invoke("reset")
                if show(result):
                    message(TITLE, "Previous mail settings restored. To revoke this appliance credential, open its settings in the Hub. Your cloud server is unchanged.")
    finally:
        console.width, console.height = width, height
