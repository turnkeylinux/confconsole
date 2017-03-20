Let's Encrypt - Advanced Usage
==============================

Serving a custom "Maintence" message
------------------------------------

As noted, whilst it is serving the challenges, add-water will 
redirect all other urls to the web root. By default it will display 
a simple "Maintenance" message via a basic index.html file. 

If you wish to display a custom message, then you can add a custom 
index.html file to /var/lib/confconsole/letsencrypt/. E.g. to copy 
across the default and then tweak it:

````
mkdir -p /var/lib/confconsole/letsencrypt/
cp /usr/share/confconsole/letsencrypt/index.html \
  /var/lib/confconsole/letsencrypt/index.html
````
add-water will server /var/lib/confconsole/letsencrypt/index.html
if it exists, or otherwise will fall back to the default.

Note: it must be named `index.html` and contain only HTML (and CSS).
      PHP or other server side languages are not supported. The 
      exception is JavaScript as that is processed client side.


Using dehydrated-wrapper with multiple domains
----------------------------------------------

The interactive Confconsole plugin only supports a single domain with
up to 4 subdomains. However, the dehydrated-wrapper can handle 
multiple domains. To support that you will need to manually make 
configuration adjustments in a number of places:

  - add additional domains to /etc/dehydrated/confconsole.domains.txt

    - ensure that each line starts with the base domain, followed by
      any subdomains

    - Note: If you re-run confconsole's Let's Encrypt plugin, your 
            custom additional domains will be removed.

  - adjust your webserver virtual hosts to use the relevant 
    certificates in /var/lib/dehydrated/certs/DOMAIN each domain will
    have it's own subdirectory under /var/lib/dehydrated/certs/

  - by default, the last domain (and any subdomains) configured, will
    be the one which work for Webmin & Webshell (and Adminer, if it's 
    included). To change this behaviour, you can adjust the hook 
    script, or simply rearange the order of your domains and put the 
    one you want Webmin & Webshell available from last.

  - by default, the cron job will only check the expiry of 
    /etc/ssl/private/cert.pem so if you adjust the hook script, you 
   will probably also want to adjust the cron job, so it checks the 
   expiry of a certificate you are using.
