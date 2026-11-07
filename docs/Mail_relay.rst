Confconsole - App email
======================

Link to TurnKey Hub
------------------

Choose **Advanced**, **Mail relaying**, then **Mail relay** and
**Link to TurnKey Hub**. Open
https://hub.turnkeylinux.org/link on your phone or computer, sign in or
create a free account, and enter the displayed code, such as ``ABCD&1234``.
Then select **Check** in Confconsole.

A free account includes app email delivery, a tklapp.com hostname and
dynamic DNS. Paid accounts can use a custom sending domain. Hub-launched
appliances link automatically.

Apps that send through the appliance's system mail service use the relay
without separate app configuration. Choose **Test** to submit a test email,
then check the recipient's inbox to confirm delivery. Incoming email remains
with your existing mailbox provider.

Custom SMTP
-----------

Choose **Custom** to use another SMTP provider. Enter its host, port,
username and password. The connection requires authenticated SMTP with a
verified TLS certificate. Port 587 uses STARTTLS; port 465 uses implicit TLS.
Settings are applied only after the encrypted connection is verified.

Status and recovery
-------------------

**Status** checks the current connection. If the link request expires or is
denied, choose **Link to TurnKey Hub** to start again. Cancelling keeps the
working mail settings.

**Reset mail** restores the previous local mail settings while preserving the
Hub link and dynamic DNS. Custom SMTP also leaves dynamic DNS configured. Revoke an old
appliance credential in the Hub when it is no longer needed. Resetting local
mail settings does not delete a cloud server or revoke a source server's
credentials when preparing a clone.
