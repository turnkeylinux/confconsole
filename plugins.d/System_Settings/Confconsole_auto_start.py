"""Enable/Disable Confconsole autostart on login"""

from os import chmod, stat, path

CONFCONSOLE_AUTO = path.expanduser("~/.bashrc.d/confconsole-auto")


def enable_autostart() -> None:
    st = stat(CONFCONSOLE_AUTO)
    chmod(CONFCONSOLE_AUTO, st.st_mode | 0o111)


def disable_autostart() -> None:
    st = stat(CONFCONSOLE_AUTO)
    chmod(CONFCONSOLE_AUTO, st.st_mode ^ 0o111)


def check_autostart() -> str | bool:
    if path.isfile(CONFCONSOLE_AUTO):
        st = stat(CONFCONSOLE_AUTO)
        return st.st_mode & 0o111 == 0o111
    else:
        return "fail"


def run():
    enabled = check_autostart()
    if enabled == "fail":
        msg = "Auto-start file for Confconsole does not exist.\n"
        # console is inherited so doesn't need to be defined
        r = console.msgbox("Error", msg)  # type: ignore[not-defined]
    else:
        status = "enabled" if enabled else "disabled"
        msg = """Confconsole Auto start is currently {}"""
        r = console._wrapper(
            "yesno",  # type: ignore[not-defined]
            msg.format(status),
            10,
            30,
            yes_label="Toggle",
            no_label="Ok",
        )
        while r == "ok":
            if enabled:
                disable_autostart()
            else:
                enable_autostart()
            enabled = check_autostart()
            status = "enabled" if enabled else "disabled"
            r = console._wrapper(
                "yesno",  # type: ignore[not-defined]
                msg.format(status),
                10,
                30,
                yes_label="Toggle",
                no_label="Ok",
            )
