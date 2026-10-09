// hids - a small host intrusion detector (file integrity monitor) for VaeVictis OS.
//
// What it does
//
//	-init     records a baseline (SHA-256, mode, owner) of the watched programs, services, startup files and /boot
//	-check    compares the system with the baseline once and exits (code 1 if something differs)
//	-watch    runs as a daemon: verifies the baseline at start, then watches the same paths with inotify
//	          and logs every change to /var/log/hids.log and to the journal (popups: see hids-notify)
//	-seal     accept the current state as the new baseline (stops the daemon, records, starts it again)
//	-stopped  called by systemd when the daemon stops (ExecStopPost): warns unless the system is shutting down
//
// Design notes
//   - A real-time tripwire: no cron job, nothing at a fixed time. Besides inotify the daemon re-checks everything
//     by itself at random intervals (1 to 3 hours) and immediately when the kernel reports lost events.
//   - An alert is raised only when the file really differs from the baseline (content, mode or owner): a "touch" is
//     not an alert, and the alert says what changed. A new SETUID file is always critical.
//   - Folders that do not exist yet (~/.config/autostart, /etc/ld.so.preload...) are watched through their parent,
//     so creating them is noticed.
//   - Package updates are recognised (dpkg holds its lock while it works): changes made then are not alerts;
//     when the package manager finishes, the baseline is refreshed.
//   - In a live session (boot=live) the baseline is taken at start-up and kept in /run, because live-config
//     creates the live user and changes /etc/passwd, /etc/shadow and /etc/sudoers during boot.
//   - On an installed system with no baseline yet, the first start creates one (trust on first use).
//   - Nothing is ignored by file extension. The only exclusions are exact files that change at every boot
//     (-exclude, default /boot/grub/grubenv).
//   - The daemon never talks to the desktop and never switches user: it only writes the log. The popups come from
//     hids-notify, a small script that runs in the user's own session and reads the log with the user's rights.
//   - No third-party code: file watching uses the kernel's inotify interface through the standard library.
package main

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"math/rand/v2"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

const version = "2.1"

const sealMarker = "/run/hids.sealing" // present while -seal works: the daemon stopping then is not an alarm

var (
	dirsFlag    = flag.String("dirs", "", "comma-separated files and folders to watch (default: the built-in list, see builtinTargets)")
	excludeFlag = flag.String("exclude", "/boot/grub/grubenv", "comma-separated exact files to ignore")
	dbFlag      = flag.String("db", "", "baseline file (default: /var/log/hids_baseline.json, or /run/hids_baseline.json in a live session)")
	logFlag     = flag.String("log", "/var/log/hids.log", "log file")
	locksFlag   = flag.String("locks", "/var/lib/dpkg/lock-frontend,/var/lib/dpkg/lock", "package manager lock files")
	serviceFlag = flag.String("service", "sysctl-helper.service", "systemd unit of the daemon (used by -seal)")
	doInit      = flag.Bool("init", false, "record the baseline and exit")
	doCheck     = flag.Bool("check", false, "compare the system with the baseline once and exit")
	doWatch     = flag.Bool("watch", false, "run as a daemon")
	doSeal      = flag.Bool("seal", false, "accept the current state: stop the daemon, record a new baseline, start the daemon")
	doStopped   = flag.Bool("stopped", false, "called by systemd after the daemon stopped")
	showVer     = flag.Bool("version", false, "print the version and exit")
)

