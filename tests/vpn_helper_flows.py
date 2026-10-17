import base64, importlib.machinery, importlib.util, io, os, sys, json, tempfile, subprocess, contextlib, socket, stat
H = sys.argv[1]
def load():
    l = importlib.machinery.SourceFileLoader("helper", H); s = importlib.util.spec_from_loader("helper", l)
    h = importlib.util.module_from_spec(s); l.exec_module(h); return h
def key(): return base64.b64encode(os.urandom(32)).decode()
PK, PUB = key(), key()
T = tempfile.mkdtemp()
calls = []
def setup(h, wg_rc=0, dns_ok=True):
    h.CONF_DIR = f"{T}/etc"; h.STATE_DIR = f"{T}/var"; h.INDEX = f"{T}/var/nodes"
    h.RUN_DIR = f"{T}/run"; h.RT_DIR = f"{T}/run/run"; h.EP_DIR = f"{T}/run/endpoints"; h.KS_FLAG = f"{T}/run/killswitch"
    h.MODPROBE = "/bin/true"
    def fake_wg(action, conf):
        calls.append(("wg-quick", action, open(conf).read()))
        return wg_rc
    h.sandboxed_wg_quick = fake_wg
    h.set_dns = lambda n, d, s: calls.append(("dns+", n, tuple(d))) or dns_ok
    h.unset_dns = lambda n: calls.append(("dns-", n))
    h.live_endpoints = lambda n: {PUB: ("185.159.157.1", 51820)}
    return h
