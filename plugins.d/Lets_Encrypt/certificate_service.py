#!/usr/bin/python3
"""Shared TurnKey certificate operations for Confconsole and Webmin."""

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile


ETC = Path("/etc/dehydrated")
SHARE = Path("/usr/share/confconsole/letsencrypt")
CRON = Path("/etc/cron.daily/confconsole-dehydrated")
CERT = Path("/etc/ssl/private/cert.pem")
CERT_KEY = Path("/etc/ssl/private/cert.key")
CERT_CHAIN = Path("/usr/local/share/ca-certificates/cert.crt")
ARCHIVE = Path("/var/lib/dehydrated/certs")
RUN = Path("/run/confconsole-acme")
LOCK = RUN / "update.lock"
UNIT = "confconsole-acme.service"
WRAPPER = Path(__file__).resolve().with_name("dehydrated-wrapper")
SERVICE = Path(__file__).resolve()
LEXICON = Path("/usr/local/src/venv/lexicon/bin/lexicon")
STAGING_CA = "https://acme-staging-v02.api.letsencrypt.org/directory"
PROVIDER = re.compile(r"[a-z][a-z0-9_]{0,40}\Z")
PEM_LEAF = re.compile(br"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", re.S)
LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
ALIAS = re.compile(r"[a-zA-Z0-9_.-]{1,253}\Z")
FIELDS = {
    "cloudflare": ("Cloudflare", (
        ("auth_token", "API token or global API key", True),
        ("zone_id", "Zone ID", False),
        ("auth_username", "Account email (global API key only)", False),
    )),
    "route53": ("Amazon Route 53", (
        ("auth_access_key", "Access key ID", False),
        ("auth_access_secret", "Secret access key", True),
        ("zone_id", "Hosted zone ID", False),
    )),
}


class CertificateError(Exception):
    """An action or recovery step suitable for display to the administrator."""


def config_file():
    return ETC / "confconsole.config"


def domains_file():
    return ETC / "confconsole.domains.txt"


def hook_file():
    return ETC / "confconsole.hook.sh"


def provider_file(provider):
    return ETC / f"lexicon_{provider}.yml"


def read(path, default=""):
    try:
        return path.read_text()
    except FileNotFoundError:
        return default


def directives(text):
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def values(text):
    return dict((k, v.strip().strip("'").strip('"'))
                for k, v in (line.split("=", 1) for line in directives(text) if "=" in line))


def configured_domains(text):
    current = directives(text)
    return current[0].split(">", 1)[0].split() if current else []


def default_alias(domains):
    for domain in domains:
        if domain.startswith("*."):
            return domain.replace("*", "star").replace(".", "_")
    return ""


def existing_configuration():
    config = read(config_file(), read(SHARE / "dehydrated-confconsole.config"))
    domains = read(domains_file())
    return config, domains


def stock_certificate_path(path):
    # The deploy hooks write these paths directly. A symlink could redirect
    # a TurnKey issue into a separately managed service's certificate.
    if path.parent.resolve() != path.parent:
        return False
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except FileNotFoundError:
        return True


def browser_editable(config, domains):
    # Preserve unmanaged directives, aliases, edited hooks and schedules.
    if not all(stock_certificate_path(path) for path in (CERT, CERT_KEY, CERT_CHAIN)):
        return False
    defaults = read(SHARE / "dehydrated-confconsole.config")
    options = re.compile(
        r"""(?:CHALLENGETYPE=(?:['"]?)(?:http-01|dns-01)(?:['"]?)|"""
        r"""PROVIDER=(?:['"]?)[a-z][a-z0-9_]{0,40}(?:['"]?))\Z"""
    )

    def without_options(text):
        return [line for line in directives(text)
                if not options.fullmatch(line)
                and line not in (f'CA="{STAGING_CA}"', f"CA='{STAGING_CA}'", f"CA={STAGING_CA}")]

    if without_options(config) != without_options(defaults):
        return False
    if any(path.is_symlink() for path in (config_file(), domains_file(), hook_file(), CRON)):
        return False
    groups = directives(domains)
    if len(groups) > 1 or len(configured_domains(domains)) > 5:
        return False
    if groups and ">" in groups[0]:
        parts = groups[0].split(">", 1)
        if parts[1].strip() != default_alias(parts[0].split()):
            return False
    if hook_file().exists():
        hook = read(hook_file())
        if hook not in {read(SHARE / f"dehydrated-confconsole.hook-{mode}.sh")
                        for mode in ("http-01", "dns-01")}:
            return False
    if CRON.exists() and read(CRON) != read(SHARE / "dehydrated-confconsole.cron"):
        return False
    return True


