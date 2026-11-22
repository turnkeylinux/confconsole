#!/usr/bin/python3
# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved
"""TurnKey Configuration Console

Options:
    -h, --help           Display this help and exit
        --usage          Display usage screen without Advanced Menu
        --nointeractive  Do not display interactive dialog
        --plugin=<name>  Run plugin directly

"""

import json
import errno
import fcntl
import pty
import re
import secrets
import signal
import logging
import os
import sys
import subprocess
from subprocess import CalledProcessError
import getopt
import ipaddress
import shlex
import struct
import termios
import time
from string import Template
from io import StringIO
from contextlib import contextmanager
from shutil import get_terminal_size
import traceback

import dialog
from dialog import DialogError
from systemd.journal import JournalHandler
import netinfo

import ipaddr
import ifutil
import conf
import plugin

from typing import NoReturn, Iterable, Any

USAGE: str = __doc__ if __doc__ else ""
PLUGIN_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "plugins.d"
)
PROXY_PLUGIN_PATH = os.path.join(PLUGIN_PATH, "Proxy_Settings")
LETS_ENCRYPT_PLUGIN_PATH = os.path.join(PLUGIN_PATH, "Lets_Encrypt")
NETWORKING_PLUGINS = {
    "Free HTTPS certificate": (LETS_ENCRYPT_PLUGIN_PATH, "Set up HTTPS and renewal"),
    "Proxy settings": (PROXY_PLUGIN_PATH, "Configure the APT proxy"),
}
BACKUP_LOG = "/var/log/tklbam-backup"
TKLBAM_PLAN_LIMIT = 12
BACKUP_EMAIL_SUCCESS = "/etc/tklbam/email-success"

handler = JournalHandler(SYSLOG_IDENTIFIER="confconsole")
handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
logging.getLogger().setLevel(logging.DEBUG)
logging.getLogger().addHandler(handler)
log = logging.getLogger(__name__)


def notification_recipient(path="/etc/aliases",
                           disabled_path="/var/lib/turnkey-onboarding/root-forward-disabled",
                           state_path="/var/lib/turnkey-onboarding/state.json") -> str:
    """Show the contact and whether root mail forwarding is active."""
    if os.path.exists(disabled_path):
        try:
            with open(state_path) as state_file:
                address = json.load(state_file).get("notification_choice", "")
            if re.fullmatch(r"[^\s,@]+@[^\s,@]+", address):
                return f"Security contact: {address} (system mail forwarding off)"
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        return "Security contact: System mail forwarding off"
    try:
        with open(path) as aliases:
            for line in aliases:
                match = re.match(r"^\s*root\s*:\s*([^#\n]+)", line, re.I)
                if match:
                    recipients = match.group(1).strip()
                    if re.search(r"[^\s,@]+@[^\s,@]+", recipients):
                        return f"Security contact: {recipients}"
                    break
    except OSError:
        pass
    return "Security contact: Not set"


def local_hub_status() -> dict:
    """Read the locally stored Hub service state without a network request."""
    try:
        command = ["/usr/lib/inithooks/bin/turnkey-hub", "status", "--local"]
        result = subprocess.run(command + ["--read-only", "--json"],
                                capture_output=True, text=True, timeout=5)
        if result.returncode:
            if "unrecognized arguments: --read-only" in result.stderr:
                return {"status_error": "update_inithooks"}
            return {}
        state = json.loads(result.stdout)
        if isinstance(state, dict) and state.get("connection_status") in ("linked", "disconnected"):
            return state
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return {}


def hub_link_status() -> str:
    state = local_hub_status().get("connection_status")
    if state == "linked":
        return "hub.turnkeylinux.org: CONNECTED"
    if state == "disconnected":
        return "hub.turnkeylinux.org: NOT CONNECTED"
    return "hub.turnkeylinux.org: STATUS UNAVAILABLE"


def hub_service_lines(state: dict, backup_status: str) -> str:
    """Show each service independently, using only locally recorded state."""
    connection = state.get("connection_status")
    heading = {"linked": "Connected (last known)", "disconnected": "Not connected"}.get(connection, "Status unavailable")
    if state.get("status_error") == "update_inithooks":
        heading = "Update Inithooks"
    email = dns = "Status unavailable"
    if connection == "disconnected":
        email = dns = "Not connected"
        if state.get("mail_preference") == "manual":
            email = "Custom SMTP" if state.get("mode") == "custom" and state.get("status") == "ready" else "Needs attention"
    elif connection == "linked":
        services = state.get("services")
        services = services if isinstance(services, dict) else {}
        mail = services.get("mail")
        mail = mail if isinstance(mail, dict) else {}
        dns_state = services.get("dns")
        dns_state = dns_state if isinstance(dns_state, dict) else {}
        if state.get("mail_preference") == "manual":
            email = "Custom SMTP" if state.get("mode") == "custom" and state.get("status") == "ready" else "Needs attention"
        elif mail.get("error") or mail.get("status") in ("revoked", "unavailable", "error"):
            email = "Needs attention"
        elif mail.get("enabled") is False:
            email = "Disabled"
        elif mail.get("status") == "pending_verification":
            email = "Waiting for domain verification"
        elif state.get("mode") == "hub" and state.get("status") == "ready" and mail.get("enabled") is True:
            email = "Configured"
        elif mail.get("enabled") is True and state.get("setup_pending"):
            email = "Setup in progress"
        elif mail.get("enabled") is True:
            email = "Needs attention"
        if dns_state.get("error") or dns_state.get("status") in ("revoked", "unavailable", "error"):
            dns = "Needs attention"
        elif dns_state.get("enabled") is False:
            dns = "Disabled"
        elif dns_state.get("enabled") is True:
            dns = "Enabled in Hub"
    backup = backup_status.strip()
    for prefix in ("Backups:", "TKLBAM:"):
        if backup.startswith(prefix):
            backup = backup[len(prefix):].strip()
            break
    if not backup:
        backup = "Status unavailable"
    if connection == "linked":
        services = state.get("services")
        services = services if isinstance(services, dict) else {}
        service = services.get("backup")
        service = service if isinstance(service, dict) else {}
        issue = {"disabled": "Disabled in Hub", "setup_required": "Finish setup in Hub",
                 "migration_required": "Migration required", "unavailable": "Needs attention",
                 "revoked": "Needs attention", "error": "Needs attention"}.get(service.get("status"))
        if issue:
            if backup.startswith("Backup ID #"):
                history = re.sub(r", Updated \S+ (\d{4}-\d\d-\d\d \d\d:\d\d)",
                                 r", updated \1", backup)
                backup = issue + "\n    Last: " + history
            else:
                backup = issue
    # Keep backup history readable when the terminal is narrow.
    backup = backup.replace(", Updated ", "\n                   Updated ", 1)
    return (f"hub.turnkeylinux.org: {heading}\n\n"
            f"  Email delivery:  {email}\n"
            f"  DNS:             {dns}\n"
            f"  Backups:         {backup}")


def backup_log_position() -> tuple[int, int, int] | None:
    try:
        stat = os.stat(BACKUP_LOG)
        return stat.st_dev, stat.st_ino, stat.st_size
    except OSError:
        return None


def backup_summary(position: tuple[int, int, int] | None) -> str:
    """Read statistics written by this run without changing its live output."""
    try:
        with open(BACKUP_LOG, "rb") as log_file:
            stat = os.fstat(log_file.fileno())
            if position and ((stat.st_dev, stat.st_ino) != position[:2] or stat.st_size < position[2]):
                return ""
            start = position[2] if position else 0
            log_file.seek(max(start, stat.st_size - 262144))
            text = log_file.read(262144).decode("utf-8", errors="replace")
    except OSError:
        return ""
    marker = text.rfind("[ Backup Statistics ]")
    if marker < 0:
        return ""
    values = {}
    pattern = re.compile(r"^(ElapsedTime|NewFiles|ChangedFiles|DeletedFiles|TotalDestinationSizeChange|Errors)\s+([0-9.]+)(?:\s+\(([^()\r\n]{1,80})\))?\s*$")
    for line in text[marker:].splitlines()[1:]:
        match = pattern.match(line.strip())
        if match:
            values[match.group(1)] = (match.group(2), match.group(3))
        elif line.strip().startswith("---"):
            break
    lines = []
    if "ElapsedTime" in values:
        number, pretty = values["ElapsedTime"]
        lines.append("Duration: " + (pretty or number + " seconds"))
    if "TotalDestinationSizeChange" in values:
        number, pretty = values["TotalDestinationSizeChange"]
        lines.append("Data uploaded: " + (pretty or number + " bytes"))
    for key, label in (("NewFiles", "New files"), ("ChangedFiles", "Changed files"),
                       ("DeletedFiles", "Deleted files"), ("Errors", "Errors")):
        if key in values:
            lines.append(label + ": " + values[key][0])
    return "\n".join(lines)


