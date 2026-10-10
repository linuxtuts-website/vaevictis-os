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

The build is repeatable: the same files, the same `SOURCE_DATE_EPOCH` and the same Debian release (its `dpkg` and `xz`) give a
byte-identical `.deb`. On another distribution the contents are the same but the compressed bytes can differ.

## A new ISO

Only for fresh installs and for milestones (a new Debian point release, a large change). Existing installations do not need it.
