# Security notice: VaeVictis OS 1.0 installations (2026-10-12)

**Who is affected:** every system installed from the VaeVictis OS 1.0 ISO. The live session is not affected beyond its
documented live defaults.
**What to do:** run the four commands below once, then log out and back in. It takes a minute and changes nothing else.
**Fixed in:** VaeVictis OS 1.0.1 (new installs). Download: <https://vaevictisos.org/>

## The fix

Open a terminal on the installed system and run:

```bash
sudo rm -f /usr/share/polkit-1/rules.d/sudo_on_live.rules
sudo gpasswd -d "$USER" libvirt
sudo usermod -p '*' root
sudo make-ssl-cert generate-default-snakeoil --force-overwrite
```

Then log out and log in again (the group change takes effect at the next login).

If the integrity monitor (HIDS) shows alerts about `/etc/group`, `/etc/gshadow` or `/etc/shadow` right after this, they come
from these commands. Accept the new state with:

```bash
sudo /usr/libexec/systemd-sysctl-helper -seal
```

## What was wrong

1. **A live-session rule was copied into installed systems.** The live session lets its user (`user`) do administrative
   tasks without a password. The installer copied that rule to the installed system. If you chose the username `user`,
   programs running as you could get administrator rights without asking for your password. The first command removes it
   (it is harmless to run with any username).
2. **The installer added your account to the `libvirt` group.** Members of that group can manage the system's virtual
   machines without a password, which is equivalent to administrator rights. The second command removes your account from
   it. Virtual machines keep working: virt-manager now asks for your password.
3. **The root account kept a password hash from the build system.** Root was and stays locked (nobody can log in as root);
   the third command removes the leftover hash.
4. **The TLS key `ssl-cert-snakeoil` was the same on every system.** Nothing in a default install uses it; the fourth command
   creates a key of your own, in case you later install a service that does.

## Check that it worked

```bash
ls /usr/share/polkit-1/rules.d/sudo_on_live.rules   # "No such file or directory"
id -nG | grep -w libvirt                            # prints nothing (after the new login)
pkexec true                                         # asks for your password: cancel it
```

## Credit and contact

Found in an internal audit of the VaeVictis code. Questions or reports: admin@vaevictisos.org, or GitHub's private
vulnerability reporting on the repository.
