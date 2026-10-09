# Threat model

VaeVictis OS is a **hardened everyday desktop**, not an anonymity or anti-forensics system. This page says what it is meant to
protect against, what it is not, and which parts you have to trust.

## Who it is for

A person leaving Windows or macOS who wants a desktop that is safe by default: no open ports, encrypted disk, automatic security
updates, no telemetry, and a few honest tools (VPN, password manager, change detection).

## What it protects against

| Threat | How |
|---|---|
| Remote attackers scanning the internet | Nothing listens by default; incoming traffic is dropped; SSH off (and hardened + fail2ban if you turn it on) |
| Your laptop is lost or stolen while powered off | LUKS2 on root and `/home`, encrypted swap, if you chose encryption in the installer |
| Common malware dropping files or persistence | HIDS tripwire watches programs, services, cron, PAM, shell startup files, SSH keys, `/boot`; a change raises an alert |
| Memory-corruption exploitation | `init_on_alloc`/`init_on_free`, `slab_nomerge`, `randomize_kstack_offset`, `vsyscall=none`, restricted `dmesg`, BPF, ptrace, kernel pointers |
| Network snooping on public Wi-Fi | WireGuard VPN manager with a kill switch (you must trust the VPN provider) |
| Known bugs in installed software | Automatic security updates from Debian |
| Metadata leaks in documents you share | mat2 |

## What it does NOT protect against

- **Targeted or state-level attackers.** No claim is made against them.
- **Anonymity.** No Tor, no traffic shaping. Your VPN provider (or ISP) sees your traffic.
- **Physical access to a running or sleeping machine** (cold-boot memory attacks, DMA).
- **Tampering with `/boot` while the machine is off.** `/boot` is unencrypted so GRUB can start, and Secure Boot is not
  supported, so an "evil maid" can replace the kernel or initramfs. HIDS can notice it only on the next boot, from the system it
  protects.
- **A malicious or compromised root.** HIDS lives on the machine it watches.
- **Malicious firmware**, hardware implants, or a compromised Debian archive.
- **Browser fingerprinting and web tracking** beyond uBlock Origin.

## HIDS: what it is and what it is not

HIDS is a **tripwire**: it assumes the intruder does not know it is there. The first change to a watched file is logged and shown
as a popup. It has no cron job and no fixed schedule (real-time inotify plus a full check at random intervals of 1 to 3 hours), and
it tells you when the watcher itself is stopped. The baseline is taken on the first start of an installed system ("trust on
first use"), so it cannot tell you about a system that was already compromised before. It does **not** stop an attacker who is root,
knows it exists and disables it before changing anything. The source is public (`build/hids.go`), so this is not a secret: use it as an
alarm, not as a wall.

## Things you must trust

- Debian and its archive signatures.
- The VaeVictis scripts in this repository (small, readable, GPL) and the way the ISO was built: verify your download with the
  published SHA-256 and GPG signature, and compare the package list (`PACKAGES.txt`, SBOM) published with each release.
- Your VPN provider, if you use one.

## Defaults that are public on purpose

- Live session: user `user`, password `live`, passwordless `sudo`. Valid only in the live session; the installed system has none of it.
- The firewall allows all outgoing traffic. This is deliberate: blocking outgoing ports by default breaks normal use and gives
  a false sense of safety. If you need an egress policy, edit `/etc/nftables.conf`.

## Reporting a problem

See [SECURITY.md](SECURITY.md).
