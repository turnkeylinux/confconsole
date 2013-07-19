#!/usr/bin/python
# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved
"""TurnKey Configuration Console

Options:
    --usage         Display usage screen without Advanced Menu

"""

import os
import sys
import dialog
import ipaddr
from string import Template

import ifutil
import netinfo
import executil

import conf

from StringIO import StringIO
import traceback

class Error(Exception):
    pass

def fatal(e):
    print >> sys.stderr, "error: " + str(e)
    sys.exit(1)

def usage(e=None):
    if e:
        print >> sys.stderr, "error: " + str(e)

    print >> sys.stderr, "Syntax: %s" % (sys.argv[0])
    print >> sys.stderr, __doc__.strip()
    sys.exit(1)

class Console:
    def __init__(self, title=None, width=60, height=20):
        self.width = width
        self.height = height

        self.console = dialog.Dialog(dialog="dialog")
        self.console.add_persistent_args(["--no-collapse"])
        self.console.add_persistent_args(["--ok-label", "Select"])
        self.console.add_persistent_args(["--cancel-label", "Back"])
        self.console.add_persistent_args(["--colors"])
        if title:
            self.console.add_persistent_args(["--backtitle", title])

    def _handle_exitcode(self, retcode):
        if retcode == 2: # ESC, ALT+?
            text = "Do you really want to quit?"
            if self.console.yesno(text) == 0:
                sys.exit(0)
            return False
        return True

    def _wrapper(self, dialog, text, *args, **kws):
        try:
            method = getattr(self.console, dialog)
        except AttributeError:
            raise Error("dialog not supported: " + dialog)

        while 1:
            ret = method("\n" + text, *args, **kws)
            if type(ret) is int:
                retcode = ret
            else:
                retcode = ret[0]

            if self._handle_exitcode(retcode):
                break

        return ret

    def infobox(self, text):
        return self._wrapper("infobox", text)

    def yesno(self, text):
        return self._wrapper("yesno", text)

    def msgbox(self, title, text, button_label="ok"):
        return self._wrapper("msgbox", text, self.height, self.width,
                             title=title, ok_label=button_label)

    def menu(self, title, text, choices, no_cancel=False):
        return self._wrapper("menu", text, self.height, self.width,
                             menu_height=len(choices)+1,
                             title=title, choices=choices, no_cancel=no_cancel)

    def form(self, title, text, fields, ok_label="Apply", cancel_label="Cancel"):
        return self._wrapper("form", text, self.height, self.width,
                             form_height=len(fields)+1,
                             title=title, fields=fields,
                             ok_label=ok_label, cancel_label=cancel_label)

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
    OK = 0
    CANCEL = 1

    def __init__(self, advanced_enabled=True):
        title = "TurnKey Linux Configuration Console"
        self.width = 60
        self.height = 20

        self.console = Console(title, self.width, self.height)
        
        # sometimes it would be nice to have the appname be something other
        # than the hostname. Allow developers to create  file containing the appname
        # in /etc/appname
        try:
            self.appname = file("/etc/appname", 'r').read().rstrip()
        except IOError as e:
            self.appname = "TurnKey Linux %s" % netinfo.get_hostname().upper()
            
        self.installer = Installer(path='/usr/bin/di-live')

        self.advanced_enabled = advanced_enabled

    @staticmethod
    def _get_filtered_ifnames():
        ifnames = []
        for ifname in netinfo.get_ifnames():
            if ifname.startswith(('lo', 'tap', 'br', 'tun', 'vmnet', 'wmaster')):
                continue
            ifnames.append(ifname)

        ifnames.sort()
        return ifnames

    @classmethod
    def _get_default_nic(cls):
        def _validip(ifname):
            ip = ifutil.get_ipconf(ifname)[0]
            if ip and not ip.startswith('169'):
                return True
            return False

        ifname = conf.Conf().default_nic
        if ifname and _validip(ifname):
            return ifname

        for ifname in cls._get_filtered_ifnames():
            if _validip(ifname):
                return ifname

        return None

    def _get_advmenu(self):
        items = []
        items.append(("Networking", "Configure appliance networking"))

        if self.installer.available:
            items.append(("Install", "Install to hard disk"))

        items.append(("Reboot", "Reboot the appliance"))
        items.append(("Shutdown", "Shutdown the appliance"))
        items.append(("Quit", "Quit the configuration console"))

        return items

    def _get_netmenu(self):
        menu = []
        for ifname in self._get_filtered_ifnames():
            addr = ifutil.get_ipconf(ifname)[0]
            ifmethod = ifutil.get_ifmethod(ifname)

            if addr:
                desc = addr
                if ifmethod:
                    desc += " (%s)" % ifmethod

                if ifname == self._get_default_nic():
                    desc += " [*]"
            else:
                desc = "not configured"

            menu.append((ifname, desc))

        return menu

    def _get_ifconfmenu(self, ifname):
        menu = []
        menu.append(("DHCP", "Configure networking automatically"))
        menu.append(("StaticIP", "Configure networking manually"))

        if not ifname == self._get_default_nic() and \
           len(self._get_filtered_ifnames()) > 1 and \
           ifutil.get_ipconf(ifname)[0] is not None:
            menu.append(("Default", "Show this adapter's IP address in Usage"))

        return menu

    def _get_ifconftext(self, ifname):
        addr, netmask, gateway, nameservers = ifutil.get_ipconf(ifname)
        if addr is None:
            return "Network adapter is not configured\n"

        text =  "IP Address:      %s\n" % addr
        text += "Netmask:         %s\n" % netmask
        text += "Default Gateway: %s\n" % gateway
        text += "Name Server(s):  %s\n\n" % " ".join(nameservers)

        ifmethod = ifutil.get_ifmethod(ifname)
        if ifmethod:
            text += "Networking configuration method: %s\n" % ifmethod

        if len(self._get_filtered_ifnames()) > 1:
            text += "Is this adapter's IP address displayed in Usage: "
            if ifname == self._get_default_nic():
                text += "yes\n"
            else:
                text += "no\n"

        return text

    def usage(self):
        if self.advanced_enabled:
            default_button_label = "Advanced Menu"
            default_return_value = "advanced"
        else:
            default_button_label = "Quit"
            default_return_value = "quit"

        #if no interfaces at all - display error and go to advanced
        if len(self._get_filtered_ifnames()) == 0:
            error = "No network adapters detected"
            if not self.advanced_enabled:
                fatal(error)

            self.console.msgbox("Error", error)
            return "advanced"

        #if interfaces but no default - display error and go to networking
        ifname = self._get_default_nic()
        if not ifname:
            error = "Networking is not yet configured"
            if not self.advanced_enabled:
                fatal(error)

            self.console.msgbox("Error", error)
            return "networking"

        #tklbam integration
        try:
            tklbam_status = executil.getoutput("tklbam-status --short")
        except executil.ExecError, e:
            if e.exitcode in (10, 11): #not initialized, no backups
                tklbam_status = e.output
            else:
                tklbam_status = ''

        #display usage
        ipaddr = ifutil.get_ipconf(ifname)[0]
        hostname = netinfo.get_hostname().upper()

        try:
            #backwards compatible - use usage.txt if it exists
            t = file(conf.path("usage.txt"), 'r').read()
            text = Template(t).substitute(appname=self.appname, hostname=hostname, ipaddr=ipaddr)

            retcode = self.console.msgbox("Usage", text,
                                          button_label=default_button_label)
        except conf.Error:
            t = file(conf.path("services.txt"), 'r').read().rstrip()
            text = Template(t).substitute(appname=self.appname, hostname=hostname, ipaddr=ipaddr)

            text += "\n\n%s\n\n" % tklbam_status
            text += "\n" * (self.height - len(text.splitlines()) - 7)
            text += "         TurnKey Backups and Cloud Deployment\n"
            text += "             https://hub.turnkeylinux.org"

            retcode = self.console.msgbox("%s appliance services" % hostname,
                                          text, button_label=default_button_label)

        if retcode is not self.OK:
            self.running = False

        return default_return_value

    def advanced(self):
        #dont display cancel button when no interfaces at all
        no_cancel = False
        if len(self._get_filtered_ifnames()) == 0:
            no_cancel = True
        retcode, choice = self.console.menu("Advanced Menu",
                                            self.appname + " Advanced Menu\n",
                                            self._get_advmenu(),
                                            no_cancel=no_cancel)

        if retcode is not self.OK:
            return "usage"

        return "_adv_" + choice.lower()

    def networking(self):
        ifnames = self._get_filtered_ifnames()

        #if no interfaces at all - display error and go to advanced
        if len(ifnames) == 0:
            self.console.msgbox("Error", "No network adapters detected")
            return "advanced"

        # if only 1 interface, dont display menu - just configure it
        if len(ifnames) == 1:
            self.ifname = ifnames[0]
            return "ifconf"

        # display networking
        text = "Choose network adapter to configure\n"
        if self._get_default_nic():
            text += "[*] This adapter's IP address is displayed in Usage"

        retcode, self.ifname = self.console.menu("Networking configuration",
                                                 text, self._get_netmenu())

        if retcode is not self.OK:
            return "advanced"

        return "ifconf"

    def ifconf(self):
        retcode, choice = self.console.menu("%s configuration" % self.ifname,
                                            self._get_ifconftext(self.ifname),
                                            self._get_ifconfmenu(self.ifname))

        if retcode is not self.OK:
            # if multiple interfaces go back to networking
            if len(self._get_filtered_ifnames()) > 1:
                return "networking"

            return "advanced"

        return "_ifconf_" + choice.lower()

    def _ifconf_staticip(self):
        def _validate(addr, netmask, gateway, nameservers):
            """Validate Static IP form parameters. Returns an empty array on
               success, an array of strings describing errors otherwise"""

            errors = []
            if not addr:
                errors.append("No IP address provided")
            elif not ipaddr.is_legal_ip(addr):
                errors.append("Invalid IP address: %s" % addr)

            if not netmask:
                errors.append("No netmask provided")
            elif not ipaddr.is_legal_ip(netmask):
                errors.append("Invalid netmask: %s" % netmask)

            for nameserver in nameservers:
                if nameserver and not ipaddr.is_legal_ip(nameserver):
                    errors.append("Invalid nameserver: %s" % nameserver)

            if len(nameservers) != len(set(nameservers)):
                errors.append("Duplicate nameservers specified")

            if errors:
                return errors

            if gateway:
                if not ipaddr.is_legal_ip(gateway):
                    return [ "Invalid gateway: %s" % gateway ]
                else:
                    iprange = ipaddr.IPRange(addr, netmask)
                    if gateway not in iprange:
                        return [ "Gateway (%s) not in IP range (%s)" % (gateway,
                                                                        iprange) ]
            return []

        addr, netmask, gateway, nameservers = ifutil.get_ipconf(self.ifname)
        input = [addr, netmask, gateway]
        input.extend(nameservers)

        # include minimum 2 nameserver fields and 1 blank one
        if len(input) < 4:
            input.append('')

        if input[-1]:
            input.append('')

        field_width = 30
        field_limit = 15

        while 1:
            fields = [
                ("IP Address", input[0], field_width, field_limit),
                ("Netmask", input[1], field_width, field_limit),
                ("Default Gateway", input[2], field_width, field_limit),
            ]

            for i in range(len(input[3:])):
                fields.append(("Name Server", input[3+i], field_width, field_limit))

            text = "Static IP configuration (%s)" % self.ifname
            retcode, input = self.console.form("Network settings", text, fields)

            if retcode is not self.OK:
                break

            # remove any whitespaces the user might of included
            for i in range(len(input)):
                input[i] = input[i].strip()

            # unconfigure the nic if all entries are empty
            if not input[0] and not input[1] and not input[2] and not input[3]:
                ifutil.unconfigure_if(self.ifname)
                break

            addr, netmask, gateway = input[:3]
            nameservers = input[3:]
            for i in range(nameservers.count('')):
                nameservers.remove('')

            err = _validate(addr, netmask, gateway, nameservers)
            if err:
                err = "\n".join(err)
            else:
                err = ifutil.set_static(self.ifname, addr, netmask,
                                        gateway, nameservers)
                if not err:
                    break

            self.console.msgbox("Error", err)

        return "ifconf"

    def _ifconf_dhcp(self):
        self.console.infobox("Requesting DHCP for %s..." % self.ifname)
        err = ifutil.set_dhcp(self.ifname)
        if err:
            self.console.msgbox("Error", err)

        return "ifconf"

    def _ifconf_default(self):
        conf.Conf().set_default_nic(self.ifname)
        return "ifconf"

    def _adv_install(self):
        text = "Please note that any changes you may have made to the\n"
        text += "live system will *not* be installed to the hard disk.\n\n"
        self.console.msgbox("Installer", text)

        self.installer.execute()
        return "advanced"

    def _shutdown(self, text, opt):
        if self.console.yesno(text) == self.OK:
            self.running = False
            cmd = "shutdown %s now" % opt
            fgvt = os.environ.get("FGVT")
            if fgvt:
                cmd = "chvt %s; " % fgvt + cmd
            executil.system(cmd)

        return "advanced"

    def _adv_reboot(self):
        return self._shutdown("Reboot the appliance?", "-r")

    def _adv_shutdown(self):
        return self._shutdown("Shutdown the appliance?", "-h")

    def _adv_quit(self):
        default_return_value = "advanced" if self.advanced_enabled else "usage"

        if self.console.yesno("Do you really want to quit?") == self.OK:
            self.running = False

        return default_return_value

    _adv_networking = networking
    quit = _adv_quit

    def loop(self, dialog="usage"):
        self.running = True
        prev_dialog = dialog

        while dialog and self.running:
            try:
                try:
                    method = getattr(self, dialog)
                except AttributeError:
                    raise Error("dialog not supported: " + dialog)

                new_dialog = method()
                prev_dialog = dialog
                dialog = new_dialog

            except Exception, e:
                sio = StringIO()
                traceback.print_exc(file=sio)

                self.console.msgbox("Caught exception", sio.getvalue())
                dialog = prev_dialog

def main():
    advanced_enabled = True

    args = sys.argv[1:]
    if args:
        if args[0] == '--usage':
            advanced_enabled = False
        else:
            usage()

    if os.geteuid() != 0:
        fatal("confconsole needs root privileges to run")

    tc = TurnkeyConsole(advanced_enabled)
    tc.loop()

if __name__ == "__main__":
    main()

