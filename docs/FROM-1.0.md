# Coming from 1.0 or 1.0.1

An installed system does not turn into 1.1 by itself: the ISO is only the way to install. Debian's updates keep arriving as
before (`sudo apt update && sudo apt full-upgrade`, security fixes every day). This page says what of 1.1 you can apply to a
1.0 system yourself, and what needs a new installation.

## 1. The security notice (if you have not done it yet)

The four commands of the [2026-10-12 security notice](SECURITY-NOTICE-2026-10-12.md). They matter more than anything below.

## 2. Remove the HIDS (recommended)

**Why it is gone.** The HIDS (the file-integrity monitor, running as the service `sysctl-helper`) was the largest piece of this
project's own code always running as **root**. Code that runs as root all the time is code an attacker would love to find a
bug in, and a file monitor on the same machine can be switched off by anyone who already has root, which is exactly the case it
was meant to catch. 1.1 spends that effort where it protects more: the programs that open files from anywhere run in a sandbox,
the VPN runs with the least privileges, the kill switch fails closed. No known vulnerability: keeping it is not dangerous,
removing it is simply the better trade.

To remove it (it stops the service, then deletes its files; nothing else is touched):

```bash
sudo systemctl disable --now sysctl-helper.service
sudo chattr -i /usr/libexec/systemd-sysctl-helper /var/log/hids_baseline.json 2>/dev/null || true
sudo rm -f /usr/libexec/systemd-sysctl-helper /etc/systemd/system/sysctl-helper.service \
    /usr/local/bin/hids-gui /usr/local/bin/hids-notify /etc/xdg/autostart/hids-notify.desktop \
    /usr/share/applications/hids-security.desktop /usr/share/icons/hicolor/scalable/apps/hids.svg \
    /var/log/hids.log /var/log/hids_baseline.json
sudo systemctl daemon-reload
```

Then log out and in again (the popup helper stops). The Welcome window of 1.0 will now show the HIDS as "inactive": expected.
Check: `systemctl status sysctl-helper` answers "could not be found".

## 3. The VaeVictis APT repository

So that VaeVictis programs update with `apt`: [UPDATING.md, "On 1.0 / 1.0.1"](UPDATING.md#on-10--101-add-it-yourself).

## 4. Two kernel settings of 1.1

No typing into another program's terminal (`TIOCSTI`) and no `io_uring` (a kernel interface with a long history of bugs; a
desktop does not need it). If you run virtual machines with QEMU or virt-manager, they keep working (they fall back to
another method).

```bash
printf 'dev.tty.legacy_tiocsti = 0\nkernel.io_uring_disabled = 2\n' | sudo tee /etc/sysctl.d/91-vaevictis-1.1.conf
sudo sysctl --system >/dev/null && cat /proc/sys/dev/tty/legacy_tiocsti /proc/sys/kernel/io_uring_disabled
```

It prints `0` and `2`.

## 5. What needs a new installation

These are part of the image or of the installer, so they come only with the 1.1 ISO:

- the boot menu password (GRUB) and the new boot screens;
- the sandbox for Aurora, LinPaint+ and VaeVictis PDF;
- the VPN with least privileges and the stronger kill switch (it also blocks virtual machines and stays closed during a
  reconnect);
- v-snap only on encrypted disks, with the kernels in `/boot`;
- the mount options of `/boot`, the EFI partition and `/home`;
- the APT repository already configured.

If you reinstall: copy your files to an **encrypted** disk first (your home folder, VPN configuration files, KeePassXC database),
check that the copy opens, then install from the 1.1 ISO. Your VPN files are imported again with the VPN manager.
