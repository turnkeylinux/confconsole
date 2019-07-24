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

The Configuration Console will be invoked automatically on a new vt (by
its init script) unless the boot paramater 'noconfconsole' is present 
on /proc/cmdline. 

The Configuration Console (confconsole) may be executed manually as
well:

.. code-block:: bash

    confconsole

Advanced
--------

For version v1.0.0 (default in TurnKey v14.2+), Confconsole has been
significantly refactored and includes some long overdue additional
functionality. The additional functionality is provided by way of a
"`Plugin`_ system. To navigate to the new plugins, please enter the
"advanced" menu.

The advanced menu:

.. image:: ./docs/images/01_confconsole_core_advanced.png

As of v1.0.0 the Advanced menu provides the following functionality
(some items have additional docs avaialble via clickable headings):

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

  - install security updates
  - update hostname

- Install the system to the hard disk (only when running live)
- Reboot the appliance
- Shut down the appliance
- Quit (return to commandline)

Installation
------------

Confconsole is installed by default in all `TurnKey Linux Appliances`_
so no installation should be required for TurnKey users.

For users of TurnKey Linux v14.0 & v14.1, please see below for how to
upgrade to the latest version.

In theory it should be compatible with vanilla Debian Jessie (and 
possibly vanilla Ubuntu of a similar age version too). However, 
currently it depends on a legacy version of `python-dialog`_ (which
is packaged in the TurnKey apt repo).

At some point we hope to rewrite it to rely on the default
python-dialog.

Upgrade to v1.0.0+
------------------

Confconsole v1.0.0 is installed by default in TurnKey Linux v14.2+.
However it is also possible to upgrade to the current version on
other v14.x releases.

To upgrade your instance of Confsole on v14.0 & v14.1, including 
support for Let's Encrypt, please do the following:

.. code-block:: bash

    apt-get update
    apt-get install confconsole python-bottle authbind dehydrated

Plugins
-------

The plugins system allows support for additional functionality via
simply dropping a(n appropriately coded) python plugin file within the
Confconsole file hierarchy. We aim to include more new functionality via
this in coming releases. 

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
.. _python-dialog: https://github.com/turnkeylinux/pythondialog
