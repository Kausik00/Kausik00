# Chapter 6: Processes, systemd, and Service Management

*DevOps Handbook — Part II, Pages 86–105*

---

## 6.1 Understanding Linux processes

A **process** is a running instance of a program. Each has a **PID** (Process ID), owner, state, and resource usage.

```bash
ps aux                  # All processes (BSD style)
ps -ef                  # All processes (POSIX style)
top                     # Interactive process viewer
htop                    # Enhanced top (install separately)
pgrep nginx             # Find PIDs by name
pkill -HUP nginx        # Send signal to processes by name
```

### Process states

| State | Code | Meaning |
|-------|------|---------|
| Running | R | Executing or runnable |
| Sleeping | S | Waiting for event |
| Zombie | Z | Terminated but not reaped by parent |
| Stopped | T | Paused (e.g., Ctrl+Z) |

### Signals

```bash
kill -15 <pid>          # SIGTERM — graceful shutdown (default)
kill -9 <pid>           # SIGKILL — force kill (last resort)
kill -HUP <pid>         # SIGHUP — reload config (many daemons)
```

---

## 6.2 systemd — modern service manager

Most Linux distros use **systemd** to boot the system and manage services (units).

```bash
systemctl status nginx
systemctl start nginx
systemctl stop nginx
systemctl restart nginx
systemctl reload nginx          # Reload config without full restart
systemctl enable nginx          # Start on boot
systemctl disable nginx
systemctl list-units --type=service --state=running
journalctl -u nginx -f          # Follow service logs
journalctl -u nginx --since "1 hour ago"
```

### Unit files

Service definitions live in `/etc/systemd/system/` or `/lib/systemd/system/`.

Example `/etc/systemd/system/myapp.service`:

```ini
[Unit]
Description=My Application
After=network.target

[Service]
Type=simple
User=appuser
WorkingDirectory=/opt/myapp
ExecStart=/opt/myapp/bin/server
Restart=on-failure
RestartSec=5
Environment=PORT=8080

[Install]
WantedBy=multi-user.target
```

After creating or editing a unit:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now myapp
```

---

## 6.3 Cron and timers

### cron — scheduled tasks

```bash
crontab -e              # Edit user crontab
crontab -l              # List crontab
```

Cron format: `minute hour day month weekday command`

```
# Every day at 2:30 AM — backup database
30 2 * * * /opt/scripts/backup.sh >> /var/log/backup.log 2>&1
```

System-wide jobs: `/etc/cron.d/`, `/etc/cron.daily/`, etc.

### systemd timers (preferred on modern systems)

Timers are more flexible and integrate with journald logging.

```ini
# /etc/systemd/system/backup.timer
[Unit]
Description=Daily backup

[Timer]
OnCalendar=*-*-* 02:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl enable --now backup.timer
systemctl list-timers
```

---

## 6.4 Resource limits and troubleshooting

```bash
# CPU and memory per process
ps -o pid,user,%cpu,%mem,cmd -p <pid>

# Open files by process
lsof -p <pid>
ss -tlnp                   # Listening TCP ports with process
df -h                      # Disk usage
free -h                    # Memory usage
dmesg | tail               # Kernel messages
```

### Common production issues

| Symptom | Likely cause | Check |
|---------|--------------|-------|
| Service won't start | Bad config, missing binary | `journalctl -u service -n 50` |
| Port in use | Another process bound | `ss -tlnp \| grep :80` |
| Disk full | Logs, temp files | `df -h`, `du -sh /var/log/*` |
| OOM killed | Memory exhaustion | `dmesg \| grep -i oom` |

---

## 6.5 Chapter summary

- Manage processes with `ps`, `kill`, and signals.
- Use **systemctl** and **journalctl** for services on systemd systems.
- Schedule jobs with cron or systemd timers.
- Check logs first when debugging service failures.

---

## 🧪 Lab 6.1

1. Create a simple bash script that writes a timestamp to a log every minute.
2. Run it as a systemd service + timer.
3. Practice `systemctl status`, `journalctl -f`, and graceful stop/start.

---

*Next: [Chapter 9 — Git Internals](../part-03-git/chapter-09-git-internals.md)*
