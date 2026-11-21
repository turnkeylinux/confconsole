"""Get Let's Encrypt SSL cert"""

menu_order = -2

import requests
from os.path import isdir
from shutil import which
from urllib.parse import urlparse

LE_INFO_URL = "https://acme-v02.api.letsencrypt.org/directory"

TITLE = "Certificate Creation Wizard"

DESC = """Please enter domain(s) to generate certificate for.

To generate a single certificate for up to five domains (including subdomains),
enter each domain into a box, one domain per box. Empty boxes will be ignored.

Wildcard domains are supported, but only when using DNS-01 challenge. Alias
will be auto generated, so should not be entered here. See:
https://www.turnkeylinux.org/docs/confconsole/letsencrypt#wildcard

To generate multiple certificates, please consult the advanced docs:
https://www.turnkeylinux.org/docs/letsencrypt#advanced
"""

dehydrated_conf = "/etc/dehydrated"
def doOnce() -> None:
    global dns_01, dns_config, certificate_service
    # impByPath inherited so doesn't need to be defined
    dns_01 = impByPath("Lets_Encrypt/dns_01.py")
    dns_config = impByPath("Lets_Encrypt/dns_config.py")
    certificate_service = impByPath("Lets_Encrypt/certificate_service.py")


def run() -> None:
    field_width = 60
    msg = ""
    try:
        response = requests.get(LE_INFO_URL, timeout=(5, 15))
        response.raise_for_status()
    except requests.exceptions.SSLError:
        msg = (
            "The ACME server's TLS certificate could not be verified.\n\n"
            "Check the system clock and trusted CA certificates. If a proxy "
            "inspects HTTPS, ask your administrator to configure its trusted "
            "CA or use a trusted connection."
        )
    except requests.exceptions.Timeout:
        msg = (
            "The ACME directory request timed out. Check internet access "
            "and proxy settings."
        )
    except requests.exceptions.ConnectionError:
        msg = (
            "Could not connect to the ACME server. Check DNS, internet "
            "access and proxy settings."
        )
    except requests.exceptions.HTTPError:
        msg = "The ACME server returned an HTTP error. Try again later."
    except requests.exceptions.RequestException:
        msg = (
            "The ACME directory request failed. Check internet access "
            "and proxy settings."
        )
    else:
        try:
            tos_url = response.json()["meta"]["termsOfService"]
            if (
                not isinstance(tos_url, str)
                or not tos_url.startswith("https://")
                or not urlparse(tos_url).hostname
                or any(char.isspace() for char in tos_url)
            ):
                raise ValueError("Invalid terms URL")
        except (ValueError, KeyError, TypeError):
            msg = (
                "The ACME directory returned invalid terms-of-service "
                "information. Try again later; if this persists, check "
                "whether a proxy is replacing the server's response."
            )
    if msg:
        console.msgbox(
            "Let's Encrypt unavailable",
            msg + "\n\nChoose Get certificate to retry after resolving this.",
            autosize=True,
        )
        return

    ret = console.yesno(
        "Before getting a Let's Encrypt certificate, you must agree to the"
        " current Terms of Service.\n\n"
        "You can find the current Terms of Service here:\n\n"
        f"{tos_url}\n\n"
        "Do you agree to the Let's Encrypt Terms of Service?",
        autosize=True,
    )
    if ret != "ok":
        return

    if not isdir(dehydrated_conf):
        console.msgbox(
            "Error",
            f"Dehydrated not installed or {dehydrated_conf} not found,"
            " dehydrated can be installed via apt from the Debian repos.\n\n"
            "More info: www.turnkeylinux.org/docs/letsencrypt",
            autosize=True,
        )
        return

    ret, challenge = console.menu(
        "Challenge type",
        "Select challenge type to use",
        [
            ("http-01", "Requires public web access to this system"),
            ("dns-01", "Requires your DNS provider to provide an API"),
        ],
    )
    if ret != "ok":
        return

    provider = ""
    provider_settings = None
    if challenge == "http-01":
        ret = console.yesno(
            "DNS must be configured before obtaining certificates."
            " Incorrectly configured DNS and excessive attempts could"
            " lead to being temporarily blocked from requesting"
            " certificates.\n\n"
            "You can check for a valid 'A' DNS record for your domain via"
            " Google:\n    https://toolbox.googleapps.com/apps/dig/\n\n"
            "Do you wish to continue?",
            autosize=True,
        )
        if ret != "ok":
            return

    elif challenge == "dns-01":
        if not dns_01.initial_setup():
            return
        providers, err = dns_01.get_providers()
        if err or not providers:
            console.msgbox("DNS providers", err or "No DNS providers are available.", autosize=True)
            return
        config_text, _ = certificate_service.existing_configuration()
        selected = certificate_service.values(config_text).get("PROVIDER")
        # Put the provider saved by either interface first. Keep other stored
        # credentials available when an administrator changes providers.
        providers = sorted(providers, key=lambda choice: choice[0] != selected)
        ret, provider = console.menu(
            "DNS providers list", "Select DNS provider you'd like to use", providers,
        )
        if ret != "ok" or not provider:
            return

        if provider == "auto" and not which("nslookup"):
            ret = console.yesno(
                "Automatic provider selection needs the nslookup tool. Install it now?",
                autosize=True,
            )
            if ret != "ok":
                return
            returncode, message = dns_01.apt_install(["dnsutils"])
            if returncode != 0:
                console.msgbox("Error", message, autosize=True)
                return

        try:
            _, config = dns_01.load_config(provider)
        except OSError:
            console.msgbox(
                "Could not read settings",
                "Check that the provider configuration and Confconsole "
                "templates are readable, then retry.",
                autosize=True,
            )
            return
        values = dns_config.edit_config(console, provider, config)
        if values is None:
            return
        provider_settings = "\n".join(values) + "\n"

    _, config_names = certificate_service.existing_configuration()
    groups = certificate_service.directives(config_names)
    values = certificate_service.configured_domains(config_names)[:5]
    values += [""] * (5 - len(values))
    alias = groups[0].partition(">")[2].strip() if groups else ""

    while True:
        fields = [
            (f"Domain {i + 1}", i + 1, 0, value, i + 1, 10, field_width, 255)
            for i, value in enumerate(values)
        ]
        ret, values = console.form(TITLE, DESC, fields, autosize=True)
        if ret != "ok":
            return
        try:
            domains = certificate_service.validate_domains(values, challenge)
        except certificate_service.CertificateError as error:
            console.msgbox("Check domain names", str(error))
            continue
        if console.yesno(
            "Replace the current certificate configuration and request a certificate?"
        ) != "ok":
            continue
        form = {"domains": domains, "challenge": challenge, "provider": provider,
                "accept_terms": True}
        try:
            certificate_service.issue(
                form, terminal_credentials=provider_settings, alias=alias, browser=False
            )
        except certificate_service.CertificateError as error:
            console.msgbox("Certificate setup", str(error))
        except OSError:
            console.msgbox(
                "Certificate setup", "Could not update certificate settings. Check the server logs."
            )
        else:
            console.msgbox("Certificate installed", "The TurnKey certificate is ready.")
            return
