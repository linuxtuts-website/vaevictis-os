#!/bin/bash
# VaeVictis OS installer
set -Eeuo pipefail
# Any command that fails stops the installer: say so loudly, with the command, instead of vanishing silently.
trap 'rc=$?; echo -e "\n!! INSTALLATION FAILED (exit code $rc) at line $LINENO: $BASH_COMMAND" >&2' ERR

TARGET=/mnt/vaevictis-target
KEYDIR=/run/vv-keys          # key files of the encrypted partitions: only ever in RAM, shredded when done
ENC=0                        # 1 = LUKS disk encryption (asked below)
OPEN_MAPS=()                 # device-mapper names we opened, closed again at the end
log()  { echo -e "\n==> $*"; }
warn() { echo -e "\nWARNING: $*" >&2; }
die()  { echo -e "\nERROR: $*" >&2; exit 1; }

# Close the encrypted volumes we opened (last opened first) and destroy the key files.
close_crypt() {
    local k m
    for ((k = ${#OPEN_MAPS[@]} - 1; k >= 0; k--)); do
        m="${OPEN_MAPS[$k]}"
        umount "/dev/mapper/$m" 2>/dev/null || true          # the desktop may have mounted it a second time
        cryptsetup close "$m" 2>/dev/null && continue
        udevadm settle 2>/dev/null || true; sleep 1          # something (udev, a file manager) still holds it: wait and retry
        cryptsetup close "$m" 2>/dev/null && continue
        cryptsetup close --deferred "$m" 2>/dev/null \
            || echo "Note: encrypted volume $m is still open; it closes by itself when you shut down." >&2
    done
    OPEN_MAPS=()
    if [ -d "$KEYDIR" ]; then
        find "$KEYDIR" -type f -exec shred -u {} + 2>/dev/null
        rm -rf "$KEYDIR"
    fi
}

# Unmount everything on error (or at the end of the script)
cleanup() {
    local rc=$?
    set +e
    if grep -qs " $TARGET" /proc/mounts; then
        sync
        umount -R "$TARGET" 2>/dev/null || umount -R -l "$TARGET" 2>/dev/null
    fi
    close_crypt
    exit "$rc"
}
trap cleanup EXIT

[ "$(id -u)" -eq 0 ] || die "Run this script as root."

# The installer copies the RUNNING system: that is only safe from the live session.
grep -qw "boot=live" /proc/cmdline || [ "${VV_FORCE:-}" = 1 ] \
    || die "Run the installer from the VaeVictis live session (it copies the running system). Set VV_FORCE=1 only if you know what you are doing."

for c in parted lsblk blkid rsync mkfs.ext4 mkfs.vfat mkswap wipefs partprobe udevadm blockdev chroot dpkg; do
    command -v "$c" >/dev/null 2>&1 || die "Missing required command: $c"
done

# The live system must have a kernel in /boot, otherwise GRUB cannot boot anything
compgen -G "/boot/vmlinuz-*" >/dev/null \
    || die "No kernel found in /boot of the running system: the installed system would not boot."

EFI_MODE=0
[ -d /sys/firmware/efi ] && EFI_MODE=1

# ---------------------------------------------------------------- helpers
read_uint() {   # read_uint VAR "prompt" default
    local __r
    while true; do
        read -rp "$2 [default: $3]: " __r; __r=${__r:-$3}
        if [[ "$__r" =~ ^[0-9]+$ ]]; then printf -v "$1" '%s' "$__r"; return 0; fi
        echo "Please enter a whole number."
    done
}

part_path() { if [[ "$DISK" =~ [0-9]$ ]]; then echo "${DISK}p$1"; else echo "${DISK}$1"; fi; }

# With encryption on, every partition except the EFI/bios_grub one, /boot and swap holds a LUKS2 volume. The filesystem
# is then on /dev/mapper/NAME, not on the partition itself: fs_dev gives the right device for partition number idx+1.
declare -A CRYPT_MAP=()                            # partition index -> mapper name
is_luks_part() {                                   # is_luks_part INDEX
    [ "$ENC" -eq 1 ] || return 1
    case "${P_MNT[$1]}" in /boot/efi|/boot|-|swap) return 1 ;; *) return 0 ;; esac
}
fs_dev() {                                         # fs_dev INDEX
    if [ -n "${CRYPT_MAP[$1]:-}" ]; then echo "/dev/mapper/${CRYPT_MAP[$1]}"; else part_path $(($1 + 1)); fi
}

declare -a P_MNT=() P_SIZE=() P_FS=() P_NAME=()   # SIZE in MiB (0 = all remaining space)
add_part() { P_MNT+=("$1"); P_SIZE+=("$2"); P_FS+=("$3"); P_NAME+=("$4"); }
mnt_in_use() { local m; for m in "${P_MNT[@]}"; do [ "$m" = "$1" ] && return 0; done; return 1; }

# ---------------------------------------------------------------- disk
log "Available disks:"
lsblk -dpno NAME,SIZE,MODEL | grep -v -E 'loop|sr[0-9]' || true
echo
read -rp "Enter destination device (e.g., /dev/sda): " DISK
[ -b "$DISK" ] || die "Device '$DISK' does not exist."
if lsblk -nrpo LABEL "$DISK" 2>/dev/null | grep -qx 'VAEVICTIS'; then
    die "$DISK holds the VaeVictis installation medium (label VAEVICTIS): choose another disk."
fi

# Refuse the disk the live system is running from
while read -r _dev _mp; do
    [ -z "${_mp:-}" ] && continue
    case "$_mp" in
        /|/cdrom*|/run/live/*|/lib/live/*|/isodevice*|/run/archiso*)
            die "$DISK contains the running system / install media (mounted on $_mp)." ;;
    esac
done < <(lsblk -nrpo NAME,MOUNTPOINT "$DISK")

DISK_MIB=$(( $(blockdev --getsize64 "$DISK") / 1048576 ))

# ---------------------------------------------------------------- localization
echo
# Timezone: nobody remembers "Europe/Rome", so choose the country and confirm the city.
TZ_INPUT=UTC; KB_SUGGEST=us
pick_timezone() {
    local zi=/usr/share/zoneinfo q n i cc tz name city ans
    local -a C Z
    if [ ! -f "$zi/iso3166.tab" ] || [ ! -f "$zi/zone.tab" ]; then
        read -rp "Timezone, e.g. Europe/Rome [UTC]: " tz || tz=""
        tz=${tz:-UTC}; [ -f "$zi/$tz" ] && TZ_INPUT="$tz"; return 0
    fi
    while true; do
        read -rp "Your country: 2-letter code (it, de, uk, us...) or part of its name (e.g. ital). Enter = UTC: " q || q=""
        [ -n "$q" ] || { TZ_INPUT=UTC; return 0; }
        case "${q,,}" in    # names the time zone database spells differently: these win over a substring search ("uk" is in "Ukraine")
            uk|u.k.|"united kingdom"|england|scotland|wales|"great britain") C=("GB"$'\t'"Britain (UK)") ;;
            usa|u.s.a.|america)                                              C=("US"$'\t'"United States") ;;
            *) C=()
               # exactly two letters: an ISO country code (it, de, fr...). "it" alone would match Haiti, Kuwait, Lithuania...
               if [[ "$q" =~ ^[A-Za-z]{2}$ ]]; then
                   mapfile -t C < <(awk -F'\t' -v c="${q^^}" '/^#/ {next} $1==c {print $1 "\t" $2}' "$zi/iso3166.tab")
               fi
               [ "${#C[@]}" -gt 0 ] || mapfile -t C < <(awk -F'\t' -v q="$q" '/^#/ {next} index(tolower($2), tolower(q)) {print $1 "\t" $2}' "$zi/iso3166.tab") ;;
        esac
        if [ "${#C[@]}" -eq 0 ]; then echo "No country matches '$q'. Try another part of the name."; continue; fi
        if [ "${#C[@]}" -gt 12 ]; then echo "${#C[@]} countries match: type more letters."; continue; fi
        cc="${C[0]%%$'\t'*}"; name="${C[0]#*$'\t'}"
        if [ "${#C[@]}" -gt 1 ]; then
            for i in "${!C[@]}"; do printf '  %2d) %s\n' "$((i+1))" "${C[$i]#*$'\t'}"; done
            read -rp "Number [1-${#C[@]}, Enter to search again]: " n || n=""
            [[ "$n" =~ ^[0-9]+$ ]] && [ "$n" -ge 1 ] && [ "$n" -le "${#C[@]}" ] || continue
            cc="${C[$((n-1))]%%$'\t'*}"; name="${C[$((n-1))]#*$'\t'}"
        fi
        # the zone that covers most of the country first, so that Enter is usually right
        mapfile -t Z < <(awk -F'\t' -v c="$cc" '$1==c {print (($4 ~ /most|mainland/) ? 0 : 1) "\t" $3 "\t" $4}' "$zi/zone.tab" \
                         | sort -s -t$'\t' -k1,1n | cut -f2-)
        [ "${#Z[@]}" -gt 0 ] || { echo "No timezone listed for $name."; continue; }
        if [ "${#Z[@]}" -eq 1 ]; then
            tz="${Z[0]%%$'\t'*}"
        else
            echo "$name has several time zones:"
            for i in "${!Z[@]}"; do
                printf '  %2d) %-26s %s\n' "$((i+1))" "${Z[$i]%%$'\t'*}" "${Z[$i]#*$'\t'}"
            done
            read -rp "Number [1-${#Z[@]}, Enter = 1, 0 = start again]: " n || n=""
            n=${n:-1}
            [[ "$n" =~ ^[0-9]+$ ]] && [ "$n" -ge 1 ] && [ "$n" -le "${#Z[@]}" ] || continue
            tz="${Z[$((n-1))]%%$'\t'*}"
        fi
        [ -f "$zi/$tz" ] || { echo "Time zone '$tz' is not installed on this system."; continue; }
        city="${tz##*/}"; city="${city//_/ }"
        read -rp "$name, time of $city ($tz). Correct? [Y/n]: " ans || ans=""
        case "${ans,,}" in n|no) continue ;; esac
        TZ_INPUT="$tz"; KB_SUGGEST="$(echo "$cc" | tr 'A-Z' 'a-z')"
        [ -e "/usr/share/X11/xkb/symbols/$KB_SUGGEST" ] || KB_SUGGEST=us
        return 0
    done
}
pick_timezone
while true; do
    read -rp "Keyboard layout: it, us, gb, de, fr, es... [default: $KB_SUGGEST]: " KB_INPUT; KB_INPUT=${KB_INPUT:-$KB_SUGGEST}
    KB_INPUT="${KB_INPUT,,}"; [ "$KB_INPUT" = uk ] && KB_INPUT=gb        # the layout of the United Kingdom is called gb
    [[ "$KB_INPUT" =~ ^[a-z]{2,10}$ ]] && [ -e "/usr/share/X11/xkb/symbols/$KB_INPUT" ] && break
    echo "'$KB_INPUT' is not a keyboard layout on this system. Use the country code: it, us, gb, de, fr, es..."
