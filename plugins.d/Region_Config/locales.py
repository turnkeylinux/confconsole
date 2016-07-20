'''Reconfigure locales'''
import os

def run():
    console.infobox('We STRONGLY recommend you choose "None" as your default locale.')
    os.system('dpkg-reconfigure locales')
