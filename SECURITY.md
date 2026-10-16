# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for a security problem.

Use GitHub's **private vulnerability reporting**: the "Report a vulnerability" button on the Security tab of this repository.

Please include: what you found, the VaeVictis version (`cat /etc/os-release` or the ISO file name), and steps to reproduce.
Please give a reasonable time to fix it before you publish. This is a one-person, best-effort project: there is no formal
response time, but reports are read and answered.

## Scope

In scope: the scripts and programs in this repository (installer, `vv-*` tools, VPN manager and its privileged helper, the
sandbox of the desktop programs, `v-snap`, the boot menu password, the APT repository and its packages, firewall rules and
hardening settings), and mistakes in how the ISO is assembled (for example a file that should not be in the image).

Out of scope: vulnerabilities in Debian packages themselves (report them to Debian), attacks that need an already-compromised root, and
the documented limits in [THREAT-MODEL.md](THREAT-MODEL.md).

## Supported versions

Only the latest release, in **maintenance mode**: security fixes on a best-effort basis, no guaranteed response time,
no new features. Older releases (and the HIDS of 1.0 and 1.0.1) receive no fixes. See [DISCLAIMER.md](DISCLAIMER.md).

## Code review welcome

The code has not been audited by an independent third party. Reviews of the parts that run as root are especially
welcome: `build/vv-vpn-helper`, `build/vaevictis_install.sh`, `build/v-snap`, `build/vv-grub-password`, `build/vv-panic-action`,
and the sandbox `build/vv-sandbox`. Report anything security-relevant privately, as described above.

## Verifying releases

Each release ships a `SHA256SUMS` file, its detached GPG signature `SHA256SUMS.asc` (when signed), the package list and an SBOM
(CycloneDX). Check them before you install.
