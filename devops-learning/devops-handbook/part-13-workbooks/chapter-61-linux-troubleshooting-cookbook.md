# Chapter 61: Linux Production Troubleshooting Cookbook

*DevOps Handbook — Pages 299–308 of this PDF edition*

*DevOps Handbook — Workbook*
---

## 61.1 How production Linux failures actually present

Production troubleshooting is not a catalog of commands. It is a **hypothesis loop**: observe a symptom, bound the blast radius, pick the layer most likely to explain the symptom, gather *just enough* evidence to confirm or reject the hypothesis, then either remediate or escalate with a timeline. Engineers who jump straight to `reboot` or `kill -9` often destroy the only evidence that would have prevented a repeat incident.

This workbook is written for on-call engineers who already know `ps`, `systemctl`, and `journalctl` from earlier chapters, but who now must **debug under time pressure** on a host that still has customers on it. The goal is a repeatable cookbook: boot problems, disk exhaustion, memory pressure, systemd unit failures, syscall-level debugging with `strace`, journald pitfalls, and performance isolation (CPU, I/O, network, lock contention).

Treat every host as if it will be the only copy of the truth. Preserve logs, `dmesg`, systemd unit files, and a process dump *before* you restart a flapping service. If the machine is a cloud VM, snapshot the disk only when that is cheaper than losing forensic data—not as a reflex.

| Symptom class | First question | Typical layer |
|---------------|----------------|---------------|
| Instance unreachable on SSH | Is it the host, the network path, or sshd? | Boot, cloud networking, sshd |
| Service “up” but returning 5xx | Is the process listening, healthy, or blocked? | Application, systemd, sockets |
| Gradual slowdown | CPU, memory reclaim, disk latency, or lock wait? | Performance |
| Sudden full stop | Kernel panic, OOM, disk full, or fencing? | Kernel / resources |
| Intermittent | Clock skew, DNS, retries, or GC? | Cross-cutting |

---

## 61.2 A 90-second triage sequence

When a page fires, run a **fixed 90-second pass** before improvising. Muscle memory beats ad-hoc curiosity at 03:00.

```bash
# Identity and time (clock skew hides causality)
hostnamectl; date -u; timedatectl status

# Load vs CPU vs I/O wait (the three are not the same)
uptime
vmstat 1 5
mpstat -P ALL 1 5

# Memory and reclaim
free -h
ps aux --sort=-%mem | head -20

# Disk pressure
df -hT
df -i
iostat -xz 1 5

# Who is waiting on what
ss -lntup
systemctl --failed
journalctl -p err -b --no-pager | tail -80
dmesg -T | tail -80
```

Interpret **load average** correctly. Load is the run-queue length plus uninterruptible sleep (`D` state). A load of 40 on a 4-vCPU box can mean CPU saturation *or* disks stuck in I/O wait. `vmstat`’s `r` (runnable) versus `b` (blocked) column splits those worlds. High `wa` in `top`/`vmstat` is disk or NFS, not “the CPU is busy.”

| Signal | Meaning | Next tool |
|--------|---------|-----------|
| High `r`, low `b`, high `%usr` | CPU-bound user work | `perf top`, language profiler |
| High `r`, high `%sys` | Kernel/syscall heavy | `perf`, `strace`, `bpftrace` |
| High `b`, high `wa` | I/O wait | `iostat`, `iotop`, `blktrace` |
| `si`/`so` climbing | Swap thrash | `free`, OOM history, cgroup limits |
| Failed units | systemd did not reach active | `systemctl status`, journal |

Lab machines and production hosts differ in one critical way: **cgroups**. A process can be OOM-killed inside a slice while the host still has free RAM. Always check both `free` and cgroup memory files (or `systemd-cgtop`) before declaring “plenty of memory.”

---

## 61.3 Boot failures: from firmware to multi-user.target

Boot issues split into **the kernel never starts**, **the kernel starts but root does not mount**, and **userspace starts but the service graph never reaches a useful target**. Cloud serial consoles (`aws ec2 get-console-output`, GCP serial port, Azure boot diagnostics) are mandatory; SSH is often unavailable.

### 61.3.1 GRUB, initramfs, and rootfs

If the instance sits on a GRUB prompt, the bootloader cannot find a kernel or the `root=` argument is wrong after a volume attach. For systemd-based distros, an emergency shell often means `/` mounted read-only or a failed local-fs target.

```bash
# From a rescue ISO or serial emergency shell
cat /proc/cmdline
lsblk -f
blkid
findmnt
journalctl -b -o short-precise | head -200
systemctl list-jobs
systemctl status local-fs.target
```

