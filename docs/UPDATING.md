# Updating VaeVictis

## What updates by itself

Everything that comes from Debian: security fixes are installed automatically every day (`unattended-upgrades`), and
`sudo apt update && sudo apt full-upgrade` brings the rest up to date. You do **not** need a new ISO for this: the ISO is only
the way to install the system the first time.

## The VaeVictis programs: a signed APT repository

The VaeVictis programs (Aurora, LinPaint+, VaeVictis PDF, the `vv-*` tools) are not in Debian's archive. They are being turned
into ordinary Debian packages (`.deb`), one at a time, and published in a **signed APT repository**:
<https://apt.linuxtuts.online/> (the files are in [`vaevictis-apt`](https://github.com/linuxtuts-website/vaevictis-apt)).
Today it holds **Aurora** (`vaevictis-aurora`), the **fixed VaeVictis tools** (`vaevictis-tools`, see below) and the
repository's own key package (`vaevictis-archive-keyring`).

### From 1.1: already configured

A system installed from the 1.1 ISO has the package `vaevictis-archive-keyring`, which holds the key, the source entry and a pin:

- the repository may provide **only packages named `vaevictis-*`**: anything else it offered (for example a "newer" copy of a
  Debian package) is ignored by apt (`/etc/apt/preferences.d/vaevictis`);
- its index is signed with the key `0A41 158C 1DD6 718D 3D3F  FED0 6848 6B39 B2A9 9993` and carries an **expiry date**: an old
  index is refused after its date, so it cannot be served for long to hide a newer fixed package;
- `sudo apt update && sudo apt upgrade` updates these programs together with the rest of the system; they are not installed
  automatically in the background (only Debian's security updates are).

To stop trusting it: `sudo apt purge vaevictis-archive-keyring`. Check what apt would take from where: `apt policy vaevictis-aurora`.

### The fixed tools: `vaevictis-tools`

The 1.1 image put the VaeVictis tools in `/usr/local` (the desktop launchers, the polkit rule and the sudo rule expect them
there). `vaevictis-tools` carries fixed versions and puts them **at the same paths**: the app sandbox, the VPN manager and its
helper, the VPN polkit rule, v-snap and the panic button. It arrives with `sudo apt update && sudo apt full-upgrade` (Aurora
1.1.2 depends on it), or directly: `sudo apt install vaevictis-tools`.

- A copy is replaced **only if it is exactly a version VaeVictis shipped**. A copy you changed is left alone (the package says
  so), and a missing tool is not added. The replaced copies are kept in `/var/lib/vaevictis-tools/backup/`.
- Removing the package does not restore the old copies (`sudo apt purge vaevictis-tools` also deletes the backups).
- On 1.0 and 1.0.1, the VPN manager and v-snap are different versions, so they stay as they are; only the files identical to
  1.1 (the VPN polkit rule and the panic button) are replaced. For the rest, see [FROM-1.0.md](FROM-1.0.md).

### On 1.0 / 1.0.1: add it yourself

**1. Download the key and check its fingerprint** (compare it with the one printed here and in the `vaevictis-apt` README):

```bash
sudo install -d -m 0755 /etc/apt/keyrings
sudo curl -fsSLo /etc/apt/keyrings/vaevictis.gpg https://apt.linuxtuts.online/vaevictis-archive-keyring.gpg
gpg --show-keys --with-fingerprint /etc/apt/keyrings/vaevictis.gpg
```

```
0A41 158C 1DD6 718D 3D3F  FED0 6848 6B39 B2A9 9993
```

**2. Add the repository for a moment, install its key package, then let the package take over:**

```bash
sudo tee /etc/apt/sources.list.d/vaevictis-bootstrap.sources >/dev/null <<'EOF'
Types: deb
URIs: https://apt.linuxtuts.online
Suites: vaevictis
Components: main
Signed-By: /etc/apt/keyrings/vaevictis.gpg
EOF
sudo apt update
sudo apt install vaevictis-archive-keyring vaevictis-aurora
sudo rm /etc/apt/sources.list.d/vaevictis-bootstrap.sources /etc/apt/keyrings/vaevictis.gpg
sudo apt update
```

(The `rm` is needed: apt refuses two entries for the same repository with different keys.) If you followed the older version of
this page, your entry is called `vaevictis.sources`: when `apt install vaevictis-archive-keyring` asks about that file, answer `Y`
(take the package's version), then delete `/etc/apt/keyrings/vaevictis.gpg`.

To stop trusting the repository later: `sudo apt purge vaevictis-archive-keyring`.

What this asks you to trust, in plain words:

- A package from this repository is installed as root, so whoever holds the signing key could push code to every system that uses
  it. The key (ed25519) is kept by the author on an encrypted disk, protected by a password; it is not on any server. It is a
  single key, not a hardware token.
- GitHub Pages only serves public files. The index files (`Release`, `InRelease`) are signed; `apt` rejects anything that does not
  verify. A published version is never changed: a fix is a new version.
- Every package is also published as an immutable release of this project, with its SHA-256, so you can compare.
- If the key were ever lost or stolen: what happens and what you do is written in [APT-REPOSITORY.md](APT-REPOSITORY.md).

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
