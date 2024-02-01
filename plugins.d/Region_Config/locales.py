'''Reconfigure locales'''
import subprocess
import os


def run():
    # interactive & console are inherited so doesn't need to be defined
    if interactive:  # type: ignore[not-defined]
        console.msgbox(   # type: ignore[not-defined]
            'Locale',
            'We STRONGLY recommend you choose "None" as your default locale.',
            autosize=True)

        subprocess.run(['dpkg-reconfigure', 'locales'])
    else:
        locale = os.getenv('LOCALE')

        if locale:
            subprocess.run(['locale-gen', locale])
            subprocess.run(['update-locale', f'LANG={locale}',
                            f'LANGUAGE={locale}', f'LC_ALL={locale}'])
            subprocess.run(['dpkg-reconfigure', '-f', 'noninteractive',
                            'locales'])