Common production causes:

| Cause | Evidence | Remediation pattern |
|-------|----------|---------------------|
| Wrong UUID after disk clone | `root=` UUID missing in `blkid` | Fix fstab/GRUB, regenerate initramfs |
| Full `/` during upgrade | `No space left` in journal *during* boot | Rescue, clear logs/journal, complete package tx |
| Corrupt filesystem | `XFS (dm-0): Corruption detected` | `xfs_repair`/`fsck` on **unmounted** volume |
| SELinux relabel loop | `.autorelabel` present, boot loops | Fix labels, disable temporarily only with ticket |
| Initramfs missing modules | Drop to initramfs, cannot find root | Rebuild initramfs with storage/virtio modules |

Never `fsck` a mounted XFS/ext4 volume “to save time.” That is how you convert a recoverable filesystem into a support-escalation.

### 61.3.2 systemd boot graph

```bash
systemd-analyze blame
systemd-analyze critical-chain
systemctl list-dependencies multi-user.target
systemctl list-units --failed
systemctl cat sshd.service
```

A unit stuck in `activating` with a slow `ExecStartPre` (for example a network mount) blocks dependents. `TimeoutStartSec` defaults are easy to miss: a unit can be killed and restarted forever, looking like a crashloop even though the binary is fine.

**Emergency vs rescue vs single-user:** `rescue.target` starts a root shell with more of the system; `emergency.target` is closer to a sulogin on the root fs. Know which one your AMI actually provides over serial.

---

## 61.4 Disk: capacity, inodes, mounts, and silent I/O errors

“Disk full” is three different problems: **bytes**, **inodes**, and **the filesystem the application actually writes to** (bind mounts, overlay, `/var/lib/docker`, NFS).

```bash
df -hT
df -i
du -xhd1 /var | sort -h
lsof +L1 | head          # deleted-but-open files still holding space
findmnt -T /var/lib/app
ls -l /proc/<pid>/fd | grep deleted
```

Deleted-but-open files are the classic “`df` shows 100% after we truncated logs” failure. Restart the process (or send it a reopen signal) after truncating; otherwise the inode stays allocated.

### 61.4.1 Latency vs capacity

A volume at 40% full can still be **latency-dead** because of gp2 burst credits, a noisy neighbor on shared SAN, or a RAID rebuild. `iostat -xz` fields that matter in production:

| Field | Why it matters |
|-------|----------------|
| `%util` | Device busy time; 100% means the queue is never idle |
| `await` | Average wait including queue time |
| `svctm` (older iostat) | Misleading; prefer `await` + histogram tools |
| `avgqu-sz` | Queue depth building up |
| `r/s` `w/s` | Ops mix; random small writes hurt HDDs and some SSDs |

```bash
iostat -xz 1
pidstat -d 1
iotop -oPa
# Find which file is hot (needs debugfs / bcc)
# sudo /usr/share/bcc/tools/fileslower 10
```

**Read-only remounts** after I/O errors appear in `dmesg` as `Remounting filesystem read-only`. Applications then fail with `EROFS`. Check cloud volume health, cable/virtio errors, and whether the instance hit an underlying storage incident. Remounting rw without fixing the device is gambling.

### 61.4.2 LVM, thin pools, and container disks

Docker/containerd overlay plus a thin LVM pool can report space in three places at once. Always map:

```bash
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT,UUID
vgs; lvs -a
docker system df          # if Docker is in the path
crictl df                 # kubelet/containerd nodes
```

---

## 61.5 Memory: userspace leaks, reclaim, and the OOM killer

Memory troubleshooting starts by separating **anonymous RSS**, **file cache**, **slab**, **swap**, and **cgroup limits**. `free -h` showing “available” memory is not a promise your JVM can allocate a 4 GiB heap.

```bash
free -h
cat /proc/meminfo
ps -eo pid,user,rss,vsz,cmd --sort=-rss | head -20
smem -k -s rss           # if installed; better proportional set size
systemd-cgtop -m
cat /sys/fs/cgroup/memory/memory.stat   # v1
cat /sys/fs/cgroup/system.slice/memory.current  # v2 example
```

### 61.5.1 OOM killer forensics

When the kernel OOM-kills, the victim is chosen by **oom_score** (adjusted by `oom_score_adj`). The log line lives in `dmesg`/`journalctl -k`, not in the application log.

