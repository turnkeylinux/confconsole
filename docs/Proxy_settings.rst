Confconsole - Proxy settings
============================

.. contents::

Overview
--------

The confconsole proxy setting plugin currently allows you to set a proxy
for apt. This will allow you to get system updates and install 
packages, even if your server is hidden behind a proxy server.

.. image:: ./images/05_confconsole_proxy_settings.png

Apt proxy
---------

Selecting this option allows you to set the domain of a HTTP proxy for
use by the apt package management system.

Currently only HTTP proxies are supported (i.e. not HTTPS). If you
require use of an HTTPS proxy, unfortunately, you'll need to manually
configure that. 

Alternate ports (other than 80) are also possible by appending the port
to the end. E.g. http://proxy.example.com:8080

**Note:** you must include the scheme for your proxy. As only HTTP is
supported, that means it should look like this:

    http://proxy.example.com

