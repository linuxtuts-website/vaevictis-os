# Threat model

VaeVictis OS is a **hardened everyday desktop**, not an anonymity or anti-forensics system. This page says what it is meant to
protect against, what it is not, and which parts you have to trust.

## Who it is for

A person leaving Windows or macOS who wants a desktop that is safe by default: no open ports, encrypted disk, automatic security
updates, no telemetry, and a few honest tools (VPN, password manager, snapshots).

## What it protects against

| Threat | How |
|---|---|
| Remote attackers scanning the internet | Nothing listens by default; incoming traffic is dropped; SSH off (and hardened + fail2ban if you turn it on) |
| Your laptop is lost or stolen while powered off | LUKS2 on root and `/home`, encrypted swap, if you chose encryption in the installer |
| A malicious PDF, song or image | Aurora, LinPaint+ and VaeVictis PDF run in a sandbox: no network, system and home read-only except the data folders, keys and browser profiles hidden, D-Bus filtered |
| Someone at the keyboard changing the start options to skip the login | GRUB password: starting needs none, editing the entries or the GRUB console does |
| Memory-corruption exploitation | `init_on_alloc`/`init_on_free`, `slab_nomerge`, `randomize_kstack_offset`, `vsyscall=none`, restricted `dmesg`, BPF, ptrace, kernel pointers |
| Network snooping on public Wi-Fi | WireGuard VPN manager; its kill switch blocks everything outside the tunnel, also for virtual machines and during a reconnect (you must trust the VPN provider) |
| A bug in the VPN tools turned against the system | Configs read with a whitelist (no commands); WireGuard runs in a systemd sandbox with only `CAP_NET_ADMIN` and a read-only system |
| Known bugs in installed software | Automatic security updates from Debian; VaeVictis packages from a signed repository whose index expires, pinned to `vaevictis-*` names only |
| Metadata leaks in documents you share | mat2 |

## What it does NOT protect against

- **Targeted or state-level attackers.** No claim is made against them.
- **Anonymity.** No Tor, no traffic shaping. Your VPN provider (or ISP) sees your traffic.
- **Physical access to a running or sleeping machine** (cold-boot memory attacks, DMA).
- **Tampering with `/boot` while the machine is off.** `/boot` is unencrypted so GRUB can start, and Secure Boot is not
  supported, so an "evil maid" who can start the computer from another disk can replace the kernel or initramfs, or the GRUB
  configuration with its password. The GRUB password stops changes made at the boot menu only. A firmware (BIOS/UEFI) password
  and no booting from USB make the attack much harder.
- **A malicious or compromised root**, or malware running as your user that waits for you to type your password.
- **Programs outside the sandbox** (LibreOffice, and anything you install yourself) opening malicious files; inside the sandbox a
  malicious file can still change files in your data folders.
- **Malicious firmware**, hardware implants, or a compromised Debian archive.
- **Browser fingerprinting and web tracking** beyond uBlock Origin.

## Removed in 1.1: the HIDS

1.0 and 1.0.1 shipped a file-integrity monitor (HIDS) running as root. It was removed in 1.1: it was the largest piece of this
project's own code always running with full privileges, and a tripwire that a root attacker can switch off adds little against the
threats above. The sandbox, the GRUB password and the least-privilege VPN replace it with protections that do not depend on noticing
an intrusion after the fact.

## Things you must trust

- Debian and its archive signatures.
- The VaeVictis scripts in this repository (small, readable, GPL) and the way the ISO was built: verify your download with the
  published SHA-256 and GPG signature, and compare the package list (`PACKAGES.txt`, SBOM) published with each release.
- Your VPN provider, if you use one.
- The VaeVictis APT repository (preconfigured from 1.1): its signing key and the maintainer's GitHub and Cloudflare accounts,
  protected by two-factor login. A pin limits it to packages named `vaevictis-*`; see [docs/APT-REPOSITORY.md](docs/APT-REPOSITORY.md)
  for what happens if the key or an account is compromised.

## Defaults that are public on purpose

- Live session: user `user`, password `live`, passwordless `sudo`. Valid only in the live session; the installed system has none of it (since 1.0.1: systems installed from 1.0 need the
  [2026-10-12 security notice](docs/SECURITY-NOTICE-2026-10-12.md)).
- The firewall allows all outgoing traffic. This is deliberate: blocking outgoing ports by default breaks normal use and gives
  a false sense of safety. If you need an egress policy, edit `/etc/nftables.conf`.

## Reporting a problem

See [SECURITY.md](SECURITY.md).