```bash
journalctl -k -b | grep -i -E 'out of memory|killed process|oom'
dmesg -T | grep -i oom
ps -eo pid,comm,oom_score,oom_score_adj,rss --sort=-oom_score | head
```

Record: which PID died, total pages, cgroup, and whether `memory.oom.group` killed an entire cgroup (common under systemd and Kubernetes). Restarting the service without raising the limit or fixing the leak only schedules the next page.

### 61.5.2 Leak versus cache versus fragmentation

| Pattern | Cache reclaimable? | Typical cause |
|---------|--------------------|---------------|
| RSS climbs, never falls | No | Leak, unbounded cache in-process |
| `Cached` high, `Available` healthy | Yes | Linux using RAM as page cache (good) |
| `SUnreclaim` high | No | Kernel slab leak / module issue |
| High `Committed_AS` vs RAM+swap | Overcommit | Fork bombs, huge reservations |
| `Dirty` stuck high | Writeback stuck | Slow disk or frozen NFS |

Transparent Huge Pages (THP) can add latency for databases; `anon_transparent_hugepages` in `perf` traces and `/sys/kernel/mm/transparent_hugepage/enabled` belong in the MongoDB/Redis/PostgreSQL runbook.

---

## 61.6 systemd unit failures in production

`systemctl status` is the start, not the end. Read the **full** unit (drop-ins included), the cgroup, the last 200 journal lines, and whether the unit is **masked**, **static**, or **enabled**.

```bash
systemctl status app.service -l --no-pager
systemctl cat app.service
systemctl show app.service -p ActiveState,SubState,Result,ExecMainStatus,NRestarts
ls /etc/systemd/system/app.service.d/
journalctl -u app.service -b --no-pager
systemd-cgls
```

### 61.6.1 Types, restart loops, and sandboxing

| `Type=` | Failure mode if wrong |
|---------|------------------------|
| `simple` | Forking daemon looks “active” then parent exits; children unreaped |
| `forking` | PIDFile missing → systemd loses the daemon |
| `notify` | App never sends `READY=1` → start timeout |
| `oneshot` | RemainAfterExit mis-set → confusing active state |

```ini
[Service]
Type=notify
WatchdogSec=30
Restart=on-failure
RestartSec=3
StartLimitBurst=5
StartLimitIntervalSec=60
MemoryMax=2G
TasksMax=4096
```

`StartLimitBurst` combined with `Restart=always` produces **start-limit-hit**: the unit goes `failed` and stays down until `systemctl reset-failed`. That looks like “systemd randomly stopped us” in incident reports.

Sandboxing (`ProtectSystem`, `PrivateTmp`, `NoNewPrivileges`, `CapabilityBoundingSet`) causes mysterious `EACCES` that developers reproduce “fine on the laptop.” Compare `systemd-analyze security app.service` and the actual `openat` failures in `strace`.

### 61.6.2 Timers versus cron

Prefer systemd timers for host-local jobs you must observe. `systemctl list-timers --all` shows last/next; missed timers after a long shutdown do not always catch up (`Persistent=`). Cron failures often go only to local mail that nobody reads.

---

## 61.7 strace, lsof, and syscall-level truth

When logs lie (“connection refused” that is actually `EPERM` from a security module, or a hang that is a blocking `read` on a FIFO), **syscalls do not lie**.

```bash
# Attach to a running PID; follow clones
strace -f -tt -T -p <pid> -o /tmp/app.strace

# Start the binary under strace (captures startup)
strace -f -tt -T -s 200 -o /tmp/start.strace /usr/bin/app --config /etc/app.yaml

# Count syscalls (cheap overview)
strace -c -p <pid>

# Only network-ish calls
strace -e trace=network,file -p <pid>
```

Read traces with intent:

| Pattern | Interpretation |
|---------|----------------|
| Repeating `restart_syscall` / `futex` | Waiting on a lock or condition |
| `connect` → `EINPROGRESS` → long poll | Network stall or blackhole |
| `openat` → `ENOENT` | Missing file; check cwd vs unit WorkingDirectory |
| `openat` → `EACCES`/`EPERM` | DAC, LSM, or systemd hardening |
| `write` → `EPIPE` | Peer closed; often a proxy or sidecar |
| `recvfrom` returning 0 | Orderly TCP close |

`strace` has overhead. On a latency-sensitive process, sample with `perf`/`bpftrace` or use `strace -e` to shrink the filter. Never leave `strace -f` on a multi-threaded JVM in production for more than a brief window.

Complementary tools:

