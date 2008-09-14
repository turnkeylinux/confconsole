#!/usr/bin/python

import dialog

import executil
import ifutil

class Error(Exception):
    pass

class Console:
    def __init__(self, title=None, width=60, height=18):
        self.width = width
        self.height = height

        self.console = dialog.Dialog(dialog="dialog")
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

class TurnkeyConsole:
    def __init__(self):
        title = "Turnkey Linux Console Configuration"
        self.width = 60
        self.height = 18

        self.console = Console(title, self.width, self.height)
        self.appname = "Turnkey Linux %s" % ifutil.get_hostname().capitalize()

    @staticmethod
    def _get_netservices():
        def _openport(port):
            for conn in ifutil.get_connections():
                if conn.proto in ('tcp', 'tcp6') and \
                   conn.lhost in ('0.0.0.0', ipaddr) and \
                   conn.lport == port:
                    return True
            return False

        ipaddr = ifutil.get_ipconf()[0]
        if not ipaddr or ipaddr.startswith('169'): # self assigned
            return "Error: default interface not configured\n"

        services = {80: "Web Browser:  http://%s\n" % ipaddr,
                    22: "Secure Shell: ssh root@%s\n" % ipaddr}

        services_list = ""
        for port in services:
            if _openport(port):
                services_list += services[port]

        if not services_list:
            return "Error: no services binded to default interface"

        return services_list

    def _get_infotitle(self):
        return self.appname

    def _get_infotext(self):
        header = "You may access this %s appliance\n" % self.appname
        header += "over the network using the following methods:\n\n"

        body = self._get_netservices()

        footer = "For more information visit the Turnkey Linux Website\n"
        footer += "             http://www.turnkeylinux.org"

        curlines = header.count('\n') + body.count('\n') + footer.count('\n')
        bodypad = "\n"*(self.height - 6 - curlines)
        return header + body + bodypad + footer

    def _get_advtitle(self):
        return "Advanced Menu"

    def _get_advtext(self):
        return "%s %s\n" % (self.appname, self._get_advtitle())

    def _get_advchoices(self):
        return [("StaticIP", "Manual network configuration"),
                ("DHCP", "Automatic network configuration"),
                ("Reboot", "Reboot the appliance"),
                ("Shutdown", "Shutdown the appliance")]

    def dialog_info(self):
        return self.console.msgbox(self._get_infotitle(),
                                   self._get_infotext(), 
                                   button_label=self._get_advtitle())

    def dialog_adv(self):
        retcode, choice = self.console.menu(self._get_advtitle(),
                                            self._get_advtext(),
                                            self._get_advchoices())
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

        for addr in input:
            if addr and not ifutil.valid_ipv4(addr):
                self.console.msgbox("Invalid Input", "Invalid Address: %s" % addr)
                return

        err = ifutil.set_ipconf(*input)
        if err:
            self.console.msgbox("Error", err)

    def _adv_dhcp(self):
        self.console.infobox("Requesting DHCP...")
        err = ifutil.get_dhcp()
        if err:
            self.console.msgbox("Error", err)

    def _adv_reboot(self):
        if self.console.yesno("Reboot the appliance?") == 0:
            executil.system("shutdown -r now")

    def _adv_shutdown(self):
        if self.console.yesno("Shutdown the appliance?") == 0:
            executil.system("shutdown -h now")

    def loop(self):
        while 1:
            if self.dialog_info() is not 0:
                break

            self.dialog_adv()

def main():
    TurnkeyConsole().loop()


if __name__ == "__main__":
    main()

