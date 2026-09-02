# Chapter 72: Linux Command Encyclopedia

This encyclopedia is organized by job, not by man-page section. Every command includes a realistic flag set and a note on when *not* to use it. Copy, adapt, and keep a local cheatsheet—do not run destructive examples on production without a change window.

Conventions used throughout:

| Marker | Meaning |
|--------|---------|
| `#` | root or sudo implied |
| `$` | unprivileged |
| `HOST` | replace with a real hostname |
| Never pipe to `rm` | shown as anti-patterns |

---

## 72.1 Files, directories, and permissions

### Listing and identifying

```bash
ls -lah --time-style=long-iso /var/log
ls -li file                  # inode
stat file                    # timestamps, inode, links
file /usr/sbin/sshd          # type
namei -lx /var/run/docker.sock
tree -L 2 -h /opt            # if installed
```

`ls` colors and aliases can hide the real binary—use `/bin/ls` when debugging scripts.

### Copy, move, sync

```bash
cp -a src dest               # archive: sparse, xattrs, links
cp --reflink=auto big.img /mnt/fast/
mv old new
rsync -aHAX --info=progress2 src/ dest/
rsync -a --delete --dry-run src/ dest/
install -m 0755 -o root -g root bin /usr/local/bin/tool
```

`cp -a` vs `rsync`: rsync is resumable and can exclude. Never rsync a live database directory and expect consistency.

### Find and locate

```bash
find /var -xdev -type f -mtime +30 -name '*.log' -print
find / -xdev -type f -size +100M -printf '%s %p\n' | sort -n | tail
find /home -type f -perm -4000 -ls
find /tmp -type f -name '*.tmp' -mtime +7 -delete   # careful
locate nginx.conf            # updatedb required
```

Always `-xdev` on huge hosts to stay on one filesystem. `find -delete` is easy to invert—preview with `-print` first.

### Permissions and ownership

```bash
chmod 0640 file
chmod u=rw,g=r,o= file
chmod -R a+rX directory      # X: execute only on dirs/already-exec
chown -R app:app /var/lib/app
chgrp ops file
umask 027
getfacl file
setfacl -m u:alice:r file
setfacl -x u:alice file
lsattr file
chattr +i /etc/resolv.conf   # immutable; remember to -i later
```

| Mode | Meaning |
|------|---------|
| 0644 | file rw-r--r-- |
| 0755 | dir/exec rwxr-xr-x |
| 0750 | group-only traverse |
| 2775 | setgid directory (group inheritance) |
| 1777 | sticky `/tmp` |

### Links and special files

```bash
ln target hardlink
ln -s /opt/app/current /opt/app/live
readlink -f /opt/app/live
mkfifo /tmp/log.pipe
mknod
```

### Disk usage

```bash
df -hT
df -i
du -xhd1 /var | sort -h
ncdu /var                    # interactive
lsblk -f
blkid
findmnt
mount | column -t
```

Deleted-open files:

```bash
lsof +L1
# truncate without restart (emergency)
: > /proc/PID/fd/N
```

---

## 72.2 Text, logs, and data wrangling

```bash
grep -Rni --exclude-dir=.git 'ERROR' /var/log/app
grep -E '^(5[0-9]{2})' access.log
rg -n 'panic' --type go      # ripgrep if installed
sed -n '100,140p' file
sed -i.bak 's/foo/bar/g' file
awk '{print $1, $NF}' access.log
awk -F, '$3>100 {s+=$3} END{print s}' metrics.csv
cut -d: -f1 /etc/passwd
sort -u | uniq -c | sort -nr
head -n 50; tail -n 50; tail -F /var/log/syslog
less +F file                 # follow in less
column -t
paste
join -t, file1 file2
comm -12 a b
diff -u old new
diff -rq dir1 dir2
csplit
tr '[:upper:]' '[:lower:]'
rev
wc -lwc file
sha256sum file
base64 -w0 file
jq '.items[].metadata.name' list.json
yq e '.spec.replicas' deploy.yaml
```

Log triage pattern:

```bash
journalctl -u nginx --since '10 min ago' -o json | jq -r .MESSAGE
awk '{print $1}' access.log | sort | uniq -c | sort -nr | head
```

Do not `cat file | grep`. Use `grep pattern file`. Do not `cat huge | awk` when `awk` can read the file.

Python one-liners when awk gets painful:

```bash
python3 -c 'import sys,json; print(json.load(sys.stdin)["version"])'
```

---

## 72.3 Processes, jobs, and resource use

```bash
ps auxf
ps -eo pid,ppid,user,stat,pcpu,pmem,wchan:20,cmd --sort=-pcpu | head
pstree -p
top
htop
pidstat -u -r -d 1
mpstat -P ALL 1
vmstat 1
iostat -xz 1
uptime
free -h
slabtop
watch -n1 'ps -p $(pgrep -d, nginx) -o pid,pcpu,rss,cmd'
```

Signals:

```bash
kill -TERM PID
kill -INT PID
kill -HUP PID                # reload if the app supports it
kill -USR1 PID
kill -9 PID                  # last resort
pkill -f 'gunicorn: worker'
killall -v nginx
```

Job control (interactive):

```bash
command &
jobs
fg %1
bg %1
disown -h %1
nohup ./long.sh > /tmp/out 2>&1 &
timeout 30s ./flaky
stdbuf -oL ./app | tee log
```

`nice`/`ionice`:

```bash
nice -n 19 ./batch
renice -n 5 -p PID
ionice -c3 -p PID            # idle IO class
```

`strace` / `lsof`:

```bash
strace -f -e trace=network,file -p PID
strace -c ./binary           # syscall time summary
lsof -p PID
lsof -iTCP:5432 -sTCP:ESTABLISHED
lsof +D /var/lib/app         # slow on large trees
```

`/proc` gems:

```bash
cat /proc/PID/cmdline | tr '\0' ' '; echo
cat /proc/PID/environ | tr '\0' '\n'
ls -l /proc/PID/fd
cat /proc/PID/status         # NStgid, Seccomp, Cpus_allowed
cat /proc/PID/io
cat /proc/PID/limits
cat /proc/PID/cgroup
cat /proc/net/tcp
```

---

## 72.4 systemd and the journal

```bash
systemctl list-units --type=service --state=running
systemctl status ssh.service
systemctl cat ssh.service
systemctl show ssh.service -p MainPID -p ActiveState
systemctl daemon-reload
systemctl restart ssh
systemctl reload nginx
systemctl enable --now foo
systemctl mask foo           # stronger than disable
systemctl reset-failed
systemctl list-timers
systemd-analyze blame
systemd-analyze critical-chain
systemd-analyze security ssh.service
```

Journal:

```bash
journalctl -u ssh -b --no-pager
journalctl -u ssh --since '2026-09-01 00:00:00'
journalctl -k -b             # kernel
journalctl -p err..alert
journalctl -f
journalctl --disk-usage
journalctl --vacuum-size=200M
```

Unit snippet (drop-in):

```bash
systemctl edit app.service
```

```ini
[Service]
Environment=GOMAXPROCS=4
LimitNOFILE=65535
Restart=on-failure
RestartSec=3
WatchdogSec=30
```

Timers instead of cron:

```ini
# /etc/systemd/system/backup.timer
[Timer]
OnCalendar=*-*-* 02:30:00
Persistent=true
[Install]
WantedBy=timers.target
```

---

## 72.5 Users, auth, and sudo

```bash
id
who; w; last -a | head
getent passwd app
getent group sudo
useradd -m -s /bin/bash -G ops alice
usermod -aG docker alice
passwd alice
chage -l alice
visudo
sudo -l
sudo -u app -H bash -l
```

`/etc/sudoers.d/` example:

```
alice ALL=(root) NOPASSWD: /usr/bin/systemctl restart nginx
```

SSH:

```bash
sshd -T | grep -E 'permitroot|passwordauth|pubkey'
ssh-keygen -t ed25519 -a 100
ssh-copy-id -i ~/.ssh/id_ed25519.pub HOST
ssh -o StrictHostKeyChecking=accept-new HOST
```