```bash
lsof -p <pid>
lsof -iTCP -sTCP:LISTEN
ls -l /proc/<pid>/cwd /proc/<pid>/root
cat /proc/<pid>/limits
nsenter -t <pid> -n ss -lntp     # same netns as container
```

---

## 61.8 journald: what you think you collected versus what you have

`journalctl` is the default flight recorder on modern distros—until disk quotas, rate limits, or volatile storage throw records away.

```bash
journalctl --disk-usage
systemd-analyze cat-config systemd/journald.conf
ls -l /etc/systemd/journald.conf /etc/systemd/journald.conf.d/
journalctl -u nginx.service --since "2026-09-02 14:00" --until "2026-09-02 15:00"
journalctl -o json-pretty -n 5
journalctl _PID=1234
journalctl -k          # kernel
journalctl --list-boots
```

| Knob | Production effect |
|------|-------------------|
| `Storage=volatile` | Journals gone after reboot—bad for postmortems |
| `SystemMaxUse=` | Old boots vacuumed; “it was fine yesterday” has no log |
| `RateLimitIntervalSec` / `Burst` | Storms of logs disappear during the incident |
| `ForwardToSyslog=` | Split brain if rsyslog also filters |
| vacuuming during incident | `journalctl --vacuum-size=` can delete the outage |

Always pin time windows in **UTC** and record the host timezone in the incident ticket. Use `-o short-iso-precise` when correlating with distributed traces.

For services that log to files *and* journal, decide a single source of truth. Duplicate pipelines create “the dashboard disagrees with the host” arguments.

---

## 61.9 Performance isolation: CPU, scheduler, and off-CPU

CPU troubleshooting is not `top` sorted by `%CPU` forever. You need **on-CPU** versus **off-CPU** (waiting).

```bash
# Quick
pidstat -u 1
perf top -g
perf record -F 99 -g -p <pid> -- sleep 30
perf report --stdio | head -80

# Run queue and scheduler latency (bcc)
# runqlat, runqlen, cpudist
```

**Steal time** (`%st` in `top`/`mpstat`) on noisy hypervisors means you do not own the CPU you paid for. No amount of application tuning fixes steal; move instance family or dedicated hosts.

**Softirq / ksoftirqd** high alongside network load points at packet processing (see Chapter 62). **kworker** + high I/O points at writeback.

Flame graphs ( Brendan Gregg’s method ) remain the fastest way to explain “CPU is 80% and the app is slow”: you may discover JSON parsing, regex, or TLS as the real cost center.

---

## 61.10 Network-adjacent host issues (without replacing packet labs)

Before blaming Kubernetes or the load balancer, prove the **local** stack:

```bash
ip -br a
ip route
ss -s
ss -m                    # socket memory
nstat -az | head
tc qdisc show
iptables -S; nft list ruleset | head
sysctl net.ipv4.tcp_tw_reuse net.core.somaxconn
cat /proc/net/sockstat
```

`SYN backlog` overflows (`ListenDrops`) look like client timeouts while `ss -ltn` still shows the port LISTEN. Tune `somaxconn` *and* the application listen backlog.

Conntrack table full (`nf_conntrack: table full`) drops NEW connections. Check `nf_conntrack_count` versus `nf_conntrack_max`.

---

## 61.11 Filesystem and kernel breadcrumbs you must not skip

```bash
uname -a
cat /proc/cmdline
sysctl vm.swappiness vm.overcommit_memory
lsmod | head
cat /var/log/cloud-init.log | tail   # first-boot identity issues
last -x | head
who -b
```

Kernel regressions after unattended-upgrades are real. Record the running kernel versus the one GRUB will boot next (`rpm -q kernel` / `linux-image` packages). A host that “fails every reboot” may be booting a newly installed kernel with a broken module (NFS, NVIDIA, ZFS).

---

## 61.12 Worked incident: API latency, host looks idle

**Symptom:** p99 API latency 2s; `top` shows 15% CPU; load average 12 on 8 CPUs.

**90-second pass:** `vmstat` shows `b=8`, `wa=40%`. Disk, not CPU.

**iostat:** `await=80ms` on the data volume; `%util=100%`.

**iotop:** `postgres` and `fluent-bit` competing.

**Root cause:** Fluent Bit buffer spilled to disk after a downstream Elasticsearch outage; the same volume hosted PG DATA.

**Fix:** Move logs to a separate volume; backpressure Fluent Bit; add disk latency alerts (`node_disk_io_time_seconds` / `await` recording rules—Chapter 68).

**Lesson:** Resource isolation is a troubleshooting control, not only a capacity plan.

---

## 61.13 Production-safe remediation checklist

