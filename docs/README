
TurnKey GNU/Linux Configuration Console
===================================

A pretty version of this readme (with screenshots and clickable links)
is avaialble online from:

https://www.turnkeylinux.org/docs/confconsole

The source can be found on GitHub:

https://github.com/turnkeylinux/confconsole

The Configuration Console's objective is to provide the user with basic
network configuration information and the ability to perform basic
tasks, so as not to force the user to the command line.

The information provided includes:
    - The binded IP address
    - The listening services the user may connect to over the network

The basic tasks that the user may perform include:

    - Networking:
      - Setting a static IP address
      - Requesting DHCP

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

The new functionality (as of v1.0.0) is provided by the plugins system. 
For more information and/or if you wish to develop your own plugins, 
please see docs/Plugins.rst

When setting a static IP address or requesting DHCP, /etc/network/interfaces
will be updated so the changes are perminent (unless the configuration
file has been customized by the user).

The Configuration Console will be invoked automatically on a new vt (by
its init script) unless the boot paramater 'noconfconsole' is present 
on /proc/cmdline. 

The Configuration Console (confconsole) may be executed manually as well.