@contextmanager
def redraw_dialog_on_resize(console: "Console"):
    """End the active dialog on resize so its caller can rebuild its layout."""
    state = {"changed": False, "pid": None}
    backend = console.console
    original_call = backend._call_program
    previous_handler = signal.getsignal(signal.SIGWINCH)

    def stop_dialog() -> None:
        pid = state["pid"]
        if pid is None:
            return
        try:
            exited = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            if exited is None:
                os.kill(pid, signal.SIGTERM)
        except (ChildProcessError, ProcessLookupError):
            pass

    def on_resize(_signum, _frame) -> None:
        state["changed"] = True
        stop_dialog()

    def track_dialog(*args, **kwargs):
        result = original_call(*args, **kwargs)
        state["pid"] = result[0]
        if state["changed"]:
            stop_dialog()
        return result

    backend._call_program = track_dialog
    signal.signal(signal.SIGWINCH, on_resize)
    try:
        yield state
    finally:
        signal.signal(signal.SIGWINCH, previous_handler)
        backend._call_program = original_call


class ConfconsoleError(Exception):
    pass


def fatal(msg: str) -> NoReturn:
    msg = f"Error: {msg}"
    log.error(msg)
    print(msg, file=sys.stderr)
    sys.exit(1)


def usage(msg: str | getopt.GetoptError = "") -> NoReturn:
    if msg:
        msg = f"Error: {msg}"
        log.error(msg)
        print(msg, file=sys.stderr)

    print(f"Syntax: {sys.argv[0]}", file=sys.stderr)
    print(USAGE.strip(), file=sys.stderr)
    sys.exit(1)


def format_fields(
    fields: Iterable[tuple[str, str, int, int]],
) -> list[tuple[str, int, int, str, int, int, int, int]]:
    """Takes fields in format (label, field, label_length, field_length) and
    outputs fields in format (label, ly, lx, item, iy, ix, field_length,
    input_length)
    """
    out = []
    for i, (label, field, l_length, f_length) in enumerate(fields):
        out.append(
            (label, i + 1, 1, field, i + 1, l_length + 1, l_length, f_length)
        )
    return out


WrapperReturn = str | tuple[str, str]


def dialog_config() -> str | None:
    """Use the console palette unless the administrator supplied a dialog theme."""
    if os.environ.get("DIALOGRC") or os.path.isfile(os.path.expanduser("~/.dialogrc")) or os.path.isfile("/etc/dialogrc"):
        return None
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "conf", "dialogrc")
    return path if os.path.isfile(path) else None


class Console:
    def __init__(
        self,
        title: str | None = None,
        width: int = 65,
        height: int = 25,
    ) -> None:
        self.width = width
        self.height = height
        self.title = title

        self.console = dialog.Dialog(dialog="dialog", DIALOGRC=dialog_config())
        self.console.add_persistent_args(["--no-collapse"])
        self.console.add_persistent_args(["--ok-label", "Select"])
        self.console.add_persistent_args(["--cancel-label", "Back"])
        self.console.add_persistent_args(["--colors"])
        if conf.Conf().copy_paste:
            self.console.add_persistent_args(["--no-mouse"])
        if title:
            self.console.add_persistent_args(["--backtitle", title])

    def _handle_exitcode(self, retcode: str) -> bool:
        if retcode == "esc":
            self.confirm_quit()
            return False
        return True

    def confirm_quit(self) -> None:
        try:
            answer = self.console.yesno("\n    Do you really want to quit?", height=7, width=39)
        except KeyboardInterrupt:
            return
        if answer == self.console.OK:
            sys.exit(130)

    def _wrapper(
        self,
        dialog: str,
        text: str,
        *args: Any,
        **kws: Any,
    ) -> WrapperReturn:
        try:
            method = getattr(self.console, dialog)
        except AttributeError:
            raise ConfconsoleError(f"dialog not supported: {dialog}")

        ret: WrapperReturn = ""

        while 1:
            try:
                contents = text if dialog == "editbox_str" else f"\n{text}"
                ret = method(contents, *args, **kws)
            except KeyboardInterrupt:
                self.confirm_quit()
                continue
            except DialogError as e:
                if "Can't make new window" in e.message:
                    self.console.msgbox(
                        "Terminal too small for UI, resize terminal and"
                        " press OK",
                        ok_label="OK",
                    )
                    continue
                else:
                    raise

            if type(ret) is str:
                retcode = ret
            else:
                retcode = ret[0]

            if self._handle_exitcode(retcode):
                break

        return ret

    def infobox(self, text: str) -> str:
        v = self._wrapper("infobox", text)
        assert isinstance(v, str)
        return v

    def progress(self, title: str, text: str) -> None:
        width = min(60, max(40, get_terminal_size((80, 24)).columns - 4))
        self._wrapper("infobox", text, 9, width, title=title)

    def clear_screen(self) -> None:
        if sys.stdout.isatty():
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()

    def yesno(self, text: str, autosize: bool = False,
              ok_label: str = "Yes", cancel_label: str = "No",
              title: str | None = None, defaultno: bool = False) -> str:
        if autosize:
            text += "\n "
            height, width = 0, 0
        else:
            height, width = 10, 30
        options = {"yes_label": ok_label, "no_label": cancel_label}
        if title:
            options["title"] = title
        if defaultno:
            options["defaultno"] = True
        v = self._wrapper("yesno", text, height, width, **options)
        assert isinstance(v, str)
        return v

    def msgbox(
        self,
        title: str,
        text: str,
        button_label: str = "ok",
        autosize: bool = False,
        extra_label: str | None = None,
        backtitle: str | None = None,
    ) -> str:
        if autosize:
            text += "\n "
            height, width = 0, 0
        else:
            height, width = self.height, self.width

        options = {"title": title, "ok_label": button_label}
        if backtitle is not None:
            options["backtitle"] = backtitle
        if extra_label:
            options.update(extra_button=True, extra_label=extra_label, default_button="extra")
        v = self._wrapper("msgbox", text, height, width, **options)
        assert isinstance(v, str)
        return v

    def actionbox(self, title: str, text: str, primary: str, secondary: str,
                  backtitle: str | None = None) -> str:
        options = {"title": title, "yes_label": primary, "no_label": secondary}
        if backtitle is not None:
            options["backtitle"] = backtitle
        v = self._wrapper("yesno", text, self.height, self.width, **options)
        assert isinstance(v, str)
        return v

    def scrollbox(self, title: str, text: str) -> None:
        terminal = get_terminal_size((80, 24))
        height = min(20, terminal.lines - 2, max(8, len(text.splitlines()) + 6))
        self._wrapper("scrollbox", text, height,
                      min(self.width, terminal.columns - 4), title=title, exit_label="Close")

    def inputbox(
        self,
        title: str,
        text: str,
        init: str = "",
        ok_label: str = "OK",
        cancel_label: str = "Cancel",
    ) -> tuple[str, str]:
        no_cancel = True if cancel_label == "" else False
        v = self._wrapper(
            "inputbox",
            text,
            self.height,
            self.width,
            title=title,
            init=init,
            ok_label=ok_label,
            cancel_label=cancel_label,
            no_cancel=no_cancel,
        )
        assert isinstance(v, tuple)
        return v

    def passwordbox(self, title: str, text: str) -> tuple[str, str]:
        v = self._wrapper("passwordbox", text, 0, 0, title=title,
                          ok_label="Continue", cancel_label="Back", insecure=True)
        assert isinstance(v, tuple)
        return v

    def show_generated_passphrase(self, password: str) -> bool:
        """Display the generated passphrase without placing it in argv or a file."""
        text = ("Generated backup passphrase:\n\n" + password +
                "\n\nSave it somewhere safe. You will need it to restore this backup.")
        args = ["--no-collapse", "--colors", "--backtitle", self.title or "TurnKey GNU/Linux",
                "--title", "Generated passphrase", "--yes-label", "Use passphrase", "--no-label", "Back",
                "--yesno", text, "0", "0"]
        if conf.Conf().copy_paste:
            args.insert(0, "--no-mouse")
        payload = " ".join('"' + arg.replace("\\", "\\\\").replace('"', '\\"') + '"' for arg in args).encode()
        env = os.environ.copy()
        theme = dialog_config()
        if theme:
            env["DIALOGRC"] = theme
        while True:
            reader, writer = os.pipe()
            try:
                os.write(writer, payload)
                os.close(writer)
                writer = None
                try:
                    result = subprocess.run(["dialog", "--file", f"/proc/self/fd/{reader}"],
                                            pass_fds=(reader,), env=env)
                except KeyboardInterrupt:
                    self.confirm_quit()
                    continue
            finally:
                os.close(reader)
                if writer is not None:
                    os.close(writer)
            if result.returncode == 0:
                return True
            if result.returncode == 1:
                return False
            if result.returncode == 255:
                self.confirm_quit()
                continue
            raise ConfconsoleError("Could not display the generated passphrase.")

    def menu(
        self,
        title: str,
        text: str,
        choices: list[tuple[str, str]],
        no_cancel: bool = False,
        compact: bool = False,
        pad: bool = False,
        no_tags: bool = False,
        preserve_tags: bool = False,
    ) -> tuple[str, str]:
        height = self.height
        menu_height = len(choices) + 1
        if compact:
            terminal = get_terminal_size((80, 24))
            extra_rows = 2 if pad else 0
            height = min(height, terminal.lines - 2, max(9, len(choices) + len(text.splitlines()) + 7 + extra_rows))
            menu_height = min(len(choices) + extra_rows, max(1, height - len(text.splitlines()) - 6))
        backend = getattr(self, "console", None)
        palette = getattr(backend, "DIALOGRC", None)
        menu_palette = None
        if not no_tags and choices:
            width = min(self.width, get_terminal_size((80, 24)).columns)
            longest_tag = max(len(tag) for tag, _ in choices)
            # Leave room for dialog's borders and built-in column gap.
            limit = max(1, width - longest_tag - 10)
            if preserve_tags:
                choices = [
                    (tag, desc if len(desc) <= limit else desc[:limit - 1] + "…")
                    for tag, desc in choices
                ]
            if palette and palette == dialog_config():
                # Use a tag-only highlight so the added gutter stays dark.
                candidate = palette + "-menu"
                longest_desc = max(len(desc) for _, desc in choices)
                gap = min(4, limit - longest_desc)
                if longest_desc and gap > 0 and os.path.isfile(candidate):
                    menu_palette = candidate
                    choices = [
                        (tag, " " * gap + desc if desc else desc)
                        for tag, desc in choices
                    ]
        options = {"title": title, "choices": choices, "no_cancel": no_cancel}
        if no_tags:
            options["no_tags"] = True
        if pad and choices and menu_height >= len(choices) + 2:
            # dialog's menu widget has no nonselectable padding rows. Keep its
            # initial focus on the first action and ignore the empty row if it
            # is selected with the keyboard.
            options["choices"] = [("", "")] + choices
            options["default_item"] = choices[0][0]
        if menu_palette:
            backend.DIALOGRC = menu_palette
        try:
            while True:
                result = self._wrapper("menu", text, height, self.width,
                                       menu_height=menu_height, **options)
                assert isinstance(result, tuple)
                if not (pad and result[0] == "ok" and not result[1]):
                    return result
        finally:
            if menu_palette:
                backend.DIALOGRC = palette

    def form(
        self,
        title: str,
        text: str,
        fields: list[tuple[str, int, int, str, int, int, int, int]],
        ok_label: str = "Apply",
        cancel_label: str = "Cancel",
        autosize: bool = False,
    ) -> tuple[str, str]:
        if autosize:
            text += "\n "
            height, width = 0, 0
        else:
            height, width = self.height, self.width
        v = self._wrapper(
            "form",
            text,
            fields,
            height=height,
            width=width,
            form_height=len(fields) + 1,
            title=title,
            ok_label=ok_label,
            cancel_label=cancel_label,
        )
        assert isinstance(v, tuple)
        return v

    def editbox(self, title: str, contents: str) -> tuple[str, str]:
        result = self._wrapper(
            "editbox_str", contents, height=0, width=0, title=title,
            ok_label="Save", cancel_label="Cancel",
        )
        assert isinstance(result, tuple)
        return result