1. **Stabilize** — stop the bleeding (shed load, fail over) before deep dives if SLO burn is severe.
2. **Snapshot evidence** — `sosreport`, journal export, `perf`/trace files, `dmesg`.
3. **Change one variable** — do not restart systemd, rotate logs, and scale simultaneously.
4. **Write the timeline in UTC** — include kernel OOM lines and unit `NRestarts`.
5. **Prevent repeat** — cgroup limits, disk alerts on inodes *and* bytes, journal persistence, runbook updates.

```bash
# Evidence bundle (customize; run as root)
mkdir -p /var/tmp/incident-$(date -u +%Y%m%dT%H%M%SZ)
cd /var/tmp/incident-*
hostnamectl > host.txt
date -u > utc.txt
dmesg -T > dmesg.txt
journalctl -b > journal-boot.txt
systemctl --failed > failed-units.txt
ss -lntup > listen.txt
ps auxf > ps.txt
df -hT > df.txt
```

---

## 🧪 Lab 61.1 — Recover a “full disk” that is not full

**Goal:** Experience deleted-open files and inode exhaustion.

1. Create a small loop filesystem and mount it at `/mnt/lab`.
2. Run a Python process that appends to `/mnt/lab/app.log` and never reopens the file.
3. `rm /mnt/lab/app.log` while the process runs. Confirm `df` still shows used space.
4. Use `lsof +L1` and `/proc/<pid>/fd` to identify the deleted file.
5. Restart the process; confirm space returns.
6. Fill the filesystem with many empty files until `df -i` hits 100% while `df -h` still shows free bytes. Observe application `ENOSPC`.

**Write-up:** two paragraphs on why log rotation *must* signal processes (copytruncate vs recreate).

---

## 🧪 Lab 61.2 — systemd start-limit-hit and notify timeout

1. Write a unit with `Type=notify`, `TimeoutStartSec=10`, and a binary that never sends `sd_notify`.
2. Watch it hit start timeout and restart until `start-limit-hit`.
3. Fix with `Type=simple` *or* a real notify, then `systemctl reset-failed`.
4. Add `MemoryMax=` and a memory hog; capture the OOM journal line and cgroup event.

---

## 🧪 Lab 61.3 — strace a hanging CLI

1. Create a FIFO (`mkfifo /tmp/block`) and a script that reads from it.
2. Start the script; it hangs. `strace -p` and identify the blocking `read`.
3. Write to the FIFO; observe the syscall return.
4. Repeat with a TCP `nc -l` server you never connect to; contrast `connect` hang vs `read` hang.

---

## 61.14 Chapter map: tools versus questions

| Question | Tools |
|----------|--------|
| Did the kernel see the failure? | `dmesg`, `journalctl -k` |
| Did systemd intend this state? | `systemctl show/cat`, failed units |
| Is it bytes, inodes, or latency? | `df`, `iostat`, `lsof` |
| Is it this cgroup or the host? | `systemd-cgtop`, cgroup fs |
| What syscall is stuck? | `strace`, `lsof`, `bpftrace` |
| Are logs actually retained? | journal disk usage, rate limits |
| CPU or wait? | `vmstat`, `perf`, run-queue tracers |

---

## Review questions

1. Why can load average be high while `%CPU` in `top` looks low? Which `vmstat` columns separate the cases?
2. A volume shows 20% used but PostgreSQL commit latency exploded. Which metrics do you collect before blaming the query planner?
3. Explain `start-limit-hit`. Which two unit settings interact to produce it, and how do you recover without rebooting?
4. After `rm logfile`, `df` still shows 100%. What happened, and how do you prove it?
5. Where do you find evidence that the OOM killer ran inside a cgroup rather than at the host level?
6. Give two reasons `strace -f` on a production JVM can make the incident worse. What would you use instead for a 30-second profile?
7. `journalctl` has no logs from the outage window after a reboot. List three `journald.conf` causes.
8. A unit fails with `EACCES` opening `/tmp/app.sock`. The binary works under the same user in a shell. What systemd features do you inspect first?
9. How do you distinguish “sshd is down” from “the instance never reached network-online” using only serial console and systemd?
10. Design a 90-second triage for “intermittent 502 from the box behind the NLB.” Include one CPU check, one disk check, one socket check, and one journal check.

---

## Further practice

Pair this chapter with Chapter 6 (systemd fundamentals), Chapter 7 (Linux networking CLI), and Chapter 62 (packet labs). The host cookbook ends where the packet leaves the NIC; do not skip that boundary during real incidents.