---

## 72.6 Networking

### Addressing and routes

```bash
ip -br a
ip -d link
ip route
ip route get 1.1.1.1
ip rule
ip neigh
bridge link
```

`ifconfig`/`route` are legacy. Prefer `ip`.

### Sockets

```bash
ss -lntp
ss -s
ss -ti
ss -o state time-wait
ss -tn dst :443
```

### DNS and HTTP

```bash
dig +trace example.com
dig @1.1.1.1 A example.com
dig -x 1.1.1.1
host example.com
getent hosts example.com     # NSS path
resolvectl query example.com
curl -I --http2 https://example.com
curl -v --connect-timeout 3 https://example.com/health
curl -o /dev/null -s -w '%{http_code} %{time_namelookup} %{time_connect} %{time_appconnect} %{time_total}\n' https://example.com
openssl s_client -connect example.com:443 -servername example.com </dev/null | openssl x509 -noout -dates -subject
```

### Capture and firewall

```bash
tcpdump -ni eth0 port 80 -c 20
tcpdump -ni any host 10.0.1.5 and port 5432 -w /tmp/pg.pcap
tcpdump -A -s0 -ni eth0 'tcp port 80 and (tcp[((tcp[12:1] & 0xf0) >> 2):4] = 0x47455420)'
nft list ruleset
iptables-save
iptables -t nat -L -n -v
```

Read pcaps with `tshark -r file -q -z io,phs` or Wireshark locally. Do not tcpdump on busy hosts without a snaplen and a count.

### Connectivity tests

```bash
ping -c 4 HOST
mtr -rw HOST
traceroute -n HOST
nc -vz HOST 443
ncat --ssl HOST 443
nping --tcp -p 443 HOST
iperf3 -c HOST
```

---

