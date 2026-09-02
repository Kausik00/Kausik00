# Chapter 5: Linux Fundamentals — Filesystem, Users, Permissions

*DevOps Handbook — Pages 20–23 of this PDF edition*
---

## 5.1 Why Linux dominates DevOps

Most servers, containers, and cloud instances run **Linux**. As a DevOps engineer you will SSH into machines, debug production issues, write shell scripts, and configure services daily. Windows matters too (Active Directory, .NET shops), but Linux fluency is non-negotiable.

Common distributions:

| Distro | Typical use |
|--------|-------------|
| **Ubuntu** | Cloud default, tutorials, desktops |
| **Debian** | Stable base for Ubuntu and containers |
| **RHEL / Rocky / Alma** | Enterprise, regulated industries |
| **Amazon Linux** | AWS-optimized |

---

## 5.2 Filesystem hierarchy (FHS)

| Path | Purpose |
|------|---------|
| `/` | Root of entire tree |
| `/home` | User home directories (`/home/alice`) |
| `/root` | root user's home |
| `/etc` | Configuration files |
| `/var` | Variable data: logs (`/var/log`), caches |
| `/tmp` | Temporary files (often cleared on reboot) |
| `/usr` | User programs and libraries |
| `/bin`, `/sbin` | Essential binaries |
| `/opt` | Optional third-party software |
| `/proc`, `/sys` | Virtual filesystems for kernel info |

Everything is a **file** in Unix—including devices and sockets.

---

## 5.3 Essential navigation commands

```bash
pwd                  # Print working directory
ls -lah              # List files (human-readable, including hidden)
cd /etc/nginx        # Change directory
cd ..                # Parent directory
cd ~                 # Home directory
tree -L 2 /etc       # Tree view (install: apt install tree)
```

**Tab completion** saves time: type partial names and press `Tab`.

---

## 5.4 File operations

```bash
cp source dest           # Copy
cp -r dir1 dir2          # Copy directory recursively
mv old new               # Move or rename
rm file                  # Delete (careful!)
rm -rf directory         # Delete directory recursively (very careful!)
mkdir -p path/to/dir     # Create nested directories
touch file.txt           # Create empty file or update timestamp
cat file                 # Print file contents
less /var/log/syslog     # Paginated view (q to quit)
head -n 20 file          # First 20 lines
tail -f /var/log/app.log # Follow log in real time
```

### Finding files

```bash
find /var/log -name "*.log" -mtime -7    # Logs modified in 7 days
find / -type f -size +100M 2>/dev/null   # Files larger than 100MB
locate nginx.conf                         # Fast index search (updatedb)
```

---

## 5.5 Users, groups, and permissions

### Users and groups

```bash
id                     # Current user UID, GID, groups
whoami
cat /etc/passwd        # User accounts
cat /etc/group         # Groups
sudo command           # Run as root (if permitted)
su - username          # Switch user
```

### Permission model

Each file has three permission sets for **user (u)**, **group (g)**, **others (o)**:

```
-rwxr-xr--  1 alice  developers  4096  Jan 15 10:00 deploy.sh
 │││││││││
 │││└┴┴┴┴┴─ others: read
 ││└─────── group: read, execute
 └──────── user: read, write, execute
```

| Symbol | Meaning |
|--------|---------|
| `r` (4) | Read |
| `w` (2) | Write |
| `x` (1) | Execute (directories: enter) |

```bash
chmod 755 script.sh       # rwxr-xr-x
chmod u+x script.sh       # Add execute for user
chown alice:developers file
chgrp developers file
```

### Special permissions

- **setuid** — Run as file owner (e.g., `passwd`)
- **setgid** — Run as group; dirs inherit group
- **sticky bit** — On `/tmp`, only owner can delete own files

---

## 5.6 Package management (Debian/Ubuntu)

```bash
sudo apt update                    # Refresh package index
sudo apt upgrade -y                # Upgrade installed packages
sudo apt install nginx -y          # Install package
apt search nginx                   # Search
apt show nginx                     # Package info
sudo apt remove nginx              # Remove
dpkg -l | grep nginx               # List installed
```

**RHEL/Rocky equivalent:** `dnf install`, `dnf update`.

---

## 5.7 Text processing (daily DevOps tools)

```bash
grep -r "ERROR" /var/log/app/           # Search recursively
grep -E "timeout|refused" log.txt         # Extended regex
awk '{print $1}' access.log               # Column extraction
sed 's/old/new/g' file.txt                # Stream editor
sort file | uniq -c | sort -rn | head     # Count unique lines
wc -l file                                # Line count
```

**Pipes (`|`)** chain commands: stdout of one → stdin of next.

---

## 5.8 Environment and shell

```bash
echo $PATH              # Executable search path
export MY_VAR=hello     # Set environment variable
env                     # All environment variables
which python3           # Path to executable
alias ll='ls -lah'      # Command shortcut
```

Shell config files: `~/.bashrc`, `~/.profile` (sourced on login).

---

## 5.9 SSH — remote access

```bash
ssh user@hostname
ssh -i ~/.ssh/mykey.pem ec2-user@1.2.3.4
scp file user@host:/remote/path
rsync -avz ./local/ user@host:/remote/    # Efficient sync
```

**`~/.ssh/config`** simplifies connections:

```
Host prod-web
    HostName 10.0.1.50
    User ubuntu
    IdentityFile ~/.ssh/prod.pem
```

Then: `ssh prod-web`

---

## 5.10 Chapter summary

- Linux FHS organizes `/etc`, `/var`, `/home`, and more.
- Master `ls`, `cd`, `cp`, `mv`, `rm`, `find`, `grep`, `tail -f`.
- Permissions: user/group/other + `chmod`/`chown`.
- Use `apt`/`dnf` for packages; SSH for remote ops.

---

## 🧪 Lab 5.1 — Linux sandbox

1. Create user `devops-lab` with home directory.
2. Create `~/scripts/deploy.sh` with `#!/bin/bash` and `echo "Deploying..."`.
3. Set permissions to `755`; run it.
4. Write a one-liner to count ERROR lines in a sample log file.
5. Configure SSH key auth to a local VM or cloud instance.

---

## Review questions

1. What directory holds system configuration files?
2. What does permission `644` mean in symbolic notation?
3. How do you follow a log file in real time?
4. What is the difference between `cp` and `mv`?

---

*Continue: Chapter 6 — Processes, systemd, and Service Management (outline in TOC)*
