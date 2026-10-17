# Changelog

## 1.2 (not released yet)

Fixes found with AI-assisted reviews of the code (Lumo 2.0 Max by Proton, Argon by Google), each one checked against the
code and, where possible, with a test. This is **not an independent security audit**: AI reviews miss problems and report
problems that do not exist. Systems installed from 1.1 get these fixes as the package **`vaevictis-tools`** from the
VaeVictis APT repository (`sudo apt update && sudo apt full-upgrade`).

- **Sandbox (`vv-sandbox`):** only regular files given as arguments, checked after following links; a file reached through a
  link is made visible alone and read-only; hidden files, files in hidden folders and in `~/bin` are read-only; nothing of
  `/run` (except `/run/media`), `/proc`, `/sys` or `/dev`; never a folder. In 1.1, a crafted link opened with one of the three
  programs could make `~/.bashrc`, the whole home folder or the session's runtime folder writable inside the sandbox.
  Secrets moved elsewhere behind a link are now hidden at their real place.
- **VPN:** `Table` other than `auto` and `FwMark` are refused (with `Table = off` the tunnel showed as connected while the
  traffic left outside it, when the kill switch was off); every `[Peer]` needs an `Endpoint`; the password is asked at every
  action (it was kept for about five minutes, during which any program of the session could switch the kill switch off);
  disconnecting a tunnel never releases the kill switch of another one; the kill switch flag is readable by root only.
- **Installer:** refuses to finish if an account of the live session is still there; no separate partition for anything
  under `/usr`, nor for `/var`, `/var/lib` or APT's state.
- **v-snap:** refuses a system snapshot or restore when `/usr`, `/usr/local`, `/var` or `/var/lib` are separate partitions (the
  snapshot would leave them out); never copies or deletes another snapshot store.
- **Panic button, VPN manager:** the commands they run are taken only from the system folders.
- **Packages:** new `vaevictis-tools` 1.2.0; `vaevictis-aurora` 1.1.2 depends on it (the player is unchanged).

## 1.1 (2026-10-16)

Systems installed from 1.0 still need the [2026-10-12 security notice](docs/SECURITY-NOTICE-2026-10-12.md);
what else of 1.1 they can apply (removing the HIDS, the APT repository, two kernel settings): [docs/FROM-1.0.md](docs/FROM-1.0.md).

- **HIDS removed.** The file-integrity daemon was the largest piece of this project's code always running as root; the
  protections below replace it. `vv-branding` removes it from older build trees.
- **Boot menu password (GRUB)**, always set by the installer: starting needs none; editing the start options or the GRUB console
  needs user `grub` and that password (PBKDF2, 210000 rounds), which must differ from the other passwords and use only keys
  that GRUB's US keyboard reads the same. `sudo vv-grub-password` changes it.
- **New boot screens** (style A, minimal, violet): GRUB menu with the logo, and a Plymouth screen with a thin progress bar and the
  disk passphrase box (any length, the keyboard in use, error messages shown). `Esc` still shows every boot message. The
  password prompt, the editor and the start messages of GRUB stay black (no leftover picture behind them). New wallpaper in the
  same style, the default for desktop and lock screen (every user can choose another one).
- **Installer:** free space shown before every size question and each size checked; the root partition must hold the system;
  whole disks only; mount points checked; the live session switches to your keyboard layout and a typing test, with its reason
  explained, checks it;
  SSD TRIM before partitioning; `/boot` and EFI `nosuid,nodev,noexec`, `/home` and data partitions `nosuid,nodev`; the disk
  passphrase is cleared from memory after use; no "Install" launcher on installed systems.
