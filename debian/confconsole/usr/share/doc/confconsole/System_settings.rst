System settings
===============

.. contents::

Overview
--------

Miscellaneous system settings. Currently a bit of a "catchall" for some
functionality we wanted to include.

.. image:: ./images/07_confconsole_system_settings.png

Security updates
----------------

This option manually checks for and installs Debian and TurnKey
security updates for package managed software (i.e. the base OS and
most; but not neccessarily all software pre-included).

By default, all TurnKey servers automatically install security updates
daily. This option allows you to manually trigger the updates.

This plugin leverages `turnkey-install-security-updates`, thus provides
exactly the same functionality.

**Note:** As stated, this only installs software that is covered by the
Debian package management system. It does not apply to third party
package management software (such as pip for python, cpan for perl,
gem for ruby, composer for php, etc). More often than not, that also
means NOT webapps installed direct from third parties. Upgrading
third party software must be done manually.

Hostname
--------

This option allows you to manually update the system's hostname. By
default TurnKey systems have a default hostname that matches the name
of the appliance. E.g. our LAMP server has a hostname of 'lamp',
WordPress server has a hostname of 'wordpress', etc.

A hostname may consist of multiple segements/labels, separated by a
period/full-stop (i.e.: '.'). Each segment must contain only the
ASCII letters 'a' through 'z' (case-insensitive), the digits '0'
through '9', and the hyphen ('-'). No other symbols, punctuation
characters, or white space are permitted. Each segment must be no
more than 64 characters and the total hostname length must not exceed
255 characters.

Some applications may need to be restarted to note the new hostname.
Rebooting is one easy way to ensure that the new hostname is being
used everywhere.
