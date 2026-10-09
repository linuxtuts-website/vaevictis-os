# VaeVictis OS

A hardened **Debian 13 (trixie)** desktop for people who want to switch to Linux and keep their data safe.
Live USB, graphical desktop (GNOME), disk-encrypting installer. Free, open, and honest about what it does and does not do.

**Status: 1.0.** Download page: <https://linuxtuts.online/vaevictis/vaevictis.html>

## Download and verify

Get the ISO, `SHA256SUMS` and (when published) `SHA256SUMS.asc` from the download page, then:

```bash
sha256sum -c SHA256SUMS                  # must print: OK
gpg --verify SHA256SUMS.asc SHA256SUMS   # must say: Good signature (once you imported the release key)
```

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
  It also asks for your keyboard layout and whether to use the hardened boot options.
- **Disk encryption (cryptsetup, LUKS2)** on the root and `/home` partitions, random-key encrypted swap, one passphrase typed at boot.
  `/boot` stays unencrypted so GRUB can start: see the [threat model](THREAT-MODEL.md).
- **Firewall (nftables):** incoming traffic dropped (SSH only if you switch it on), forwarding dropped except for virtual machines
  (libvirt), outgoing traffic **not blocked**. `sudo nft list ruleset` shows exactly what is active.
- **Nothing listens by default.** SSH is installed and hardened (port 2299, keys only, no root, only the `sshusers` group, fail2ban)
  but switched off. fail2ban watches it once enabled.
- **Hardened kernel settings** (`vv-secure`): hidden kernel pointers, restricted `dmesg`/BPF/ptrace, no core dumps, protected
  links and FIFOs. Hardened boot options (memory wiped on allocation and free, `slab_nomerge`, IPv6 off...) are on in the live
  session and offered by the installer (default: yes). A "compatibility" live boot entry switches the extra hardening off if your
  hardware has trouble.
- **AppArmor**, CPU microcode, **automatic security updates** from Debian.
- **HIDS** (`build/hids.go`): a small file-integrity monitor written in Go with the standard library only. It watches programs, services,
  startup files, account files, SSH keys and `/boot` in real time (inotify), re-checks everything at random intervals, alerts on
  any real change (content, mode, owner, new SETUID files) and on its own being stopped. Popups come from a script that runs in
  your own session; the root daemon never talks to your desktop. It is a tripwire, not a guarantee: see the threat model.
  **It has a deliberately neutral name:** the service is `sysctl-helper.service` and the program `/usr/libexec/systemd-sysctl-helper`,
  so that an intruder does not see "hids" at a glance. It is **not part of systemd**: it is this project's program, built from
  `build/hids.go`, and the HIDS Security app shows its real state. It writes only a local log
  (`/var/log/hids.log`) and sends nothing anywhere. Use it only on systems that are yours, or where you are authorised to monitor.
- **VPN manager** (`vv-vpn`): WireGuard front-end with a kill switch and IPv6-aware configs. Works with any WireGuard
  `.conf` (tested with ProtonVPN files).
- **Tools:** KeePassXC (offline password manager), mat2 (metadata cleaner), Panic Mode (cut the network and power off), Lynis,
  uBlock Origin preinstalled in Firefox ESR, an optional NVIDIA proprietary driver installer (`vv-nvidia`).
- **Simple desktop apps for people coming from Windows or macOS**, so you do not need to learn heavyweight tools on day one: **Aurora** (music player), **LinPaint+** (a Paint-style editor that also takes screenshots you can edit right away), **VaeVictis PDF** (`vv-pdf`: PDF viewer and page editor) and **VaeVictis XML** (`vv-xml`: small XML editor). Aurora, `vv-pdf` and `vv-xml` use no network at all.
- **Snapshots without Timeshift** (`v-snap`): a small menu-driven tool using rsync and hard links. It takes a snapshot of the whole
  system (without `/home`) or backs up any folder, keeps the snapshots on the system disk or on an external disk or USB stick, and only
  changed files use new space. List, restore and delete from the same menu. Run it with `sudo v-snap`.
- The **Welcome window** shows these settings read live from the running system, so you do not have to trust this page.

## What it does NOT do

- It is **not an anonymity system** like Tails: no Tor, your provider sees your traffic unless you use a VPN you trust.
- **No Secure Boot** support yet; **`/boot` is not encrypted**, so someone with physical access can tamper with it.
- Panic Mode is **not a secure erase**: it cuts the network and powers off; RAM is not wiped.
- HIDS **detects** changes; it cannot prove that nothing happened, and a root attacker who knows about it can disable it.
- No persistence in the live session. The proprietary NVIDIA driver is not included (optional script).

## Network activity

No telemetry, no analytics. The only automatic connections are the daily check for Debian security updates, time sync, and whatever
the programs you start do (Firefox ESR follows its own settings). Verify with `sudo nft list ruleset` and `ss -tulpn`.

## Build it yourself

Everything that makes the ISO is in `build/`, in plain shell and Python, readable top to bottom. See [docs/BUILDING.md](docs/BUILDING.md).
`vv-verify-iso` checks a finished image before you publish it, and `vv-release` refuses to produce a release if anything personal
(keys, history, users, VPN configs) is still inside.

## Repository layout

| Path | What |
|---|---|
| `build/` | the `vv-*` tools, installer, HIDS, desktop files: all that goes into the image (keep the files together: scripts find each other next to themselves) |
| `docs/` | build guide |
| `THREAT-MODEL.md` | what it protects against, and what it does not |
| `SECURITY.md` | how to report a vulnerability |
| `CHANGELOG.md` | release notes |

## How it is made

VaeVictis is a one-person project. The maintainer is not a professional programmer: much of the code was written with the help of AI assistants under his direction: the first versions of the desktop apps (Aurora, LinPaint+) were generated with **Gemini (Google)**; the installer, the `vv-*` tools, the HIDS and the optimisation of the apps were done with **Claude (Anthropic)**. Every release is tested on virtual and real machines (including complete LUKS installs), and the build is scripted and public. Nobody has independently audited the code yet. If you can read shell, Python or Go, a review is very welcome (see [SECURITY.md](SECURITY.md) to report problems privately).

## Warranty and licence

Provided **as is, without warranty**. Try it in a virtual machine or from the USB stick first. **The installer erases the disk or
partitions you select: back up your data first.**

The VaeVictis scripts and programs in this repository are released under the **GNU General Public License v3.0 or later** (see `LICENSE`).
The system is made of Debian packages, each under its own licence (see `/usr/share/doc/*/copyright` inside the ISO).
Artwork (logo, wallpaper) is not covered by the GPL unless stated: please ask before reusing it.

## Free, and staying free

No paid version, no paid support. Donations, if you want to give any, are voluntary and buy no support, features or priority.
