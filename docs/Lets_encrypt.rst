Confconsole - Let's Encrypt
===========================

.. contents::

Overview
--------

Confconsole Let's Encrypt plugin provides a simple way to get free, valid
SSL/TLS certificates via Let's Encrypt. It leverages the dehydrated_ tool to
interact with ACME SSL/TLS providers and uses a custom mini-webserver (named
`add-water`) to host the challenges required to prove your ownership of the
domain name.

To use this tool, you must already have configured DNS 'A' record(s) to point
your server's public IP. A static IP is recommended, although so long as an
'A' record points to your server when you `Get certificate`_.

Because it uses it's own built-in mini-server (`add-water`), this tool will
work with any webserver included with any TurnKey appliance (or even no
webserver), regardless of webserver configuration. This can be extended fairly
easily to work with other servers if required.

.. image:: ./images/03_confconsole_lets_encrypt.png

Currently support webservers are:

- Apache
- LigHTTPd
- Nginx
- Tomcat7/Tomcat8

Cert auto renew
---------------

Selecting this option makes the default SSL/TLS certificate renewal cron job
(`/etc/cron.daily/confconsole-dehydrated`) executable (or not). Only
executable files within /etc/cron.daily are triggered automatically by cron.

Do not run this until you have received your initial certificate. The cron job
doesn't exist in the cron.daily directory until you `Get certificate`_. This
ensures that the cron job can't be enabled until a valid SSL/TLS cert has been
generated.

**Note:** TurnKey Let's Encrypt integration **does not** currently
support wildcard certificates. That requires the DNS validation
method, which is not currently an option by default. If you need wildcard
certificates, you will need to either use Dehydrated directly (with
an appropriate hook script to make the required DNS records), or
use an alternate tool (that supports the `DNS-01` validation method)
to get your SSL/TLS certificates.

For more info about what the cron job actually does, please see `Cron
job details`_ below.

Get certificate
---------------

Selecting this option will allow you to get a single SSL/TLS
certificate for your server. The certificate can include up to 5
fully qualified domain names (FQDNs).

Additional domains are optional, please leave any unused lines blank.
Whilst it doesn't really matter what order the domains are in, it is
recommended that you add your root domain, or primary domain first.

If you wish to set more than 5 domains or you wish to create more
than one certificate, manual configuration is required. Please see
`Advanced - create multiple certificates (&/or more than 5 domains)`_
below.

**Note:** Before you attempt to retrieve a certificate, you must have your
domain's nameservers correctly configured with 'A' records which resolve all
of your selected domains to the server you are running confconsole. Failure
to do so will cause the Let's Encrypt challenges to fail (so you won't get a
certificate). Repeated failures may cause your server to be blocked (for up to
a week - perhaps longer) from further attempts.

Getting a certificate - Behind the scenes
-----------------------------------------

The process goes like this:

- Confconsole Let's Encrypt plugin writes the domain (and subdomains)
  to `/etc/dehydrated/confconsole.domains.txt`
- Confconsole calls dehydrated-wrapper
- dehydrated-wrapper stops webserver listening on port 80
- dehydrated-wrapper checks for `/etc/dehydrated/confconsole.config`
  (config file); if it doesn't exist, it copies the default file
  from:
  `/usr/share/confconsole/letsencrypt/dehydrated-confconsole.config`
- dehydrated-wrapper checks for `/etc/dehydrated/confconsole.hook.sh`
  (hook script); if it doesn't exist, it copies the default file
  from:
  `/usr/share/confconsole/letsencrypt/dehydrated-confconsole.hook.sh`
- dehydrated-wrapper checks for
  `/etc/cron.daily/confconsole-dehydrated` (cron script); if it
  doesn't exist, it copies the default file from:
  `/usr/share/confconsole/letsencrypt/dehydrated-confconsole.cron`
- dehydrated-wrapper calls dehydrated, passing `confconsole.config`,
  `confconsole.hook.sh` & `confconsole.domains.txt` (all stored
  within `/etc/dehydrated/`)
- dehydrated contacts Let's Encrypt and gets the challenge (to prove you
  control the domain)
- Whilst hosting the challenge, add-water temporarily redirects all
  web traffic except for the challenge (i.e. 304 - temporarily moved)
  to the web root. A simple "Under Maintence" message is displayed. To
  provide a custom html page, please see `Advanced - custom maintence
  message`_ below. UNder normal circumstance, that will only be
  visible for a few seconds.
- via the hook script, dehydrated serves Let's Encrypt challenges
  using add-water server (minimalist python webserver)
- when done, add-water is killed (via hook script)
- dehydrated writes certificate to `/etc/ssl/private/cert.pem` (via
  hook script); original certs generated by dehydrated remain in
  `/var/lib/dehydrated/certs/DOMAIN`
