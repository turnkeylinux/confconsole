"""Run the interactive security update from either Confconsole entry point."""
import subprocess
import sys


def run_security_updates():
    """Show live updater output and let users read errors before returning."""
    if sys.stdout.isatty():
        print('\033[2J\033[H', end='', flush=True)
    try:
        result = subprocess.run(['turnkey-install-security-updates'], check=False)
        failed = result.returncode != 0
    except OSError as error:
        print(f'Could not start security updates: {error}', file=sys.stderr, flush=True)
        failed = True
    if failed:
        print('\nSecurity updates failed.', flush=True)
        if sys.stdin.isatty():
            try:
                input('Press Enter to return to Confconsole. ')
            except EOFError:
                pass
