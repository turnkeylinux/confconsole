Confconsole - Region config
===========================

.. contents::

Overview
--------

The Region config plug in allows users to customize common regional
settings on their TurnKey server. Configurable setting include
keyboard layout, locales (i.e. language and encoding) and timezone.

.. image:: ./images/06_confconsole_region_config.png

This is only useful if you wish to change from the defaults. The TurnKey
Linux system defaults are:

- keyboard: English (US) - aka US International
- locale: 

Keyboard
--------

Select this option to reconfigure the default keyboard layout which your
server will use. Default is English (US). 

Please note that additional packages are needed to reconfigure this, so
your server will need to be connected to the internet to complete this.

If the required package is not already installed, you will be given
the option to install it.

Locale
------

A system "locale" refers to the regional conventions for things such as
date and time formatting, character display and currency display. This
essentially includes language, although not explicitly (not all programs
support alternate languages).

When you first select this option, you will be greated with an extensive
list of avaialble locales. Simply scroll through them and use <space> to
select/deselect locales. 

It is strongly suggested that you leave 'en_US.UTF-8' (the default)
enabled as some software requires it to function properly. It is
further suggested that you only enable the relevant UTF-8 character
set. UTF is generally the acceptd standard.

**Important note:** You are strongly urged to set the default locale to
"None". This ensures that users logging in via SSH can use their local
PC locale, rather than being forced to use the system setting.

**Note:** TurnKey includes a utility called locale-purge. This allows us
to keep the size of the instalation as small as possible. The downside
of that is that the system by default does not include documentation and
for languages other than English. If you do no use English as a first
language and would like to restore the non-English documentation, you
will need to manually re-install any/all packages for which the
alternate language documentation is missing. Please note, not all
packages include non-English docs. Also note that this only applies to
packages installed prior to setting your locale. All packages installed
after setting your locale, will keep everything related to configured
locales.

Tzdata
------

Tzdata relates to the local timezone. On a server, as a general rule
it is best to use UTC time. And that is indeed the TurnKey default.
However, Linux can be easily configured to adopt a region specific
offset.

This means, that whilst the underlaying system will still use UTC,
for any users (and software running on the system) it will display
the local timezone by default.

Simply select your region. Then select the relevant city/area.

**Note:** Some PHP applications may require you to also set the
timezone in your php.ini file. This confconsole plug in does NOT do
that! If you need to do that, you will need to manually adjust that
yourself.
