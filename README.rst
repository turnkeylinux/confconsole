TurnKey GNU/Linux Configuration Console
=======================================

.. contents::

Overview
--------

The objective of the Configuration Console (AKA confconsole) is to 
provide the user with basic network configuration information and the
ability to perform basic tasks, so as not to force the user to the
command line.

It is licensed under `GPLv3`_. We aim to keep this documentation up to
date, but the `Confconsole documentation source`_ should always be up to
date.

Main screen and basic functionality
-----------------------------------

The main screen of Confconsole provides the following information:

- The currently bound IP address
- The listening services the user may connect to over the network

.. image:: ./docs/images/00_confconsole_core_main.png

Configuration Console will be invoked automatically on firstboot, but without
the "Advanced Menu" available. By default it will also auto launch (with
"Advanced Menu") on first login. Unless you enable auto-start, it will
need to be manually invoked for subsequent use.

Manually invoke the Configuration Console (confconsole) like this:

.. code-block:: bash

    confconsole

Advanced
--------

Additional Confconsole functionality is provided by way of a
"`Plugin`_" system. To navigate to the plugins, please enter the
"Advanced" menu. Note that only the default plugins are noted here.
Some TurnKey GNU/Linux appliances may have additional (or modified)
plugins.

The advanced menu:

.. image:: ./docs/images/01_confconsole_core_advanced.png

The Advanced menu provides the below functionality in all appliances
(some items have additional docs available via clickable headings).

- `Networking`_:

  - Setting a static IP address
  - Requesting DHCP

- `Let's Encrypt`_:

  - Enable/disable auto SSL cert update
  - Get SSL certificate from Let's Encrypt

- `Mail relaying`_:

  - configure and enable remote SMTP email relay

- `Proxy settings`_:

  - configure apt proxy

- `Region config`_:

  - Keyboard layout
  - Locales and language
  - Tzdata (timezone)

- `System settings`_:

  - confconsole autostart config
  - install security updates
  - update hostname

- Install the system to the hard disk (only available when running live)
- Reboot the appliance
- Shut down the appliance
- Quit (return to commandline)

Installation
------------

Confconsole is installed by default in all `TurnKey Linux Appliances`_
so no installation should be required for TurnKey users.

Confconsole should be compatible with vanilla Debian (and likely recent
vanilla Ubuntu too). It does have some specific TurnKey dependencies,
but most dependencies come direct from Debian.

Upgrade Confconsole
-------------------

Confconsole is installed by default in `TurnKey Linux Appliances`_. However,
to ensure that you are running the latest version, you can upgrade via apt:

.. code-block:: bash

    apt-get update
    apt-get install confconsole

If you have problems or questions, please post on our `support forums`_
(requires free website user account).

Plugins
-------

The plugins system allows support for additional functionality via simply
dropping a(n appropriately coded) python3 plugin file within the Confconsole
file hierarchy. We aim to include more new functionality via this in coming
releases.

Developers may be interested in reading further about the `Plugin`_ system.

.. _GPLv3: https://www.gnu.org/licenses/gpl-3.0.txt
.. _Confconsole documentation source: https://github.com/turnkeylinux/confconsole/blob/master/docs/Readme.rst
.. _Plugin: ./docs/Plugins.rst
.. _Networking: ./docs/Networking.rst
.. _Let's Encrypt: ./docs/Lets_encrypt.rst
.. _Mail relaying: ./docs/Mail_relay.rst
.. _Proxy settings: ./docs/Proxy_settings.rst
.. _Region config: ./docs/Region_config.rst
.. _System settings: ./docs/System_settings.rst
.. _TurnKey Linux Appliances: https://www.turnkeylinux.org/all
.. _support forums: https://www.turnkeylinux.org/forum/support