done
while true; do
    read -rp "Hostname [default: vaevictis]: " NEW_HOSTNAME; NEW_HOSTNAME=${NEW_HOSTNAME:-vaevictis}
    [[ "$NEW_HOSTNAME" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]] && break
    echo "Invalid hostname."
done
HARDEN_OPTS="ipv6.disable=1 slab_nomerge init_on_alloc=1 init_on_free=1 page_alloc.shuffle=1 randomize_kstack_offset=on vsyscall=none debugfs=off tsx=off"
echo "Hardened boot options: $HARDEN_OPTS"
echo "(IPv6 off matches the firewall, which has no IPv6 rules. With 'n' IPv6 stays on but will not work through the firewall.)"
read -rp "Apply the hardened boot options to the installed system? [Y/n]: " HARDEN_IN
case "${HARDEN_IN,,}" in n|no) HARDEN=0 ;; *) HARDEN=1 ;; esac

# ---------------------------------------------------------------- disk encryption
echo
echo "Disk encryption (LUKS2): your files are unreadable without a passphrase, for example if the computer is stolen."
echo "  - You type the passphrase at EVERY start, before the login screen. If you forget it, the data is lost for good."
echo "  - /boot and the EFI partition stay unencrypted: the computer needs them to ask for the passphrase."
echo "  - Swap is encrypted with a random key at every start, so hibernation is not available."
read -rp "Encrypt the disk? [Y/n]: " ENC_IN
case "${ENC_IN,,}" in n|no) ENC=0 ;; *) ENC=1 ;; esac
if [ "$ENC" -eq 1 ]; then
    for c in cryptsetup shred; do
        command -v "$c" >/dev/null 2>&1 || die "Missing required command for encryption: $c"
    done