// Places where an intruder makes himself permanent or gains power. Folders are watched recursively.
func builtinTargets() []string {
	t := []string{
		// programs
		"/bin", "/sbin", "/usr/bin", "/usr/sbin", "/usr/local/bin", "/usr/local/sbin", "/usr/local/libexec", "/usr/libexec",
		// accounts, privileges, login
		"/etc/passwd", "/etc/shadow", "/etc/group", "/etc/gshadow", "/etc/sudoers", "/etc/sudoers.d",
		"/etc/pam.d", "/etc/security", "/etc/polkit-1/rules.d",
		// libraries injected into every program
		"/etc/ld.so.preload", "/etc/ld.so.conf", "/etc/ld.so.conf.d",
		// things that run by themselves
		"/etc/crontab", "/etc/cron.d", "/etc/cron.hourly", "/etc/cron.daily", "/etc/cron.weekly", "/etc/cron.monthly", "/var/spool/cron",
		"/etc/systemd/system", "/etc/systemd/user", "/usr/lib/systemd/system", "/usr/lib/systemd/user",
		"/etc/udev/rules.d", "/etc/NetworkManager/dispatcher.d", "/etc/xdg/autostart", "/etc/rc.local",
		"/etc/apt/apt.conf.d", "/etc/modprobe.d", "/etc/modules-load.d", "/etc/initramfs-tools",
		// shells
		"/etc/profile", "/etc/profile.d", "/etc/bash.bashrc", "/etc/environment",
		// remote access, firewall, package sources
		"/etc/ssh/sshd_config", "/etc/ssh/sshd_config.d", "/etc/nftables.conf", "/etc/hosts",
		"/etc/apt/sources.list", "/etc/apt/sources.list.d", "/etc/apt/trusted.gpg.d", "/etc/apt/keyrings",
		// boot chain (/boot is not encrypted even with LUKS)
		"/boot", "/etc/default/grub", "/etc/grub.d",
	}
	homes, _ := filepath.Glob("/home/*")
	homes = append(homes, "/root")
	for _, h := range homes {
		for _, f := range []string{".bashrc", ".bash_profile", ".bash_login", ".bash_logout", ".profile", ".zshrc", ".zprofile",
			".ssh/authorized_keys", ".ssh/config", ".config/autostart", ".config/systemd/user", ".config/environment.d"} {
			t = append(t, filepath.Join(h, f))
		}
	}
	return t
}

// Paths whose change deserves a critical notification.
var criticalExact = map[string]bool{
	"/etc/passwd": true, "/etc/shadow": true, "/etc/sudoers": true, "/etc/ld.so.preload": true,
	"/usr/bin/su": true, "/usr/bin/sudo": true, "/usr/bin/passwd": true,
}

var criticalPrefix = []string{"/etc/sudoers.d/", "/etc/pam.d/", "/etc/ld.so.conf.d/", "/etc/systemd/system/", "/etc/cron",
	"/etc/ssh/", "/boot/", "/root/.ssh/", "/usr/libexec/systemd-sysctl-helper"}

func isCritical(path string) bool {
	if criticalExact[path] {
		return true
	}
	for _, p := range criticalPrefix {
		if strings.HasPrefix(path, p) {
			return true
		}
	}
	return strings.Contains(path, "/.ssh/authorized_keys")
}

var logger *log.Logger

// ---------------------------------------------------------------------------- baseline

// A baseline maps a path to "SHA-256 MODE UID:GID" (regular files) or "link:DESTINATION" (symbolic links).
type baseline struct {
	Version int               `json:"version"`
	Created string            `json:"created"`
	Files   map[string]string `json:"files"`
}

const baselineVersion = 3

func isLive() bool {
	b, err := os.ReadFile("/proc/cmdline")
	return err == nil && strings.Contains(" "+string(b)+" ", " boot=live ")
}

func dbPath() string {
	if *dbFlag != "" {
		return *dbFlag
	}
	if isLive() {
		return "/run/hids_baseline.json"
	}
	return "/var/log/hids_baseline.json"
}

func targets() []string {
	list := builtinTargets()
	if *dirsFlag != "" {
		list = strings.Split(*dirsFlag, ",")
	}
	seen := map[string]bool{}
	var out []string
	for _, t := range list {
		t = strings.TrimSpace(t)
		if t == "" {
			continue
		}
		if r, err := filepath.EvalSymlinks(t); err == nil { // /bin is a link to /usr/bin on Debian
			t = r
		}
		if !seen[t] {
			seen[t] = true
			out = append(out, t)
		}
	}
	sort.Strings(out)
	return out
}

