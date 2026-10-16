# VaeVictis OS

A hardened **Debian 13 (trixie)** desktop for people who want to switch to Linux and protect their data better.
Live USB, graphical desktop (GNOME), disk-encrypting installer. Free, open, and honest about what it does and does not do.

**Status: 1.1.** Download page: <https://vaevictisos.org/>

> **No warranty.** VaeVictis OS is provided **as is, without warranty of any kind** (GPL-3.0, sections 15 and 16). Every
> protection described here is designed to reduce a risk; none of them is guaranteed to work in every case: software has bugs
> and new attacks appear. Read the [threat model](THREAT-MODEL.md), keep backups, and use it at your own risk.
> Full text, also in Italian: [DISCLAIMER.md](DISCLAIMER.md).

> **Installed 1.0? Run the four commands of the [2026-10-12 security notice](docs/SECURITY-NOTICE-2026-10-12.md)**
> (one minute, then log out and back in). Installs from the 1.0.1 or 1.1 ISO are not affected.
>
> **Coming from 1.0 or 1.0.1:** what of 1.1 you can apply yourself (removing the HIDS, the APT repository, two kernel
> settings) and what needs a new installation: [docs/FROM-1.0.md](docs/FROM-1.0.md).

## Download and verify

Get the ISO, `SHA256SUMS`, `SHA256SUMS.asc` and `vaevictis-release-key.asc` from the release, then:

```bash
sha256sum -c SHA256SUMS                          # must print: OK
gpg --show-keys vaevictis-release-key.asc        # the fingerprint must be 0A41158C1DD6718D3D3FFED068486B39B2A99993
gpg --import vaevictis-release-key.asc
gpg --verify SHA256SUMS.asc SHA256SUMS           # must say: Good signature from "VaeVictis OS Archive Signing Key"
```

The release key is the same key that signs the APT repository: `0A41 158C 1DD6 718D 3D3F  FED0 6848 6B39 B2A9 9993`. Compare
the fingerprint with the one on <https://vaevictisos.org> and in the [vaevictis-apt](https://github.com/linuxtuts-website/vaevictis-apt)
README, three places that would all have to be changed by an attacker. (Releases before 1.1 have only the `.sha256` file.)

Put it on a USB stick (4 GB or more, it will be erased). On Linux the repository has a guarded tool, `build/vv-usb`, that
refuses system disks and shows you what it is about to erase; `dd` and balenaEtcher work too.

Requirements: 64-bit PC (BIOS or UEFI), 4 GB RAM or more, 20 GB disk to install.
**Secure Boot is not supported yet** (the boot loader is not signed): switch it off in the firmware settings.

## The live session

You are logged in automatically as **`user`**, password **`live`**, with passwordless `sudo`. The password is public on purpose and
valid only in the live session. Nothing is saved to the USB stick. The installed system has **no autologin and no preset password**.

## What is inside

- **A small, original installer** (`vaevictis_install.sh`, plain shell, no heavy framework): it copies the live system to the disk with
  rsync. You choose the disk and design the layout yourself: size of `/`, optional separate `/home`, and any **extra mount points**
  (`/var`, `/srv`, a data partition...) each with the filesystem you want: **ext4, xfs or btrfs** (default ext4: light and fast).
  It shows the free space before every size question and checks each size against it (the root partition must hold the system).
  It accepts only a whole disk, switches the live session to your keyboard layout and checks it with a short typing test, tells an
  SSD to drop its old data (TRIM) before writing, and mounts `/boot` and EFI `nosuid,nodev,noexec`, `/home` and data partitions
  `nosuid,nodev`.
- **Disk encryption (cryptsetup, LUKS2)** on the root and `/home` partitions, random-key encrypted swap, one passphrase typed at boot
  (8 characters or more, no upper limit). `/boot` stays unencrypted so GRUB can start: see the [threat model](THREAT-MODEL.md).
- **Boot menu password (GRUB), always set by the installer:** VaeVictis starts normally without it; it is asked only to change the
  start options or open the GRUB console, which could otherwise skip your login. Username `grub`; change it with
  `sudo vv-grub-password`. It must differ from your other passwords (its hash is on the unencrypted `/boot`).
- **Boot screens:** a minimal GRUB menu and a Plymouth screen (logo, progress bar, the passphrase box with the keyboard in use).
  `Esc` shows every boot message, as before.