fi

# ---------------------------------------------------------------- partition layout
echo
REST_TAKEN=0

if [ "$EFI_MODE" -eq 1 ]; then
    read_uint EFI_SIZE "EFI/boot partition size in MiB" 512
    [ "$EFI_SIZE" -ge 100 ] || die "EFI partition must be at least 100 MiB."
    add_part /boot/efi "$EFI_SIZE" vfat ESP
else
    echo "BIOS mode detected: a 1 MiB bios_grub partition will be created (GPT)."
    add_part - 1 biosgrub biosgrub
fi

[ "$ENC" -eq 1 ] && add_part /boot 1024 ext4 boot     # kernel + initramfs: GRUB reads this one before anything is unlocked

read_uint SWAP_SIZE "Swap size in MiB (0 for none)" 2048
[ "$SWAP_SIZE" -gt 0 ] && add_part swap "$SWAP_SIZE" swap swap

read_uint ROOT_GB "Root (/) partition size in GiB (0 = all remaining space)" 20
if [ "$ROOT_GB" -eq 0 ]; then REST_TAKEN=1; add_part / 0 ext4 root
else add_part / $((ROOT_GB * 1024)) ext4 root; fi

# Extra custom partitions
while [ "$REST_TAKEN" -eq 0 ]; do
    read -rp "Add another custom partition (e.g., /var, /data)? [y/N]: " ADD_EXTRA
    case "${ADD_EXTRA,,}" in y|yes) ;; *) break ;; esac

    read -rp "Mount point (e.g., /data): " MNT_PT
    MNT_PT=${MNT_PT%/}
    if ! [[ "$MNT_PT" =~ ^/[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$ ]]; then
        echo "Invalid mount point (use an absolute path, no spaces)."; continue
    fi
    case "$MNT_PT" in
        /boot/efi|/proc|/sys|/dev|/run) echo "'$MNT_PT' cannot be used here."; continue ;;
    esac
    if mnt_in_use "$MNT_PT"; then echo "'$MNT_PT' is already in the layout."; continue; fi

    read_uint MNT_SIZE_GB "Size in GiB for $MNT_PT (0 = all remaining space)" 10
    while true; do
        read -rp "Filesystem for $MNT_PT (ext4/xfs/btrfs) [default: ext4]: " MNT_FS; MNT_FS=${MNT_FS:-ext4}
        case "$MNT_FS" in ext4|xfs|btrfs) command -v "mkfs.$MNT_FS" >/dev/null 2>&1 && break
                                          echo "mkfs.$MNT_FS is not available." ;;
                          *) echo "Choose ext4, xfs or btrfs." ;;
        esac
    done
    NAME=$(echo "${MNT_PT#/}" | tr '/' '-' | cut -c1-12)
    if [ "$MNT_SIZE_GB" -eq 0 ]; then REST_TAKEN=1; add_part "$MNT_PT" 0 "$MNT_FS" "$NAME"
    else add_part "$MNT_PT" $((MNT_SIZE_GB * 1024)) "$MNT_FS" "$NAME"; fi
done

# /home
if [ "$REST_TAKEN" -eq 0 ] && ! mnt_in_use /home; then
    while true; do
        read -rp "Home (/home) size in GiB [Enter = all remaining space, 'none' = no separate /home]: " HOME_GB
        if [ -z "$HOME_GB" ]; then add_part /home 0 ext4 home; REST_TAKEN=1; break
        elif [ "${HOME_GB,,}" = "none" ]; then break
        elif [[ "$HOME_GB" =~ ^[0-9]+$ ]] && [ "$HOME_GB" -gt 0 ]; then
            add_part /home $((HOME_GB * 1024)) ext4 home; break
        else echo "Enter a positive number, nothing, or 'none'."; fi
    done
fi

# Size check
USED=1; for s in "${P_SIZE[@]}"; do USED=$((USED + s)); done
LIMIT=$((DISK_MIB - 1))
if [ "$REST_TAKEN" -eq 1 ]; then
    [ $((LIMIT - USED)) -ge 256 ] || die "Not enough space: the remaining partition would be < 256 MiB."
    REST_MIB=$((LIMIT - USED))
else
    [ "$USED" -le "$LIMIT" ] || die "Layout (${USED} MiB) does not fit on $DISK (${DISK_MIB} MiB)."
    REST_MIB=0
fi

