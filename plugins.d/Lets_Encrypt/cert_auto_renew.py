"""Toggle automatic renewal."""

menu_label = "Autorenew"
menu_order = -1


def doOnce():
    global certificates
    certificates = impByPath("Lets_Encrypt/certificate_service.py")


def run():
    if not certificates.CRON.is_file():
        console.msgbox("Automatic renewal", "Get a certificate to enable automatic renewal.")
        return
    while True:
        enabled = certificates.renewal_enabled()
        status = "enabled" if enabled else "disabled"
        choice = console._wrapper(
            "yesno", f"Automatic certificate renewal is {status}.", 10, 30,
            yes_label="Toggle", no_label="OK",
        )
        if choice != "ok":
            return
        try:
            certificates.set_renewal(not enabled, browser=False)
        except certificates.CertificateError as error:
            console.msgbox("Automatic renewal", str(error))
            return
        except OSError:
            console.msgbox("Automatic renewal", "Could not update the renewal schedule.")
            return
