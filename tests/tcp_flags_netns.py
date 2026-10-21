"""The TCP flag rules of the firewall, packet by packet (1.3). Run as root in an empty network namespace:
    unshare -n python3 -I tests/tcp_flags_netns.py NFTABLES_CONF
NFTABLES_CONF is the file vv-harden writes (in its test mode: VV_CHROOT=DIR VV_SKIP_CHROOT=1 build/vv-harden).
Each "tcp flags ... drop" line of the file is loaded alone, with a counter, and TCP packets with every flag combination
that matters are sent to 127.0.0.1: only the scanner combinations may be counted, never a packet of a real connection
(an XMAS rule that compared only FIN, PSH and URG also dropped FIN|PSH|URG|ACK, a valid end of a connection)."""
import json, re, socket, struct, subprocess, sys

rules = [ln.strip() for ln in open(sys.argv[1]) if ln.strip().startswith("tcp flags") and ln.strip().endswith(" drop")]
if len(rules) != 4:
    sys.exit(f"expected 4 tcp flags rules, found {len(rules)}")
subprocess.run(["ip", "link", "set", "lo", "up"], check=True)
body = "\n".join(f"        tcp dport 9 {r[:-len(' drop')]} counter drop" for r in rules)
subprocess.run(["nft", "-f", "-"], check=True, text=True, input=f"""table inet t {{
    chain input {{
        type filter hook input priority 0; policy accept;
{body}
    }}
}}
""")

F = {"fin": 1, "syn": 2, "rst": 4, "psh": 8, "ack": 16, "urg": 32}


def csum(b):
    if len(b) % 2:
        b += b"\0"
    s = sum(struct.unpack(f"!{len(b) // 2}H", b))
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return ~s & 0xFFFF


def send(flags):
    src = dst = socket.inet_aton("127.0.0.1")
    tcp = struct.pack("!HHIIBBHHH", 40000, 9, 1, 0, 5 << 4, flags, 1024, 0, 0)
    tcp = tcp[:16] + struct.pack("!H", csum(src + dst + struct.pack("!BBH", 0, 6, len(tcp)) + tcp)) + tcp[18:]
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(tcp), 1, 0, 64, 6, 0, src, dst)
    ip = ip[:10] + struct.pack("!H", csum(ip)) + ip[12:]
    s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
    s.sendto(ip + tcp, ("127.0.0.1", 0))
    s.close()


def counters():
    data = json.loads(subprocess.run(["nft", "-j", "list", "table", "inet", "t"], capture_output=True, text=True,
                                     check=True).stdout)
    return [e["rule"]["expr"][-2]["counter"]["packets"] for e in data["nftables"] if "rule" in e]


def flags(names):
    return sum(F[n] for n in names.split("|")) if names else 0


# combination -> which rule drops it (index in the file, 0..3) or None
CASES = {"": 0, "fin|psh|urg": 1, "fin|syn": 2, "fin|syn|ack": 2, "syn|rst": 3, "syn|rst|ack": 3,
         "fin|psh|urg|ack": None, "syn": None, "syn|ack": None, "ack": None, "psh|ack": None, "fin|ack": None,
         "fin|psh|ack": None, "rst": None, "rst|ack": None, "urg|ack": None, "urg|psh|ack": None}
ok = 0
for combo, rule in CASES.items():
    before = counters()
    send(flags(combo))
    after = counters()
    hit = [i for i, (a, b) in enumerate(zip(before, after)) if b != a]
    want = [] if rule is None else [rule]
    if hit != want:
        sys.exit(f"FAIL: flags '{combo or 'none'}' dropped by rules {hit}, expected {want}\nrules: {rules}")
    ok += 1
print(f"tcp flag rules: {ok} combinations checked")
