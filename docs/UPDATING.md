# Updating VaeVictis

## What updates by itself

Everything that comes from Debian: security fixes are installed automatically every day (`unattended-upgrades`), and
`sudo apt update && sudo apt full-upgrade` brings the rest up to date. You do **not** need a new ISO for this: the ISO is only
the way to install the system the first time.

## The VaeVictis programs: a signed APT repository

The VaeVictis programs (Aurora, LinPaint+, VaeVictis PDF, the `vv-*` tools, the HIDS) are not in Debian's archive, so by default
`apt` does not know them. In release 1.0 they are plain files copied into the image.

They are being turned into ordinary Debian packages (`.deb`), one at a time, and published in a **signed APT repository**:
<https://apt.linuxtuts.online/> (the files are in [`vaevictis-apt`](https://github.com/linuxtuts-website/vaevictis-apt)).
Today it holds **Aurora 1.1.0** (`vaevictis-aurora`). It is something you add yourself, on purpose, and it is never switched on
behind your back.

**1. Download the key and check its fingerprint** (compare it with the one printed here, in the `vaevictis-apt` README and on the
[project page](https://linuxtuts.online/vaevictis/vaevictis.html)):

```bash
sudo install -d -m 0755 /etc/apt/keyrings
sudo curl -fsSLo /etc/apt/keyrings/vaevictis.gpg https://apt.linuxtuts.online/vaevictis-archive-keyring.gpg
gpg --show-keys --with-fingerprint /etc/apt/keyrings/vaevictis.gpg
```

```
0A41 158C 1DD6 718D 3D3F  FED0 6848 6B39 B2A9 9993
```

**2. Add the repository and install:**

```bash
sudo tee /etc/apt/sources.list.d/vaevictis.sources >/dev/null <<'EOF'
Types: deb
URIs: https://apt.linuxtuts.online
Suites: vaevictis
Components: main
Signed-By: /etc/apt/keyrings/vaevictis.gpg
EOF
sudo apt update
sudo apt install vaevictis-aurora
```

From then on `sudo apt update && sudo apt upgrade` updates these programs together with the rest of the system. To stop trusting
the repository, delete `/etc/apt/sources.list.d/vaevictis.sources` and `/etc/apt/keyrings/vaevictis.gpg`.

What this asks you to trust, in plain words:

- A package from this repository is installed as root, so whoever holds the signing key could push code to every system that uses
  it. The key (ed25519) is kept by the author on an encrypted disk, protected by a password; it is not on any server. It is a
  single key, not a hardware token.
- GitHub Pages only serves public files. The index files (`Release`, `InRelease`) are signed; `apt` rejects anything that does not
  verify. A published version is never changed: a fix is a new version.
- Every package is also published as an immutable release of this project, with its SHA-256, so you can compare.
- If the key were ever lost or stolen it would be revoked, and a new key and fingerprint would be published here and on the project
  page.

### Without the repository: the `.deb` from the release

You can install a package directly instead, without adding the repository:

```bash
sudo apt install ./vaevictis-aurora_1.1.0_all.deb
```

Download the `.deb` and its `.sha256` from the [`aurora-v1.1.0` release](https://github.com/linuxtuts-website/vaevictis-os/releases/tag/aurora-v1.1.0)
(the file in the repository is byte for byte the same). It is a release of its own: the 1.0 ISO still carries the first version of
Aurora, and a published release can never be changed.

- It replaces a copy of Aurora that was put into `/usr/local/bin` by hand (that folder wins over `/usr/bin`, so the old copy would
  hide the package). The old file is removed only if it really is Aurora; anything else of yours is left alone.
- To remove it: `sudo apt remove vaevictis-aurora`. `debsums vaevictis-aurora` checks that its files are unchanged.
- The `.deb` file itself is not signed (the repository index is): check the SHA-256 published with it
  (`sha256sum -c vaevictis-aurora_1.1.0_all.deb.sha256`) and, if you like, look inside before you install:
  `dpkg-deb -I FILE.deb` (description and dependencies) and `dpkg-deb -c FILE.deb` (the files it will install).

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
