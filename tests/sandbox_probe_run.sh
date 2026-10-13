cd /
runuser -u tester -- env XDG_RUNTIME_DIR=/run/user/1000 HOME=/home/tester DISPLAY=:99 PATH=/usr/local/bin:/usr/bin:/bin bash -c '
dbus-daemon --session --address=unix:path=/run/user/1000/bus --fork --nopidfile >/dev/null
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
python3 /root/fakebus.py & sleep 1.5
echo hello > ~/projects/a.pdf; echo hi > /tmp/b.pdf
for p in vv-pdf aurora linpaint; do
  echo "### profile $p"
  /usr/local/libexec/vv-sandbox $p /usr/local/lib/vaevictis/probe ~/projects/a.pdf /tmp/b.pdf 2>&1
done
echo "### outside any sandbox, for comparison"
/usr/local/lib/vaevictis/probe 2>&1 | grep -E "ssh|Evil|bashrc"
ls -la ~ | grep -E "autostart|newfile" ; ls ~/.config
'
