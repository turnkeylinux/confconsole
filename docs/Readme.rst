
TurnKey GNU/Linux Configuration Console
=======================================

A pretty version of this readme (with screenshots and clickable links)
is avaialble online from:

https://www.turnkeylinux.org/docs/confconsole

The source can be found on GitHub:

https://github.com/turnkeylinux/confconsole

The objective of Configuration Console (aka Confconsole) is to provide the user
with basic network configuration information and the ability to perform some
common tasks selected via a menu, rather than command line tools.

The information provided on the inital screen - or "limited" mode - includes:
    - The binded IP address
    - The listening services the user may connect to over the network

The tasks that may perform include in "full mode" include:

    - Networking:
      - Setting a static IP address or enable DHCP

    - Let's Encrypt (see docs/Lets_encrypt.rst):
      - Enable/disable auto SSL cert update
      - Get SSL certificate from Let's Encrypt

    - Mail relaying (see docs/Mail_relay.rst):
      - configure and enable remote SMTP email relay

    - Proxy settings (see docs/Proxy_settings.rst):
      - configure apt proxy

    - Region config (see docs/Region_config.rst):
      - Keyboard layout
      - Locales and language
      - Tzdata (timezone)

    - System settings (see docs/System_settings.rst):
      - install security updates
      - update hostname

    - Installing the system to the hard disk (if live)
    - Rebooting the appliance
    - Shutting down the appliance

When setting a static IP address or requesting DHCP, /etc/network/interfaces
will be updated so the changes are permanent (unless the configuration

Most confconsole functionality is provided via a plugin system.
For more information and/or if you wish to develop your own plugins,
please see docs/Plugins.rst

When setting a static IP address or requesting DHCP, /etc/network/interfaces
will be updated so the changes are perminent (unless the configuration
file has been customized by the user).

A limited Confconsole - showing only Network info - will be invoked
automatically on the default vt (virtual terminal). This can be disabled by
adding 'noconfconsole' to the GRUB_CMDLINE_LINUX variable. To do that, edit
/etc/default/grub and run 'update-grub'.

The full Confconsole will be invoked on the first terminal login as 'root' (or
'admin' on an AWS Marketplace instance). Launching on every login can be
enable in Confconsole >> Advanced >> System Settings.

Confconsole) may be executed manually as well (prefix with 'sudo' on AWS MP):

    confconsole
