# Coming from 1.0 or 1.0.1

An installed system does not turn into 1.1 by itself: the ISO is only the way to install. Debian's updates keep arriving as
before (`sudo apt update && sudo apt full-upgrade`, security fixes every day). This page says what of 1.1 you can apply to a
1.0 system yourself, and what needs a new installation.

## Read this first: weaknesses of 1.0 and 1.0.1 that 1.1 fixes

A full review of the code (13 October 2026) found these problems in 1.0 and 1.0.1. Each one can expose data you expected
to be protected. They are addressed in 1.1 only, so **a new installation from 1.1 is recommended** (section 5). Until then,
these are the possible threats and what you can do:

- **VPN kill switch.** It blocks the traffic of this PC when the tunnel drops, but **not the traffic of virtual machines**
  running on it; and if a reconnect fails, the kill switch **stays off**. Until you reinstall: do not rely on the kill switch
  while virtual machines run, and after every reconnect check your address (the CHECK button of the VPN manager).
- **v-snap snapshots.** A system snapshot contains secret files: the key that unlocks `/home`, password hashes, VPN and
  Wi-Fi keys. 1.0 lets you save it to **any** disk, including an unencrypted USB stick, where anyone holding the stick can
  read those files. Until you reinstall: save snapshots only to an encrypted disk, and **delete snapshots that are on
  unencrypted disks**. Restore only snapshots you made yourself, and after a kernel update do not restore an older system
  snapshot (on encrypted installs the kernel in `/boot` is not part of it).
- **VaeVictis PDF.** From a password-protected PDF, *Extract*, *Split* and *Export PNG* create files **without the
  password**, without warning. Until you reinstall: check the files you extracted from protected PDFs and protect or delete
  them.
- **The HIDS** (the integrity monitor, service `sysctl-helper`). Code that always runs as root adds attack surface, and
  reviews found robustness problems in it and in its dashboard (for example, the dashboard runs helper programs found
  through your `PATH`, and its service has more privileges than it needs). It was removed in 1.1 and **no longer receives
  fixes**: removing it is recommended (section 2).

This list covers what is known today. Other problems may exist in 1.0, 1.0.1 and 1.1 alike: VaeVictis is provided as is,
without warranty (GPL-3.0, sections 15 and 16).

## 1. The security notice (if you have not done it yet)

The four commands of the [2026-10-12 security notice](SECURITY-NOTICE-2026-10-12.md). They matter more than anything below.

## 2. Remove the HIDS (recommended)

**Why it is gone.** The HIDS (the file-integrity monitor, running as the service `sysctl-helper`) was the largest piece of this
project's own code always running as **root**. Code that runs as root all the time is code an attacker would love to find a
bug in, and a file monitor on the same machine can be switched off by anyone who already has root, which is exactly the case it
was meant to catch. 1.1 spends that effort where we expect it to help more: the programs that open files from anywhere run in a sandbox,
the VPN runs with the least privileges, the kill switch is designed to fail closed. The HIDS no longer receives fixes:
removing it is recommended.

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
desktop does not need it). If you run virtual machines with QEMU or virt-manager, they should keep working (they fall back to
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
- the VPN with least privileges and the stronger kill switch (designed to also block virtual machines and to stay closed during a
  reconnect);
- v-snap only on encrypted disks, with the kernels in `/boot`;
- the mount options of `/boot`, the EFI partition and `/home`;
- the APT repository already configured.

If you reinstall: copy your files to an **encrypted** disk first (your home folder, VPN configuration files, KeePassXC database),
check that the copy opens, then install from the 1.1 ISO. Your VPN files are imported again with the VPN manager.
