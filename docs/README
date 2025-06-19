TurnKey GNU/Linux Configuration Console
=======================================

A pretty version of this readme (with screenshots and clickable links)
is available online from:

https://www.turnkeylinux.org/docs/confconsole

The source can be found on GitHub:

https://github.com/turnkeylinux/confconsole

TurnKey Configuration Console (AKA Confconsole) is a terminal based, menu
driven config tool. It provides some basic info and allows users to easily
access and update many common TurnKey configuration options.

Overview
--------

The objective of Confconsole is to provide users with basic network
information and perform some common tasks. Configuration is performed
via menus, rather than requiring commands to be run within a terminal.

Confconsole is licensed under <a class="reference external" href="https://www.gnu.org/licenses/gpl-3.0.txt">GPLv3</a>.

Main screen and basic functionality
-----------------------------------

When Confconsole is started, the main screen is displayed. At boot, Confconsole
is invoked automatically on the default vt (virtual terminal). However until
run as 'root', Confconsole runs in "limited" mode and no configuration is
allowed.

Auto starting Confconsole "limited" mode at boot can be disabled by adding
'noconfconsole' to the GRUB_CMDLINE_LINUX variable. Edit the Grub variable in
/etc/default/grub and run 'update-grub'.

The information provided by the main screen/"limited" mode includes:

    - The current external IP address
    - The services the user may connect to over the network
    - TKLBAM status

Advanced
--------

The "Advanced" Confconsole option menus are only available in "full mode".
"Full" mode is only invoked on the first terminal login as 'root' (or 'admin'
on an AWS Marketplace instances). Launching on every login can be enable via:

    Confconsole >> Advanced >> System Settings

Confconsole "full" mode can also be started manually by 'root' (prefix with
'sudo' on AWS MP):

    confconsole

Advanced options available in "full" mode are accessed by selecting the
"Advanced" button on the initial Main screen. Some appliances include
additional options, but the options available in all appliances are:

    - Networking:
      - Set a static IP address or enable DHCP
        - IMPORTANT: this should not be changed when network configuration
          is handled externally

    - Let's Encrypt (see docs/Lets_encrypt.rst):
      - Enable/disable auto SSL cert update
      - Get SSL certificate from Let's Encrypt (via HTTP-01 or DNS-01)

    - Mail relaying (see docs/Mail_relay.rst):
      - Configure and enable remote SMTP email relay

    - Proxy settings (see docs/Proxy_settings.rst):
      - Configure apt proxy

    - Region config (see docs/Region_config.rst):
      - Keyboard layout
      - Locales and language
      - Tzdata (timezone)

    - System settings (see docs/System_settings.rst):
      - Enable/Disable Confconsole autostart
      - Config SecUpdate default behavior
      - Install security updates
      - Update hostname

    - Installing the system to the hard disk (only when running live)
    - Reboot the appliance
    - Shut down the appliance
    - Quit (back to command line)

Network config notes
++++++++++++++++++++

When setting a static IP address or requesting DHCP, unless the user has
manually updated the interfaces file - /etc/network/interfaces - the changes
will be permanent.

Installation
------------

Confconsole is pre-installed by default in all TurnKey Linux Appliances
so no installation should be required for TurnKey users.

Confconsole should be compatible with vanilla Debian (and probably vanilla
Ubuntu too). Most, if not all dependencies should be available from the default
Debian "main" repo.

Upgrading
---------

To ensure that you are running the latest Confconsole version, you can check
for upgrades via apt:

    apt-get update
    apt-get install confconsole

Plugins
-------

Most confconsole functionality is provided via a plugins system.
The plugins system allows support for additional functionality via
simply dropping a plugin file within the Confconsole file hierarchy.
We aim to add additional functionality via plugins as we go.

Developers may be interested in reading further about the
<a href="/docs/confconsole/plugins">Plugins</a> system.
