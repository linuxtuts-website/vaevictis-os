# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for a security problem.

Use GitHub's **private vulnerability reporting**: the "Report a vulnerability" button on the Security tab of this repository.

Please include: what you found, the VaeVictis version (`cat /etc/os-release` or the ISO file name), and steps to reproduce.
Please give a reasonable time to fix it before you publish. This is a one-person, best-effort project: there is no formal
response time, but reports are read and answered.

## Scope

In scope: the scripts and programs in this repository (installer, `vv-*` tools, HIDS, VPN manager and its privileged helper,
firewall rules and hardening settings), and mistakes in how the ISO is assembled (for example a file that should not be in the image).

Out of scope: vulnerabilities in Debian packages themselves (report them to Debian), attacks that need an already-compromised root, and
the documented limits in [THREAT-MODEL.md](THREAT-MODEL.md).

## Supported versions

Only the latest release is supported.

## Verifying releases

Each release ships a `SHA256SUMS` file, its detached GPG signature `SHA256SUMS.asc` (when signed), the package list and an SBOM
(CycloneDX). Check them before you install.