def nft_has():
    r = subprocess.run(["nft", "list", "table", "inet", "vv_killswitch"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""
def run(h, fn, *a):
    err = io.StringIO(); rc = 0
    with contextlib.redirect_stderr(err):
        try: fn(*a)
        except SystemExit as e: rc = e.code if isinstance(e.code, int) else 1
    return rc, err.getvalue()
n = 0
def check(c, m):
    global n
    if not c: print("FAIL:", m); sys.exit(1)
    n += 1
os.makedirs(f"{T}/etc", mode=0o700)
conf_ip = f"[Interface]\nPrivateKey = {PK}\nAddress = 10.2.0.2/32\nDNS = 10.2.0.1\n[Peer]\nPublicKey = {PUB}\nAllowedIPs = 0.0.0.0/0\nEndpoint = 185.159.157.1:51820\n"
conf_host = conf_ip.replace("185.159.157.1:51820", "vpn.example.net:51820")
open(f"{T}/etc/pip.conf", "w").write(conf_ip); open(f"{T}/etc/phost.conf", "w").write(conf_host)

# A: connect with kill switch, success
h = setup(load()); calls.clear()
rc, err = run(h, h.cmd_up, "pip", True)
check(rc == 0, f"A rc {rc} {err}")
check('oifname "pip" accept' in nft_has() and "185.159.157.1" in nft_has() and "chain forward" in nft_has(), "A rules")
check(os.path.exists(h.KS_FLAG), "A flag")
check(stat.S_IMODE(os.stat(h.KS_FLAG).st_mode) == 0o600, "A flag root-only (1.2)")
check(("dns+", "pip", ("10.2.0.1",)) in calls, "A dns")
rt = f"{T}/run/run/pip.conf"
check(stat.S_IMODE(os.stat(rt).st_mode) == 0o600 and stat.S_IMODE(os.stat(f"{T}/run/run").st_mode) == 0o700, "A perms")
wq = [c for c in calls if c[0] == "wg-quick"][0]
check("DNS" not in wq[2] and "Endpoint = 185.159.157.1:51820" in wq[2], "A runtime conf")
check(json.load(open(f"{T}/run/endpoints/pip.json")) == {PUB: ["185.159.157.1", 51820]}, "A cache")

# B: reconnect fails while the kill switch is on: it must stay on (fail closed)
h = setup(load(), wg_rc=1); calls.clear()
os.remove(rt)
rc, err = run(h, h.cmd_up, "pip", True)
check(rc == 1 and "stays on" in err, f"B {rc} {err}")
check('oifname "pip" accept' in nft_has() and os.path.exists(h.KS_FLAG), "B still blocked")
check(not os.path.exists(rt), "B runtime conf removed")

# C: blocked + server by host name, no cache: refused, nothing looked up, still blocked
h = setup(load()); calls.clear()
def no_dns(*a, **k): raise AssertionError("DNS lookup while blocked")
socket.getaddrinfo = no_dns
rc, err = run(h, h.cmd_up, "phost", True)
check(rc == 1 and "kill switch" in err and "stays on" in err, f"C {rc} {err}")
check(not [c for c in calls if c[0] == "wg-quick"], "C wg-quick must not run")
check('oifname "pip" accept' in nft_has(), "C previous rules kept")

# D: blocked + host name + last known address of the same server: connects without any lookup
os.makedirs(f"{T}/run/endpoints", exist_ok=True)
json.dump({PUB: ["185.159.157.9", 51820]}, open(f"{T}/run/endpoints/phost.json", "w"))
h = setup(load()); calls.clear()
rc, err = run(h, h.cmd_up, "phost", True)
check(rc == 0, f"D {rc} {err}")
wq = [c for c in calls if c[0] == "wg-quick"][0]
check("Endpoint = 185.159.157.9:51820" in wq[2] and "example" not in wq[2], "D endpoint from cache")

# E: blocked, connect WITHOUT kill switch: stays blocked while connecting, released after success
subprocess.run(["nft", "-f", "-"], input=load().ks_rules("pip", [("185.159.157.1", 51820)]), text=True, check=True)
open(h.KS_FLAG, "w").write("pip\n")
h = setup(load()); calls.clear()
socket.getaddrinfo = no_dns
rc, err = run(h, h.cmd_up, "pip", False)
check(rc == 0 and not nft_has() and not os.path.exists(h.KS_FLAG), f"E {rc} {err} {nft_has()}")

# F: DNS cannot be set: tunnel taken down again, error, kill switch (asked) stays
h = setup(load(), dns_ok=False); calls.clear()
rc, err = run(h, h.cmd_up, "pip", True)
check(rc == 1 and "DNS" in err and ("wg-quick", "down") == [c for c in calls if c[0] == "wg-quick"][-1][:2], f"F {rc} {err}")
check(nft_has() != "", "F kill switch stays")

# G0: disconnecting ANOTHER tunnel never releases the kill switch that guards "pip" (1.2)
h = setup(load()); calls.clear()
rc, err = run(h, h.cmd_down, "other")
check(nft_has() != "" and open(h.KS_FLAG).read().strip() == "pip", f"G0 kill switch of pip kept {rc} {err}")

# G: disconnect: everything back to normal
h = setup(load()); calls.clear()
rc, err = run(h, h.cmd_down, "pip")
check(not nft_has() and not os.path.exists(h.KS_FLAG) and ("dns-", "pip") in calls, f"G {rc} {err}")
check(not os.path.exists(f"{T}/run/endpoints/pip.json"), "G cache removed")

# H: import refuses hooks and unknown settings, accepts a plain config
h = setup(load())
for bad in (conf_ip + "PostUp = id\n", conf_ip + "Foo = 1\n"):
    sys.stdin = io.TextIOWrapper(io.BytesIO(bad.encode()))
    rc, err = run(h, h.cmd_import, "x1")
    check(rc == 1 and "Refused" in err and not os.path.exists(f"{T}/etc/x1.conf"), f"H bad {err}")
sys.stdin = io.TextIOWrapper(io.BytesIO(conf_ip.encode()))
rc, err = run(h, h.cmd_import, "x2")
check(rc == 0 and stat.S_IMODE(os.stat(f"{T}/etc/x2.conf").st_mode) == 0o600, f"H good {err}")
print(f"helper flows: {n} checks passed")
