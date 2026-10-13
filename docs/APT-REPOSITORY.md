# The VaeVictis APT repository: how it is kept safe

<https://apt.linuxtuts.online/> (files: [`vaevictis-apt`](https://github.com/linuxtuts-website/vaevictis-apt)) delivers the
VaeVictis programs as Debian packages. From release 1.1 the image trusts it by default, through the package
`vaevictis-archive-keyring`. Whoever can publish there can run code as root on every VaeVictis system that updates, so the
rules below are not optional.

## What protects users

| Protection | What it does |
|---|---|
| Signed index | `InRelease` / `Release.gpg` are signed by the archive key. `apt` refuses anything else. |
| Key used only for this source | `Signed-By: /usr/share/keyrings/vaevictis-archive-keyring.gpg`: the key is valid for this repository only, never for Debian's. |
| Pin to `vaevictis-*` | `/etc/apt/preferences.d/vaevictis`: from this site only packages named `vaevictis-*` can be installed. A "newer" copy of a Debian package offered by it gets priority -1 and is never chosen. |
| Expiry date | The signed index carries `Valid-Until` (30 days). Nobody can keep serving an old signed index to hide a fixed package: after the date `apt` reports the repository as expired and ignores it. |
| Never replaced | `vv-apt-publish` refuses a different file under an already published name and version: a fix is always a new version. |
| Offline release check | `vv-release` signs `SHA256SUMS` with one named key and checks it with the exported public key alone. |

Not automatic: VaeVictis packages are updated by `apt upgrade` (or GNOME Software), not by unattended-upgrades, which
installs only Debian security updates.

## Requirements for the maintainer (before every publication)

1. **Two-factor login** on the GitHub account and on the Cloudflare account (DNS of `linuxtuts.online`). Without it,
   `vv-apps --apt-repo` must not be used: a stolen password would be enough to change the site or the DNS.
2. **The secret key** stays on the maintainer's computer, protected by a passphrase, never in the repository, in GitHub
   secrets or in CI. Best: the primary key (certification only) offline on a USB stick, only the signing subkey on the PC.
3. **A revocation certificate** made once and kept offline: `gpg --output revoke-vaevictis.asc --gen-revoke 0A41158C1DD6718D3D3FFED068486B39B2A99993`
   (gpg also keeps one in `~/.gnupg/openpgp-revocs.d/`: copy it to the offline stick too).

## Publishing and re-signing

```
packaging/aurora/build.sh                       # or the package you changed
build/vv-apt-publish --repo ~/vaevictis-apt --key 0A41158C1DD6718D3D3FFED068486B39B2A99993 dist/vaevictis-aurora_X_all.deb
git -C ~/vaevictis-apt status                   # check, then commit and push yourself
```

**Re-sign before `Valid-Until`** (the script prints the date): the same command **without packages**, then commit and push.
If the date passes, systems show "Release file ... is expired" for this repository only; Debian's updates keep working,
and everything is fine again at the next re-signing.

## Dates to remember

| When | What |
|---|---|
| every < 30 days | re-sign the index (`vv-apt-publish` without packages) |
| before 2028-10-09 | the signing subkey `AEAB52A05F132CF78D85364486DF1E428F666F06` expires: extend it (`gpg --quick-set-expire 0A41158C1DD6718D3D3FFED068486B39B2A99993 2y AEAB52A05F132CF78D85364486DF1E428F666F06`), update `packaging/archive-keyring/vaevictis-archive-keyring.asc` and the repository's `vaevictis-archive-keyring.gpg`/`.asc`, publish a new `vaevictis-archive-keyring` version (it reaches every system with the next update), **then** sign with the extended key |
| before 2031-10-09 | the primary key expires: extend it the same way |

## If the key, the GitHub account or the Cloudflare account may be compromised

1. **Stop publishing.** Do not push anything to `vaevictis-apt` until it is clear what happened.
2. **Tell users at once** (GitHub Security Advisory on `vaevictis-os`, the site, the README of `vaevictis-apt`), with the
   one command that stops trusting the repository: `sudo apt purge vaevictis-archive-keyring` (1.1 and later), or, on a
   system where it was added by hand: `sudo rm /etc/apt/sources.list.d/vaevictis.sources /etc/apt/keyrings/vaevictis.gpg`.
3. **Secure the accounts**: change the passwords, check the two-factor settings, the SSH and deploy keys, the personal access
   tokens and the authorized applications of GitHub; the API tokens, members and DNS records of Cloudflare.
4. **Revoke the key**: import the revocation certificate (`gpg --import revoke-vaevictis.asc`) and publish the revoked public
   key in place of the old one. `apt` does not ask keyservers: revocation only reaches systems through step 2 and step 5.
5. **New key**: create it, put its fingerprint in `vv-apt-publish`, `packaging/archive-keyring/build.sh` and this document,
   publish it through several channels (site, GitHub, README), and tell users how to install the new
   `vaevictis-archive-keyring` by hand after checking its SHA-256 against those channels.
6. **Check what was published** while the key was not safe: every package version in `pool/` against the GitHub release
   assets and their SHA-256; anything that does not match is announced in the advisory.
