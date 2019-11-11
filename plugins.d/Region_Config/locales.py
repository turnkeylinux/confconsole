'''Reconfigure locales'''
import os


def run():
    if interactive:
        console.msgbox(
            'Locale',
            'We STRONGLY recommend you choose "None" as your default locale.',
            autosize=True)

        os.system('dpkg-reconfigure locales')
    else:
        locale = os.getenv('LOCALE')

        if locale:
            os.system('locale-gen %s' % locale)
            os.system('update-locale LANG={0} LANGUAGE={0} LC_ALL={0}'
                      ''.format(locale))
            os.system('dpkg-reconfigure -f noninteractive locales')
