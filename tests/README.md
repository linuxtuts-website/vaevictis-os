# Tests

Run on any Linux machine as root (they use network namespaces and never touch the real network).

| File | What it checks | How to run |
|---|---|---|
| `vpn_helper_logic.py` | config whitelist (hooks, SaveConfig, unknown settings, bad values, custom routing `Table`/`FwMark`, peers without `Endpoint` refused), the clean copy wg-quick reads, IPv6 handling, server names under the kill switch, interface names | `python3 -I tests/vpn_helper_logic.py build/vv-vpn-helper /tmp/ks.nft` |
| `vpn_helper_flows.py` | connect / reconnect / disconnect with the real `nft`: the kill switch stays on when a reconnect fails, no DNS lookup while blocked, DNS failure takes the tunnel down, import refusals, the kill switch flag is root-only, disconnecting another tunnel keeps the kill switch | `unshare -n python3 -I tests/vpn_helper_flows.py build/vv-vpn-helper` |
| `vpn_killswitch_netns.sh` | packets: with the kill switch on, this PC reaches only the VPN server, virtual machines reach nothing outside the tunnel, this PC still answers its VMs | inside a Debian 13 root with `iproute2`, `nftables`, `python3`, `iputils-ping`, with `/tmp/ks-lan.nft` made by `ks_rules("proton-ch1", [("10.9.0.1", 51820)])`: `unshare -m -n` + mount `proc`, `sys`, `dev` + `chroot ROOT /tmp/kstest.sh` |

| `sandbox_args.sh` | which files given as arguments `vv-sandbox` makes visible and how (1.2): hidden files, `~/bin`, links (to a file, to a folder, through a linked folder) and `/tmp` read-only and alone, `/proc` and the runtime folder refused, data folders writable, secrets behind links hidden, resolved paths passed to the program. A stand-in `bwrap` prints the arguments, no sandbox is started | as root, with a user `tester`: `bash tests/sandbox_args.sh build/vv-sandbox` |
| `sandbox_probe.py` + `sandbox_fakebus.py` + `sandbox_probe_run.sh` + `sandbox_env.sh` | what a program can do inside `vv-sandbox` for each profile: no network, read-only system and home, data folders and the opened file's folder writable, secrets hidden, private /tmp and /run, D-Bus limited to notifications (Aurora) or the screenshot portal (LinPaint+) | in a Debian 13 root with a user `tester` (uid 1000) and an X server on :99: copy the probe to `/usr/local/lib/vaevictis/probe`, the fake bus to `/root/fakebus.py`, then `tests/sandbox_env.sh ROOT /root/sandbox_probe_run.sh` (it uses `pivot_root`: user namespaces do not work inside a chroot) |

wg-quick itself and its systemd sandbox, and the three programs on a real Wayland desktop with sound, need a real
system: see the test list in the release kit.

## APT repository (done for 1.1, not scripted here)

`build/vv-apt-publish` was run with a throwaway key on a copy of `vaevictis-apt`: it added 1.1.1, re-signed with
`Valid-Until`, refused a different file under the same version and a package not named `vaevictis-*`. Then Debian 13's apt,
pointed at that copy (served as `apt.linuxtuts.online` on 127.0.0.1) with the pin of `vaevictis-archive-keyring`, chose
`vaevictis-aurora` 1.1.1 at priority 500, gave a `bash` 99 offered by a hostile index priority -1 (never the candidate),
and refused an index past its validity ("Release file ... is expired").