- dehydrated hands back to dehydrated-wrapper
- dehydrated-wrapper restarts webserver
- dehydrated-wrapper restarts stunnel (so Webmin & Webshell also use new cert)
- dehydrated-wrapper hands back to confconsole

Cron job details
----------------

The cron job daily checks the expiry date of the default certificate
(`/etc/ssl/private/cert.pem`) and if it will expire within 30 days or
less, it runs dehydrated-wrapper (using the --force switch).

The daily check means that even if it has difficulties one day, it will try
again the next. With a 30 day window, only real problems should stop your
certificate from being updated in time.

Advanced - custom maintence message
-----------------------------------

As noted, whilst it is serving the challenges, `add-water` will redirect all
other urls to the web root. By default it will display a simple "Maintenance"
message via a basic index.html file.

If you wish to display a custom message, then you can add a custom index.html
file to /var/lib/confconsole/letsencrypt/. E.g. to copy across the default and
then tweak it:

.. code-block:: bash

    mkdir -p /var/lib/confconsole/letsencrypt/
    cp /usr/share/confconsole/letsencrypt/index.html \
      /var/lib/confconsole/letsencrypt/index.html

`add-water` will serve /var/lib/confconsole/letsencrypt/index.html if it
exists, or otherwise will fall back to the default.

**Note:** The custom file must be named `index.html` and contain only
valid HTML, which may contain inline CSS and/or JavaScript. PHP or
other server side scripting languages are **not** supported.

Advanced - create multiple certificates (&/or more than 5 domains)
------------------------------------------------------------------

The interactive Confconsole plugin only supports creation of a single
certificate with up to 5 domains. However, dehydrated itself (and the
dehydrated-wrapper) can handle many more. It can also write out to
multiple individual certificates.

For every line in `/etc/dehydrated/confconsole.domains.txt` which is
not commented (i.e. doesn't start with `#`), dehydrated will attempt
to create a certificate. Individual domains should be space separated.
Additional whitespaces (e.g. spaces, tabs, empty lines, etc) are
ignored.

To create a single certificate with more than 5 domains, please manually edit
`/etc/dehydrated/confconsole.domains.txt` and add your additional domains onto
the end of the current domain line. As noted, domains should be space
separated. If that file does not exist, first copy the emplate file,
like this:

.. code-block:: bash

   cp /usr/share/confconsole/letsencrypt/dehydrated-confconsole.domains \
         /etc/dehydrated/confconsole.domains.txt

If adding additional domains to the one line (thus generating only one
certificate), the only additional action required is to run our
dehydrated-wrapper script. Do that like this:

.. code-block:: bash

   /usr/lib/confconsole/plugins.d/Lets_Encrypt/dehydrated-wrapper \
         --register --force

Unless you wish to keep the sites completely separate (e.g. a "shared
hosting" type arrangement) using a single certificate is recommened.
You can still host completely different content with each domain via
virtual-hosts, whilst using the same certificate. Using the default
TurnKey config, all siteswill inherit the default certificate.

To create an additional certificate(s); on a new line, add the domain(s)
for the additional certificate (domains should be space separated). A
unique certificate will be generated for each line.

If you create multiple certificates, the last certificate generated
will be the default server certificate for the main webserver, as
well as Webmin and Webshell. Unless of course you reconfigure things.

The additional certificates can be found in
`/var/lib/dehydrated/DOMAIN`, where DOMAIN is the first domain listed
on each line.

You will need to manually configure the usage of these certificates.
Generally that will require you to explicitly state the certificate
path to use in each virtual host (or app if not a webserver).
Further elaboration is outside the scope of this doc. Please feel free
to seek further assistance on the `TurnKey Linux forums`_ (requires free
website user account).

- **WARNING:** If you re-run confconsole's Let's Encrypt plugin after
  reconfiguring `/etc/dehydrated/confconsole.domains.txt` with more
  than 5 domains and/or more than one certificate, your custom
  changes will be lost! You have been warned!

- **WARNING:** the cron job only checks the expiry of
  `/etc/ssl/private/cert.pem`. Under most circumstance that will be
  fine. By default `/etc/ssl/private/cert.pem` will be updated at the
  same time as the other certificates (even if you aren't using it).
  However, if you adjust the hook script to no longer update
  `/etc/ssl/private/cert.pem`, you will also need to adjust the cron
  job to check the expiry of a certificate you are updating. Failure
  to do so will result in daily certificate updates, which may get
  your server temporarily blocked from accessing the Let's Encrypt
  servers.

.. _Dehydrated: https://github.com/dehydrated-io/dehydrated
.. _TurnKey Linux forums: https://www.turnkeylinux.org/forum
