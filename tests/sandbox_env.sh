#!/bin/bash
# sandbox-env.sh ROOT SCRIPT: ROOT becomes the real root of a new mount namespace (pivot_root, not chroot: the kernel
# refuses user namespaces, which bubblewrap needs, inside a chroot), with a user session for tester (uid 1000),
# a private /run and /tmp, and the X server :99 of this machine.
R="$1"; SCRIPT="$2"
exec unshare --mount --pid --fork --propagation private -- bash -c '
R="$1"; SCRIPT="$2"
mount --bind "$R" "$R"
mount -t proc proc "$R/proc"; mount --rbind /sys "$R/sys"; mount --rbind /dev "$R/dev"; mount -t tmpfs tmpfs "$R/run"
mount -t tmpfs tmpfs "$R/tmp"; mkdir -p "$R/tmp/.X11-unix"; mount --bind /tmp/.X11-unix "$R/tmp/.X11-unix"
mkdir -p "$R/run/user/1000" "$R/run/dbus" "$R/.oldroot"; chown 1000:1000 "$R/run/user/1000"; chmod 700 "$R/run/user/1000"
touch "$R/run/dbus/system_bus_socket" "$R/tmp/hostfile"; chmod 666 "$R/tmp/hostfile"
cd "$R" && pivot_root . .oldroot && umount -l /.oldroot
exec /usr/bin/env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin HOME=/root bash "$SCRIPT"
' _ "$R" "$SCRIPT"
