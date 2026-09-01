# Chapter 16: Python for DevOps — boto3, requests, pathlib

*DevOps Handbook — Part V, Pages 281–305*

---

## 16.1 Why Python dominates DevOps automation

Python balances readability, rich libraries, and fast iteration. It powers Ansible modules, AWS Lambda, glue scripts, data migration tools, and CI steps. You will use it alongside bash (Chapter 8) for anything beyond simple command wrapping.

Core libraries for this handbook:

| Library | Purpose |
|---------|---------|
| **boto3** | AWS API SDK |
| **requests** | HTTP client |
| **pathlib** | Modern filesystem paths |
| **json / yaml** | Config and API payloads |
| **subprocess** | Safe CLI invocation |
| **logging** | Structured operational logs |

---

## 16.2 Project layout and virtual environments

Never install packages globally on shared CI runners without pinning. Use **venv** per project:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install boto3 requests
pip freeze > requirements.txt
```

Minimal repo layout:

```
tools/
  aws_inventory/
    __init__.py
    main.py
    requirements.txt
    README.md
tests/
  test_inventory.py
```

Pin versions in `requirements.txt` for reproducible CI:

```
boto3==1.34.162
requests==2.32.3
```

---

## 16.3 pathlib: filesystem without footguns

`pathlib.Path` replaces brittle string path concatenation:

```python
from pathlib import Path

root = Path(__file__).resolve().parent
config_dir = root / "config"
log_file = Path("/var/log/app") / "deploy.log"

if not config_dir.exists():
    config_dir.mkdir(parents=True, exist_ok=True)

for yaml_file in config_dir.glob("*.yaml"):
    print(yaml_file.read_text(encoding="utf-8")[:200])

# Safe join — no double slashes
staging = root / ".." / "staging" / "inventory.json"
staging = staging.resolve()
```

Use `.read_text()`, `.write_text()`, `.iterdir()`, and `.glob()` instead of `os.path` when starting new scripts.

---

## 16.4 requests: HTTP for APIs and health checks

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

def get_health(url: str, timeout: float = 5.0) -> bool:
    try:
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json().get("status") == "ok"
    except requests.RequestException as exc:
        print(f"health check failed: {exc}")
        return False

if __name__ == "__main__":
    ok = get_health("https://api.example.com/health")
    raise SystemExit(0 if ok else 1)
```

Best practices:

- Always set **timeouts** (`timeout=(connect, read)`).
- Use **`raise_for_status()`** or explicit status handling.
- Reuse **Session** for connection pooling in loops.
- Never disable TLS verify in production (`verify=False` is debug-only).

---

## 16.5 boto3: AWS automation

boto3 uses **botocore** for API calls. Credentials resolve via environment variables, `~/.aws/credentials`, or IAM role on EC2/EKS.

```python
import boto3
from botocore.exceptions import ClientError

def list_stopped_instances(region: str = "us-east-1"):
    ec2 = boto3.client("ec2", region_name=region)
    paginator = ec2.get_paginator("describe_instances")
    stopped = []

    for page in paginator.paginate(
        Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}]
    ):
        for reservation in page["Reservations"]:
            for inst in reservation["Instances"]:
                name = next(
                    (t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"),
                    "unnamed",
                )
                stopped.append({"id": inst["InstanceId"], "name": name})
    return stopped

def stop_instance(instance_id: str, region: str = "us-east-1") -> None:
    ec2 = boto3.client("ec2", region_name=region)
    try:
        ec2.stop_instances(InstanceIds=[instance_id])
    except ClientError as e:
        raise RuntimeError(f"stop failed: {e}") from e
```

### Resource vs client

| API | Style | Use |
|-----|-------|-----|
| **client** | Low-level dict responses | Full API coverage |
| **resource** | Object-oriented | Convenient for EC2/S3 common ops |

```python
s3 = boto3.resource("s3")
for bucket in s3.buckets.all():
    print(bucket.name)
```

Handle **`ClientError`** with error codes (`AccessDenied`, `InvalidParameterValue`) for actionable messages.

---

## 16.6 Idempotency and dry-run patterns

DevOps scripts should be safe to re-run:

```python
def ensure_tag(ec2_client, instance_id: str, key: str, value: str) -> None:
    ec2_client.create_tags(
        Resources=[instance_id],
        Tags=[{"Key": key, "Value": value}],
    )
    # create_tags is idempotent for same key/value on AWS
```

Add **`--dry-run`** CLI flags for destructive operations; boto3 supports `DryRun` on many calls to validate permissions without effect.

---

## 16.7 CLI entry points with argparse

```python
import argparse
from pathlib import Path

def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy artifact to S3")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()

    if not args.file.is_file():
        parser.error(f"file not found: {args.file}")

    # upload logic here
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

Use **`raise SystemExit(main())`** so CI captures exit codes.

---

## 16.8 Logging instead of print

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

log.info("starting sync", extra={"bucket": "my-bucket"})
```

Structured JSON logging (for Loki/CloudWatch) can use `python-json-logger` in larger services.

---

## 16.9 Testing Python automation

```python
# tests/test_health.py
from unittest.mock import patch, MagicMock
import inventory  # your module

def test_get_health_ok():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "ok"}
    mock_resp.raise_for_status = MagicMock()
    with patch("inventory.session.get", return_value=mock_resp):
        assert inventory.get_health("http://test") is True
```

Run with `pytest`; mock external APIs—never hit production AWS in unit tests.

---

## 16.10 Security notes

- Store secrets in env vars or secret managers—not in code.
- Use **least-privilege IAM** policies scoped to required actions.
- Validate input paths to prevent **`../../`** escapes when operating on filesystems.
- Scan dependencies with **pip-audit** or SCA in CI.

---

## 16.11 Chapter summary

- Use **venv + pinned requirements** for reproducible automation.
- **pathlib** simplifies safe filesystem operations.
- **requests** needs timeouts, retries, and explicit error handling.
- **boto3** clients/resources automate AWS—paginate and handle `ClientError`.
- Add **argparse**, logging, dry-run, and **pytest** mocks for production-quality scripts.

---

## 🧪 Lab 16.1 — EC2 inventory script

1. Write `list_ec2_by_tag.py --tag-key Environment --tag-value staging`.
2. Output JSON list of instance ID, type, state, private IP.
3. Run with read-only IAM; add `--output table` optional format.
4. Add pytest with mocked boto3 responses.

---

## 🧪 Lab 16.2 — Health gate for CI

1. Implement `check_health.py --url URL --retries 5 --interval 10`.
2. Exit non-zero on failure for use in GitHub Actions step.
3. Document usage in README with example workflow snippet.

---

## Review questions

1. Why use `requests.Session` in a loop?
2. Difference between boto3 client and resource?
3. How does pathlib improve on string path joins?
4. What three elements belong in every HTTP call in automation?
5. How do you test boto3 code without calling AWS?

---

*Next: [Chapter 17 — Go for CLI Tools and Operators](./chapter-17-go-cli-tools.md)*
