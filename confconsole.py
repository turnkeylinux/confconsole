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

    @staticmethod
    def _get_filtered_ifnames():
        ifnames = []
        for ifname in ifutil.get_ifnames():
            if ifname.startswith(('lo', 'tap', 'br', 'tun', 'vmnet', 'wmaster')):
                continue
            ifnames.append(ifname)

        ifnames.sort()
        return ifnames

    def _get_usagetext(self, ifname):
        ipaddr = ifutil.get_ipconf(ifname)[0]
        text = file(self._get_template_path("usage.txt"), 'r').read()

        return Template(text).substitute(appname=self.appname,
                                         ipaddr=ipaddr)

    def _get_advtitle(self):
        return "Advanced Menu"

    def _get_advtext(self):
        return "%s %s\n" % (self.appname, self._get_advtitle())

    def _get_advmenu(self):
        items = []
        items.append(("Networking", "Configure appliance networking"))

        if self.installer.available:
            items.append(("Install", "Install to hard disk"))

        items.append(("Reboot", "Reboot the appliance"))
        items.append(("Shutdown", "Shutdown the appliance"))
        items.append(("Quit", "Quit the configuration console"))

        return items

    def _get_ifdefault(self):
        for ifname in self._get_filtered_ifnames():
            if ifutil.get_ipconf(ifname)[0]:
                return ifname

        return None

    def _get_netmenu(self):
        ifnames = ifutil.get_ifnames()
        menu = []
        for ifname in self._get_filtered_ifnames():
            addr = ifutil.get_ipconf(ifname)[0]
            ifmethod = ifutil.get_ifmethod(ifname)

            if addr:
                desc = addr
                if ifmethod:
                    desc += " (%s)" % ifmethod

                if ifname == self._get_ifdefault():
                    desc += " [*]"
            else:
                desc = "not configured"

            menu.append((ifname, desc))

        return menu

    def _get_ifconftext(self, ifname):
        addr, netmask, gateway, nameserver = ifutil.get_ipconf(ifname)
        if addr is None:
            return "Interface is not configured\n"
        
        text =  "IP Address:      %s\n" % addr
        text += "Netmask:         %s\n" % netmask
        text += "Default Gateway: %s\n" % gateway
        text += "Name Server:     %s\n\n" % nameserver

        ifmethod = ifutil.get_ifmethod(ifname)
        if ifmethod:
            text += "Interface configuration method: %s\n" % ifmethod

        if ifname == self._get_ifdefault():
            text += "Set as default NIC displayed in Usage\n"

        return text

    def _get_ifconfmenu(self, ifname):
        menu = []
        menu.append(("DHCP", "Configure this NIC automatically"))
        menu.append(("StaticIP", "Configure this NIC manually"))

        if not ifname == self._get_ifdefault():
            menu.append(("Default", "Set as default NIC displayed in Usage"))

        return menu

    def dialog_usage(self):
        ifname = self._get_ifdefault()
        if not ifname or ifutil.get_ipconf(ifname)[0].startswith('169'):
            self.console.msgbox("Error", "No interfaces are configured")
            if len(self._get_filtered_ifnames()) > 1:
                return self.dialog_net()
            
            return self.dialog_ifconf(ifname)

        return self.console.msgbox("Usage",
                                   self._get_usagetext(ifname),
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

    def dialog_net(self):
        retcode, choice = self.console.menu("Networking configuration", 
                                            "Choose interface to configure", 
                                            self._get_netmenu())

        if retcode is not 0:
            return

        self.dialog_ifconf(choice)

    _adv_networking = dialog_net

    def dialog_ifconf(self, ifname):
        while 1:
            retcode, choice = self.console.menu("%s configuration" % ifname,
                                                self._get_ifconftext(ifname),
                                                self._get_ifconfmenu(ifname))

            if retcode is not 0:
                break

            try:
                choice = choice.lower()
                method = getattr(self, "_ifconf_" + choice)
            except AttributeError:
                raise Error("ifconf choice not supported: " + choice)

            method(ifname)

    def _ifconf_staticip(self, ifname):
        ipaddr, netmask, gateway, nameserver = ifutil.get_ipconf(ifname)
        field_width = 30
        field_limit = 15
        fields = [
            ("IP Address", ipaddr, field_width, field_limit),
            ("Netmask", netmask, field_width, field_limit),
            ("Default Gateway", gateway, field_width, field_limit),
            ("Name Server", nameserver, field_width, field_limit)
        ]

        retcode, input = self.console.form("Network settings",
                                           "Static IP configuration (%s)" % ifname,
                                           fields)
        if retcode is not 0:
            return

        err = ifutil.set_ipconf(ifname, *input)
        if err:
            self.console.msgbox("Error", err)

    def _ifconf_dhcp(self, ifname):
        self.console.infobox("Requesting DHCP for %s..." % ifname)
        err = ifutil.get_dhcp(ifname)
        if err:
            self.console.msgbox("Error", err)

    def _ifconf_default(self, ifname):
        # todo
        pass

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
            if self.dialog_usage() is not 0:
                break

            self.dialog_adv()

def main():
    TurnkeyConsole().loop()


if __name__ == "__main__":
    main()

