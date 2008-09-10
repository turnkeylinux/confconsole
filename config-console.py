#!/usr/bin/python

import dialog

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

    def msgbox(self, title, text, button_label="ok"):
        return self.console.msgbox(text, self.height, self.width,
                                   title=title, ok_label=button_label)

    def menu(self, title, text, choices):
        return self.console.menu(text, self.height, self.width,
                                 title=title, choices=choices)

    def form(self, title, text, fields):
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
        #todo: check listening ports
        ipaddr = ifutil.get_ipinfo()[0]
        if not ipaddr or ipaddr.startswith('169'): # self assigned
            return "Error: default interface not configured\n"

        info = "Web Browser:  http://%s\n" % ipaddr
        info += "Secure Shell: ssh root@%s\n" % ipaddr
        return info

    def _get_infotitle(self):
        return self.appname

    def _get_infotext(self):
        header = "\nYou may access this %s appliance\n" % self.appname
        header += "over the network using the following methods:\n\n"

        body = self._get_netservices()

        footer = "For more information visit the Turnkey Linux Website\n"
        footer += "             http://www.turnkeylinux.org"

        curlines = header.count('\n') + body.count('\n') + footer.count('\n')
        bodypad = "\n"*(self.height - 5 - curlines)
        return header + body + bodypad + footer

    def _get_advtitle(self):
        return "Advanced Menu"

    def _get_advtext(self):
        return "\n%s %s\n" % (self.appname, self._get_advtitle())

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
        ipaddr, netmask, gateway, nameserver = ifutil.get_ipinfo()
        field_width = 30
        fields = [
            ("IP Address", ipaddr, field_width),
            ("Netmask", netmask, field_width),
            ("Default Gateway", gateway, field_width),
            ("Name Server", nameserver, field_width)
        ]

        retcode, input = self.console.form("\nNetwork Settings",
                                           "Static IP Configuration", fields)
        if retcode is not 0:
            return

        # verify input are ipaddresss's - usability and security issues
        for addr in input:
            if addr and not ifutil.valid_ipv4(addr):
                self.console.msgbox("Invalid Input", "Invalid Address: %s" % addr)
                return

        ifutil.set_ipinfo(*input)

    def _adv_dhcp(self):
        self.console.msgbox("", "dhcp")

    def _adv_reboot(self):
        self.console.msgbox("", "reboot")

    def _adv_shutdown(self):
        self.console.msgbox("", "shutdown")

    def loop(self):
        while 1:
            if self.dialog_info() is not 0:
                break

            self.dialog_adv()


def main():
    TurnkeyConsole().loop()
    #TurnkeyConsole()._adv_staticip()



if __name__ == "__main__":
    main()