- **Sandbox for the programs that open files from anywhere:** Aurora, LinPaint+ and VaeVictis PDF run in bubblewrap with no
  network, a read-only system and home (except the data folders, their settings and the opened file's folder), hidden keys and
  browser profiles, filtered D-Bus.
- **VPN with least privilege:** configs read with a whitelist (commands refused at import and at connect); WireGuard runs in a
  systemd sandbox with only `CAP_NET_ADMIN` and a read-only system; the helper sets DNS itself. **Kill switch:** designed to also block
  virtual machines (forward chain) and to stay on during a reconnect and after a failed one; no DNS lookup while it blocks.
- **v-snap:** snapshots only on encrypted disks (or the system disk of an unencrypted system), in a root-only folder pinned with
  a private bind mount; system snapshots include the kernels in `/boot`, and a restore puts back matching kernels and runs
  `update-grub`; a 1.0 snapshot is restored only if it has the modules of the installed kernels.
- **Programs:** VaeVictis PDF keeps the password of a protected PDF in extracted and split files, warns before exporting a
  protected page as PNG and caps its size; dialogs show plain text. Aurora 1.1.1: song tags escaped, single-instance socket file,
  works with a read-only home. LinPaint+: Copy really copies to the clipboard; licence shown as GPL. Panic: the passwordless rule
  is limited to administrators (`%sudo`).
- **Kernel:** `dev.tty.legacy_tiocsti=0` (no typing into other terminals), `kernel.io_uring_disabled=2`.
- **APT repository trusted by default, with limits:** package `vaevictis-archive-keyring` (key for this source only, a pin that
  allows only `vaevictis-*` packages from it), index signed with an expiry date (`vv-apt-publish`), procedures in
  [docs/APT-REPOSITORY.md](docs/APT-REPOSITORY.md).
- **Signed release:** `SHA256SUMS.asc`, signed with the key of the APT repository (`0A41 158C 1DD6 718D 3D3F  FED0 6848 6B39 B2A9 9993`).
- **Build:** every VaeVictis file in the image now comes from a script (`vv-apps`, `vv-boot-theme`); `vv-verify-iso` compares
  them byte for byte with the repository; `vv-release --key` signs with one named key and checks it; `vv-usb` reads the stick
  back without the page cache; tests in `tests/`. Links point to vaevictisos.org.

## 1.0.1 (2026-10-12): security release

Fixes found in an audit of the VaeVictis code. Systems installed from 1.0 need the four commands of the
[security notice](docs/SECURITY-NOTICE-2026-10-12.md); the 1.0.1 installer does all of it by itself.
- **Installer:** removes the polkit rule that the live session writes for its user (`user`): copied into an installed system it
  gave administrator rights without a password to a user with that name. The installer refuses to finish if such a rule is left.
- **Installer:** no longer adds the user to the `libvirt` group (administrator-equivalent without a password); virt-manager asks
  for the password instead.
- **Image and installer:** root is locked with no password hash at all (1.0 kept a locked hash from the build system); every
  installed system creates its own `ssl-cert-snakeoil` TLS key; `/root` is emptied (build caches and an obsolete script).
- **HIDS 2.1.1:** file names with control characters can no longer forge lines in the log or break the dashboard.
- **Debian security updates** included in the image: ghostscript, xz-utils/liblzma.
- **Build:** `vv-chroot seal`, `vv-release` and `vv-verify-iso` check all of the above, so it cannot come back unnoticed.
- `vv-panic-action` (the root part of the panic button) and the shipped version of VaeVictis PDF are now in the repository too.

## APT repository (2026-10-10)

A signed APT repository at <https://apt.linuxtuts.online/> (files: [`vaevictis-apt`](https://github.com/linuxtuts-website/vaevictis-apt)),
so that `apt upgrade` can update the VaeVictis programs. It is not enabled by default: you add it yourself.
- Holds `vaevictis-aurora` 1.1.0, byte for byte the file of the `aurora-v1.1.0` release (same SHA-256).
- Index files signed with an ed25519 key, fingerprint `0A41 158C 1DD6 718D 3D3F  FED0 6848 6B39 B2A9 9993`. The private key stays on
  the author's encrypted disk, not on any server. Checked with `apt` on Debian 13: valid signature accepted, altered index or
  signature rejected.
- Hosted on GitHub Pages; a published package version is never changed.

## Aurora 1.1.0 (2026-10-10)

A release of its own (`aurora-v1.1.0`): the first VaeVictis program shipped as a Debian package (`vaevictis-aurora`). It is
**not** in the 1.0 ISO, which carries the first version of Aurora.
- The spectrum analyses the audio that is playing (it used random numbers before): full-width strip, 64 bands, frequency
  read-out when you hover a bar.
- Sharper text (real bold instead of weight 600, better contrast).
- `QT_QPA_PLATFORM` can be set from the shell (for example `xcb`) to test X11.
- `.deb` built from the repository with `packaging/aurora/build.sh`; it replaces a hand-copied `/usr/local/bin/aurora`.

## 1.0 (2026-10-09)

First public release. Debian 13 (trixie), kernel 6.12, GNOME. Hybrid BIOS + UEFI live ISO (Secure Boot not supported).

**Installer**
- LUKS2 disk encryption (root, optional separate `/home`), encrypted swap with a random key, `/boot` unencrypted.
- Shows what is on the disk before it erases anything; saves the firmware boot list before and after; stops with the failing
  command and line if something goes wrong; refuses to finish if an automatic or timed login is left active.

**Security**
- nftables: input drop, forward drop (virtual machines only), output not blocked.
- Hardened sshd and fail2ban, switched off by default (port 2299, keys only).
- Kernel and sysctl hardening, hardened boot options (live and installer), IPv6 off by default.
- HIDS 2.1: real-time file-integrity tripwire (inotify, standard library only), watches programs, services, cron, PAM, shell
  startup files, SSH keys and `/boot`; alerts on content, mode or owner change and on new SETUID files; random-interval full
  re-check; warns when the watcher stops; popups through `hids-notify` in the user's session; sandboxed systemd unit.
- VPN manager: WireGuard front-end with a kill switch; configs with IPv6 work on systems where IPv6 is off.
- uBlock Origin installed for Firefox ESR; KeePassXC, mat2, Panic Mode, Lynis, hard-link snapshots (`v-snap`).

**Look and boot**
- VaeVictis wallpaper, GRUB theme with cyan menu entries on the live ISO and the installed system, loading messages shown
  directly on the wallpaper, boot messages visible (no `quiet`).

**Build tools**
- `vv-iso`, `vv-chroot`, `vv-secure`, `vv-harden`, `vv-branding`, `vv-hids`, `vv-liveuser`, `vv-verify-iso`, `vv-release`, `vv-usb`.

**Known limits**
- No Secure Boot; `/boot` not encrypted; not an anonymity system; Panic Mode is not a secure erase; the proprietary NVIDIA
  driver is optional (`vv-nvidia`). See [THREAT-MODEL.md](THREAT-MODEL.md).
