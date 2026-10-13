# Building VaeVictis OS

The image is built from a Debian 13 (trixie) root filesystem kept in a folder (a *chroot*) and turned into a hybrid BIOS + UEFI live ISO.
Every step is a small script in `build/`: read it before you run it. The scripts find each other next to themselves, so keep the
files of `build/` together in one folder and run them from there.

> The chroot path defaults to the author's disk. Set your own once per terminal:
> `export VV_CHROOT=/path/to/chroot`

## You need

A Debian or Ubuntu machine with: `debootstrap`, `squashfs-tools`, `xorriso`, `mtools`, `grub-common`, `grub-pc-bin`,
`grub-efi-amd64-bin`, `dpkg-dev` (for `dpkg-deb`), `apt-utils` (for `apt-ftparchive`, publishing only), and for testing
`qemu-system-x86`, `ovmf`. About 25 GB free. Run as a normal user with `sudo`.

## Steps

1. **Create the base system.**
   `sudo debootstrap --arch=amd64 trixie "$VV_CHROOT" http://deb.debian.org/debian`
   then install the desktop and tools. `./vv-chroot pkgcheck` reports what a fully working desktop still lacks
   (fonts, codecs, firmware, packages the tools need); install what it lists with `./vv-chroot run apt-get install ...`.
2. **Audit.** `./vv-chroot audit` is a read-only report of what still needs fixing.
3. **Apply the project's settings** (each is safe to repeat; replaced files are backed up outside the image):
   - packages the 1.1 programs need: `./vv-chroot run apt-get install bubblewrap xdg-dbus-proxy xdg-user-dirs plymouth plymouth-label fonts-ibm-plex`
   - the Debian packages of this repository, from the repository root: `packaging/aurora/build.sh` and
     `packaging/archive-keyring/build.sh` (they write `dist/`)
   - `./vv-secure`: kernel and system hardening, panic button, `vv-grub-password`
   - `./vv-harden`: nftables firewall, hardened sshd (switched off), fail2ban
   - `./vv-apps [--apt-repo]`: every VaeVictis program, its launchers and its sandbox (see below); with `--apt-repo` also the
     APT repository (only when the conditions at the top of `vv-apps` hold: two-factor login on GitHub and Cloudflare, a signed
     index with an expiry date)
   - `./vv-branding`: icons, Welcome window, login screen, system identity (it also removes what 1.0 builds had of the HIDS)
   - `./vv-boot-theme`: the GRUB menu and the Plymouth boot screen (it rebuilds the chroot's initramfs)
   - optional: `vv-nvidia` is installed by `vv-apps`; it is run by the user on the installed system
4. **Replace the personal user with the live user.** `./vv-liveuser` shows the plan, `./vv-liveuser --apply` does it.
5. **Seal the chroot.** `./vv-chroot seal` removes machine-id, SSH host keys, shell history, logs and other leftovers.
6. **Build.** `./vv-iso build --release` (xz, smaller; refuses an unsealed chroot). Faster test build: `./vv-iso build`.
7. **Verify.** `./vv-verify-iso iso-out/vaevictis-DATE.iso` mounts the ISO read-only and checks structure, exact file sizes of
   the files changed in this build, packages, boot options, and that nothing personal is inside. It prints the SHA-256.
8. **Test in a VM.** `./vv-iso run-uefi` (or `run` for BIOS). To try the installer on a blank virtual disk:
   `./vv-iso disk 40G && ./vv-iso install uefi`, then `./vv-iso boot uefi` to start the installed system.
   The tests in `tests/` run on any Linux machine (see `tests/README.md`).
9. **Release.** `./vv-release VERSION [--sign --key FINGERPRINT]` refuses to continue if anything personal is still in the chroot, then writes
   `release/VERSION/` with the ISO, `SHA256SUMS` (+ GPG signature with `--sign`), CycloneDX SBOM, `PACKAGES.txt`, `SOURCES.txt`,
   `grub.cfg.txt` (the exact boot options) and `BUILD-INFO.txt`.

## Custom desktop applications

`./vv-apps` installs them from this repository, nothing is copied by hand:

| What | Where in the image |
|---|---|
| Aurora | the package `vaevictis-aurora` (`/usr/bin/aurora`), built by `packaging/aurora/build.sh` |
| VaeVictis PDF, LinPaint+ | `/usr/local/lib/vaevictis/vv-pdf`, `/usr/local/lib/vaevictis/linpaint` (from `vv-pdf.py`, `linpaint.py`) |
| their commands | `/usr/local/bin/aurora`, `vv-pdf`, `linpaint`: three-line scripts that always start the program through `vv-sandbox` |
| the sandbox | `/usr/local/libexec/vv-sandbox` (bubblewrap + xdg-dbus-proxy): see the comment at its top for what each program may do |
| v-snap, VPN manager, installer, vv-nvidia | `/usr/local/bin`, `/usr/local/libexec`, `/usr/local/sbin`, with their menu launchers and the desktop launchers of new users |
| apt | `/etc/apt/apt.conf.d/99-vaevictis-no-bloat` (no recommended or suggested packages) |

The libraries each program needs are the `import` lines at the top of its file; `vv-apps` checks that they import in the chroot.
`VV_NO_SANDBOX=1 vv-pdf` starts a program without its sandbox, only to find out whether the sandbox is what breaks it.

## Publishing packages

`build/vv-apt-publish --repo PATH-TO/vaevictis-apt --key 0A41158C1DD6718D3D3FFED068486B39B2A99993 dist/*.deb` adds the packages
(only `vaevictis-*`, a published version is never replaced), signs the index with an expiry date (30 days by default) and checks the
signatures with the published key. It never commits or pushes. **Re-sign before the expiry date** (the same command without
packages), otherwise every VaeVictis system reports the repository as expired. Procedures: [APT-REPOSITORY.md](APT-REPOSITORY.md).

## Writing the image to a USB stick

`./vv-usb /dev/sdX [ISO]` writes the newest ISO and checks the result. It refuses anything that is not a whole disk, a disk holding
a mounted system folder or LUKS, or a disk smaller than the image, shows what is on the disk, and asks you to type the device name.

## Reproducibility

The ISO is not bit-for-bit reproducible yet (timestamps, `apt` state at build time). What is published instead: the full package list with
versions (`PACKAGES.txt`), a CycloneDX SBOM with the hashes of our own programs, the exact boot options, and the build date.
