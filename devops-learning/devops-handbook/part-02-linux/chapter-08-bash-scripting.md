# Chapter 8: Bash Scripting for Automation

*DevOps Handbook — Pages 32–36 of this PDF edition*
---

## 8.1 When bash is the right tool

Bash excels at **gluing** existing CLI tools: deploy hooks, cron jobs, CI steps, and quick operational scripts. Reach for Python or Go when you need complex logic, libraries, or testability—but bash remains the **lingua franca** of Linux automation.

Rules of thumb:

| Use bash | Use Python/Go instead |
|----------|----------------------|
| Wrapping `kubectl`, `aws`, `curl`, `tar` | Parsing complex JSON at scale |
| CI job steps under 50 lines | Long-running services |
| One-off migration with tight deadline | Shared libraries across teams |
| Systemd `ExecStart` wrappers | Heavy unit testing requirements |

---

## 8.2 Script anatomy and safety

Every production script should start with:

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
```

| Option | Effect |
|--------|--------|
| `set -e` | Exit on first command failure |
| `set -u` | Error on unset variables |
| `set -o pipefail` | Pipeline fails if any stage fails |
| `IFS` | Safer word splitting for loops |

Optional: `set -x` for trace mode during debugging (remove before committing secrets to logs).

### Shebang and portability

```bash
#!/usr/bin/env bash    # Preferred: finds bash in PATH
#!/bin/bash            # OK on most Linux; macOS may be old bash
```

Avoid bashisms in scripts that must run on **Alpine `/bin/sh`** (ash)—use `#!/bin/sh` and POSIX syntax, or explicitly require bash.

---

## 8.3 Variables, quoting, and expansion

```bash
name="api-server"
count=3
echo "Deploying ${name} x${count}"
echo 'Literal ${name} not expanded'

# Command substitution
today=$(date -u +%Y-%m-%d)
files=$(find /var/log -name '*.log' | wc -l)

# Default values
region="${AWS_REGION:-us-east-1}"
```

**Always quote variable expansions** unless you intentionally want word splitting:

```bash
rm -rf "$tmpdir"          # Good
rm -rf $tmpdir              # Dangerous if empty or contains spaces
```

Arrays (bash-specific):

```bash
services=(nginx api worker)
for svc in "${services[@]}"; do
  systemctl is-active --quiet "$svc" || echo "$svc down"
done
```

---

## 8.4 Conditionals and tests

```bash
if [[ -f /etc/nginx/nginx.conf ]]; then
  echo "nginx config present"
elif [[ -d /opt/myapp ]]; then
  echo "app directory exists"
else
  echo "neither found" >&2
  exit 1
fi
```

Common tests:

| Test | Meaning |
|------|---------|
| `[[ -f path ]]` | Regular file exists |
| `[[ -d path ]]` | Directory exists |
| `[[ -z "$var" ]]` | String empty |
| `[[ "$a" == "$b" ]]` | String equality |
| `[[ "$n" -gt 0 ]]` | Numeric greater than |

Use `[[ ]]` in bash (not single-bracket `[ ]` unless POSIX required).

---

## 8.5 Loops and functions

```bash
for env in staging production; do
  echo "Deploying to $env"
  ./deploy.sh "$env"
done

while read -r line; do
  echo "Log: $line"
done < /var/log/app.log

deploy() {
  local env="$1"
  local version="$2"
  echo "deploy $version -> $env"
}

deploy staging "v1.2.3"
```

Use **`local`** inside functions to avoid polluting global scope.

---

## 8.6 Exit codes and error handling

Exit code `0` = success; non-zero = failure. CI systems and `set -e` depend on this.

```bash
if ! kubectl apply -f manifest.yaml; then
  echo "apply failed" >&2
  exit 1
fi

# Or with trap for cleanup
cleanup() {
  rm -f "$lockfile"
}
trap cleanup EXIT

lockfile=$(mktemp)
# ... critical section ...
```

`trap` ensures cleanup runs on exit, interrupt, or error—essential for temp files and lock release.

---

## 8.7 External commands and JSON

Prefer structured tools over fragile `grep` of command output when possible:

```bash
# jq for JSON (install in CI images)
instance_id=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 describe-instances --instance-ids "$instance_id" \
  | jq -r '.Reservations[0].Instances[0].PrivateIpAddress'

# Avoid parsing human tables with awk unless no JSON API exists
```

For simple key=value files:

```bash
# shellcheck disable=SC1091
source /etc/default/myapp
echo "$APP_PORT"
```

Never `source` untrusted files.

---

## 8.8 Logging and observability

```bash
log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2
}

log "Starting backup"
```

- Send logs to **stderr**; reserve stdout for data piped to other commands.
- Include **timestamps in UTC** for correlating with centralized logging.
- Avoid echoing secrets; redact tokens in debug output.

---

## 8.9 Argument parsing

```bash
usage() {
  echo "Usage: $0 -e ENV -v VERSION" >&2
  exit 1
}

env=""
version=""

while getopts ":e:v:h" opt; do
  case "$opt" in
    e) env="$OPTARG" ;;
    v) version="$OPTARG" ;;
    h) usage ;;
    *) usage ;;
  esac
done

[[ -n "$env" && -n "$version" ]] || usage
```

For long options (`--env`), consider `getopt` or a thin Python wrapper; keep bash CLIs simple.

---

## 8.10 Script layout in repos

```
scripts/
  deploy.sh
  lib/
    common.sh          # shared functions, sourced by other scripts
  README.md            # usage, env vars, examples
```

```bash
# deploy.sh
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"
```

Run **`shellcheck`** in CI on all shell scripts—it catches quoting bugs and portability issues early.

---

## 8.11 Security considerations

| Risk | Mitigation |
|------|------------|
| Command injection | Never pass untrusted input to `eval`; quote variables |
| Secrets in args | Use env vars or secret managers; avoid `ps` exposure |
| World-writable paths | Check `TMPDIR`; use `mktemp` |
| `curl \| bash` | Pin checksums; avoid in production install flows |
| SUID / excessive sudo | Run with least privilege |

---

## 8.12 Chapter summary

- Start scripts with **`set -euo pipefail`** and quote expansions.
- Use functions, **`local`**, and **`trap`** for maintainable automation.
- Prefer **JSON APIs + jq** over parsing human-formatted CLI tables.
- Log to **stderr** with UTC timestamps; never leak secrets.
- Run **shellcheck** and document usage in README files.

---

## 🧪 Lab 8.1 — Health check script

1. Write `healthcheck.sh` that accepts `-u URL` and exits 0 only if HTTP status is 200.
2. Use `curl -sS -o /dev/null -w '%{http_code}'`.
3. Add `--timeout SECONDS` optional flag.
4. Run shellcheck and fix all warnings.

---

## 🧪 Lab 8.2 — Batch service restart

1. Create `restart-services.sh` reading service names from a file (one per line).
2. For each service: check active with `systemctl`, restart if failed, log result.
3. Use `trap` to write a summary count on exit.
4. Test with dummy unit names and intentional failures.

---

## Review questions

1. What do `set -e`, `set -u`, and `pipefail` each prevent?
2. Why quote `"$variable"` when passing paths to commands?
3. When should you choose Python over bash for automation?
4. What is the purpose of `trap cleanup EXIT`?
5. How do you safely share functions across multiple bash scripts in a repo?

---

*Next: [Chapter 9 — Git Internals: Objects, Refs, and the DAG](../part-03-git/chapter-09-git-internals.md)*
