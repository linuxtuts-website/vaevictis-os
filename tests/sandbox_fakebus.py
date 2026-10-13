# fake session services: Notifications, the portal (Screenshot + OpenURI) and an "evil" service
import gi
from gi.repository import Gio, GLib
XML = {
 "org.freedesktop.Notifications": ("/org/freedesktop/Notifications", '<node><interface name="org.freedesktop.Notifications"><method name="GetServerInformation"><arg type="s" direction="out"/><arg type="s" direction="out"/><arg type="s" direction="out"/><arg type="s" direction="out"/></method></interface></node>'),
 "org.freedesktop.portal.Desktop": ("/org/freedesktop/portal/desktop", '<node><interface name="org.freedesktop.portal.Screenshot"><method name="Screenshot"><arg type="s" direction="in"/><arg type="a{sv}" direction="in"/><arg type="o" direction="out"/></method></interface><interface name="org.freedesktop.portal.OpenURI"><method name="OpenURI"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="a{sv}" direction="in"/><arg type="o" direction="out"/></method></interface></node>'),
 "org.example.Evil": ("/", '<node><interface name="org.example.Evil"><method name="Run"><arg type="s" direction="out"/></method></interface></node>'),
}
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
def handler(conn, sender, path, iface, method, params, inv):
    if method == "GetServerInformation": inv.return_value(GLib.Variant("(ssss)", ("fake", "vv", "1", "1.2")))
    elif method == "Screenshot":
        token = params.unpack()[1].get("handle_token", "t")
        rpath = "/org/freedesktop/portal/desktop/request/%s/%s" % (sender[1:].replace(".", "_"), token)
        inv.return_value(GLib.Variant("(o)", (rpath,)))
        def emit():
            conn.emit_signal(sender, rpath, "org.freedesktop.portal.Request", "Response",
                             GLib.Variant("(ua{sv})", (0, {"uri": GLib.Variant("s", "file:///home/tester/Pictures/shot.png")})))
            return False
        GLib.timeout_add(300, emit)
    elif method == "OpenURI": inv.return_value(GLib.Variant("(o)", ("/org/freedesktop/portal/desktop/request/x/y",)))
    else: inv.return_value(GLib.Variant("(s)", ("EVIL RAN",)))
for name, (path, xml) in XML.items():
    for iface in Gio.DBusNodeInfo.new_for_xml(xml).interfaces:
        bus.register_object(path, iface, handler, None, None)
    Gio.bus_own_name_on_connection(bus, name, Gio.BusNameOwnerFlags.NONE, None, None)
GLib.MainLoop().run()