# ---------------------------------------------------------------- user
echo
while true; do
    read -rp "New username: " NEWUSER
    [[ "$NEWUSER" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] && break
    echo "Invalid username (lowercase letters, digits, _ and - only)."
done
while true; do
    read -rsp "Password for $NEWUSER: " PASS1; echo
    read -rsp "Confirm password: " PASS2; echo
    [ -z "$PASS1" ] && { echo "Password cannot be empty."; continue; }
    [ "${#PASS1}" -ge 8 ] || { echo "Use at least 8 characters."; continue; }
    [ "$PASS1" = "$PASS2" ] && break || echo "Passwords do not match."
done

LUKS_PASS=""
if [ "$ENC" -eq 1 ]; then
    echo
    echo "Encryption passphrase: you type it at every start, so choose something you will remember. Nobody can recover your data without it."
    echo "Three or four words with spaces (for example: blue river morning coffee) are easy to remember and hard to guess."
    echo "Letters, digits and spaces only: symbols and accents are typed differently by this live session and by the boot prompt,"
    echo "and a passphrase that cannot be typed again at start would lock you out of your own disk."
    while true; do
        read -rsp "Encryption passphrase (at least 8 characters): " LP1; echo
        read -rsp "Confirm passphrase: " LP2; echo
        [ "${#LP1}" -ge 8 ] || { echo "Use at least 8 characters."; continue; }
        if printf '%s' "$LP1" | LC_ALL=C grep -q '[^A-Za-z0-9 ]'; then
            echo "Letters (without accents), digits and spaces only, please."; continue
        fi
        [ "$LP1" = "$LP2" ] || { echo "Passphrases do not match."; continue; }
        [ "${#LP1}" -ge 12 ] || echo "Tip: a longer phrase is harder to guess. Continuing with this one."
        LUKS_PASS="$LP1"; break
    done
    unset LP1 LP2
fi

# ---------------------------------------------------------------- summary + confirmation
echo
echo "================ INSTALLATION PLAN ================"
echo "Disk      : $DISK (${DISK_MIB} MiB) - $([ "$EFI_MODE" -eq 1 ] && echo UEFI || echo BIOS)/GPT"
echo "Hostname  : $NEW_HOSTNAME   User: $NEWUSER   TZ: $TZ_INPUT   Keyboard: $KB_INPUT"
echo "Boot opts : $([ "$HARDEN" -eq 1 ] && echo "hardened ($HARDEN_OPTS)" || echo "standard")"
echo "Encryption: $([ "$ENC" -eq 1 ] && echo "LUKS2 on everything except EFI and /boot; random-key swap; passphrase at every start" || echo "none")"
printf '%-4s %-16s %-10s %s\n' "N." "Mount" "FS" "Size"
for i in "${!P_MNT[@]}"; do
    sz="${P_SIZE[$i]} MiB"; [ "${P_SIZE[$i]}" -eq 0 ] && sz="${REST_MIB} MiB (remaining)"
    printf '%-4s %-16s %-10s %s\n' "$((i + 1))" "${P_MNT[$i]}" "${P_FS[$i]}" "$sz"
done
echo "==================================================="
# Disk names (nvme0n1, nvme1n1, sda...) can swap between one boot and the next: show what is on the disk TODAY, so a
# wrong disk is recognised at a glance (an existing Windows/Linux system, a data disk) before anything is erased.
echo -e "\nWhat is on $DISK right now (all of it will be erased):"
lsblk -o NAME,SIZE,FSTYPE,LABEL,MODEL "$DISK" 2>/dev/null | sed 's/^/   /' || true
echo "   Disk model/serial: $(lsblk -dno MODEL,SERIAL "$DISK" 2>/dev/null | sed 's/  */ /g')"
echo -e "\nWARNING: ALL DATA on $DISK will be DESTROYED."
read -rp "Type YES to proceed: " CONFIRM
[ "$CONFIRM" = "YES" ] || die "Aborted."

# ---------------------------------------------------------------- partitioning
log "Releasing $DISK..."
for p in $(lsblk -nrpo NAME "$DISK"); do
    swapoff "$p" 2>/dev/null || true
    umount "$p" 2>/dev/null || true
done
# An earlier, interrupted install may have left encrypted volumes open on this disk: close them (children first).
for m in $(lsblk -nrpo NAME,TYPE "$DISK" | awk '$2=="crypt"{print $1}' | tac || true); do
    cryptsetup close "$m" 2>/dev/null || true
done
wipefs -a "$DISK" >/dev/null

log "Partitioning $DISK..."
parted -s "$DISK" mklabel gpt
START=1
for i in "${!P_MNT[@]}"; do
    N=$((i + 1)); SZ=${P_SIZE[$i]}
    if [ "$SZ" -eq 0 ]; then END="100%"; else END="$((START + SZ))MiB"; fi
    case "${P_FS[$i]}" in
        biosgrub) parted -s "$DISK" mkpart biosgrub "${START}MiB" "$END"
                  parted -s "$DISK" set "$N" bios_grub on ;;
        vfat)     parted -s "$DISK" mkpart ESP fat32 "${START}MiB" "$END"
                  parted -s "$DISK" set "$N" esp on ;;
        swap)     parted -s "$DISK" mkpart swap linux-swap "${START}MiB" "$END" ;;
        *)        parted -s "$DISK" mkpart "${P_NAME[$i]}" "${P_FS[$i]}" "${START}MiB" "$END" ;;
    esac
    START=$((START + SZ))
done

partprobe "$DISK" || true
udevadm settle || true
for i in "${!P_MNT[@]}"; do
    dev=$(part_path $((i + 1)))
    for _ in $(seq 1 20); do [ -b "$dev" ] && break; sleep 0.5; done
    [ -b "$dev" ] || die "Partition device $dev did not appear."
done

