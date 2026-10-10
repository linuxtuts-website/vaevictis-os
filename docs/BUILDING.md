# Building VaeVictis OS

The image is built from a Debian 13 (trixie) root filesystem kept in a folder (a *chroot*) and turned into a hybrid BIOS + UEFI live ISO.
Every step is a small script in `build/`: read it before you run it. The scripts find each other next to themselves, so keep the
files of `build/` together in one folder and run them from there.

> The chroot path defaults to the author's disk. Set your own once per terminal:
> `export VV_CHROOT=/path/to/chroot`

## You need

A Debian or Ubuntu machine with: `debootstrap`, `squashfs-tools`, `xorriso`, `mtools`, `grub-common`, `grub-pc-bin`,
`grub-efi-amd64-bin`, and for testing `qemu-system-x86`, `ovmf`. About 25 GB free. Run as a normal user with `sudo`.
Go is installed inside the chroot only for the build of HIDS and purged afterwards.

## Steps

1. **Create the base system.**
   `sudo debootstrap --arch=amd64 trixie "$VV_CHROOT" http://deb.debian.org/debian`
   then install the desktop and tools. `./vv-chroot pkgcheck` reports what a fully working desktop still lacks
   (fonts, codecs, firmware, packages the tools need); install what it lists with `./vv-chroot run apt-get install ...`.
2. **Audit.** `./vv-chroot audit` is a read-only report of what still needs fixing.
3. **Apply the project's settings** (each is safe to repeat; replaced files are backed up outside the image):
   - `./vv-secure`: kernel and system hardening
   - `./vv-harden`: nftables firewall, hardened sshd (switched off), fail2ban
   - `./vv-branding`: icons, Welcome window, login screen, GRUB theme, system identity
   - `./vv-hids`: builds the HIDS inside the chroot and installs it with its dashboard, popups and service
   - the VPN manager (`inject-vv-vpn.sh`), `vv-nvidia` (optional driver script), the installer (`vaevictis_install.sh`)
   - the custom desktop applications (Aurora, LinPaint+, VaeVictis PDF): see [below](#custom-desktop-applications)
4. **Replace the personal user with the live user.** `./vv-liveuser` shows the plan, `./vv-liveuser --apply` does it.
5. **Seal the chroot.** `./vv-chroot seal` removes machine-id, SSH host keys, shell history, logs and other leftovers.
6. **Build.** `./vv-iso build --release` (xz, smaller; refuses an unsealed chroot). Faster test build: `./vv-iso build`.
7. **Verify.** `./vv-verify-iso iso-out/vaevictis-DATE.iso` mounts the ISO read-only and checks structure, exact file sizes of
   the files changed in this build, packages, boot options, and that nothing personal is inside. It prints the SHA-256.
8. **Test in a VM.** `./vv-iso run-uefi` (or `run` for BIOS). To try the installer on a blank virtual disk:
   `./vv-iso disk 40G && ./vv-iso install uefi`, then `./vv-iso boot uefi` to start the installed system.
9. **Release.** `./vv-release VERSION [--sign]` refuses to continue if anything personal is still in the chroot, then writes
   `release/VERSION/` with the ISO, `SHA256SUMS` (+ GPG signature with `--sign`), CycloneDX SBOM, `PACKAGES.txt`, `SOURCES.txt`,
   `grub.cfg.txt` (the exact boot options) and `BUILD-INFO.txt`.

## Custom desktop applications

Aurora (music player), LinPaint+ (image editor and screenshot tool) and VaeVictis PDF (`vv-pdf`) are single Python programs
kept in `build/`. They are **not installed by a script yet**: in the image they were copied into the chroot by hand, and this is
the exact result you must reproduce (as root, with the chroot's paths):

| What | Where in the image | Mode |
|---|---|---|
| the program | `/usr/local/bin/aurora`, `/usr/local/bin/linpaint`, `/usr/local/bin/vv-pdf` | `755` |
| the menu launchers | `/usr/share/applications/aurora.desktop`, `linpaint.desktop`, `vv-pdf.desktop` (and `vaevictis_install.desktop` for the installer) | `644` |
| the icons | `vv-aurora.svg`, `vv-linpaint.svg`, `vv-pdf.svg` in the `hicolor` icon theme (`/usr/share/icons/hicolor/`) | `644` |

The first line of each program is its interpreter (`#!/usr/bin/env python3`), so the file is copied under the command name
without the `.py` extension. The libraries each program needs are the `import` lines at the top of the file; install the matching
Debian packages in the chroot (for example `vv-pdf` uses PyMuPDF and PyQt6). Aurora and `vv-pdf` open no network connection at all.
After copying, run `./vv-chroot audit` again and, in the test VM, open each program once from the menu.

Scripting this step is on the to-do list.

## Writing the image to a USB stick

`./vv-usb /dev/sdX [ISO]` writes the newest ISO and checks the result. It refuses anything that is not a whole disk, a disk holding
a mounted system folder or LUKS, or a disk smaller than the image, shows what is on the disk, and asks you to type the device name.

## Reproducibility

The ISO is not bit-for-bit reproducible yet (timestamps, `apt` state at build time). What is published instead: the full package list with
versions (`PACKAGES.txt`), a CycloneDX SBOM with the hashes of our own programs, the exact boot options, and the build date.