## 72.7 Storage, LVM, and filesystems

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,UUID,MOUNTPOINT
fdisk -l
parted /dev/nvme0n1 print
pvdisplay; vgdisplay; lvdisplay
lvs -a
mkfs.xfs /dev/vg/data
mount -o noatime,discard /dev/vg/data /data
tune2fs -l /dev/sdX1
xfs_info /data
xfs_growfs /data
resize2fs /dev/sdX1
sync; echo 3 > /proc/sys/vm/drop_caches   # lab only
```

NFS:

```bash
showmount -e nfs-server
mount -t nfs -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600 SERVER:/export /mnt
nfsstat -c
```

SMART and errors:

```bash
dmesg -T | grep -iE 'i/o error|ext4|xfs|nvme'
smartctl -a /dev/nvme0
```

---

## 72.8 Kernel, sysctl, modules

```bash
uname -a
cat /etc/os-release
sysctl -a | grep -E 'ip_forward|somaxconn|swappiness'
sysctl -w net.ipv4.ip_forward=1   # ephemeral; persist in /etc/sysctl.d
lsmod
modinfo overlay
dmesg -T | tail
sysctl fs.inotify.max_user_watches
nproc
lscpu
numactl -H
```

Useful production sysctls (document before applying):

| Key | Typical reason |
|-----|----------------|
| `net.core.somaxconn` | large reverse proxies |
| `net.ipv4.ip_local_port_range` | high connection churn |
| `net.netfilter.nf_conntrack_max` | NAT/conntrack exhaustion |
| `vm.swappiness` | DB nodes often low |
| `fs.file-max` | many containers |

---

## 72.9 Package managers and software

Debian/Ubuntu:

```bash
apt-get update
apt-get install -y --no-install-recommends jq
apt-cache policy nginx
dpkg -l | grep nginx
dpkg -L nginx
apt-get changelog nginx | head
```

RHEL/Alma:

```bash
dnf install -y jq
rpm -q --changelog kernel | head
repoquery -l nginx
```

---

## 72.10 Archives, compression, transfers

```bash
tar -czf app.tgz -C /opt app
tar -tzf app.tgz | head
tar --exclude='*.tmp' -cf - dir | ssh HOST 'tar -xf - -C /dest'
gzip -k file
zstd -T0 -19 file
xz -T0 file
scp -C file HOST:/tmp/
sftp HOST
curl -fL -o file.tgz URL
wget -c URL
aria2c -x 8 URL
```

---

## 72.11 Time, cron, and locale

```bash
timedatectl
chronyc tracking
date -u +%FT%TZ
TZ=America/New_York date
crontab -l
crontab -e
run-parts /etc/cron.daily
```

Prefer systemd timers for new work. Cron `PATH` is minimal—always use absolute paths.

---

## 72.12 Security auditing commands

```bash
sshd -T
lynis audit system            # if installed
chkrootkit                    # noisy; not a complete program
find / -xdev -perm -4000 -type f 2>/dev/null
ausearch -m EXECVE -ts recent
auditctl -l
getenforce                    # SELinux
sestatus
aa-status                     # AppArmor
umask
```

---

## 72.13 Containers on the host (runtime view)

```bash
crictl ps
crictl inspect CID
ctr -n k8s.io containers ls
nsenter -t PID -n ip a
nsenter -t PID -m ls /etc/resolv.conf
lsns
```

---

## 72.14 One-page incident command block

Paste into a war-room note when a host is sick:

```bash
date -u; hostname; uptime; cat /etc/os-release | head -2
df -hT; df -i | grep -v tmpfs
free -h
mpstat -P ALL 1 3
iostat -xz 1 3
ss -s
ip -br a
journalctl -p err -b --no-pager | tail -50
dmesg -T | tail -30
ps -eo pid,user,stat,pcpu,pmem,cmd --sort=-pcpu | head -20
```

---

## 72.15 Scripting hygiene with the same tools

```bash
set -euo pipefail
IFS=$'\n\t'
readonly ROOT=/opt/app
mapfile -t files < <(find "$ROOT" -type f -name '*.conf')
printf '%q\n' "$unsafe"
```

Use `shellcheck`. Quote variables. Prefer `[[ ]]`. Do not parse `ls`.

---

## 72.16 Performance snapshot with `perf` and eBPF

```bash
perf top -g
perf record -g -p PID -- sleep 10
perf report
bpftrace -e 'tracepoint:syscalls:sys_enter_connect { @[comm]=count(); }'
```

Requires debug permissions and often a matching kernel. Prefer a staging host or a short production sample with change control.

---

## 72.17 Comparison tables

| Need | Tool |
|------|------|
| CPU per process | `pidstat`, `top` |
| CPU per core | `mpstat` |
| Run queue | `vmstat`, `uptime` |
| Disk latency | `iostat -xz` |
| Who has the file | `lsof`, `fuser` |
| Syscalls | `strace`, `perf` |
| Packets | `tcpdump`, `ss` |
| Names | `dig` vs `getent` |
| Service logs | `journalctl -u` |

| Anti-pattern | Prefer |
|--------------|--------|
| `kill -9` first | TERM, wait, KILL |
| `chmod 777` | correct owner + 750/640 |
| `curl \| sudo bash` | signed packages |
| `echo y \| rm -rf` | explicit paths, trash |
| `tail /var/log/messages` on journald-only | `journalctl` |
| `ifconfig` in new docs | `ip` |

---

## 72.18 Worked example: “API host is slow”

1. `uptime` — load 18 on 4 CPUs → queued work.
2. `mpstat` — `%iowait` 40% → storage.
3. `iostat` — `await` 80ms on `nvme0n1` → EBS or worn disk.
4. `pidstat -d` — postgres writing heavily.
5. `lsof` on data dir — expected.
6. Check cloud burst credits / noisy neighbor.
7. Mitigate: reduce autovacuum concurrency, scale disk IOPS, add read replica.

If `%iowait` is low and `%usr` is high, jump to `perf` and application profiles instead.

---

## 72.19 Worked example: “Cannot bind port 80”

```bash
ss -lntp | grep ':80'
# nginx dead but docker published 80:80
systemctl status nginx docker
journalctl -u nginx -b
# 80 requires cap or root
getcap $(which nginx)
```

Another common cause: `ipv6only` vs dual-stack bind, or systemd socket activation already owning the port.

---

## 72.20 Keeping this encyclopedia honest

Commands age. `iptables` yields to `nft`, `netstat` to `ss`, `ifconfig` to `ip`. When you learn a new distro, dump equivalents (`man ip-address`). Prefer tools that ship in the base image of your production AMI so runbooks do not depend on `htop` being installed.

Print a one-page subset for on-call, not this whole chapter. The goal is that your fingers can reach diagnosis in under a minute: **identity of the bottleneck, then the right tool, then a reversible action**.

---

## 72.21 Permissions debugging cookbook

When a service fails with `Permission denied`, resist `chmod 777`. Walk this sequence:

1. **Who is the process?** `ps -o user,uid,gid,cmd -p PID` and systemd `User=` / `DynamicUser=`.
2. **What path?** `strace -e file` or the error message. Remember relative paths depend on `WorkingDirectory=`.
3. **DAC:** `namei -lx /full/path` shows each component’s mode. A directory without execute bit blocks traversal even if the file is 644.
4. **ACL / LSM:** `getfacl`, `ls -Z`, `ausearch`. SELinux `avc: denied` needs a context fix, not 777.
5. **Capabilities:** binding 80/443 without root needs `CAP_NET_BIND_SERVICE` or a proxy.
6. **Namespaces:** the file you see on the host is not the file in the container mount ns.

```bash
# Directory execute bit is the usual surprise
mkdir -p /opt/app/conf
chmod 640 /opt/app/conf/app.yaml
chmod 711 /opt/app          # accidentally dropped x on conf
namei -lx /opt/app/conf/app.yaml
chmod 750 /opt/app /opt/app/conf
```

---

## 72.22 systemd drop-in patterns for DevOps

| Need | Drop-in |
|------|---------|
| More FDs | `LimitNOFILE=65535` |
| Restart loop | `Restart=on-failure` + `StartLimitBurst=5` |
| Secrets file | `EnvironmentFile=-/etc/app/env` (dash = optional) |
| Hardening | `ProtectSystem=strict`, `PrivateTmp=true`, `NoNewPrivileges=true` |
| Socket | `Requires=app.socket` |

```bash
systemctl edit app.service
systemd-analyze security app.service
systemctl revert app.service   # remove drop-ins
```

Never edit vendor units under `/lib/systemd/system` in place; they return on package upgrade.

---

## 72.23 Network “it works from the box but not the pod”

```bash
# Host
curl -sS https://api.partner.test/health
# Same from container netns
PID=$(crictl inspect --output go-template '{{.info.pid}}' CID)
nsenter -t "$PID" -n curl -sS https://api.partner.test/health
```

If host works and nsenter fails: routing, NAT, or NetworkPolicy/DNS in the ns. If both fail: upstream, TLS, or egress firewall. If curl works but the app fails: the app’s resolver, proxy env vars (`HTTP_PROXY`), or IPv6 (`curl -4` vs `-6`).

---

## 72.24 Text processing for access logs (copy-paste)

Combined log format fields vary; this nginx-ish pattern is a starting point:

```bash
# top URLs
awk '{print $7}' access.log | sort | uniq -c | sort -nr | head
# status histogram
awk '{print $9}' access.log | sort | uniq -c | sort -nr
# p95-ish of request time if $request_time is last field
awk '{print $NF}' access.log | sort -n | awk 'BEGIN{c=0} {a[c++]=$1} END{print a[int(c*0.95)]}'
```

Prefer structured JSON logs and `jq` in new services so you are not maintaining awk folklore.

---

## 72.25 What to memorize vs look up

Memorize: `ss`, `ip`, `journalctl`, `systemctl`, `df/du`, `ps/top`, `dig` vs `getent`, signal 15 vs 9, inode vs bytes. Look up: `perf` events, nftables syntax, xfs_repair flags. The encyclopedia exists so on-call does not invent flags from memory under pressure.
