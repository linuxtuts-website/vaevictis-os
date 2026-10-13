#!/usr/bin/python3 -I
# probe: run INSIDE the sandbox in place of a program; prints what it can and cannot do
import os, socket, sys, subprocess
H = os.path.expanduser("~")
def t(name, fn):
    try:
        r = fn(); print(f"  {name:38s}: {r if r is not None else 'yes'}")
    except Exception as e:
        print(f"  {name:38s}: no ({type(e).__name__})")
def w(p):
    with open(p, "w") as fh: fh.write("x")
    os.remove(p)
def net():
    s = socket.create_connection(("1.1.1.1", 53), timeout=2); s.close()
t("network (connect 1.1.1.1:53)", net)
t("interfaces", lambda: ",".join(sorted(l.split(":")[0].strip() for l in open("/proc/net/dev").read().splitlines()[2:])))
t("write ~/.bashrc", lambda: w(H + "/.bashrc.vvtest") )
t("create ~/.config/autostart/x.desktop", lambda: w(H + "/.config/autostart/x.desktop"))
t("create ~/newfile", lambda: w(H + "/newfile"))
t("write ~/Documents", lambda: w(H + "/Documents/t"))
t("write ~/Music", lambda: w(H + "/Music/t"))
t("write ~/projects (folder of the file)", lambda: w(H + "/projects/t"))
t("read ~/.ssh/id_test", lambda: open(H + "/.ssh/id_test").read().strip() or "(empty)")
t("read ~/.bash_history", lambda: open(H + "/.bash_history").read().strip() or "(empty)")
t("see host /tmp/hostfile", lambda: os.path.exists("/tmp/hostfile") or (_ for _ in ()).throw(FileNotFoundError()))
t("see /run/dbus/system_bus_socket", lambda: os.path.exists("/run/dbus/system_bus_socket") or (_ for _ in ()).throw(FileNotFoundError()))
t("write /etc", lambda: w("/etc/vvtest"))
t("processes visible", lambda: len([p for p in os.listdir("/proc") if p.isdigit()]))
for a in sys.argv[1:]:
    t(f"open argument {a}", lambda a=a: (open(a).read(1), "readable")[1])
    t(f"write argument {a}", lambda a=a: (open(a, "a").close(), "writable")[1])
def call(dest, path, iface, method, sig="", *args):
    import gi
    from gi.repository import Gio, GLib
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    v = GLib.Variant(sig, args) if sig else None
    return str(bus.call_sync(dest, path, iface, method, v, None, Gio.DBusCallFlags.NONE, 2000, None).unpack())[:40]
if os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
    t("D-Bus Notifications.Notify", lambda: call("org.freedesktop.Notifications", "/org/freedesktop/Notifications", "org.freedesktop.Notifications", "GetServerInformation"))
    t("D-Bus portal Screenshot", lambda: call("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop", "org.freedesktop.portal.Screenshot", "Screenshot", "(sa{sv})", "", {}))
    t("D-Bus portal OpenURI", lambda: call("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop", "org.freedesktop.portal.OpenURI", "OpenURI", "(ssa{sv})", "", "https://example.org", {}))
    t("D-Bus other service (org.example.Evil)", lambda: call("org.example.Evil", "/", "org.example.Evil", "Run"))
else:
    t("D-Bus", lambda: (_ for _ in ()).throw(ConnectionError("no bus")))
