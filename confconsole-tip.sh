# Sourced by /etc/profile for interactive login shells.
case $- in
    *i*) ;;
    *) return 0 ;;
esac
[ -z "${TURNKEY_HUB_BACKUP_TIP_SHOWN:-}" ] || return 0

# Also silence the older Hub-managed login script, if present.
TURNKEY_HUB_BACKUP_TIP_SHOWN=1
[ -t 1 ] && [ "${TERM:-dumb}" != dumb ] || return 0
command -v confconsole >/dev/null 2>&1 || return 0

if [ -n "${BASH_VERSION:-}" ] && [ -r "$HOME/.bashrc" ] &&
        [ -x "$HOME/.bashrc.d/confconsole-auto" ] &&
        [ -r /etc/confconsole/confconsole.conf ]; then
    case $(sed -nE 's/^autostart +([a-z]+).*/\1/p' /etc/confconsole/confconsole.conf) in
        true|once) return 0 ;;
    esac
fi

if [ "$(id -u)" -eq 0 ]; then
    printf '\nTip: Open the server configuration menu with:\n\n  confconsole\n\n'
elif command -v sudo >/dev/null 2>&1 && {
    id -nG | grep -qw sudo ||
        { [ "$(id -un)" = admin ] && sudo -n -l -- /usr/bin/confconsole >/dev/null 2>&1; }
}; then
    # TurnKey's admin can have a direct sudoers entry without the sudo group.
    printf '\nTip: Open the server configuration menu with:\n\n  sudo confconsole\n\n'
fi