# ---------------------------------------------------------------- encryption
if [ "$ENC" -eq 1 ]; then
    log "Encrypting partitions (LUKS2). This takes a few seconds for each one..."
    install -d -m 0700 "$KEYDIR"
    for i in "${!P_MNT[@]}"; do
        is_luks_part "$i" || continue
        raw=$(part_path $((i + 1)))
        wipefs -a "$raw" >/dev/null
        if [ "${P_MNT[$i]}" = "/" ]; then
            name=vv_root
            printf '%s' "$LUKS_PASS" | cryptsetup luksFormat --type luks2 --batch-mode --key-file=- "$raw"
            printf '%s' "$LUKS_PASS" | cryptsetup open --type luks --key-file=- "$raw" "$name"
        else
            # The other volumes open by themselves with a random key file kept on the (encrypted) root, so you type ONE
            # passphrase. The passphrase is added as a second key: if the key file is ever lost, it still opens them.
            name="vv_c$((i + 1))"
            head -c 64 /dev/urandom > "$KEYDIR/$name.key"; chmod 0400 "$KEYDIR/$name.key"
            cryptsetup luksFormat --type luks2 --batch-mode --key-file="$KEYDIR/$name.key" "$raw"
            printf '%s' "$LUKS_PASS" | cryptsetup luksAddKey --batch-mode --key-file="$KEYDIR/$name.key" "$raw" -
            cryptsetup open --type luks --key-file="$KEYDIR/$name.key" "$raw" "$name"
        fi
        OPEN_MAPS+=("$name"); CRYPT_MAP[$i]="$name"
    done
fi

# ---------------------------------------------------------------- formatting
log "Formatting filesystems..."
for i in "${!P_MNT[@]}"; do
    dev=$(fs_dev "$i"); lbl="${P_NAME[$i]}"
    case "${P_FS[$i]}" in
        biosgrub) continue ;;
        vfat)  wipefs -a "$dev" >/dev/null; mkfs.vfat -F32 -n EFI "$dev" ;;
        swap)  [ "$ENC" -eq 1 ] && continue          # encrypted swap is created at every start (see /etc/crypttab)
               wipefs -a "$dev" >/dev/null; mkswap -L swap "$dev" ;;
        ext4)  wipefs -a "$dev" >/dev/null; mkfs.ext4 -F -L "$lbl" "$dev" ;;
        xfs)   wipefs -a "$dev" >/dev/null; mkfs.xfs -f -L "$lbl" "$dev" ;;
        btrfs) wipefs -a "$dev" >/dev/null; mkfs.btrfs -f -L "$lbl" "$dev" ;;
    esac
done