class Installer:
    def __init__(self, path: str) -> None:
        self.path: str = path
        self.available: bool = self._is_available()

    def _is_available(self) -> bool:
        if not os.path.exists(self.path):
            return False

        with open("/proc/cmdline") as fob:
            return "boot=live" in fob.readline().split()

    def execute(self) -> None:
        if not self.available:
            raise ConfconsoleError("installer is not available to be executed")

        subprocess.run([self.path])


class TurnkeyConsole:
    OK = "ok"
    CANCEL = 1

    def __init__(
        self,
        pluginManager: plugin.PluginManager,
        eventManager: plugin.EventManager,
        advanced_enabled: bool = True,
    ) -> None:
        title = "TurnKey GNU/Linux Configuration Console"
        self.width = 65
        self.height = 25

        self.console = Console(title, self.width, self.height)

        # sometimes it would be nice to have the appname be something other
        # than the hostname. Allow developers to create  file containing the
        # appname in /etc/appname
        try:
            with open("/etc/appname", 'r') as fob:
                self.appname = fob.read().rstrip()
        except FileNotFoundError:
            self.appname = f"TurnKey Linux {netinfo.get_hostname().upper()}"

        self.installer = Installer(path="/usr/bin/di-live")

        self.advanced_enabled = advanced_enabled

        self.eventManager = eventManager
        self.pluginManager = pluginManager
        self.pluginManager.updateGlobals({"console": self.console})
        for label, (path, _) in NETWORKING_PLUGINS.items():
            section = self.pluginManager.path_map.get(path)
            if isinstance(section, plugin.PluginDir):
                section.menu_label = label

        # Return from networking plugins to their visible parent menu.
        for path, item in self.pluginManager.path_map.items():
            if item.parent == "advanced" and any(
                path == root or path.startswith(root + os.sep)
                for root, _ in NETWORKING_PLUGINS.values()
            ):
                item.parent = "_adv_networking"

    @staticmethod
    def _get_filtered_ifnames() -> list[str]:
        ifnames = []
        for ifname in netinfo.get_ifnames():
            if ifname.startswith(
                ("lo", "tap", "br", "natbr", "tun", "vmnet", "veth", "wmaster")
            ):
                continue
            ifnames.append(ifname)

        # handle bridged LXC where br0 is the default outward-facing interface
        defifname = conf.Conf().default_nic
        if defifname and defifname.startswith("br"):
            ifnames.append(defifname)
            bridgedif = (
                subprocess.run(
                    ["brctl", "show", defifname],
                    capture_output=True,
                    text=True,
                )
                .stdout.split("\n")[1]
                .split("\t")[-1]
            )
            ifnames.remove(bridgedif)

        ifnames.sort()
        return ifnames

    @classmethod
    def _get_default_nic(cls) -> str | None:
        def _validip(ifname: str) -> bool:
            ip = ifutil.get_ipconf(ifname)[0]
            if ip and not ip.startswith("169"):
                return True
            ip6 = ifutil.get_ipv6conf(ifname)[0]
            if ip6:
                return True
            return False

        defifname = conf.Conf().default_nic
        if defifname and _validip(defifname):
            return defifname

        for ifname in cls._get_filtered_ifnames():
            if _validip(ifname):
                return ifname

        return None

    @classmethod
    def _get_public_ipaddr(cls) -> str | None:
        publicip_cmd = conf.Conf().publicip_cmd
        if publicip_cmd:
            command = subprocess.run(
                shlex.split(publicip_cmd),
                capture_output=True,
                text=True,
            )
            if command.returncode == 0:
                return command.stdout.strip()

        return None

    def _get_advmenu(
        self,
    ) -> tuple[
        list[tuple[str, str]], dict[str, plugin.Plugin | plugin.PluginDir]
    ]:
        items = []
        if self._get_networking_menu():
            items.append(("Networking", "IP settings, encryption, and proxy"))

        items.append(("Backup", "Manage backups and restores"))

        if self.installer.available:
            items.append(("Install", "Install to hard disk"))

        plugin_map = {}

        for path, plug in self.pluginManager.path_map.items():
            if any(path == root for root, _ in NETWORKING_PLUGINS.values()):
                continue
            if os.path.dirname(path) == PLUGIN_PATH:
                if isinstance(plug, plugin.Plugin) and hasattr(
                    plug.module, "run"
                ):
                    items.append(
                        (
                            plug.module_name.capitalize(),
                            str(plug.module.__doc__),
                        )
                    )
                elif isinstance(plug, plugin.PluginDir):
                    items.append(
                        (plug.module_name.capitalize(), plug.description)
                    )
                plugin_map[plug.module_name.capitalize()] = plug

        items.append(("Reboot", "Reboot this server"))
        items.append(("Shutdown", "Shut down this server"))
        items.append(("Quit", "Quit the configuration console"))

        return items, plugin_map

    def _get_netmenu(self) -> list[tuple[str, str]]:
        menu = []
        for ifname in self._get_filtered_ifnames():
            log.debug("found ifname: %s", ifname)
            addr = ifutil.get_ipconf(ifname)[0]
            log.debug("ifname '%s' addr: %s", ifname, addr)
            ifmethod = ifutil.get_ifmethod(ifname)
            log.debug("ifname '%s' ifmethod: %s", ifname, ifmethod)

            if addr:
                desc = addr
                if ifmethod:
                    desc += f" ({ifmethod})"

                if ifname == self._get_default_nic():
                    desc += " [*]"
            else:
                desc = "not configured"

            menu.append((ifname, desc))

        return menu

    def _get_ifconfmenu(self, ifname: str) -> list[tuple[str, str]]:
        menu = []
        menu.append(("DHCP", "Configure networking automatically"))
        menu.append(("StaticIP", "Configure networking manually"))

        if (
            not ifname == self._get_default_nic()
            and len(self._get_filtered_ifnames()) > 1
            and ifutil.get_ipconf(ifname)[0] is not None
        ):
            menu.append(("Default", "Show this adapter's IP address in Usage"))

        return menu

    def _get_ifconftext(self, ifname: str) -> str:
        addr, netmask, gateway, nameservers = ifutil.get_ipconf(ifname)
        if addr is None:
            msg = "Network adapter is not configured"
            log.warning(msg)
            return msg + "\n"
        nameserver_str = " ".join(nameservers)
        log.info(
            f"ip: {addr} netmask: {netmask} gateway: {gateway}"
            f" nameservers: {nameserver_str}",
        )
        text = f"IP Address:      {addr}\n"
        text += f"Netmask:         {netmask}\n"
        text += f"Default Gateway: {gateway}\n"
        text += f"Name Server(s):  {nameserver_str}\n"
        ipv6_addr, ipv6_prefix = ifutil.get_ipv6conf(ifname)
        if ipv6_addr:
            log.info(f"ipv6: {ipv6_addr}/{ipv6_prefix}")
            text += f"IPv6 Address: {ipv6_addr}/{ipv6_prefix}\n"
        text += "\n"

        ifmethod = ifutil.get_ifmethod(ifname)
        if ifmethod:
            conf_method = f"Networking configuration method: {ifmethod}"
            log.info(conf_method)
            text += conf_method + "\n"

        if len(self._get_filtered_ifnames()) > 1:
            text += "Is this adapter's IP address displayed in Usage: "
            if ifname == self._get_default_nic():
                text += "yes\n"
            else:
                text += "no\n"

        return text

    def usage(self) -> str:
        if self.advanced_enabled:
            default_button_label = "Advanced Menu"
            default_return_value = "advanced"
        else:
            default_button_label = "Quit"
            default_return_value = "quit"

        # if no interfaces at all - display error and go to advanced
        if len(self._get_filtered_ifnames()) == 0:
            error = "No network adapters detected"
            log.error(error)
            if not self.advanced_enabled:
                fatal(error)

            self.console.msgbox("Error", error)
            return "advanced"

        # if interfaces but no default - display error and go to networking
        ifname = self._get_default_nic()
        if not ifname:
            error = "Networking is not yet configured"
            log.error(error)
            if not self.advanced_enabled:
                fatal(error)

            self.console.msgbox("Error", error)
            return "networking"

        # tklbam integration
        tklbamstatus_cmd = subprocess.run(
            ["which", "tklbam-status"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        if tklbamstatus_cmd:
            tklbam_result = subprocess.run(
                [tklbamstatus_cmd, "--short"],
                capture_output=True,
                text=True,
            )
            tklbam_status = tklbam_result.stdout
            backup_state = tklbam_result.returncode
        else:
            backup_state = None
            tklbam_status = (
                "TKLBAM not found - please check that it's installed."
            )
        log.info(tklbam_status)
        backup_action = {11: "Set up backups", 10: "Create backup"}.get(backup_state)
        if backup_state == 11:
            tklbam_status = "Backups: Ready to set up"
        elif backup_state == 10:
            tklbam_status = "Backups: Ready for first backup"

        # display usage
        ip_addr = self._get_public_ipaddr()
        if not ip_addr:
            ip_addr = ifutil.get_ipconf(ifname)[0]
        ipv6_addr, ipv6_prefix = ifutil.get_ipv6conf(ifname)
        hostname = netinfo.get_hostname().upper()

        try:
            with open(conf.path("services.txt")) as fob:
                t = fob.read().rstrip()
                text = Template(t).safe_substitute(
                    appname=self.appname,
                    hostname=hostname,
                    ipaddr=ip_addr,
                )
        except conf.ConfconsoleConfError:
            t = ""
            text = Template(t).safe_substitute(ipaddr=ip_addr)

        log_msg = f"Usage started - hostname: {hostname} ip: {ip_addr}"

        if ipv6_addr:
            text += "\n"
            if t.startswith("Web"):
                text += f"\nIPv6 Web:  https://[{ipv6_addr}]"
            text += f"\nIPv6 SSH:  root@{ipv6_addr}"
            log_msg = log_msg + f" ipv6: {ipv6_addr}"

        log.info(log_msg)
        text = f"{notification_recipient()}\n\n{text}"
        hub_state = local_hub_status()
        text += "\n\n" + hub_service_lines(hub_state, tklbam_status)
        if hub_state.get("connection_status") == "disconnected":
            backup_action = "Connect to Hub"
        elif hub_state.get("connection_status") != "linked":
            backup_action = None
        else:
            services = hub_state.get("services")
            services = services if isinstance(services, dict) else {}
            backup_service = services.get("backup")
            backup_service = backup_service if isinstance(backup_service, dict) else {}
            backup_problem = backup_service.get("status")
            if backup_problem in ("disabled", "setup_required", "migration_required", "unavailable", "revoked", "error"):
                self.backup_problem = backup_problem
                backup_action = "Manage backups"

        # Keep the service screen within the current terminal after resizing.
        width, height = self.console.width, self.console.height
        terminal = get_terminal_size((80, 24))
        if isinstance(width, int) and isinstance(height, int):
            self.console.width = min(width, terminal.columns - 4)
            self.console.height = min(height, terminal.lines - 2)
        # On short terminals, the full-height dialog covers the backtitle.
        display_options = {"backtitle": ""} if terminal.lines <= 24 else {}
        try:
            if backup_action:
                retcode = self.console.actionbox(
                    f"{hostname} app services", text, backup_action, default_button_label,
                    **display_options,
                )
                if retcode == self.OK:
                    if backup_action == "Connect to Hub":
                        return "connect_hub"
                    if backup_action == "Manage backups":
                        return "backup_help"
                    return "backup_setup" if backup_state == 11 else "backup_create"
                return default_return_value

            retcode = self.console.msgbox(
                f"{hostname} app services", text, button_label=default_button_label,
                **display_options,
            )
            if retcode is not self.OK:
                self.running = False
            return default_return_value
        finally:
            self.console.width, self.console.height = width, height

    def backup_help(self) -> str:
        if self.backup_problem == "disabled":
            text = "Enable backups for this server in the Hub:\n\nhttps://hub.turnkeylinux.org/email/"
        elif self.backup_problem == "migration_required":
            text = "Finish migrating your backup account in the Hub:\n\nhttps://hub.turnkeylinux.org/backup/"
        elif self.backup_problem == "setup_required":
            text = "Finish backup setup and connect your AWS account in the Hub:\n\nhttps://hub.turnkeylinux.org/backup/"
        else:
            text = "Check backup settings in the Hub and try again:\n\nhttps://hub.turnkeylinux.org/backup/"
        text += "\n\nAfter updating the Hub, return here and choose Refresh."
        if self.console.yesno(text, title="Manage backups", autosize=True,
                              ok_label="Refresh", cancel_label="Back") != self.OK:
            return "usage"
        self.console.progress("Manage backups", "Refreshing Hub services. Please wait...")
        try:
            result = subprocess.run(
                ["/usr/lib/inithooks/bin/turnkey-hub", "status", "--json"],
                capture_output=True, text=True, timeout=90,
            )
            if result.returncode:
                raise subprocess.CalledProcessError(result.returncode, result.args)
        except (OSError, subprocess.SubprocessError):
            self.console.msgbox("Manage backups", "Could not refresh Hub services. Check the connection and try again.", autosize=True)
        return "usage"

    def connect_hub(self) -> str:
        try:
            result = subprocess.run(["/usr/lib/inithooks/bin/hubservices.py", "--relink"])
            if result.returncode not in (0, 130):
                self.console.msgbox("Connect to Hub", "The connection did not finish. Try again when you are ready.", autosize=True)
        except OSError:
            self.console.msgbox("Connect to Hub", "The connection did not finish. Try again when you are ready.", autosize=True)
        return "usage"

    def backup_progress(self, command: list[str], title: str, text: str) -> subprocess.CompletedProcess:
        frames = "|/-\\"
        started = time.monotonic()
        self.console.progress(title, text + "\n\nWorking |  0:00 elapsed")
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, stdin=subprocess.DEVNULL) as process:
            frame = 0
            try:
                while True:
                    try:
                        stdout, stderr = process.communicate(timeout=1)
                        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
                    except subprocess.TimeoutExpired:
                        frame = (frame + 1) % len(frames)
                        minutes, seconds = divmod(int(time.monotonic() - started), 60)
                        self.console.progress(title, text + f"\n\nWorking {frames[frame]}  {minutes}:{seconds:02} elapsed")
            except KeyboardInterrupt:
                process.terminate()
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                raise

    def backup_setup(self) -> str:
        link_status = hub_link_status()
        if link_status == "hub.turnkeylinux.org: STATUS UNAVAILABLE":
            self.console.msgbox("Set up backups", "The Hub connection status is unavailable. Check that inithooks is installed and try again.", autosize=True)
            return "usage"
        if link_status != "hub.turnkeylinux.org: CONNECTED":
            self.console.msgbox(
                "Set up backups",
                "First, connect this server to your TurnKey Hub account. "
                "You will be asked to open the Hub in a browser and return here.",
                autosize=True,
            )
            try:
                subprocess.run(["/usr/lib/inithooks/bin/hubservices.py", "--relink"], check=True)
            except (OSError, subprocess.CalledProcessError):
                self.console.msgbox("Set up backups", "Hub connection was not completed. Try again when you are ready.", autosize=True)
                return "usage"
            if hub_link_status() != "hub.turnkeylinux.org: CONNECTED":
                return "usage"

        while True:
            try:
                result = self.backup_progress(
                    ["tklbam-init"], "Setting up backups",
                    "Connecting to the Hub and setting up backup access.\n"
                    "This may take a few minutes.",
                )
            except OSError:
                self.console.msgbox("Set up backups", "Backup setup could not start. Check that TKLBAM is installed and try again.", autosize=True)
                return "usage"
            if result.returncode == 0:
                if self.console.yesno(
                    "Backup setup is complete. Create your first backup now?",
                    autosize=True, title="Backups ready",
                    ok_label="Create backup", cancel_label="Not now",
                ) == self.OK:
                    return self.backup_create()
                return "usage"
            error = result.stderr.strip()
            if "connect your AWS account" in error or "Finish migrating your backup account" in error or "Enable backups for this server" in error:
                if "Enable backups for this server" in error:
                    instruction = "In the Hub, turn on backup access for this server:"
                    url = "https://hub.turnkeylinux.org/email/"
                else:
                    instruction = ("Finish migrating your backup account in the Hub:" if "Finish migrating" in error
                                   else "Set up backup storage and connect your AWS account in the Hub:")
                    match = re.search(r"https://hub\.turnkeylinux\.org/[^\s]*", error)
                    url = match.group(0) if match else "https://hub.turnkeylinux.org/backups/"
                text = (instruction + "\n\n" + url + "\n\n"
                        "Return here when finished and choose Continue. You can also return to the console and finish later.")
                if self.console.yesno(text, autosize=True, ok_label="Continue", cancel_label="Back") == self.OK:
                    continue
                return "usage"
            self.console.msgbox("Backup setup could not finish", error or "Check your network connection and try again.", autosize=True)
            return "usage"

    def run_backup(self) -> tuple[int, str]:
        """Show output live and retain a bounded tail for the error dialog."""
        master, slave = pty.openpty()
        try:
            terminal = get_terminal_size((80, 24))
            fcntl.ioctl(slave, termios.TIOCSWINSZ,
                        struct.pack("HHHH", terminal.lines, terminal.columns, 0, 0))
            try:
                process = subprocess.Popen(["tklbam-backup"], stdout=slave, stderr=slave)
            finally:
                os.close(slave)
            tail = bytearray()
            truncated = False
            try:
                while True:
                    try:
                        data = os.read(master, 8192)
                    except OSError as error:
                        if error.errno == errno.EIO:
                            break
                        raise
                    if not data:
                        break
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                    tail.extend(data)
                    if len(tail) > 65536:
                        del tail[:-65536]
                        truncated = True
                status = process.wait()
            except KeyboardInterrupt:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                raise
        finally:
            os.close(master)
        output = tail.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
        output = re.sub(r"\x1b\][^\x07]*(?:\x07|\x1b\\)", "", output)
        output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)
        output = "".join(c for c in output if c in "\n\t" or (ord(c) >= 32 and ord(c) != 127))
        lines = output.splitlines()
        if len(lines) > 120:
            truncated = True
        output = "\n".join(lines[-120:]).strip()
        if truncated:
            output = "Showing the most recent backup output.\n\n" + output
        return status, output

    def backup_create(self, first_backup: bool = True) -> str:
        while True:
            log_position = backup_log_position()
            self.console.clear_screen()
            print("Creating backup. Progress appears below.\n", flush=True)
            try:
                status, output = self.run_backup()
            except OSError:
                self.console.msgbox("Backup could not start", "Check that TKLBAM is installed and try again.", autosize=True)
                return "usage"
            if not status:
                summary = backup_summary(log_position)
                text = "Your first backup is complete." if first_backup else "Your backup is complete."
                if summary:
                    text += "\n\n" + summary
                else:
                    text += "\n\nReview the terminal output for backup details."
                self.console.msgbox("Backup complete", text, autosize=True)
                return "usage"

            if status == TKLBAM_PLAN_LIMIT:
                text = ("Your free plan's one backup is already in use.\n\n"
                        "Upgrade your Hub plan to back up more servers:\n"
                        "https://hub.turnkeylinux.org/billing/\n\n"
                        "Open the link in a browser and sign in if prompted.\n"
                        "After upgrading, return here and choose Retry backup.")
                choice = self.console.yesno(
                    text, autosize=True, title="Back up more servers",
                    ok_label="Retry backup", cancel_label="Back",
                )
                if choice == self.OK:
                    continue
                return "usage"

            text = "The backup could not finish."
            if output:
                text += "\n\nView the backup output for details?"
                if self.console.yesno(text, autosize=True, title="Backup could not finish",
                                      ok_label="View output", cancel_label="Back") == self.OK:
                    self.console.scrollbox("Backup output (use arrows to scroll)", output)
            else:
                self.console.msgbox("Backup could not finish", text + "\n\nNo output was available. Try again.", autosize=True)
            return "usage"

    def _backup_connect(self) -> bool:
        status = hub_link_status()
        if status == "hub.turnkeylinux.org: CONNECTED":
            return True
        if status == "hub.turnkeylinux.org: STATUS UNAVAILABLE":
            self.console.msgbox("Backups", "The Hub connection status is unavailable. Try again.", autosize=True)
            return False
        self.console.msgbox(
            "Connect to Hub",
            "Connect this server to your Hub account to manage backups. "
            "You will be asked to open the Hub in a browser and return here.",
            autosize=True,
        )
        try:
            subprocess.run(["/usr/lib/inithooks/bin/hubservices.py", "--relink"], check=True)
        except (OSError, subprocess.CalledProcessError):
            self.console.msgbox("Connect to Hub", "The connection was not completed. Try again when you are ready.", autosize=True)
            return False
        return hub_link_status() == "hub.turnkeylinux.org: CONNECTED"

    def _backup_status(self) -> tuple[int | None, str]:
        try:
            result = subprocess.run(["tklbam-status", "--short"], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return None, "Backup status is unavailable."
        if result.returncode == 11:
            return 11, "Backups: Ready to set up"
        if result.returncode == 10:
            return 10, "Backups: Ready for first backup"
        if result.returncode == 0:
            return 0, result.stdout.strip().replace("TKLBAM:", "Backups:", 1)
        return None, "Backup status is unavailable."

    def _backup_passphrase(self) -> None:
        code, password = self.console.passwordbox(
            "Backup passphrase", "Set a passphrase to protect your backup encryption key.\n\n"
            "Save it somewhere safe. You will need it to restore your backup.\n\n"
            "Leave blank to generate a strong passphrase.")
        if code != self.OK:
            return
        if not password:
            try:
                from libinithooks import passwords
                password = passwords.generate()
            except (ImportError, OSError, ValueError):
                try:
                    password = secrets.token_urlsafe(24)
                except OSError:
                    self.console.msgbox("Backup passphrase", "Could not generate a passphrase. Enter one and try again.", autosize=True)
                    return
            try:
                if not self.console.show_generated_passphrase(password):
                    return
            except (OSError, ConfconsoleError):
                self.console.msgbox("Backup passphrase", "Could not display the generated passphrase. Enter one and try again.", autosize=True)
                return
        elif password != password.rstrip():
            self.console.msgbox("Backup passphrase", "Enter a passphrase without trailing spaces.", autosize=True)
            return
        else:
            code, confirm = self.console.passwordbox("Confirm passphrase", "Enter the passphrase again:")
            if code != self.OK:
                return
            if password != confirm:
                self.console.msgbox("Backup passphrase", "The passphrases did not match. Try again.", autosize=True)
                return
        try:
            self.console.progress("Backup passphrase", "Saving the passphrase. This may take a moment.")
            result = subprocess.run(["tklbam-passphrase"], input=password + "\n", capture_output=True, text=True)
        except OSError:
            self.console.msgbox("Backup passphrase", "Could not start passphrase setup. Try again.", autosize=True)
            return
        if result.returncode:
            self.console.msgbox("Backup passphrase", "Could not save the passphrase. Check your Hub connection and try again.", autosize=True)
        else:
            self.console.msgbox("Backup passphrase", "Passphrase saved. Keep it somewhere safe.", autosize=True)

    def _backup_terminal(self, command: list[str], password: str = "") -> tuple[int, str]:
        """Show operation output live while retaining a small tail for errors."""
        self.console.clear_screen()
        print("Progress appears below.\n", flush=True)
        master, slave = pty.openpty()
        try:
            terminal = get_terminal_size((80, 24))
            fcntl.ioctl(slave, termios.TIOCSWINSZ,
                        struct.pack("HHHH", terminal.lines, terminal.columns, 0, 0))
            try:
                process = subprocess.Popen(command, stdin=subprocess.PIPE if password else subprocess.DEVNULL,
                                           stdout=slave, stderr=slave)
            finally:
                os.close(slave)
            try:
                if process.stdin is not None:
                    try:
                        process.stdin.write((password + "\n").encode())
                        process.stdin.close()
                    except BrokenPipeError:
                        pass
                tail = bytearray()
                while True:
                    try:
                        data = os.read(master, 8192)
                    except OSError as error:
                        if error.errno == errno.EIO:
                            break
                        raise
                    if not data:
                        break
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                    tail.extend(data)
                    if len(tail) > 65536:
                        del tail[:-65536]
                status = process.wait()
            except KeyboardInterrupt:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                raise
        finally:
            os.close(master)
        output = tail.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
        output = re.sub(r"\x1b\][^\x07]*(?:\x07|\x1b\\)", "", output)
        output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)
        output = "".join(c for c in output if c in "\n\t" or (ord(c) >= 32 and ord(c) != 127))
        return status, "\n".join(output.splitlines()[-120:]).strip()

    def _backup_operation(self, command: list[str], title: str, password: str = "") -> None:
        try:
            status, output = self._backup_terminal(command, password)
        except OSError:
            self.console.msgbox(title, "The operation could not start. Try again.", autosize=True)
            return
        if status == 0:
            self.console.msgbox(title, "Completed successfully.", autosize=True)
        elif command[0] == "tklbam-restore" and status == 11:
            self.console.msgbox(title, "The backup passphrase was incorrect. Select the backup and try again.", autosize=True)
        elif command[0] == "tklbam-restore" and status == 10:
            self.console.msgbox(title, "This backup is for a different appliance version. Restore it to a compatible server.", autosize=True)
        elif output and self.console.yesno("The operation could not finish. View its output?", autosize=True,
                                          title=title, ok_label="View output", cancel_label="Back") == self.OK:
            self.console.scrollbox("Operation output (use arrows to scroll)", output)
        elif not output:
            self.console.msgbox(title, "The operation could not finish. Try again.", autosize=True)

    def _backup_restore(self) -> None:
        try:
            result = self.backup_progress(
                ["tklbam-list", "%id\t%skpp\t%created\t%updated\t%size\t%label"],
                "Restore backup", "Loading your Hub backups.")
        except OSError:
            self.console.msgbox("Restore backup", "Could not load backups. Try again.", autosize=True)
            return
        if result.returncode:
            self.console.msgbox("Restore backup", "Could not load your Hub backups. Check the connection and try again.", autosize=True)
            return
        records = []
        for line in result.stdout.splitlines():
            fields = line.split("\t", 5)
            if len(fields) != 6 or not fields[0].isdigit() or not fields[4].isdigit() or int(fields[4]) == 0:
                continue
            backup_id, key_protected, created, updated, size, label = fields
            label = "".join(c for c in label if c.isprintable()).strip() or "Backup"
            created = created[:10] if created and created != "None" else "-"
            updated = updated[:10] if updated and updated != "None" else "-"
            size_bytes = int(size)
            if size_bytes < 10 * 1024:
                size_mb = "0.01"
            elif size_bytes > 1024 * 1024 * 1000 * 99.99:
                size_mb = str(size_bytes // (1024 * 1024))
            else:
                size_mb = f"{size_bytes / (1024 * 1024):.2f}"
            records.append((backup_id, key_protected, created, updated, size_mb, label))
        if not records:
            self.console.msgbox("Restore backup", "No completed Hub backups are available to restore.", autosize=True)
            return
        id_width = max(2, max(len(record[0]) for record in records))
        saved_width, saved_height = self.console.width, self.console.height
        try:
            with redraw_dialog_on_resize(self.console) as resize:
                while True:
                    resize["changed"] = False
                    terminal = get_terminal_size((80, 24))
                    width = max(40, terminal.columns - 4)
                    narrow = width < 66
                    gap = " " if narrow else "  "
                    size_heading = "MB" if narrow else "Size MB"
                    size_width = max(len(size_heading), 4, max(len(record[4]) for record in records))
                    prefix = gap.join((f"{'ID':>{id_width}}", f"{'Pass':<4}", f"{'Created':<10}",
                                       f"{'Updated':<10}", f"{size_heading:>{size_width}}")) + gap
                    label_width = max(1, width - len(prefix) - 10)
                    choices = []
                    for backup_id, key_protected, created, updated, size_mb, label in records:
                        shown_label = label if len(label) <= label_width else label[:max(0, label_width - 1)] + "…"
                        row = gap.join((f"{backup_id:>{id_width}}", f"{key_protected:<4}", f"{created:<10}",
                                        f"{updated:<10}", f"{size_mb:>{size_width}}", shown_label))
                        choices.append((backup_id, row.ljust(width - 10)))
                    self.console.width = width
                    self.console.height = terminal.lines - 2
                    try:
                        code, backup_id = self.console.menu(
                            "Restore backup", "Select a backup. Pass: passphrase required.\n\n  " + prefix + "Label",
                            choices, compact=True, no_tags=True)
                    except dialog.DialogTerminatedBySignal:
                        if not resize["changed"]:
                            raise
                    finally:
                        resize["pid"] = None
                    if not resize["changed"]:
                        break
        finally:
            self.console.width, self.console.height = saved_width, saved_height
        record = next((record for record in records if record[0] == backup_id), None)
        if code != self.OK or record is None:
            return
        _, key_protected, _, updated, _, label = record
        if self.console.yesno(
            f"Restore {label} (backup #{backup_id}, updated {updated})?\n\nThis replaces files, packages and databases on this server. "
            "Current changes may be lost. A rollback is prepared where supported.",
            autosize=True, title="Confirm restore", ok_label="Restore", cancel_label="Back", defaultno=True,
        ) != self.OK:
            return
        password = ""
        if key_protected == "Yes":
            code, password = self.console.passwordbox("Restore backup", "Enter this backup's passphrase:")
            if code != self.OK:
                return
        self._backup_operation(["tklbam-restore", "--noninteractive", backup_id], "Restore backup", password)

    def _backup_rollback(self) -> None:
        if not os.path.isdir("/var/backups/tklbam-rollback"):
            self.console.msgbox("Rollback restore", "There is no restore to roll back.", autosize=True)
            return
        if self.console.yesno(
            "Roll back the last restore?\n\nThis replaces changes made since that restore and may cause data loss.",
            autosize=True, title="Confirm rollback", ok_label="Roll back", cancel_label="Back", defaultno=True,
        ) == self.OK:
            self._backup_operation(["tklbam-restore-rollback", "--force"], "Rollback restore")

    def _adv_backup(self) -> str:
        if not self._backup_connect():
            return "advanced"
        while True:
            state, status = self._backup_status()
            rollback = os.path.isdir("/var/backups/tklbam-rollback")
            choices = []
            if state == 11:
                choices.append(("Setup", "Set up backups"))
            elif state is not None:
                choices.append(("Backup", "Create a backup"))
                choices.append(("Passphrase", "Set backup passphrase"))
            reports = os.path.exists(BACKUP_EMAIL_SUCCESS)
            choices.append(("Email reports", "Successful backup emails: " + ("On" if reports else "Off")))
            choices.append(("Restore", "Restore a Hub backup"))
            if rollback:
                choices.append(("Rollback", "Roll back the last restore"))
            code, choice = self.console.menu("Backups", status, choices, compact=True, pad=True)
            if code != self.OK:
                return "advanced"
            if choice == "Setup":
                self.backup_setup()
            elif choice == "Backup":
                self.backup_create(first_backup=(state == 10))
            elif choice == "Passphrase":
                self._backup_passphrase()
            elif choice == "Email reports":
                if reports:
                    try:
                        os.unlink(BACKUP_EMAIL_SUCCESS)
                    except OSError:
                        self.console.msgbox("Backup reports", "Could not change the setting.", autosize=True)
                elif self.console.yesno(
                    "Email a report after each successful scheduled backup?\n\n"
                    "Reports are sent to the security contact when system mail forwarding is enabled.",
                    title="Backup reports", autosize=True, ok_label="Enable", cancel_label="Back",
                ) == self.OK:
                    try:
                        with open(BACKUP_EMAIL_SUCCESS, "w"):
                            pass
                    except OSError:
                        self.console.msgbox("Backup reports", "Could not change the setting.", autosize=True)
            elif choice == "Restore":
                self._backup_restore()
            elif choice == "Rollback":
                self._backup_rollback()

    def advanced(self) -> str:
        # dont display cancel button when no interfaces at all
        no_cancel = False
        if len(self._get_filtered_ifnames()) == 0:
            no_cancel = True

        items, plugin_map = self._get_advmenu()

        retcode, choice = self.console.menu(
            "Advanced Menu",
            self.appname + " Advanced Menu\n",
            items,
            no_cancel=no_cancel,
        )

        if retcode is not self.OK:
            return "usage"

        if choice in plugin_map:
            return plugin_map[choice].path

        return "_adv_" + choice.lower()

    def networking(self) -> str:
        ifnames = self._get_filtered_ifnames()

        # if no interfaces at all - display error and go to advanced
        if len(ifnames) == 0:
            log.warning("no interfaces found")
            self.console.msgbox("Error", "No network adapters detected")
            return "_adv_networking"

        log.info(f"{len(ifnames)} interface/s found: {', '.join(ifnames)}")
        # if only 1 interface, dont display menu - just configure it
        if len(ifnames) == 1:
            self.ifname = ifnames[0]
            return "ifconf"

        # display networking
        text = "Choose network adapter to configure\n"
        if self._get_default_nic():
            text += "[*] This adapter's IP address is displayed in Usage"

        retcode, self.ifname = self.console.menu(
            "Networking configuration", text, self._get_netmenu()
        )

        if retcode is not self.OK:
            return "_adv_networking"

        return "ifconf"

    def ifconf(self) -> str:
        retcode, choice = self.console.menu(
            f"{self.ifname} configuration",
            self._get_ifconftext(self.ifname),
            self._get_ifconfmenu(self.ifname),
        )

        if retcode is not self.OK:
            # if multiple interfaces go back to networking
            if len(self._get_filtered_ifnames()) > 1:
                return "networking"

            return "_adv_networking"

        return "_ifconf_" + choice.lower()

    def _ifconf_staticip(self) -> str:
        log_msg = "Applying static ip"
        log.info(log_msg)

        def _validate(
            addr: str, netmask: str, gateway: str, nameservers: list[str]
        ) -> list[str]:
            """Validate Static IP form parameters. Returns an empty array on
            success, an array of strings describing errors otherwise"""
            log_valid_msg = f"{log_msg} {addr}"
            errors = []
            if not addr:
                errors.append("No IP address provided")
            elif not ipaddr.is_legal_ip(addr):
                errors.append(f"Invalid IP address: {addr}")

            if not netmask:
                errors.append("No netmask provided")
            elif not ipaddr.is_legal_ip(netmask):
                errors.append(f"Invalid netmask: {netmask}")

            for nameserver in nameservers:
                if nameserver:
                    try:
                        ipaddress.ip_address(nameserver)
                    except ValueError:
                        errors.append(f"Invalid nameserver: {nameserver}")

            if len(nameservers) != len(set(nameservers)):
                errors.append("Duplicate nameservers specified")

            if errors:
                log.error(f"{log_valid_msg} failed: {', '.join(errors)}")
                return errors

            # Final sanity check via the stdlib ipaddress module. Unlike
            # is_legal_ip() this rejects a syntactically-valid but nonsensical
            # (non-contiguous) netmask such as 255.0.255.0, and confirms the
            # gateway falls within the resulting network.
            try:
                network = ipaddress.IPv4Network(
                    f"{addr}/{netmask}", strict=False
                )
            except ValueError as e:
                error = f"Invalid address/netmask: {e}"
                log.error(f"{log_valid_msg} failed: {error}")
                return [error]

            if gateway:
                try:
                    gw = ipaddress.IPv4Address(gateway)
                except ValueError as e:
                    error = f"Invalid gateway: {e}"
                    log.error(f"{log_valid_msg} failed: {error}")
                    return [error]
                if gw not in network:
                    error = (
                        f"Gateway ({gateway}) not in network ({network})"
                    )
                    log.error(f"{log_valid_msg} failed: {error}")
                    return [error]

            return []

        warnings = []
        addr = None
        netmask = None
        gateway = None
        nameservers = None
        try:
            addr, netmask, gateway, nameservers = ifutil.get_ipconf(
                self.ifname, True
            )
            log.debug(
                "ifname: %s; addr: %s; netmask: %s; gateway: %s; nameservers: %s",
                self.ifname,
                addr,
                netmask,
                gateway,
                nameservers,
            )
        except CalledProcessError:
            warnings.append(
                "`route -n` returned non-0 exit code! (unable to get gateway)"
            )
        except netinfo.NetInfoError:
            warnings.append("failed to find default gateway!")
            addr, netmask, gateway, nameservers = ifutil.get_ipconf(
                self.ifname, False
            )

        if addr is None:
            warnings.append("failed to ascertain current address!")
            addr = ""
        if netmask is None:
            warnings.append("failed to ascertain current netmask!")
            netmask = ""
        if gateway is None:
            gateway = ""
        if nameservers is None:
            nameservers = []

        if warnings:
            warning_last_line = "Will leave relevant fields blank"
            log.warning(f"{log_msg} warning/s: {', '.join(warnings)}")
            log.warning(warning_last_line)
            self.console.msgbox(
                "Warning", "\n".join([*warnings, warning_last_line]),
                autosize=True,
            )

        value = [addr, netmask, gateway]
        value.extend(nameservers)

        # include minimum 2 nameserver fields and 1 blank one
        if len(value) < 4:
            value.append("")

        if value[-1]:
            value.append("")

        field_width = min(30, max(15, (get_terminal_size().columns - 10) // 2))
        field_limit = 15

        while 1:
            pre_fields: list[tuple[str, str, int, int]] = [
                ("IP Address", value[0], field_width, field_limit),
                ("Netmask", value[1], field_width, field_limit),
                ("Default Gateway", value[2], field_width, field_limit),
            ]

            for i in range(len(value[3:])):
                pre_fields.append(
                    ("Name Server", value[3 + i], field_width, 64)
                )

            fields: list[tuple[str, int, int, str, int, int, int, int]] = (
                format_fields(pre_fields)
            )
            text = f"Static IP configuration ({self.ifname})"
            retcode, input = self.console.form(
                "Network settings", text, fields, autosize=True
            )
            log.debug("static ip fields: %s", fields)
            log.debug("static ip input: %s", input)
            log.debug("static ip retcode: %s", retcode)
            if retcode is not self.OK:
                break

            # remove any whitespaces the user might of included
            value = list(map(str.strip, input))
            input = value.copy()

            # unconfigure the nic if all entries are empty
            if not input[0] and not input[1] and not input[2] and not input[3]:
                ifutil.unconfigure_if(self.ifname)
                break

            addr, netmask, gateway = input[:3]
            nameservers = input[3:]
            for i in range(nameservers.count("")):
                nameservers.remove("")

            err_parts = _validate(addr, netmask, gateway, nameservers)
            if err_parts:
                err: str = "\n".join(err_parts)
                self.console.msgbox("Error", err, autosize=True)
            else:
                in_ssh = "SSH_CONNECTION" in os.environ
                if not in_ssh or (
                    in_ssh
                    and self.console.yesno(
                        "Warning: Changing ip while an ssh session is active"
                        " will drop said ssh session!",
                        autosize=True,
                    )
                    == self.OK
                ):
                    maybe_err: str | None = ifutil.set_static(
                        self.ifname, addr, netmask, gateway, nameservers
                    )
                    if maybe_err is None:
                        break
                    self.console.msgbox("Error", maybe_err, autosize=True)
                else:
                    break

        return "ifconf"

    def _ifconf_dhcp(self) -> str:
        in_ssh = "SSH_CONNECTION" in os.environ
        if not in_ssh or (
            in_ssh
            and self.console.yesno(
                "Warning: Changing ip while an ssh session is active will"
                " drop said ssh session!",
                autosize=True,
            )
            == self.OK
        ):
            self.console.infobox(f"Requesting DHCP for {self.ifname}...")
            err = ifutil.set_dhcp(self.ifname)
            if err:
                self.console.msgbox("Error", err)

        return "ifconf"

    def _ifconf_default(self) -> str:
        conf.Conf().set_default_nic(self.ifname)
        return "ifconf"

    def _adv_install(self) -> str:
        text = "Please note that any changes you may have made to the\n"
        text += "live system will *not* be installed to the hard disk.\n\n"
        self.console.msgbox("Installer", text)

        self.installer.execute()
        return "advanced"

    def _shutdown(self, text: str, opt: str) -> str:
        if self.console.yesno(text) == self.OK:
            self.running = False
            cmd = f"shutdown {opt} now"
            fgvt = os.environ.get("FGVT")
            if fgvt:
                cmd = f"chvt {fgvt}; " + cmd
            os.system(cmd)

        return "advanced"

    def _adv_reboot(self) -> str:
        return self._shutdown("Reboot this server?", "-r")

    def _adv_shutdown(self) -> str:
        return self._shutdown("Shut down this server?", "-h")

    def _adv_quit(self) -> str:
        if not self.advanced_enabled:
            self.running = False
            return "usage"

        if (
            self.console.yesno("Do you really want to quit?", autosize=True)
            == self.OK
        ):
            self.running = False

        return "advanced"

    def _get_networking_menu(self) -> list[tuple[str, str]]:
        items = []
        if conf.Conf().networking:
            items.append(("Network adapters", "Configure IP settings"))
        for label, (path, description) in NETWORKING_PLUGINS.items():
            if path in self.pluginManager.path_map:
                items.append((label, description))
        return items

    def _adv_networking(self) -> str:
        items = self._get_networking_menu()
        if not items:
            return "advanced"
        code, choice = self.console.menu(
            "Networking", "Choose a setting", items, compact=True
        )
        if code != self.OK:
            return "advanced"
        if choice == "Network adapters":
            return "networking"
        return NETWORKING_PLUGINS[choice][0]

    quit = _adv_quit

    def loop(self, dialog: str | Any | None = "usage") -> None:
        self.running = True
        prev_dialog = dialog
        standalone = dialog != "usage"  # no "back" for plugins

        while dialog and self.running:
            try:
                if not dialog.startswith(PLUGIN_PATH):
                    try:
                        method = getattr(self, dialog)
                    except AttributeError:
                        raise ConfconsoleError(
                            f"dialog not supported: {dialog}"
                        )
                else:
                    try:
                        method = self.pluginManager.path_map[dialog].run
                    except KeyError:
                        raise ConfconsoleError(
                            f"could not find plugin dialog: {dialog}"
                        )

                new_dialog = method()
                if standalone:  # XXX This feels dirty
                    break
                prev_dialog = dialog
                dialog = new_dialog

            except KeyboardInterrupt:
                self.console.confirm_quit()
                dialog = "usage"
                standalone = False
            except Exception:  # TODO should only catch specific errors
                sio = StringIO()
                traceback.print_exc(file=sio)

                self.console.msgbox("Caught exception", sio.getvalue())
                dialog = prev_dialog


def main() -> None:
    interactive = True
    advanced_enabled = True
    plugin_name = None

    if os.geteuid() != 0:
        fatal("confconsole needs root privileges to run")

    try:
        l_opts = ["help", "usage", "nointeractive", "plugin="]
        opts, _ = getopt.gnu_getopt(sys.argv[1:], "hn", l_opts)
    except getopt.GetoptError as e:
        usage(e)

    for opt, val in opts:
        if opt in ("-h", "--help"):
            usage()
        elif opt == "--usage":
            advanced_enabled = False
        elif opt == "--nointeractive":
            interactive = False
        elif opt == "--plugin":
            plugin_name = val
        else:
            usage()

    em = plugin.EventManager()
    pm = plugin.PluginManager(
        PLUGIN_PATH, {"eventManager": em, "interactive": interactive}
    )

    if plugin_name:
        ps = list(
            filter(
                lambda x: isinstance(x, plugin.Plugin),
                pm.getByName(plugin_name),
            )
        )

        if len(ps) > 1:
            fatal(f"plugin name ambiguous, matches all of {ps}")
        elif len(ps) == 1:
            p = ps[0]

            if interactive:
                tc = TurnkeyConsole(pm, em, advanced_enabled)
                tc.loop(dialog=p.path)  # calls .run()
            else:
                assert isinstance(p, plugin.Plugin)
                p.module.run()
        else:
            fatal("no such plugin")
    else:
        tc = TurnkeyConsole(pm, em, advanced_enabled)
        tc.loop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        subprocess.run(["stty", "sane"], check=False)
        sys.exit(130)
