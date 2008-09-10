#!/usr/bin/python

import dialog


class Console:
    def __init__(self):
        title = "Turnkey Linux Console Configuration"
        self.appname = "Turnkey Linux %s" % self._get_hostname()

        self.width = 60
        self.height = 18
        self.console = dialog.Dialog(dialog="dialog")
        self.console.add_persistent_args(["--backtitle", title])

    @staticmethod
    def _get_hostname():
        return "Drupal"

    @staticmethod
    def _get_ipaddr():
        return "192.168.0.1"

    def dialog_info(self):
        header = "\nYou may access this %s Appliance over\n" % self.appname
        header += "the network using the following methods:\n"

        ipaddr = self._get_ipaddr()
        body = "Web Browser:  http://%s\n" % ipaddr
        body += "Secure Shell: ssh root@%s\n" % ipaddr

        footer = "For more information visit the Turnkey Linux Website\n"
        footer += "             http://www.turnkeylinux.org"

        text = header + "\n" + body + "\n"*6 + footer

        return self.console.msgbox(text, self.height, self.width,
                                   title=self.appname,
                                   ok_label="Advanced")

def main():
    console = Console()
    console.dialog_info()

if __name__ == "__main__":
    main()