# ---------------------------------------------------------------- mount (order: parents before children)
log "Mounting target..."
mkdir -p "$TARGET"
SWAP_UUID=""
mapfile -t SORTED < <(
    for i in "${!P_MNT[@]}"; do
        case "${P_MNT[$i]}" in -|swap) continue ;; esac
        printf '%s\t%s\n' "${P_MNT[$i]}" "$i"
    done | LC_ALL=C sort
)
for entry in "${SORTED[@]}"; do
    mnt=${entry%%$'\t'*}; idx=${entry##*$'\t'}
    mkdir -p "$TARGET$mnt"
    mount "$(fs_dev "$idx")" "$TARGET$mnt"
done

# ---------------------------------------------------------------- copying the system
log "Copying system to disk (Stateless mode)..."
RSYNC_EXCL=(
    "--exclude=/dev/*" "--exclude=/proc/*" "--exclude=/sys/*" "--exclude=/tmp/*"
    "--exclude=/run/*" "--exclude=/mnt/*" "--exclude=/media/*" "--exclude=/lost+found"
    "--exclude=/boot/efi/*" "--exclude=/cdrom/*" "--exclude=/lib/live/mount/*"
    "--exclude=/swapfile" "--exclude=/etc/fstab"
)
rsync -aHAX --info=progress2 "${RSYNC_EXCL[@]}" / "$TARGET"/ || [ $? -eq 24 ]
mkdir -p "$TARGET"/{dev,proc,sys,run,tmp,mnt,media}
chmod 1777 "$TARGET/tmp"

# ---------------------------------------------------------------- fstab
log "Generating /etc/fstab..."
{
    echo "# /etc/fstab - generated by VaeVictis installer"
    for entry in "${SORTED[@]}"; do
        mnt=${entry%%$'\t'*}; idx=${entry##*$'\t'}
        uuid=$(blkid -s UUID -o value "$(fs_dev "$idx")")
        fs=${P_FS[$idx]}
        if   [ "$mnt" = "/" ];         then opts="errors=remount-ro"; pass=1; [ "$fs" != ext4 ] && { opts="defaults"; pass=0; }
        elif [ "$mnt" = "/boot/efi" ]; then opts="umask=0077";        pass=1
        else opts="defaults"; pass=2; [ "$fs" != ext4 ] && pass=0
        fi
        echo "UUID=$uuid  $mnt  $fs  $opts  0  $pass"
    done
    for i in "${!P_MNT[@]}"; do
        if [ "${P_FS[$i]}" = swap ]; then
            if [ "$ENC" -eq 1 ]; then echo "/dev/mapper/vv_swap  none  swap  sw  0  0"
            else echo "UUID=$(blkid -s UUID -o value "$(part_path $((i + 1)))")  none  swap  sw  0  0"; fi
        fi
    done
} > "$TARGET/etc/fstab"
# (SWAP_UUID is only for the resume setting below: encrypted swap has a new random key at every start, so no resume)
if [ "$ENC" -eq 0 ]; then
    for i in "${!P_MNT[@]}"; do
        [ "${P_FS[$i]}" = swap ] && SWAP_UUID=$(blkid -s UUID -o value "$(part_path $((i + 1)))")
    done
fi

# ---------------------------------------------------------------- crypttab and key files
if [ "$ENC" -eq 1 ]; then
    log "Writing /etc/crypttab and the key files..."
    install -d -m 0700 "$TARGET/etc/cryptsetup-keys.d"
    {
        echo "# /etc/crypttab - generated by VaeVictis installer"
        for i in "${!P_MNT[@]}"; do
            raw=$(part_path $((i + 1)))
            if [ -n "${CRYPT_MAP[$i]:-}" ]; then
                name="${CRYPT_MAP[$i]}"; luks_uuid=$(blkid -s UUID -o value "$raw")
                if [ "${P_MNT[$i]}" = "/" ]; then
                    echo "$name  UUID=$luks_uuid  none  luks,initramfs"     # the one passphrase prompt, before the login screen
                else
                    install -m 0400 "$KEYDIR/$name.key" "$TARGET/etc/cryptsetup-keys.d/$name.key"
                    echo "$name  UUID=$luks_uuid  /etc/cryptsetup-keys.d/$name.key  luks"
                fi
            elif [ "${P_FS[$i]}" = swap ]; then
                echo "vv_swap  PARTUUID=$(blkid -s PARTUUID -o value "$raw")  /dev/urandom  swap,cipher=aes-xts-plain64,size=512"
            fi
        done
    } > "$TARGET/etc/crypttab"
    chmod 0644 "$TARGET/etc/crypttab"
fi

# ---------------------------------------------------------------- chroot
log "Preparing chroot..."
for fs in dev proc sys run; do
    mount --rbind "/$fs" "$TARGET/$fs"
    mount --make-rslave "$TARGET/$fs"
done

chroot_has() { chroot "$TARGET" dpkg -s "$1" >/dev/null 2>&1; }
ensure_pkgs() {
    local missing=() p
    for p in "$@"; do chroot_has "$p" || missing+=("$p"); done
    if [ "${#missing[@]}" -eq 0 ]; then return 0; fi
    chroot "$TARGET" apt-get update -qq || true
    chroot "$TARGET" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${missing[@]}"
}
set_grub_var() {   # set_grub_var NAME VALUE
    local f="$TARGET/etc/default/grub"
    touch "$f"
    if grep -qE "^#?${1}=" "$f"; then sed -i -E "s|^#?${1}=.*|${1}=${2}|" "$f"
    else echo "${1}=${2}" >> "$f"; fi
}

log "Configuring localization, hostname & users..."
echo "$NEW_HOSTNAME" > "$TARGET/etc/hostname"
touch "$TARGET/etc/hosts"
sed -i '/^127\.0\.1\.1/d' "$TARGET/etc/hosts"
echo "127.0.1.1 $NEW_HOSTNAME" >> "$TARGET/etc/hosts"

chroot "$TARGET" ln -fs "/usr/share/zoneinfo/$TZ_INPUT" /etc/localtime
echo "$TZ_INPUT" > "$TARGET/etc/timezone"
chroot "$TARGET" dpkg-reconfigure -f noninteractive tzdata 2>/dev/null || true

cat > "$TARGET/etc/default/keyboard" <<KBD
XKBMODEL="pc105"
XKBLAYOUT="$KB_INPUT"
XKBVARIANT=""
XKBOPTIONS=""
BACKSPACE="guess"
KBD
chroot "$TARGET" dpkg-reconfigure -f noninteractive keyboard-configuration 2>/dev/null || true

# New machine identity (regenerated on first boot)
: > "$TARGET/etc/machine-id"
rm -f "$TARGET/var/lib/dbus/machine-id"
ln -s /etc/machine-id "$TARGET/var/lib/dbus/machine-id" 2>/dev/null || true

scrub_live_artifacts() {
    log "Removing live-session leftovers (accounts, autologin, keys, logs)..."
    local u pk
    # 1. Live accounts. The live user has a PUBLIC password and passwordless sudo: it must never reach an installed system.
    local gone=() f
    mapfile -t gone < <(awk -F: '$3>=1000 && $3<60000 {print $1}' "$TARGET/etc/passwd")   # 60000+ is reserved for system accounts such as libvirt-qemu (64055)
    for u in "${gone[@]}"; do
        chroot "$TARGET" userdel -r "$u" 2>/dev/null || warn "could not remove the live user '$u': remove it manually after first boot."
        rm -f "$TARGET/var/lib/AccountsService/users/$u"
    done
    # Sudo rights written for the live user (live, live-user, ...). A new user with the same name must not inherit them.
    rm -f "$TARGET"/etc/sudoers.d/live*
    for u in "${gone[@]}"; do
        for f in "$TARGET"/etc/sudoers.d/*; do
            [ -f "$f" ] && grep -qw -- "$u" "$f" || continue
            sed -i "/\b$u\b/d" "$f"
            grep -qvE '^[[:space:]]*(#|$)' "$f" || rm -f "$f"
        done
    done
    # 2. The live-boot and live-config packages are only needed to boot the live session.
    pk=$(chroot "$TARGET" dpkg-query -W -f='${db:Status-Abbrev} ${Package}\n' 'live-boot*' 'live-config*' 2>/dev/null \
         | awk '$1=="ii"{print $2}' | tr '\n' ' ')
    if [ -n "$pk" ]; then
        # shellcheck disable=SC2086
        chroot "$TARGET" env DEBIAN_FRONTEND=noninteractive apt-get purge -y $pk || warn "could not purge: $pk"
    fi
    rm -rf "$TARGET/etc/live" "$TARGET/var/lib/live"
    # 3. Automatic AND timed login written by live-config while the live session was booting. It writes five lines:
    #    AutomaticLoginEnable, AutomaticLogin, TimedLoginEnable, TimedLogin, TimedLoginDelay. Leaving the timed ones
    #    active would log the live user in WITHOUT a password after a few seconds at the login screen.
    for f in daemon.conf custom.conf; do
        if [ -f "$TARGET/etc/gdm3/$f" ]; then
            sed -i -E 's/^[[:space:]]*((AutomaticLogin|TimedLogin)[A-Za-z]*[[:space:]]*=.*)$/#\1/' "$TARGET/etc/gdm3/$f"
        fi
    done
    if grep -qsE '^[[:space:]]*(AutomaticLogin|TimedLogin)[A-Za-z]*[[:space:]]*=' "$TARGET/etc/gdm3/daemon.conf" "$TARGET/etc/gdm3/custom.conf"; then
        die "automatic or timed login is still active in the installed system: refusing to finish (it would let anyone in without a password)."
    fi
    rm -f "$TARGET/etc/systemd/system/vv-live-session.service" "$TARGET/etc/systemd/system/multi-user.target.wants/vv-live-session.service" \
          "$TARGET/usr/local/libexec/vv-live-session"
    # 4. SSH host keys and logs of the live session (the installed system makes its own)
    rm -f "$TARGET"/etc/ssh/ssh_host_*
    find "$TARGET/var/log" -type f -exec truncate -s0 {} + 2>/dev/null || true
    rm -rf "$TARGET"/var/log/journal/* 2>/dev/null || true
}
scrub_live_artifacts

chroot "$TARGET" useradd -m -s /bin/bash "$NEWUSER"
chroot "$TARGET" usermod -aG sudo "$NEWUSER"
for g in audio video cdrom plugdev netdev dip libvirt kvm; do
    if chroot "$TARGET" getent group "$g" >/dev/null 2>&1; then chroot "$TARGET" usermod -aG "$g" "$NEWUSER"; fi
done
printf '%s:%s\n' "$NEWUSER" "$PASS1" | chroot "$TARGET" chpasswd
chroot "$TARGET" usermod -U "$NEWUSER" 2>/dev/null || true
chroot "$TARGET" passwd -l root
unset PASS1 PASS2

# ---------------------------------------------------------------- initramfs + GRUB
log "Preparing GRUB..."
# grub-install and update-grub come from grub2-common (NOT grub-common, which only has grub-mkconfig and grub-mkrescue).
[ -x "$TARGET/usr/sbin/grub-install" ] || ensure_pkgs grub2-common || die "grub2-common (grub-install) is missing in the target and could not be installed: connect to the network and try again."
[ -x "$TARGET/usr/sbin/grub-install" ] && [ -x "$TARGET/usr/sbin/update-grub" ] \
    || die "grub-install or update-grub is still missing in the target (package grub2-common)."
ensure_pkgs os-prober || warn "Could not install os-prober (no network?): other OSes may not be detected."

if [ "$EFI_MODE" -eq 1 ]; then
    [ -d "$TARGET/usr/lib/grub/x86_64-efi" ] || ensure_pkgs grub-efi-amd64-bin \
        || die "GRUB EFI modules missing in target and could not be installed."
    chroot_has efibootmgr || ensure_pkgs efibootmgr || warn "efibootmgr missing: boot entry may not be created."
else
    [ -d "$TARGET/usr/lib/grub/i386-pc" ] || ensure_pkgs grub-pc-bin \
        || die "GRUB BIOS modules missing in target and could not be installed."
fi

set_grub_var GRUB_DISTRIBUTOR '"VaeVictis OS"'
set_grub_var GRUB_DISABLE_OS_PROBER false
# Remove live-only options (and "quiet": boot messages stay visible) from the kernel command line
sed -i -E '/^GRUB_CMDLINE_LINUX(_DEFAULT)?=/ s/ ?(boot=(casper|live)|toram|noprompt|quiet)//g' "$TARGET/etc/default/grub"
if [ "$HARDEN" -eq 1 ]; then
    set_grub_var GRUB_CMDLINE_LINUX_DEFAULT "\"$HARDEN_OPTS\""
fi

if [ "$ENC" -eq 1 ]; then
    # Without cryptsetup-initramfs the new system could not unlock its own disk: it would not start.
    chroot_has cryptsetup-initramfs || ensure_pkgs cryptsetup cryptsetup-initramfs \
        || die "cryptsetup-initramfs is missing in the target and could not be installed: the encrypted system would not boot."
    chroot_has console-setup || ensure_pkgs console-setup \
        || warn "console-setup is missing: the passphrase prompt at boot will use the US keyboard layout."
    # Only the root disk is opened by the initramfs. Every other disk and the swap are opened by systemd once the root
    # is up, through a generator that in Debian 13 lives in the separate package systemd-cryptsetup. Without it
    # /etc/crypttab is ignored apart from the root: /home and swap never appear and the boot ends in emergency mode.
    if [ ! -e "$TARGET/usr/lib/systemd/system-generators/systemd-cryptsetup-generator" ]; then
        ensure_pkgs systemd-cryptsetup || true
        [ -e "$TARGET/usr/lib/systemd/system-generators/systemd-cryptsetup-generator" ] \
            || die "systemd-cryptsetup is missing in the target and could not be installed: /home and swap would not open at boot. Connect to the network and try again."
    fi
fi

# Avoid a resume entry pointing at the live system's swap
if [ -d "$TARGET/etc/initramfs-tools" ]; then
    mkdir -p "$TARGET/etc/initramfs-tools/conf.d"
    rm -f "$TARGET/etc/initramfs-tools/conf.d/resume"
    if [ "$ENC" -eq 1 ]; then echo "RESUME=none" > "$TARGET/etc/initramfs-tools/conf.d/resume"
    elif [ -n "$SWAP_UUID" ]; then echo "RESUME=UUID=$SWAP_UUID" > "$TARGET/etc/initramfs-tools/conf.d/resume"; fi
fi

log "Rebuilding initramfs..."
chroot "$TARGET" update-initramfs -u -k all || chroot "$TARGET" update-initramfs -c -k all

if [ "$ENC" -eq 1 ]; then
    # Check, loudly, that the initramfs can really unlock the disk. A silent miss here means a computer that never starts.
    listing=$(mktemp); found=0
    for img in "$TARGET"/boot/initrd.img-*; do
        [ -f "$img" ] || continue
        case "$img" in *.dpkg-*|*.bak) continue ;; esac
        found=1
        lsinitramfs "$img" > "$listing" 2>/dev/null || true
        grep -q 'sbin/cryptsetup' "$listing" && grep -q 'cryptroot/crypttab' "$listing" \
            || { rm -f "$listing"; die "$(basename "$img") cannot unlock the encrypted disk (cryptsetup or crypttab missing in it): refusing to finish, the system would not boot."; }
    done
    rm -f "$listing"
    [ "$found" -eq 1 ] || die "No initramfs found in the target: the system would not boot."
    echo "Initramfs check: every image can unlock the encrypted disk."
fi

log "Installing GRUB..."
# The firmware boot list belongs to the whole computer, not to the disk we are installing on. Keep a copy of it as it was
# before we touch it, so that another system on another disk can always be brought back (see the check after grub-install).
EFI_BEFORE=""
if [ "$EFI_MODE" -eq 1 ] && command -v efibootmgr >/dev/null 2>&1; then
    EFI_BEFORE=$(efibootmgr -v 2>/dev/null || true)
    if [ -n "$EFI_BEFORE" ]; then
        install -d "$TARGET/var/log"
        printf '%s\n' "$EFI_BEFORE" > "$TARGET/var/log/vaevictis-efi-before-install.txt"
        printf '%s\n' "$EFI_BEFORE" > /tmp/vaevictis-efi-before-install.txt 2>/dev/null || true
    fi
fi
if [ "$EFI_MODE" -eq 1 ]; then
    # grub-install DELETES any firmware boot entry with the same name before creating its own. If this computer already
    # has an entry called VaeVictis (an earlier install, maybe on another disk), do not destroy it unless asked to.
    BL_ID=VaeVictis
    if command -v efibootmgr >/dev/null 2>&1 && efibootmgr 2>/dev/null \
            | awk -F'\t' '{l=$1; sub(/^Boot[0-9A-Fa-f]+\*? +/, "", l); sub(/ +$/, "", l); if (l=="VaeVictis") f=1} END{exit !f}'; then
        echo
        echo "This computer already has a UEFI boot entry named 'VaeVictis' (an earlier install?)."
        echo "Using the same name would REPLACE it, and that system could stop starting from the firmware menu."
        read -rp "Replace it? [y/N]: " REPL || REPL=""
        case "${REPL,,}" in y|yes) ;; *) BL_ID="VaeVictis-$(date +%m%d%H%M)"; echo "Using the name $BL_ID instead." ;; esac
    fi
    if ! chroot "$TARGET" grub-install --target=x86_64-efi --efi-directory=/boot/efi \
            --bootloader-id="$BL_ID" --recheck; then
        warn "NVRAM entry could not be written; falling back to removable-media path."
    fi
    # Fallback copy in EFI/BOOT/BOOTX64.EFI (useful on firmware and VMs that lose NVRAM entries)
    chroot "$TARGET" grub-install --target=x86_64-efi --efi-directory=/boot/efi \
        --removable --no-nvram --recheck \
        || die "grub-install (EFI) failed."
    [ -f "$TARGET/boot/efi/EFI/BOOT/BOOTX64.EFI" ] || warn "Fallback EFI loader not found on the ESP."
    # Did the firmware boot list lose an entry that belonged to another system? Say so, and say how to bring it back.
    if [ -n "$EFI_BEFORE" ]; then
        EFI_AFTER=$(efibootmgr -v 2>/dev/null || true)
        EFI_LOST=$(comm -23 <(grep -oE '^Boot[0-9A-Fa-f]{4}' <<<"$EFI_BEFORE" | sort -u) \
                            <(grep -oE '^Boot[0-9A-Fa-f]{4}' <<<"$EFI_AFTER" | sort -u))
        if [ -n "$EFI_LOST" ]; then
            warn "These firmware boot entries existed before the install and are gone now (they belonged to another system):"
            for b in $EFI_LOST; do grep -E "^$b" <<<"$EFI_BEFORE" | cut -c1-200 >&2; done
            echo "The list as it was before is saved in /tmp/vaevictis-efi-before-install.txt and, on the new system, in /var/log/vaevictis-efi-before-install.txt." >&2
        else
            echo "Firmware boot list check: no entry of another system was removed."
        fi
    fi
else
    chroot "$TARGET" grub-install --target=i386-pc --recheck "$DISK" || die "grub-install (BIOS) failed."
fi

# Boot menu theme: the wallpaper stays and the menu sits in the centre, under the title (update-grub below picks it up).
chroot "$TARGET" env VV_NO_UPDATE=1 /usr/local/sbin/vv-grub-theme \
    || warn "GRUB theme not installed: the boot menu will use GRUB's plain look."

log "Generating GRUB configuration..."
chroot "$TARGET" update-grub
grep -q "menuentry" "$TARGET/boot/grub/grub.cfg" && grep -q "root=" "$TARGET/boot/grub/grub.cfg" \
    || die "grub.cfg has no valid Linux entry: the system would not boot."
echo "GRUB entries:"; grep -E "^menuentry" "$TARGET/boot/grub/grub.cfg" | cut -d"'" -f2 | sed 's/^/   - /'

# ---------------------------------------------------------------- done
log "Unmounting filesystems..."
sync
umount -R "$TARGET" || umount -R -l "$TARGET"
close_crypt

echo -e "\n=========================================================="
echo "  INSTALLATION COMPLETE. Remove the install media and reboot."
[ "$ENC" -eq 0 ] || echo "  At start you will be asked for the ENCRYPTION passphrase, then for your user password."
echo "=========================================================="