var excluded = map[string]bool{}

func loadExcluded() {
	for _, e := range strings.Split(*excludeFlag, ",") {
		if e = strings.TrimSpace(e); e != "" {
			excluded[e] = true
		}
	}
}

func hashFile(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// entryOf describes one file as it is now. ok is false for folders, devices and files that do not exist.
func entryOf(path string) (string, bool) {
	info, err := os.Lstat(path)
	if err != nil {
		return "", false
	}
	if info.Mode()&os.ModeSymlink != 0 {
		dest, err := os.Readlink(path)
		if err != nil {
			return "", false
		}
		return "link:" + dest, true
	}
	if !info.Mode().IsRegular() {
		return "", false
	}
	h, err := hashFile(path)
	if err != nil {
		return "", false
	}
	var mode, uid, gid uint32
	if st, ok := info.Sys().(*syscall.Stat_t); ok {
		mode, uid, gid = st.Mode&07777, st.Uid, st.Gid
	}
	return fmt.Sprintf("%s %04o %d:%d", h, mode, uid, gid), true
}

// snapshot describes every file under the targets.
func snapshot() map[string]string {
	files := map[string]string{}
	for _, t := range targets() {
		filepath.Walk(t, func(path string, info os.FileInfo, err error) error {
			if err != nil || info.IsDir() || excluded[path] {
				return nil
			}
			if e, ok := entryOf(path); ok {
				files[path] = e
			}
			return nil
		})
	}
	return files
}

func chattr(flagArg, path string) { exec.Command("chattr", flagArg, path).Run() } // best effort

// recordBaseline takes a new baseline and stores it. The baseline is returned even when it cannot be written.
func recordBaseline() (*baseline, error) {
	b := &baseline{Version: baselineVersion, Created: time.Now().UTC().Format(time.RFC3339), Files: snapshot()}
	data, err := json.Marshal(b)
	if err != nil {
		return b, err
	}
	p := dbPath()
	chattr("-i", p)
	if err := os.WriteFile(p, data, 0600); err != nil {
		return b, err
	}
	if !isLive() {
		chattr("+i", p) // immutable on a normal system: even root must unlock it deliberately
	}
	return b, nil
}

func loadBaseline() (*baseline, error) {
	data, err := os.ReadFile(dbPath())
	if err != nil {
		return nil, err
	}
	var b baseline
	if err := json.Unmarshal(data, &b); err != nil || b.Files == nil {
		return nil, fmt.Errorf("the baseline file is not valid")
	}
	if b.Version < baselineVersion {
		return nil, fmt.Errorf("the baseline has an old format (version %d)", b.Version)
	}
	return &b, nil
}

func compare(old, now map[string]string) (added, removed, modified []string) {
	for p, h := range now {
		if o, ok := old[p]; !ok {
			added = append(added, p)
		} else if o != h {
			modified = append(modified, p)
		}
	}
	for p := range old {
		if _, ok := now[p]; !ok {
			removed = append(removed, p)
		}
	}
	sort.Strings(added)
	sort.Strings(removed)
	sort.Strings(modified)
	return
}

func short(s string) string {
	if len(s) > 12 && !strings.HasPrefix(s, "link:") {
		return s[:12]
	}
	return s
}

// describe says what is different between two entries.
func describe(old, now string) string {
	if strings.HasPrefix(old, "link:") || strings.HasPrefix(now, "link:") {
		return short(old) + " -> " + short(now)
	}
	o, n := strings.Fields(old), strings.Fields(now)
	if len(o) != 3 || len(n) != 3 {
		return "changed"
	}
	var parts []string
	if o[0] != n[0] {
		parts = append(parts, "content "+short(o[0])+" -> "+short(n[0]))
	}
	if o[1] != n[1] {
		parts = append(parts, "mode "+o[1]+" -> "+n[1])
	}
	if o[2] != n[2] {
		parts = append(parts, "owner "+o[2]+" -> "+n[2])
	}
	if len(parts) == 0 {
		return "changed"
	}
	return strings.Join(parts, "; ")
}

func isSetuid(entry string) bool {
	f := strings.Fields(entry)
	if len(f) != 3 {
		return false
	}
	m, err := strconv.ParseUint(f[1], 8, 32)
	return err == nil && m&06000 != 0
}

// The baseline in use by the daemon (replaced, never modified, when the package manager finishes).
var (
	curMu sync.RWMutex
	cur   *baseline
)

func getCur() *baseline  { curMu.RLock(); defer curMu.RUnlock(); return cur }
func setCur(b *baseline) { curMu.Lock(); cur = b; curMu.Unlock() }

// ---------------------------------------------------------------------------- logging and alerts

func initLogger() {
	var w io.Writer = os.Stderr // under systemd stderr goes to the journal
	if f, err := os.OpenFile(*logFlag, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644); err == nil {
		w = io.MultiWriter(f, os.Stderr)
	}
	logger = log.New(w, "[HIDS] ", log.LstdFlags)
}

var (
	alertMu  sync.Mutex
	reported = map[string]string{} // path -> the state already reported, so the same change is not announced twice
)

func resetReported() { alertMu.Lock(); reported = map[string]string{}; alertMu.Unlock() }
func clearReported(path string) {
	alertMu.Lock()
	delete(reported, path)
	alertMu.Unlock()
}

func alert(kind, path, detail string) {
	key := kind + "|" + detail
	crit := isCritical(path) || strings.HasPrefix(kind, "NEW SETUID")
	alertMu.Lock()
	if reported[path] == key {
		alertMu.Unlock()
		return
	}
	reported[path] = key
	alertMu.Unlock()

	msg := kind + " " + path
	if detail != "" {
		msg += " (" + detail + ")"
	}
	if crit {
		msg = "[CRITICAL] " + msg // hids-notify shows these as urgent popups
	}
	logger.Printf("ALERT %s", msg)
}

func alertNew(path, entry string) {
	if isSetuid(entry) {
		f := strings.Fields(entry)
		alert("NEW SETUID FILE", path, "mode "+f[1]+" owner "+f[2])
		return
	}
	alert("new file", path, "")
}

// ---------------------------------------------------------------------------- package manager awareness

// busy reports whether another process (dpkg, apt, unattended-upgrades) holds one of the lock files.
func busy() bool {
	for _, l := range strings.Split(*locksFlag, ",") {
		f, err := os.Open(strings.TrimSpace(l))
		if err != nil {
			continue
		}
		fl := syscall.Flock_t{Type: syscall.F_RDLCK}
		err = syscall.FcntlFlock(f.Fd(), syscall.F_GETLK, &fl)
		f.Close()
		if err == nil && fl.Type != syscall.F_UNLCK {
			return true
		}
	}
	return false
}

// ---------------------------------------------------------------------------- modes

// verifyAgainst compares the whole system with b, raises an alert for every difference and returns their number.
func verifyAgainst(b *baseline) int {
	now := snapshot()
	added, removed, modified := compare(b.Files, now)
	for _, p := range modified {
		alert("modified", p, describe(b.Files[p], now[p]))
	}
	for _, p := range added {
		alertNew(p, now[p])
	}
	for _, p := range removed {
		alert("removed", p, "")
	}
	return len(added) + len(removed) + len(modified)
}

var checking atomic.Bool

// fullCheck verifies everything now (random timer, lost inotify events). Only one at a time.
func fullCheck(why string) {
	if !checking.CompareAndSwap(false, true) {
		return
	}
	defer checking.Store(false)
	if busy() {
		logger.Printf("INFO %s check skipped: the package manager is working", why)
		return
	}
	b := getCur()
	if b == nil {
		return
	}
	if n := verifyAgainst(b); n == 0 {
		logger.Printf("INFO %s check: %d files unchanged", why, len(b.Files))
	} else {
		logger.Printf("WARN %s check: %d difference(s) from the baseline of %s", why, n, b.Created)
	}
}

func runCheck() int {
	b, err := loadBaseline()
	if err != nil {
		fmt.Fprintf(os.Stderr, "no usable baseline (%s): run with -init first\n", err)
		return 2
	}
	now := snapshot()
	added, removed, modified := compare(b.Files, now)
	for _, p := range modified {
		fmt.Printf("modified: %s (%s)\n", p, describe(b.Files[p], now[p]))
	}
	for _, p := range added {
		if isSetuid(now[p]) {
			fmt.Println("NEW SETUID FILE:", p)
		} else {
			fmt.Println("new file:", p)
		}
	}
	for _, p := range removed {
		fmt.Println("removed: ", p)
	}
	if len(added)+len(removed)+len(modified) == 0 {
		fmt.Printf("OK: %d files match the baseline of %s\n", len(b.Files), b.Created)
		return 0
	}
	return 1
}

func systemctl(args ...string) { exec.Command("systemctl", args...).Run() } // best effort

// runSeal accepts the present state as the new baseline.
func runSeal() int {
	os.WriteFile(sealMarker, []byte("1"), 0600)
	defer os.Remove(sealMarker)
	systemctl("stop", *serviceFlag)
	b, err := recordBaseline()
	systemctl("start", *serviceFlag)
	if err != nil {
		fmt.Fprintf(os.Stderr, "cannot write the baseline: %v\n", err)
		return 1
	}
	fmt.Printf("[+] System sealed: %d files recorded in %s\n", len(b.Files), dbPath())
	return 0
}

// runStopped is called by systemd after the daemon stopped. A stop by "systemctl stop" is exactly what an intruder
// would do, so it is an alarm unless the system is shutting down or -seal is working.
func runStopped() {
	initLogger()
	if _, err := os.Stat(sealMarker); err == nil {
		logger.Println("INFO daemon stopped for a re-seal")
		return
	}
	if out, _ := exec.Command("systemctl", "is-system-running").Output(); strings.TrimSpace(string(out)) == "stopping" {
		logger.Println("INFO daemon stopped (system shutdown)")
		return
	}
	res, code := os.Getenv("SERVICE_RESULT"), os.Getenv("EXIT_STATUS")
	logger.Printf("ALERT [CRITICAL] the watcher stopped (result=%s exit=%s): nobody is watching until it starts again", res, code)
}

func isInteresting(path string, files map[string]bool, roots []string) bool {
	if files[path] {
		return true
	}
	for _, r := range roots {
		if path == r || strings.HasPrefix(path, r+"/") {
			return true
		}
	}
	return false
}

// ---------------------------------------------------------------------------- inotify (standard library only)

const inMask = syscall.IN_CLOSE_WRITE | syscall.IN_CREATE | syscall.IN_DELETE | syscall.IN_MOVED_FROM |
	syscall.IN_MOVED_TO | syscall.IN_ATTRIB | syscall.IN_DELETE_SELF | syscall.IN_MOVE_SELF

type fsEvent struct {
	path  string
	op    string
	isDir bool
}

type watcher struct {
	fd     int
	wds    map[int]string    // watch descriptor -> folder; touched by run() only, after start-up
	want   func(string) bool // should a new folder be watched?
	failed int               // folders that could not be watched (inotify limit)
}

func newWatcher() (*watcher, error) {
	fd, err := syscall.InotifyInit1(syscall.IN_CLOEXEC)
	if err != nil {
		return nil, err
	}
	return &watcher{fd: fd, wds: map[int]string{}}, nil
}

func (w *watcher) add(dir string) {
	if wd, err := syscall.InotifyAddWatch(w.fd, dir, inMask); err == nil {
		w.wds[wd] = dir
	} else {
		w.failed++
	}
}

func (w *watcher) addTree(root string) {
	filepath.Walk(root, func(p string, i os.FileInfo, err error) error {
		if err == nil && i.IsDir() {
			w.add(p)
		}
		return nil
	})
}

func opName(m uint32) string {
	switch {
	case m&(syscall.IN_CREATE|syscall.IN_MOVED_TO) != 0:
		return "created"
	case m&(syscall.IN_DELETE|syscall.IN_MOVED_FROM|syscall.IN_DELETE_SELF|syscall.IN_MOVE_SELF) != 0:
		return "removed"
	case m&syscall.IN_CLOSE_WRITE != 0:
		return "modified"
	}
	return "attributes changed"
}

// run reads inotify events for ever and sends them to out; new folders are watched as they appear, and the files
// already inside them are reported (they may have been created before the watch existed).
func (w *watcher) run(out chan<- fsEvent) {
	buf := make([]byte, 64*1024)
	for {
		n, err := syscall.Read(w.fd, buf)
		if err != nil {
			if err == syscall.EINTR {
				continue
			}
			close(out)
			return
		}
		for off := 0; off+syscall.SizeofInotifyEvent <= n; {
			wd := int(int32(binary.NativeEndian.Uint32(buf[off:])))
			mask := binary.NativeEndian.Uint32(buf[off+4:])
			nameLen := int(binary.NativeEndian.Uint32(buf[off+12:]))
			name := ""
			if nameLen > 0 {
				name = strings.TrimRight(string(buf[off+syscall.SizeofInotifyEvent:off+syscall.SizeofInotifyEvent+nameLen]), "\x00")
			}
			off += syscall.SizeofInotifyEvent + nameLen
			if mask&syscall.IN_Q_OVERFLOW != 0 {
				out <- fsEvent{op: "overflow"}
				continue
			}
			if mask&syscall.IN_IGNORED != 0 {
				delete(w.wds, wd)
				continue
			}
			dir, ok := w.wds[wd]
			if !ok {
				continue
			}
			path := dir
			if name != "" {
				path = filepath.Join(dir, name)
			}
			isDir := mask&syscall.IN_ISDIR != 0
			if isDir && mask&(syscall.IN_CREATE|syscall.IN_MOVED_TO) != 0 && (w.want == nil || w.want(path)) {
				w.addTree(path)
				filepath.Walk(path, func(p string, i os.FileInfo, err error) error {
					if err == nil && !i.IsDir() {
						out <- fsEvent{path: p, op: "created"}
					}
					return nil
				})
			}
			out <- fsEvent{path: path, op: opName(mask), isDir: isDir}
		}
	}
}

// handleEvent looks at what really happened to a path and alerts only if it differs from the baseline.
func handleEvent(ev fsEvent) {
	b := getCur()
	if b == nil {
		return
	}
	old, known := b.Files[ev.path]
	now, exists := entryOf(ev.path)
	switch {
	case !exists:
		if known {
			alert("removed", ev.path, "")
		}
	case !known:
		alertNew(ev.path, now)
	case old != now:
		alert("modified", ev.path, describe(old, now))
	default:
		clearReported(ev.path) // back to the baseline (or just touched): nothing to say
	}
}

// ancestorOf reports whether path is a folder above one of the roots (it may have to be watched when it appears).
func ancestorOf(path string, roots []string) bool {
	for _, r := range roots {
		if strings.HasPrefix(r, path+"/") {
			return true
		}
	}
	return false
}

func nearestExisting(p string) string {
	for p = filepath.Dir(p); p != "/" && p != "."; p = filepath.Dir(p) {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	return ""
}

func watch() {
	initLogger()
	loadExcluded()
	logger.Printf("INFO started (version %s, live session: %v)", version, isLive())

	b, err := loadBaseline()
	if isLive() || err != nil {
		if isLive() {
			logger.Println("INFO live session: taking the baseline now that the system is up")
		} else {
			logger.Printf("WARN no usable baseline (%v): creating one now (first start, trusted as it is)", err)
		}
		nb, werr := recordBaseline()
		if werr != nil {
			logger.Printf("ERROR cannot write the baseline (using it from memory): %v", werr)
		} else {
			logger.Printf("INFO baseline recorded: %d files", len(nb.Files))
		}
		setCur(nb)
	} else {
		setCur(b)
		go func() { // do not delay the watching: hashing can take a few seconds
			if n := verifyAgainst(b); n == 0 {
				logger.Printf("INFO baseline of %s verified: %d files unchanged", b.Created, len(b.Files))
			} else {
				logger.Printf("WARN %d difference(s) from the baseline of %s", n, b.Created)
			}
		}()
	}

	w, err := newWatcher()
	if err != nil {
		log.Fatal(err)
	}
	files := map[string]bool{}
	var roots []string
	for _, t := range targets() {
		info, err := os.Lstat(t)
		switch {
		case err != nil: // not there yet: watch the nearest existing folder above it, so its creation is noticed
			roots = append(roots, t)
			if p := nearestExisting(t); p != "" {
				w.add(p)
			}
		case info.IsDir():
			roots = append(roots, t)
			w.addTree(t)
		default:
			files[t] = true
			w.add(filepath.Dir(t)) // watch the folder: tools replace /etc/passwd by renaming a new file over it
		}
	}
	w.want = func(p string) bool { return isInteresting(p, files, roots) || ancestorOf(p, roots) }
	if w.failed > 0 {
		logger.Printf("WARN %d folders could not be watched (inotify limit?): the random full check still covers them", w.failed)
	}
	logger.Printf("INFO watching with inotify (%d folders)", len(w.wds))

	events := make(chan fsEvent, 1024)
	go w.run(events)

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGTERM, syscall.SIGINT)
	go func() {
		s := <-sig
		logger.Printf("INFO stopping (%v)", s)
		os.Exit(0)
	}()

	go func() { // a full check at random times: nothing to find and nothing to delete for an intruder
		for {
			time.Sleep(time.Duration(60+rand.IntN(121)) * time.Minute)
			fullCheck("periodic")
		}
	}()

	pkgActive, pkgChanged := false, 0
	tick := time.NewTicker(3 * time.Second)
	defer tick.Stop()
	for {
		select {
		case ev, ok := <-events:
			if !ok {
				logger.Println("ERROR inotify stopped")
				return
			}
			if ev.op == "overflow" {
				logger.Println("WARN too many events at once: checking everything now")
				go fullCheck("overflow")
				continue
			}
			if ev.isDir || excluded[ev.path] || !isInteresting(ev.path, files, roots) {
				continue
			}
			if busy() {
				pkgActive = true
				pkgChanged++
				continue
			}
			handleEvent(ev)
		case <-tick.C:
			if pkgActive && !busy() {
				logger.Printf("INFO package manager finished (%d changes): refreshing the baseline", pkgChanged)
				nb, err := recordBaseline()
				if err != nil {
					logger.Printf("ERROR cannot refresh the baseline on disk (using it from memory): %v", err)
				}
				setCur(nb)
				resetReported()
				pkgActive, pkgChanged = false, 0
			} else if !pkgActive && busy() {
				pkgActive = true
			}
		}
	}
}

func main() {
	flag.Parse()
	loadExcluded()
	switch {
	case *showVer:
		fmt.Println("hids", version)
	case *doInit:
		b, err := recordBaseline()
		if err != nil {
			fmt.Fprintf(os.Stderr, "cannot write the baseline: %v\n", err)
			os.Exit(1)
		}
		fmt.Printf("[+] Baseline recorded: %d files in %s\n", len(b.Files), dbPath())
	case *doCheck:
		os.Exit(runCheck())
	case *doWatch:
		watch()
	case *doSeal:
		os.Exit(runSeal())
	case *doStopped:
		runStopped()
	default:
		flag.Usage()
		os.Exit(2)
	}
}