- **Firewall (nftables):** incoming traffic dropped (SSH only if you switch it on), forwarding dropped except for virtual machines
  (libvirt), outgoing traffic **not blocked**. `sudo nft list ruleset` shows exactly what is active.
- **Nothing listens by default.** SSH is installed and hardened (port 2299, keys only, no root, only the `sshusers` group, fail2ban)
  but switched off. fail2ban watches it once enabled.
- **Hardened kernel settings** (`vv-secure`): hidden kernel pointers, restricted `dmesg`/BPF/ptrace, no core dumps, protected
  links and FIFOs, no typing into other terminals (TIOCSTI), `io_uring` off. Hardened boot options (memory wiped on allocation and free, `slab_nomerge`, IPv6 off...) are on in the live
  session and offered by the installer (default: yes). A "compatibility" live boot entry switches the extra hardening off if your
  hardware has trouble.
- **AppArmor**, CPU microcode, **automatic security updates** from Debian.
- **The programs that open files from anywhere run in a sandbox** (`vv-sandbox`, bubblewrap, the isolation Flatpak uses): Aurora,
  LinPaint+ and VaeVictis PDF have **no network at all**, see the system and your home folder read-only (except your data folders,
  their own settings and the folder of the file you open), cannot see SSH or GPG keys, keyrings, password stores or browser profiles,
  and reach D-Bus only through a filter. A malicious PDF, song or image that exploited a bug in MuPDF, FFmpeg, Qt or Tk is meant to stay
  shut in there (a bug in the kernel or in bubblewrap itself could still let it out).
- **VPN manager** (`vv-vpn`): WireGuard front-end with a kill switch and IPv6-aware configs. Works with any plain WireGuard
  client `.conf` (tested with ProtonVPN files); configs with commands (`PostUp`...) are refused. Privileged steps ask for your
  password; WireGuard itself runs in a systemd sandbox that can only configure the network. With the **kill switch** on, the firewall is set to
  block the traffic of the PC and of its virtual machines outside the tunnel, also while it reconnects or if reconnecting fails.
- **Tools:** KeePassXC (offline password manager), mat2 (metadata cleaner), Panic Mode (cut the network and power off), Lynis,
  uBlock Origin preinstalled in Firefox ESR, an optional NVIDIA proprietary driver installer (`vv-nvidia`).
- **Virtual machines, built in:** QEMU/KVM, libvirt, `virt-manager`, and `virt-install` are preinstalled, so you can
  try other systems without installing anything. As a guest, the QEMU guest agent and the SPICE agent are included (clipboard sharing,
  window resizing).
- **A familiar desktop:** GNOME 48 with the **Dash to Dock** extension (a dock to start and switch apps) and the standard GNOME
  extensions, plus the usual GNOME apps (Files, Calendar, Maps, Weather, Disks, Text Editor and others).
- **The whole software list, from the image itself:** every release carries `PACKAGES.txt`, the name and version of each package in
  the ISO (1507 for 1.0), so you can read exactly what is installed before you boot it.
- **Simple desktop apps for people coming from Windows or macOS**, so you do not need to learn heavyweight tools on day one: **Aurora** (music player), **LinPaint+** (a Paint-style editor that also takes screenshots you can edit right away) and **VaeVictis PDF** (`vv-pdf`: PDF viewer and page editor), next to LibreOffice for documents. All three run in their sandbox, without network.
- **Snapshots without Timeshift** (`v-snap`): a small menu-driven tool using rsync and hard links. It takes a snapshot of the whole
  system (with the kernels in `/boot`, without `/home`) or backs up any folder, keeps the snapshots on the system disk or on an
  **encrypted** external disk (snapshots hold the system's secrets), and only changed files use new space. List, restore (it puts
  back the matching kernels and updates GRUB) and delete from the same menu. Run it with `sudo v-snap`.
- The **Welcome window** shows these settings read live from the running system, so you do not have to trust this page.

## Updating