def validate_domains(domains, challenge):
    if challenge not in ("http-01", "dns-01"):
        raise CertificateError("Choose HTTP or DNS validation.")
    if (not isinstance(domains, list) or len(domains) > 5 or
            any(not isinstance(domain, str) for domain in domains)):
        raise CertificateError("Enter up to five domain names.")
    cleaned = [domain.strip().lower().rstrip(".") for domain in domains if domain.strip()]
    if not cleaned:
        raise CertificateError("Enter at least one domain name.")
    for domain in cleaned:
        name = domain.removeprefix("*.")
        labels = name.split(".")
        if len(domain) > 253 or len(labels) < 2 or any(not LABEL.fullmatch(p) for p in labels):
            raise CertificateError("Use public domain names such as example.com.")
        if domain != name and challenge != "dns-01":
            raise CertificateError("Choose DNS validation for wildcard names.")
    if len(set(cleaned)) != len(cleaned):
        raise CertificateError("Enter each domain name once.")
    return cleaned


def write(path, content, mode=None):
    # Keep existing service readability when changing managed settings.
    if path.is_symlink():
        raise CertificateError("Manage linked certificate configuration files from Confconsole.")
    attributes = path.stat() if path.exists() else None
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as staged:
        temporary = Path(staged.name)
        try:
            staged.write(content.encode() if isinstance(content, str) else content)
            staged.flush()
            if attributes is not None:
                os.fchown(staged.fileno(), attributes.st_uid, attributes.st_gid)
            os.fchmod(staged.fileno(), mode if mode is not None else
                      stat.S_IMODE(attributes.st_mode) if attributes is not None else 0o644)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


@contextmanager
def locked(wait=False):
    LOCK.parent.mkdir(mode=0o700, exist_ok=True)
    with LOCK.open("a") as descriptor:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError:
            raise CertificateError("Certificate setup or renewal is already running. Check its status before trying again.")
        yield descriptor


@contextmanager
def transaction(paths):
    # These are configuration files only. The wrapper owns certificate backup
    # and restoration, including service recovery after a failed activation.
    with tempfile.TemporaryDirectory(prefix="confconsole-acme-") as directory:
        backups = {}
        for i, path in enumerate(paths):
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise CertificateError("Manage custom certificate paths from Confconsole.")
            if path.exists():
                saved = Path(directory) / str(i)
                shutil.copy2(path, saved)
                attributes = path.stat()
                os.chown(saved, attributes.st_uid, attributes.st_gid)
                backups[path] = saved
        try:
            yield
        except (OSError, CertificateError, KeyboardInterrupt):
            for path in paths:
                if path in backups:
                    saved = backups[path]
                    # The newly written target may have different ownership
                    # and mode. Restore both from the original.
                    write(path, saved.read_bytes(), stat.S_IMODE(saved.stat().st_mode))
                    os.chown(path, saved.stat().st_uid, saved.stat().st_gid)
                else:
                    path.unlink(missing_ok=True)
            raise


def updated_configuration(text, challenge, provider):
    fields = {"CHALLENGETYPE": challenge}
    if challenge == "dns-01":
        fields["PROVIDER"] = provider
    result = []
    for line in text.splitlines():
        key = line.split("=", 1)[0]
        if key in fields:
            result.append(f'{key}="{fields.pop(key)}"')
        else:
            result.append(line)
    return "\n".join([*result, *(f'{key}="{value}"' for key, value in fields.items())]) + "\n"


def updated_domains(text, domains, alias):
    line = " ".join(domains) + (f" > {alias}" if alias else "")
    lines = text.splitlines()
    for i, existing in enumerate(lines):
        if existing.strip() and not existing.lstrip().startswith("#"):
            lines[i] = line
            break
    else:
        lines.append(line)
    return "\n".join(lines) + "\n"


def ready():
    return ETC.is_dir() and all(shutil.which(name) for name in ("dehydrated", "authbind"))


