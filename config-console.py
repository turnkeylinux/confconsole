#!/usr/bin/python

import dialog

import ifutil

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

def _netservices():
    #todo: get preferred ifname
    #todo: check listening ports
    ifname = 'eth1'
    ipaddr = ifutil.get_ipinfo(ifname)[0]
    if not ipaddr:
        return "Error: %s interface not configured\n" % ifname

    info = "Web Browser:  http://%s\n" % ipaddr
    info += "Secure Shell: ssh root@%s\n" % ipaddr

    return info

def appname():
    return "Turnkey Linux %s" % ifutil.get_hostname().capitalize()

def infotext(height):
    header = "\nYou may access this %s appliance\n" % appname()
    header += "over the network using the following methods:\n\n"

    body = _netservices()

    footer = "For more information visit the Turnkey Linux Website\n"
    footer += "             http://www.turnkeylinux.org"

    curlines = header.count('\n') + body.count('\n') + footer.count('\n')
    bodypad = "\n"*(height - 5 - curlines)
    return header + body + bodypad + footer

def advtext():
    return "\n%s Advanced Menu\n" % appname()

def advchoices():
    return [
        ("StaticIP", "Manual network configuration"),
        ("DHCP", "Automatic network configuration"),
        ("Reboot", "Reboot the appliance"),
        ("Shutdown", "Shutdown the appliance")
    ]

def main():
    title = "Turnkey Linux Console Configuration"
    width = 60
    height = 18

    c = Console(title, width, height)
    while 1:
        retcode = c.msgbox(appname(), infotext(height), button_label="Advanced Menu")
        if retcode is not 0:
            break

        retcode, choice = c.menu("Advanced Menu", advtext(), advchoices())
        if retcode is 2:
            break

        if retcode is 0:
            print choice
            break


if __name__ == "__main__":
    main()