Debian packages update with `apt`; security updates are installed automatically. You do not need a new ISO for that.
The VaeVictis programs are being packaged as `.deb` files one at a time and published in a **signed APT repository**,
<https://apt.linuxtuts.online/>, so that `apt upgrade` updates them too. From 1.1 it is **already configured** (package
`vaevictis-archive-keyring`), with three limits: the repository may provide **only packages named `vaevictis-*`** (a pin makes
apt ignore anything else it offered), its index is signed with the key `0A41 158C 1DD6 718D 3D3F  FED0 6848 6B39 B2A9 9993` and
**expires** if it is not re-signed (apt refuses an old index after its date). To stop trusting it: `sudo apt purge vaevictis-archive-keyring`.
Details, and how the key is protected and replaced: [docs/UPDATING.md](docs/UPDATING.md), [docs/APT-REPOSITORY.md](docs/APT-REPOSITORY.md).
From 1.0 or 1.0.1 to 1.1: [docs/FROM-1.0.md](docs/FROM-1.0.md).

## What it does NOT do

- It is **not an anonymity system** like Tails: no Tor, your provider sees your traffic unless you use a VPN you trust.
- **No Secure Boot** support yet; **`/boot` is not encrypted**, so someone who can start the computer from another disk can tamper
  with it (the GRUB password stops changes at the boot menu, not that). A firmware password and no booting from USB make it harder.
- Panic Mode is **not a secure erase**: it cuts the network and powers off; RAM is not wiped.
- The sandbox covers Aurora, LinPaint+ and VaeVictis PDF only: Firefox has its own, LibreOffice and other programs have none.
  Inside it, a malicious file can still change files in your data folders.
- No persistence in the live session. The proprietary NVIDIA driver is not included (optional script).

## Network activity

No telemetry, no analytics. The only automatic connections are the daily check for Debian security updates (and the VaeVictis
repository index), time sync, and whatever
the programs you start do (Firefox ESR follows its own settings). Verify with `sudo nft list ruleset` and `ss -tulpn`.

## Build it yourself

Everything that makes the ISO is in `build/`, in plain shell and Python, readable top to bottom. See [docs/BUILDING.md](docs/BUILDING.md).
`vv-verify-iso` checks a finished image before you publish it, and `vv-release` refuses to produce a release if anything personal
(keys, history, users, VPN configs) is still inside.

## Repository layout

| Path | What |
|---|---|
| `build/` | the `vv-*` tools, installer, programs, boot screens, desktop files: all that goes into the image (keep the files together: scripts find each other next to themselves) |
| `packaging/` | the Debian packages (`vaevictis-aurora`, `vaevictis-archive-keyring`) |
| `tests/` | tests that run on any Linux machine (VPN helper, kill switch, sandbox) |
| `docs/` | build guide, updating, coming from 1.0, APT repository procedures |
| `DISCLAIMER.md` | no warranty, limitation of liability, not for critical use (English and Italian) |
| `THREAT-MODEL.md` | what it is meant to protect against, and what it does not |
| `SECURITY.md` | how to report a vulnerability |
| `CHANGELOG.md` | release notes |

## How it is made

VaeVictis is a one-person project. The maintainer is not a professional programmer: much of the code was written with the help of AI assistants under his direction: the first versions of the desktop apps (Aurora, LinPaint+) were generated with **Gemini (Google)**; the installer, the `vv-*` tools, the optimisation and the hardening of the apps were done with **Claude (Anthropic)**. Releases are tested before publication (including a complete LUKS install in a virtual machine), and the build is scripted and public; testing finds some bugs, not all. Nobody has independently audited the code yet. If you can read shell or Python, a review is very welcome (see [SECURITY.md](SECURITY.md) to report problems privately).

## Warranty and licence

Provided **as is, without warranty of any kind**, express or implied, as the GPL-3.0 states (sections 15 and 16): the author is not
liable for damage, data loss or any security incident arising from its use. No protection described in this repository or on the
project's websites is guaranteed: see [DISCLAIMER.md](DISCLAIMER.md). Try it in a virtual machine or from the USB stick first. **The installer erases the disk or
partitions you select: back up your data first.**

The VaeVictis scripts and programs in this repository are released under the **GNU General Public License v3.0 or later** (see `LICENSE`).
The system is made of Debian packages, each under its own licence (see `/usr/share/doc/*/copyright` inside the ISO).
Artwork (logo, wallpaper) is not covered by the GPL unless stated: please ask before reusing it.

## Free, and staying free

No paid version, no paid support. Donations, if you want to give any, are voluntary and buy no support, features or priority.
