Confconsole - Networking
========================

.. contents::

Overview
--------

Networking allows the user to allocate a server IP address via DHCP
(default) or set a static IP.

.. image:: ./images/02_confconsole_core_networking.png

DHCP
----

Selecting **DHCP** from the menu will querry the local DHCP server for a new
dynamically allocated IP address.

Static
------

Selecting **StaticIP** from the menu allows you to set a static IP address
as follows:

- IP Adress: The desired static IP address
- Netmask: Subnet details (if you are on a LAN with 192.168.x.x then
  it's probably 255.255.255.0)
- Default Gateway: The internet Gateway IP address (your router IP if on
  a LAN)
- Name Server(s): The IP address(es) of DNS servers to use. Currently
  allows up to 3.

Notes
-----

By default, initially TurnKey Linux sets an IP address via DHCP (see
limitations below).

Changes to network config via Confconsole are persistent and will
survive reboot (see limitations below).

The Confconsole networking configuration is unchanged in v1.0.0.

Limitations
-----------

Only IPv4 addresses are currently supported.

In most build types, by default TurnKey Linux sets an IP address via
DHCP. The exceptions to that are Proxmox/LXC and Docker. Generally these
builds have an IP (static or dynamic), set via the host when
initially created. 

In some limited cases (e.g. Proxmox - depending on configuration),
any networking adjustments made via Confconsole (or other means) will
NOT be persistent post-reboot. The networking can still be 
reconfigured on the running system. However, changes will be lost on
reboot. As a general rule, it is recommended that unless you have a need
to reconfigure newtorking within the instance, that the desired settings
are configured on the host.

Some other platforms (e.g. AWS EC2) may not work correctly if a
static IP is set.

Technical note
--------------

Technically the Networking option is not provided by a plugin as it
is a legacy "Advanced" menu option.

