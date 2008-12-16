#!/usr/bin/python
# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved

import os
import dialog
from string import Template

import ifutil
import executil

class Error(Exception):
    pass

class Console:
    def __init__(self, title=None, width=60, height=18):
        self.width = width
        self.height = height

        self.console = dialog.Dialog(dialog="dialog")
        self.console.add_persistent_args(["--no-collapse"])
        if title:
            self.console.add_persistent_args(["--backtitle", title])

    def infobox(self, text):
        text = "\n" + text
        return self.console.infobox(text)

    def yesno(self, text):
        text = "\n" + text
        return self.console.yesno(text)

    def msgbox(self, title, text, button_label="ok"):
        text = "\n" + text
        return self.console.msgbox(text, self.height, self.width,
                                   title=title, ok_label=button_label)

    def menu(self, title, text, choices):
        text = "\n" + text
        return self.console.menu(text, self.height, self.width,
                                 menu_height=len(choices)+1,
                                 title=title, choices=choices)

    def form(self, title, text, fields):
        text = "\n" + text
        return self.console.form(text, self.height, self.width,
                                 form_height=len(fields)+1,
                                 title=title, fields=fields)

class Installer:
    def __init__(self, path):
        self.path = path
        self.available = self._is_available()

    def _is_available(self):
        if not os.path.exists(self.path):
            return False

        fh = file('/proc/cmdline')
        cmdline = fh.readline()
        fh.close()

        for cmd in cmdline.split():
            if cmd == "boot=casper":
                return True

        return False

    def execute(self):
        if not self.available:
            raise Error("installer is not available to be executed")

        executil.system(self.path)

class TurnkeyConsole:
    def __init__(self):
        title = "TurnKey Linux Configuration Console"
        self.width = 60
        self.height = 18

        self.console = Console(title, self.width, self.height)
        self.appname = "TurnKey Linux %s" % ifutil.get_hostname().capitalize()

        self.installer = Installer(path='/usr/bin/di-live')

    @staticmethod
    def _get_template_path(filename):
        for dir in ("templates", "/usr/share/confconsole/templates"):
            template_path = os.path.join(dir, filename)
            if os.path.exists(template_path):
                return template_path

        raise Error('could not find template: %s' % filename)

    def _get_infotitle(self):
        return self.appname

    def _get_infotext(self):
        ipaddr = ifutil.get_ipconf()[0]
        if not ipaddr or ipaddr.startswith('169'): # self assigned
            return "Error: default interface not configured"

        text = file(self._get_template_path("info.txt"), 'r').read()
        return Template(text).substitute(appname=self.appname,
                                         ipaddr=ipaddr)

    def _get_advtitle(self):
        return "Advanced Menu"

    def _get_advtext(self):
        return "%s %s\n" % (self.appname, self._get_advtitle())

    def _get_advmenu(self):
        items = []
        items.append(("StaticIP", "Manual network configuration"))
        items.append(("DHCP", "Automatic network configuration"))

        if self.installer.available:
            items.append(("Install", "Install to hard disk"))

        items.append(("Reboot", "Reboot the appliance"))
        items.append(("Shutdown", "Shutdown the appliance"))
        items.append(("Quit", "Quit the configuration console"))

        return items

    def dialog_info(self):
        return self.console.msgbox(self._get_infotitle(),
                                   self._get_infotext(), 
                                   button_label=self._get_advtitle())

    def dialog_adv(self):
        retcode, choice = self.console.menu(self._get_advtitle(),
                                            self._get_advtext(),
                                            self._get_advmenu())
        if retcode is not 0:
            return
        
        try:
            choice = choice.lower()
            method = getattr(self, "_adv_" + choice)
        except AttributeError:
            raise Error("advanced choice not supported: " + choice)

        method()

    def _adv_staticip(self):
        ipaddr, netmask, gateway, nameserver = ifutil.get_ipconf()
        field_width = 30
        field_limit = 15
        fields = [
            ("IP Address", ipaddr, field_width, field_limit),
            ("Netmask", netmask, field_width, field_limit),
            ("Default Gateway", gateway, field_width, field_limit),
            ("Name Server", nameserver, field_width, field_limit)
        ]

        retcode, input = self.console.form("Network Settings",
                                           "Static IP Configuration", fields)
        if retcode is not 0:
            return

        err = ifutil.set_ipconf(*input)
        if err:
            self.console.msgbox("Error", err)

    def _adv_dhcp(self):
        self.console.infobox("Requesting DHCP...")
        err = ifutil.get_dhcp()
        if err:
            self.console.msgbox("Error", err)

    def _adv_install(self):
        text = "Please note that any changes you may have made to the\n"
        text += "live system will *not* be installed to the hard disk.\n\n"
        self.console.msgbox("Installer", text)

        self.installer.execute()

    def _adv_reboot(self):
        if self.console.yesno("Reboot the appliance?") == 0:
            self.running = False
            executil.system("shutdown -r now")

    def _adv_shutdown(self):
        if self.console.yesno("Shutdown the appliance?") == 0:
            self.running = False
            executil.system("shutdown -h now")

    def _adv_quit(self):
        self.running = False

    def loop(self):
        self.running = True
        while self.running:
            if self.dialog_info() is not 0:
                break

            self.dialog_adv()

def main():
    TurnkeyConsole().loop()


if __name__ == "__main__":
    main()

