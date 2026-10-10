# Updating VaeVictis

## What updates by itself

Everything that comes from Debian: security fixes are installed automatically every day (`unattended-upgrades`), and
`sudo apt update && sudo apt full-upgrade` brings the rest up to date. You do **not** need a new ISO for this: the ISO is only
the way to install the system the first time.

## What does not update by itself (yet)

The VaeVictis programs (Aurora, LinPaint+, VaeVictis PDF, the `vv-*` tools, the HIDS) are not in Debian's archive, so `apt`
does not know them. In release 1.0 they are plain files copied into the image.

They are being turned into ordinary Debian packages (`.deb`), one at a time. **Aurora is the first**: `packaging/aurora/` holds
everything needed to build `vaevictis-aurora_VERSION_all.deb`.

```bash
sudo apt install ./vaevictis-aurora_1.1.0_all.deb
```

Download the `.deb` and its `.sha256` from the [`aurora-v1.1.0` release](https://github.com/linuxtuts-website/vaevictis-os/releases/tag/aurora-v1.1.0). It is a release of its own: the 1.0 ISO
still carries the first version of Aurora, and a published release can never be changed.

- It replaces a copy of Aurora that was put into `/usr/local/bin` by hand (that folder wins over `/usr/bin`, so the old copy would
  hide the package). The old file is removed only if it really is Aurora; anything else of yours is left alone.
- To update later, install the newer `.deb` the same way. To remove it: `sudo apt remove vaevictis-aurora`.
- `debsums vaevictis-aurora` checks that its files are unchanged.

These `.deb` files are **not signed yet** and are not in an APT repository: check the SHA-256 published with each one
(`sha256sum -c vaevictis-aurora_1.1.0_all.deb.sha256`) and, if you like, look inside before you install:
`dpkg-deb -I FILE.deb` (description and dependencies) and `dpkg-deb -c FILE.deb` (the files it will install).
A signed APT repository, so that `apt upgrade` also updates the VaeVictis programs, is planned. It will be something you add
yourself, on purpose, never switched on behind your back.

## Build the package yourself

```bash
bash packaging/aurora/build.sh        # from the repository root; writes dist/
```

The build is repeatable. To get exactly the published file, use the date it was built with:

```bash
SOURCE_DATE_EPOCH=1791624000 bash packaging/aurora/build.sh     # SHA-256 6b81d6973b155c6db153fca629e419e5149071ec5768aedc86547387fd49b37b
```

The published 1.1.0 was checked on two systems (Ubuntu 24.04 with `dpkg` 1.22.6 and `xz` 5.4.5, and Debian 13): the bytes are identical.
Without `SOURCE_DATE_EPOCH` the build uses the date of the last commit, so the contents are the same but the file differs.

## A new ISO

Only for fresh installs and for milestones (a new Debian point release, a large change). Existing installations do not need it.
