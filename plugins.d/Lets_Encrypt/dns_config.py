#!/usr/bin/python3
"""Provider settings editing, without changing files until the user saves."""

import json
import re
from shutil import get_terminal_size

import yaml


class ConfigError(ValueError):
    pass


def parse_config(text: str) -> dict:
    try:
        data = yaml.safe_load(text)
        node = yaml.compose(text)
    except yaml.YAMLError:
        # Parser diagnostics can include the credential-bearing source line.
        raise ConfigError(
            "Invalid YAML. Check the key: value lines."
        ) from None
    if data is None:
        return {}
    if not isinstance(data, dict) or any(not isinstance(k, str) for k in data):
        raise ConfigError("Settings must be a YAML mapping of option: value.")
    keys = [key.value for key, value in node.value]
    if len(set(keys)) != len(keys):
        raise ConfigError("Each setting must appear only once.")
    return data


def cloudflare_values(text: str) -> dict[str, str]:
    data = parse_config(text)
    values = {}
    for key in ("auth_username", "auth_token", "zone_id"):
        value = data.get(key, "")
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise ConfigError("Cloudflare credentials must be text values.")
        values[key] = value
    # The form preserves other options verbatim. Complex YAML credentials can
    # still be edited intact with the full editor.
    if any(
        isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken))
        for token in yaml.scan(text)
    ):
        raise ConfigError("Use the full editor for anchored settings.")
    node = yaml.compose(text)
    if node:
        if node.flow_style or any(key.value == "<<" for key, _ in node.value):
            raise ConfigError("Use the full editor for structured settings.")
        for key, value in node.value:
            if key.value in values and (
                key.start_mark.line != value.start_mark.line
                or value.start_mark.index < key.end_mark.index
                or key.start_mark.column != 0
                or value.start_mark.line != value.end_mark.line
                or value.style in ("|", ">")
            ):
                raise ConfigError(
                    "Use the full editor for multiline settings."
                )
    return values


def update_cloudflare(text: str, values: dict[str, str]) -> str:
    """Replace only authentication settings, retaining unrelated YAML text."""
    cloudflare_values(text)
    node = yaml.compose(text)
    edits = []
    found = set()
    if node:
        for key, value in node.value:
            if key.value not in values:
                continue
            found.add(key.value)
            if values[key.value]:
                edits.append(
                    (
                        value.start_mark.index,
                        value.end_mark.index,
                        json.dumps(values[key.value]),
                    )
                )
            else:
                # Remove an unused authentication method, including its old
                # credential, rather than leaving it in a comment.
                end = text.find("\n", value.end_mark.index)
                end = len(text) if end < 0 else end + 1
                edits.append((key.start_mark.index, end, ""))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    for key, value in values.items():
        if key not in found and value:
            if text and not text.endswith("\n"):
                text += "\n"
            text += f"{key}: {json.dumps(value)}\n"
    parse_config(text)
    return text


def edit_yaml(console, provider: str, text: str) -> str | None:
    console.msgbox(
        "DNS provider settings",
        "Edit the authentication settings for " + provider + ".\n\n"
        "Remove # from the example keys you need and enter their values. "
        "Leave settings empty to use credentials supplied by the environment "
        "or an instance role, if your provider supports them.\n\n"
        "Use the arrow keys to scroll and Tab to reach Save or Cancel. "
        "Credentials are visible in this full editor.",
        autosize=True,
    )
    while True:
        ret, edited = console.editbox(f"{provider} settings (YAML)", text)
        if ret != "ok":
            return None
        try:
            data = parse_config(edited)
            if any(
                isinstance(v, str) and v.startswith("YOUR_")
                for v in data.values()
            ):
                raise ConfigError(
                    "Replace the example values with your settings."
                )
        except ConfigError as exc:
            console.msgbox("Settings need attention", str(exc), autosize=True)
            text = edited
            continue
        return edited


def edit_cloudflare(console, text: str) -> str | None:
    try:
        current = cloudflare_values(text)
    except ConfigError:
        return edit_yaml(console, "cloudflare", text)
    previous_method = "key" if current["auth_username"] else "token"
    while True:
        ret, method = console._wrapper(
            "menu",
            "Choose how to authenticate with Cloudflare.",
            height=0,
            width=0,
            menu_height=3,
            title="Cloudflare credentials",
            choices=[
                ("token", "API token (recommended)"),
                ("key", "Global API key and account email"),
                ("advanced", "Full configuration editor"),
            ],
            default_item=previous_method,
        )
        if ret != "ok":
            return None
        if method == "advanced":
            return edit_yaml(console, "cloudflare", text)
        email = current["auth_username"] if method == "key" else ""
        zone = current["zone_id"]
        pending_secret = (
            current["auth_token"] if method == previous_method else ""
        )
        while True:
            field_width = max(10, min(42, get_terminal_size().columns - 24))
            secret_label = (
                "API token:" if method == "token" else "Global API key:"
            )
            fields = [(secret_label, 1, 0, "", 1, 16, field_width, 4096, 1)]
            if method == "key":
                fields.append(
                    ("Account email:", 2, 0, email, 2, 16, field_width, 255, 0)
                )
            fields.append(
                (
                    "Zone ID (opt):",
                    len(fields) + 1,
                    0,
                    zone,
                    len(fields) + 1,
                    16,
                    field_width,
                    32,
                    0,
                )
            )
            hint = (
                (
                    "API token needs DNS edit access to your zone.\n"
                    "Zone ID is optional with Zone Read permission. "
                    "Supply it if your token cannot list zones."
                )
                if method == "token"
                else (
                    "Enter your Cloudflare account email and Global API key.\n"
                    "Zone ID is optional."
                )
            )
            keep = bool(pending_secret)
            if keep:
                hint += (
                    "\nLeave the secret blank to keep the current credential."
                )
            ret, entered = console._wrapper(
                "mixedform",
                hint,
                fields,
                height=0,
                width=0,
                form_height=len(fields),
                title="Cloudflare credentials",
                ok_label="Save",
                cancel_label="Back",
                insecure=True,
            )
            if ret != "ok":
                break
            secret = entered[0].strip()
            if not secret and keep:
                secret = pending_secret
            if method == "key":
                email = entered[1].strip()
            zone = entered[-1].strip()
            error = ""
            if not secret or secret.startswith("YOUR_"):
                error = "Enter your API token or Global API key."
            elif method == "key" and (
                "@" not in email or email.startswith("YOUR_")
            ):
                error = "Enter the email address for your Cloudflare account."
            elif zone and not re.fullmatch(r"[0-9a-fA-F]{32}", zone):
                error = "Zone ID must contain 32 hexadecimal characters."
            if error:
                pending_secret = secret
                console.msgbox(
                    "Credentials need attention", error, autosize=True
                )
                continue
            return update_cloudflare(
                text,
                {
                    "auth_token": secret,
                    "auth_username": email,
                    "zone_id": zone,
                },
            )


def edit_config(console, provider: str, config: list[str]) -> list[str] | None:
    text = "\n".join(config) + "\n"
    edited = (
        edit_cloudflare(console, text)
        if provider == "cloudflare"
        else edit_yaml(console, provider, text)
    )
    return None if edited is None else edited.splitlines()