def current_certificate():
    if not CERT.is_file():
        return [], "", False
    result = subprocess.run(
        ["openssl", "x509", "-noout", "-enddate", "-dateopt", "iso_8601", "-ext", "subjectAltName",
         "-in", str(CERT)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        return [], "", False
    domains = re.findall(r"DNS:([^,\s]+)", result.stdout)
    expiry = re.search(r"^notAfter=(.+)$", result.stdout, re.M)
    if not expiry:
        return domains, "", False
    expires = datetime.fromisoformat(expiry[1].replace(" ", "T").replace("Z", "+00:00"))
    return domains, expires.isoformat(), expires > datetime.now(timezone.utc)


def leaf(path):
    try:
        match = PEM_LEAF.search(path.read_bytes())
    except FileNotFoundError:
        return None
    return b"".join(match[1].split()) if match else None


def managed_certificate(configured, domains):
    if not configured or not set(configured) <= set(domains):
        return False
    # Compare the installed leaf with dehydrated's saved leaf. This excludes
    # the factory self-signed certificate and separately assigned TLS certs.
    installed = leaf(CERT)
    if not installed:
        return False
    for name in {configured[0], default_alias(configured)} - {""}:
        if not ALIAS.fullmatch(name) or name in (".", ".."):
            continue
        storage = ARCHIVE / name
        if leaf(storage / "cert.pem") == installed:
            return True
        # After rollback, dehydrated may still point to its newer candidate.
        if any(leaf(path) == installed for path in storage.glob("cert-*.pem")):
            return True
    return False


def check_active_certificate():
    _, names = existing_configuration()
    domains, _, valid = current_certificate()
    return valid and managed_certificate(configured_domains(names), domains)


def renewal_enabled():
    return CRON.is_file() and bool(stat.S_IMODE(CRON.stat().st_mode) & 0o111)


def set_renewal(enabled, browser=True):
    if not isinstance(enabled, bool):
        raise CertificateError("Choose whether to enable automatic renewal.")
    with locked():
        config, names = existing_configuration()
        if browser and not browser_editable(config, names):
            raise CertificateError("Manage this custom renewal schedule in Confconsole.")
        domains, _, valid = current_certificate()
        if not CRON.is_file() or (enabled and browser and not (
                valid and managed_certificate(configured_domains(names), domains))):
            raise CertificateError("Get a valid TurnKey certificate before enabling renewal.")
        mode = stat.S_IMODE(CRON.stat().st_mode)
        CRON.chmod(mode | 0o111 if enabled else mode & ~0o111)


def provider_options():
    result = []
    providers = {p.stem.removeprefix("lexicon_") for p in ETC.glob("lexicon_*.yml")
                 if p.is_file() and not p.is_symlink()}
    for provider in sorted(providers | FIELDS.keys()):
        if not PROVIDER.fullmatch(provider):
            continue
        label, fields = FIELDS.get(provider, (provider, ()))
        result.append({"id": provider, "label": label, "stored": provider in providers,
                       "fields": [{"id": key, "label": description, "secret": secret,
                                   "optional": True} for key, description, secret in fields]})
    return result


def command(args, **kwargs):
    return subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, check=False, **kwargs).returncode


@contextmanager
def cancellation_requests():
    cancelled = False

    def request_stop(_signum, _frame):
        nonlocal cancelled
        cancelled = True

    signals = (signal.SIGINT, signal.SIGTERM)
    handlers = [(signum, signal.signal(signum, request_stop)) for signum in signals]
    try:
        yield lambda: cancelled
    finally:
        for signum, handler in handlers:
            signal.signal(signum, handler)


def run_wrapper(args, lock_fd, stop_requested):
    # subprocess.run kills its child when Python is interrupted. Keep the
    # wrapper alive long enough to run its EXIT trap and restore services.
    with subprocess.Popen(
        args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        pass_fds=(lock_fd,), start_new_session=True,
    ) as process:
        while not stop_requested():
            try:
                return process.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                continue
        if process.poll() is not None:
            return process.returncode
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            result = process.wait(timeout=90)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise CertificateError("Certificate recovery timed out. Check that your web services are running.")
        if result in (0, 75, 76):
            return result
        raise KeyboardInterrupt


def job_status():
    path = RUN / "status.json"
    job = json.loads(read(path, '{"state": "idle", "message": ""}'))
    if job["state"] == "running" and command(["systemctl", "is-active", "--quiet", UNIT]):
        job = json.loads(read(path, '{"state": "idle", "message": ""}'))
        if job["state"] == "running":
            return {"state": "failed", "message": "Certificate setup stopped. Check the server logs and try again."}
    return job


def status():
    config, names = existing_configuration()
    settings = values(config)
    available = ready()
    editable = browser_editable(config, names)
    domains, expires, valid = current_certificate()
    configured = configured_domains(names)
    managed = managed_certificate(configured, domains)
    reason = ""
    if not available:
        reason = "Install dehydrated and authbind to manage TurnKey certificates."
    elif not editable:
        reason = "Manage this custom certificate configuration in Confconsole."
    return {"available": available, "configurable": available and editable, "reason": reason,
            "configured_domains": configured, "domains": domains, "expires": expires,
            "managed": managed, "renewal_enabled": renewal_enabled(),
            "renewal_available": valid and managed and CRON.is_file() and editable,
            "challenge": settings.get("CHALLENGETYPE", "http-01"),
            "provider": settings.get("PROVIDER", ""), "providers": provider_options(),
            "dns_setup_needed": not LEXICON.is_file(), "job": job_status(),
            "staging": settings.get("CA") == STAGING_CA}


def loaded_module(name):
    # Confconsole loads each plugin by path, while Webmin runs this file
    # directly. Neither path relies on a process-wide import path change.
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, SERVICE.with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def credentials_for_browser(provider, supplied):
    _, fields = FIELDS.get(provider, (provider, ()))
    keys = {key for key, _, _ in fields}
    if (not isinstance(supplied, dict) or not supplied.keys() <= keys or
            any(not isinstance(v, str) or len(v) > 2048 or "\n" in v or "\r" in v or "\x00" in v
                for v in supplied.values())):
        raise CertificateError("Check the DNS provider settings and try again.")
    supplied = {key: value.strip() for key, value in supplied.items() if value.strip()}
    path = provider_file(provider)
    if path.is_symlink():
        raise CertificateError("Manage these linked DNS credentials in Confconsole.")
    if not supplied and path.is_file():
        return None
    if not fields:
        raise CertificateError("Set up this DNS provider in Confconsole first.")
    editor = loaded_module("dns_config")
    try:
        if provider == "cloudflare":
            content = read(path, read(SHARE / "lexicon-confconsole-provider_cloudflare.yml"))
            previous = editor.cloudflare_values(content)
            merged = {**previous, **supplied}
            if not merged.get("auth_token"):
                raise CertificateError("Enter a Cloudflare API token or global API key.")
            if "auth_username" in supplied and "auth_token" not in supplied and (
                    supplied["auth_username"] != previous.get("auth_username")):
                raise CertificateError("Enter a new global API key when changing the Cloudflare account.")
            if "auth_token" in supplied and "auth_username" not in supplied:
                merged["auth_username"] = ""
            if merged.get("zone_id") and not re.fullmatch(r"[a-fA-F0-9]{32}", merged["zone_id"]):
                raise CertificateError("Enter the 32-character Cloudflare zone ID.")
            return editor.update_cloudflare(content, merged)
        # Explicit Route 53 keys must be submitted as a pair. Empty settings
        # use AWS's existing default credentials chain, including EC2 roles.
        if bool(supplied.get("auth_access_key")) != bool(supplied.get("auth_access_secret")):
            raise CertificateError("Enter the Route 53 access key ID and secret access key together.")
        previous = editor.parse_config(read(path))
        import yaml
        return yaml.safe_dump({**previous, **supplied}, sort_keys=False)
    except editor.ConfigError:
        raise CertificateError("Manage these advanced DNS credentials in Confconsole.")


def request_settings(payload, browser=True):
    if not isinstance(payload, dict) or payload.get("accept_terms") is not True:
        raise CertificateError("Accept the Let's Encrypt terms to request a certificate.")
    challenge = payload.get("challenge")
    domains = validate_domains(payload.get("domains"), challenge)
    provider = payload.get("provider", "") if challenge == "dns-01" else ""
    if challenge == "dns-01" and (not isinstance(provider, str) or not PROVIDER.fullmatch(provider)):
        raise CertificateError("Choose a DNS provider.")
    credentials = (credentials_for_browser(provider, payload.get("credentials", {}))
                   if browser and provider else None)
    return domains, challenge, provider, credentials


def issue(payload, *, terminal_credentials=None, alias="", browser=True, wait=False):
    if not ready():
        raise CertificateError("Install dehydrated and authbind to request a certificate.")
    with locked(wait=wait) as lock, cancellation_requests() as stop_requested:
        config, old_domains = existing_configuration()
        if browser and not browser_editable(config, old_domains):
            raise CertificateError("Manage this custom certificate configuration in Confconsole.")
        domains, challenge, provider, credentials = request_settings(payload, browser)
        if provider and not LEXICON.is_file():
            if browser:
                write_job("running", "Installing the DNS validation tool.")
            if not loaded_module("dns_01").install_lexicon():
                raise CertificateError("Could not install the DNS validation tool. Check internet access and disk space.")
        if alias and (not ALIAS.fullmatch(alias) or alias in (".", "..")):
            raise CertificateError("Enter an alias using letters, digits, underscores, hyphens or periods.")
        alias = alias or default_alias(domains)
        touched = [config_file(), domains_file(), hook_file(), CRON]
        if provider:
            touched.append(provider_file(provider))
        with transaction(touched):
            if stop_requested():
                raise KeyboardInterrupt
            content = credentials if browser else terminal_credentials
            if provider and content is not None:
                write(provider_file(provider), content, 0o600)
            write(config_file(), updated_configuration(config, challenge, provider))
            write(domains_file(), updated_domains(old_domains, domains, alias))
            if browser:
                write_job("running", "Validating domains and installing the certificate.")
            args = [str(WRAPPER), "--locked-fd", str(lock.fileno()), "--register", "--force"]
            if browser:
                args.append("--check-installed")
            result = run_wrapper(args, lock.fileno(), stop_requested)
            if result == 75:
                raise CertificateError("Could not activate the certificate. The previous certificate is restored. Check the web service and try again.")
            if result == 76:
                raise CertificateError("Could not recover a web service after certificate setup. Check the server logs.")
            if result:
                raise CertificateError(
                    "Certificate setup failed. Check the domain addresses and public port 80, then try again."
                    if challenge == "http-01" else
                    "Certificate setup failed. Check the DNS provider credential and zone, then try again.")
    return True


def write_job(state, message):
    write(RUN / "status.json", json.dumps({"state": state, "message": message}), 0o600)


def queue(payload):
    if not ready():
        raise CertificateError("Install dehydrated and authbind to request a certificate.")
    RUN.mkdir(mode=0o700, exist_ok=True)
    with locked():
        if job_status()["state"] == "running":
            raise CertificateError("Certificate setup is already running.")
        if not browser_editable(*existing_configuration()):
            raise CertificateError("Manage this custom certificate configuration in Confconsole.")
        request_settings(payload)
        request = RUN / "request.json"
        write(request, json.dumps(payload), 0o600)
        write_job("running", "Preparing certificate setup.")
        if command(["systemd-run", "--quiet", "--collect", "--unit", UNIT,
                    "--property=KillMode=mixed", "--property=TimeoutStopSec=100s",
                    str(SERVICE), "worker"]):
            request.unlink(missing_ok=True)
            write_job("failed", "Certificate setup could not start. Try again.")
            raise CertificateError("Certificate setup could not start. Try again.")


def execute_job():
    request = RUN / "request.json"
    try:
        try:
            payload = json.loads(request.read_text())
        finally:
            request.unlink(missing_ok=True)
        issue(payload, wait=True)
    except CertificateError as error:
        write_job("failed", str(error))
    except KeyboardInterrupt:
        write_job("failed", "Certificate setup was interrupted. Check the server status before trying again.")
    except (OSError, ValueError, subprocess.SubprocessError):
        write_job("failed", "Certificate setup could not finish. Check the server logs and try again.")
    else:
        write_job("succeeded", "Certificate installed.")


def main():
    if os.geteuid() != 0:
        print(json.dumps({"error": "Run certificate setup as root."}))
        return 1
    if len(sys.argv) != 2 or sys.argv[1] not in ("status", "start", "renewal", "worker", "check-installed"):
        print(json.dumps({"error": "Choose a certificate operation."}))
        return 1
    action = sys.argv[1]
    try:
        if action == "check-installed":
            return 0 if check_active_certificate() else 1
        if action == "worker":
            execute_job()
            return 0
        if action in ("start", "renewal"):
            payload = json.loads(sys.stdin.read(16385))
            if not isinstance(payload, dict):
                raise CertificateError("Check the certificate form and try again.")
            if action == "start":
                queue(payload)
            else:
                set_renewal(payload.get("enabled"))
        print(json.dumps(status()))
    except CertificateError as error:
        print(json.dumps({"error": str(error)}))
        return 1
    except (OSError, ValueError, subprocess.SubprocessError):
        print(json.dumps({"error": "Certificate settings could not be read or updated. Check the server logs."}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
