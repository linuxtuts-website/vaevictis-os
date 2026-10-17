#!/bin/bash
# Which files given as arguments vv-sandbox makes visible, and how (1.2). No real sandbox is started: a stand-in bwrap
# prints the arguments it receives. Run as root on any Linux machine with a user "tester":
#   bash tests/sandbox_args.sh build/vv-sandbox
set -uo pipefail
SB=$(realpath -e "${1:?usage: sandbox_args.sh PATH/TO/vv-sandbox}")
id tester >/dev/null 2>&1 || { echo "needs a user named tester"; exit 2; }
[ "$(id -u)" -eq 0 ] || { echo "run as root"; exit 2; }

T=$(mktemp -d /var/tmp/sbargs.XXXXXX); chmod 755 "$T"
H="$T/home"; RT="$T/rt"; X=/tmp/.X11-unix/X97
cleanup() { rm -rf "$T"; rm -f "$X" /tmp/sbargs-real.pdf /tmp/sbargs-link.pdf; }
trap cleanup EXIT
install -d -m 755 "$T/bin"; install -d -o tester -m 700 "$H" "$RT"
install -m 755 "$SB" "$T/vv-sandbox"
printf '#!/bin/sh\nfor a in "$@"; do printf "%%s\\n" "$a"; done\n' > "$T/bin/bwrap"; chmod 755 "$T/bin/bwrap"
install -d -m 1777 /tmp/.X11-unix
python3 -c "import socket,os,sys; p=sys.argv[1]; s=socket.socket(socket.AF_UNIX); s.bind(p); os.chmod(p,0o777)" "$X"

su tester -s /bin/bash -c "
set -e; cd '$H'
mkdir -p bin dotfiles Documents Downloads sshreal
touch bin/myscript dotfiles/bashrc Documents/a.pdf a.pdf sshreal/id_ed25519 .profile
ln -s '$H/dotfiles/bashrc' .bashrc; ln -s '$H/sshreal' .ssh
ln -s '$H/dotfiles/bashrc' Downloads/readme.pdf; ln -s '$H/dotfiles' Downloads/album; ln -s '$H/bin/myscript' Downloads/s.pdf
ln -s '$H' Downloads/home.pdf; ln -s '$RT' Downloads/run.pdf
touch /tmp/sbargs-real.pdf; ln -sfn /tmp/sbargs-real.pdf /tmp/sbargs-link.pdf"

out=$(su tester -s /bin/bash -c "cd '$H' && PATH='$T/bin':/usr/bin:/bin HOME='$H' XDG_RUNTIME_DIR='$RT' WAYLAND_DISPLAY= DISPLAY=:97 \
  '$T/vv-sandbox' vv-pdf /bin/true '$H/.profile' '$H/bin/myscript' '$H/.bashrc' '$H/Downloads/readme.pdf' \
  '$H/Downloads/album/bashrc' '$H/Downloads/s.pdf' '$H/Downloads/home.pdf' '$H/Downloads/run.pdf' /proc/self/environ \
  /proc/1/environ Documents/a.pdf '$H/a.pdf' /tmp/sbargs-link.pdf 2>&1" | tr '\n' '\034')
pairs=$(printf '%s' "$out" | sed 's/\x1c--/\x1c\n--/g')   # one option per line, each item followed by \034
prog=$(printf '%s\n' "$pairs" | grep -a $'^--\034/bin/true' | tr '\034' ' ')

n=0; fail=0
has()  { if printf '%s\n' "$pairs" | grep -aqxF -- "$(printf '%s\034%s\034%s\034' "$1" "$2" "$2")"; then n=$((n+1)); else echo "FAIL: missing $1 $2"; fail=1; fi; }
has1() { if printf '%s\n' "$pairs" | grep -aqxF -- "$(printf '%s\034%s\034' "$1" "$2")"; then n=$((n+1)); else echo "FAIL: missing $1 $2"; fail=1; fi; }
hasnt(){ if printf '%s\n' "$pairs" | grep -aq -- "$1"; then echo "FAIL: unexpected $1"; fail=1; else n=$((n+1)); fi; }
has --ro-bind "$H/.profile"                       # hidden file: read only
has --ro-bind "$H/bin/myscript"                   # ~/bin: read only
has --ro-bind "$H/dotfiles/bashrc"                # reached through links: that file alone, read only
has --ro-bind /tmp/sbargs-real.pdf                # /tmp: read only
has --bind "$H/Documents"                         # normal folder of the home (also as a relative path): writable
has --bind "$H/a.pdf"                             # normal file directly in the home: that file
has1 --tmpfs "$H/sshreal"                         # a secret moved behind a link: hidden at its real place
hasnt "^--bind $H/bin"; hasnt "^--bind $H/dotfiles"; hasnt "^--bind $H$(printf '\034')"; hasnt "^--bind $RT"
hasnt "environ"; hasnt "^--bind $H/.profile"
case "$prog" in *"/bin/true $H/.profile $H/bin/myscript $H/dotfiles/bashrc"*"/tmp/sbargs-real.pdf "*) n=$((n+1)) ;;
                *) echo "FAIL: the program should get resolved paths: $prog"; fail=1 ;; esac
case "$prog" in *environ*|*home.pdf*|*run.pdf*) echo "FAIL: refused paths passed to the program: $prog"; fail=1 ;; *) n=$((n+1)) ;; esac
[ "$fail" -eq 0 ] && echo "sandbox arguments: $n checks passed" || exit 1
