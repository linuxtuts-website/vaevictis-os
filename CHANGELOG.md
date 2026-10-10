# Changelog

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
