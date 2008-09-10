#!/usr/bin/python

import dialog


class Console:
    def __init__(self, title=None):
        self.console = dialog.Dialog(dialog="dialog")
        if title:
            self.console.add_persistent_args(["--backtitle", title])

    @staticmethod
    def _get_hostname():
        return "Drupal"

    @staticmethod
    def _get_ipaddr():
        return "192.168.0.1"

    def dialog_info(self):
        appname = "%s Turnkey Linux" % self._get_hostname()
        ipaddr = self._get_ipaddr()
        text = """
You may access this %s Appliance over
the network using the following methods:

Web Browser:  http://%s
Secure Shell: ssh root@%s
%s
For more information visit the Turnkey Linux Website:
             http://www.turnkeylinux.org
""" % (appname, ipaddr, ipaddr, "\n"*5)

        return self.console.msgbox(text, 18, 60,
                                   title = appname,
                                   ok_label = "Advanced")

def main():
    console = Console("Turnkey Linux Console Configuration")
    console.dialog_info()

if __name__ == "__main__":
    main()

