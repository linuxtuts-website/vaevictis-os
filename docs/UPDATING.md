# Updating VaeVictis

## Everything updates from Debian

Security fixes are installed automatically every day (`unattended-upgrades`), and `sudo apt update && sudo apt full-upgrade`
brings the rest up to date. You do **not** need a new ISO for this: the ISO is only the way to install the system the first time.

VaeVictis has **no APT repository of its own** any more: it was closed with 1.2 ([why](APT-REPOSITORY.md)). A fix of
VaeVictis's own tools, when one is needed, is published as a file in a release.

## Installed from 1.1: the last fixes, and removing the repository

1.1 trusts the closed repository. Its last fixes are three packages in the
[1.2 release](https://github.com/linuxtuts-website/vaevictis-os/releases/tag/v1.2). Download them with `SHA256SUMS`,
`SHA256SUMS.asc` and `vaevictis-release-key.asc` into one folder, then in that folder:

```bash
gpg --show-keys vaevictis-release-key.asc        # the fingerprint must be 0A41158C1DD6718D3D3FFED068486B39B2A99993
gpg --import vaevictis-release-key.asc
gpg --verify SHA256SUMS.asc SHA256SUMS           # must say: Good signature
sha256sum --ignore-missing -c SHA256SUMS         # each package: OK
sudo apt install ./vaevictis-tools_1.3.0_all.deb ./vaevictis-aurora_1.1.3_all.deb ./vaevictis-archive-keyring_2026.10.18_all.deb
sudo apt purge vaevictis-archive-keyring         # the package is empty now: remove it too
```

What they do:

- **`vaevictis-tools` 1.3.0** puts the fixed VaeVictis tools in place of the copies the 1.1 image installed, at the same paths
  (the launchers, the polkit rule and the sudo rule expect them there): the app sandbox, the VPN manager and its helper, the VPN
  polkit rule, v-snap, the panic button, VaeVictis PDF and LinPaint+. A copy is replaced **only if it is exactly a version
  VaeVictis shipped**: a copy you changed is left alone (the package says so) and a missing tool is not added. The replaced
  copies are kept in `/var/lib/vaevictis-tools/backup/`; removing the package does not restore them.
- **`vaevictis-aurora` 1.1.3**: the fixed music player.
- **`vaevictis-archive-keyring` 2026.10.18** removes the repository's source entry, pin and key, so `apt update` no longer
  contacts it.

Only want to stop using the repository: `sudo apt purge vaevictis-archive-keyring` (**purge**, not remove: remove would leave
the source entry without its key, and `apt update` would report an error).

VaeVictis PDF is not in 1.2 (Debian's PDF viewer is there). On 1.1 it stays, fixed by `vaevictis-tools` 1.3.0. To remove it:

```bash
sudo rm /usr/local/bin/vv-pdf /usr/local/lib/vaevictis/vv-pdf /usr/share/applications/vv-pdf.desktop
```

A `.deb` file is not signed by itself: the signed `SHA256SUMS` of the release is what proves it is the published one. To look
inside before installing: `dpkg-deb -I FILE.deb` (description, dependencies) and `dpkg-deb -c FILE.deb` (the files).

## On 1.0 / 1.0.1, if you added the repository by hand

```bash
sudo apt purge vaevictis-archive-keyring         # only if you installed it ("is not installed" is fine)
sudo rm -f /etc/apt/sources.list.d/vaevictis.sources /etc/apt/sources.list.d/vaevictis-bootstrap.sources /etc/apt/keyrings/vaevictis.gpg
sudo apt update
```

What else of the newer releases you can apply yourself: [FROM-1.0.md](FROM-1.0.md).

## Build the packages yourself

```bash
bash packaging/tools/build.sh                 # from the repository root; each writes dist/
bash packaging/aurora/build.sh
bash packaging/archive-keyring/build.sh
```

The builds are repeatable: with the same `SOURCE_DATE_EPOCH` the files are byte for byte the same (without it the date of the
last commit is used, so the contents are the same but the file differs). For example the published Aurora 1.1.0:
`SOURCE_DATE_EPOCH=1791624000 bash packaging/aurora/build.sh` gives SHA-256
`6b81d6973b155c6db153fca629e419e5149071ec5768aedc86547387fd49b37b` (checked on Ubuntu 24.04 and Debian 13).

## A new ISO

Only for fresh installs. Existing installations do not need it: Debian keeps them up to date.
