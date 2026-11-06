"""Disposable terminal exercise; never writes system settings."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import confconsole

spec = importlib.util.spec_from_file_location(
    "dns_config", ROOT / "plugins.d/Lets_Encrypt/dns_config.py"
)
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)
console = confconsole.Console("DNS-01 QA fixture")
if sys.argv[1] == "cloudflare":
    lines = (
        (
            ROOT
            / "share/letsencrypt/lexicon-confconsole-provider_cloudflare.yml"
        )
        .read_text()
        .splitlines()
    )
    result = config.edit_config(console, "cloudflare", lines)
else:
    text = "\n".join(f"key{i}: value{i}" for i in range(60)) + "\n"
    result = config.edit_yaml(console, "generic", text)
print("CANCELLED" if result is None else "SAVED")
if result is not None:
    print(
        "VALID"
        if config.parse_config(
            "\n".join(result) if isinstance(result, list) else result
        )
        else "EMPTY"
    )
