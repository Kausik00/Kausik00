# Chapter 19: Testing Automation Scripts

*DevOps Handbook — Part V, Pages 346–360*

---

## 19.1 Why test automation code?

Pipeline scripts and operational tools **are production software**. Untested deploy scripts cause outages as surely as application bugs. Testing automation yields:

| Benefit | Example |
|---------|---------|
| **Regression safety** | Refactor deploy.sh without fear |
| **Documentation** | Tests show expected behavior |
| **Faster review** | CI green reduces manual guesswork |
| **Confidence in rollbacks** | Verified restore procedures |

The investment scales with **blast radius**—a one-off migration may need smoke tests only; a shared deploy tool needs full unit and integration coverage.

---

## 19.2 Test pyramid for DevOps scripts

```
        /\
       /  \     E2E (staging deploy, full pipeline)
      /----\
     /      \   Integration (docker-compose, LocalStack, kind)
    /--------\
   /          \ Unit (functions, mocked AWS/HTTP)
  /--------------\
```

| Layer | Scope | Speed | Cost |
|-------|-------|-------|------|
| **Unit** | Pure logic, mocks | Fast | Low |
| **Integration** | Real local services | Medium | Medium |
| **E2E** | Staging environment | Slow | High |

Run **many unit**, **some integration**, **few E2E** in CI budgets.

---

## 19.3 Testing bash scripts

Tools:

| Tool | Role |
|------|------|
| **bats** | Bash Automated Testing System |
| **shellcheck** | Static analysis (not tests, but required) |
| **shfmt** | Formatting consistency |

Example bats test:

```bash
#!/usr/bin/env bats
# tests/healthcheck.bats

setup() {
  load '../scripts/healthcheck.sh'
}

@test "returns 0 for HTTP 200" {
  run curl_mock 200
  [ "$status" -eq 0 ]
}
```

Pragmatic approach: extract logic to **`lib/*.sh`** functions, source in tests, mock external commands by placing stubs early in `PATH`:

```bash
# tests/bin/curl — mock
#!/usr/bin/env bash
echo "200"
```

Run in CI:

```yaml
- name: Shellcheck
  run: shellcheck scripts/*.sh
- name: Bats
  run: bats tests/
```

---

## 19.4 Testing Python automation

Use **pytest** with mocks for cloud and HTTP:

```python
from unittest.mock import patch, MagicMock
import boto3
import mymodule

@patch("boto3.client")
def test_list_buckets(mock_client):
    mock_client.return_value.list_buckets.return_value = {
        "Buckets": [{"Name": "a"}, {"Name": "b"}]
    }
    names = mymodule.list_bucket_names()
    assert names == ["a", "b"]
```

Fixtures for temp filesystem:

```python
import pytest
from pathlib import Path

@pytest.fixture
def tmp_config(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("replicas: 2\n", encoding="utf-8")
    return p
```

Run **`pytest --cov=mymodule --cov-report=term-missing`** for coverage gaps on critical paths.

---

## 19.5 Testing Go CLIs

Go's **`testing`** package plus **`httptest`** cover most CLI logic (Chapter 17). Test `RunE` functions by extracting business logic from `main`.

Table-driven tests:

```go
tests := []struct {
    name   string
    code   int
    wantOK bool
}{
    {"ok", 200, true},
    {"fail", 500, false},
}
for _, tt := range tests {
    t.Run(tt.name, func(t *testing.T) {
        // ...
    })
}
```

---

## 19.6 Integration testing with containers

**docker-compose** or **testcontainers** spin real dependencies:

```yaml
# docker-compose.test.yml
services:
  localstack:
    image: localstack/localstack:3
    environment:
      SERVICES: s3,ec2
    ports:
      - "4566:4566"
```

Point boto3 to `endpoint_url=http://localhost:4566` in integration tests marked `@pytest.mark.integration`—skip by default in fast CI jobs.

For Kubernetes manifests: **`kind`** cluster in CI, `kubectl apply --dry-run=server`, or **kubeconform** validation.

---

## 19.7 Testing Terraform and Ansible

| Tool | Test approach |
|------|---------------|
| **Terraform** | `terraform validate`, `tflint`, `checkov`, **`terraform plan`** in CI |
| **Ansible** | `ansible-playbook --syntax-check`, **molecule** with docker driver |
| **Helm** | `helm template` + kubeconform, chart unit tests |

**Terratest** (Go) applies modules in ephemeral AWS accounts—powerful but slow; use for module maintainers.

---

## 19.8 CI pipeline layout for script repos

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: shellcheck scripts/*.sh || true
      - run: pip install ruff && ruff check .
      - run: yamllint .

  unit:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements-dev.txt
      - run: pytest -q --ignore=tests/integration

  integration:
    needs: unit
    runs-on: ubuntu-latest
    services:
      localstack:
        image: localstack/localstack:3
        ports:
          - 4566:4566
    steps:
      - run: pytest tests/integration -q
```

Gate merges on **lint + unit**; run integration on main or nightly if slow.

---

## 19.9 Test data and fixtures

- Store **sanitized** sample JSON/YAML in `tests/fixtures/`.
- Never commit real **secrets** or production dumps.
- Use **factories** for repetitive object graphs (Python `dataclasses`, Go structs).

Golden file testing: compare rendered template to committed expected output; update with explicit `--update-golden` flag when intentional.

---

## 19.10 When tests are enough

Minimum bar before merging shared automation:

1. **shellcheck / ruff / go vet** clean.
2. **Unit tests** for parsing, decision branches, error paths.
3. **Dry-run** or plan-only validation for infra changes.
4. **README** with usage and rollback notes.

For incident one-offs, a **checklist and peer review** may suffice—promote to tested tooling if reused twice.

---

## 19.11 Chapter summary

- Automation scripts deserve the same **quality gates** as application code.
- Favor **unit tests with mocks**; add integration tests for cloud APIs via LocalStack/containers.
- Use **bats**, **pytest**, and Go **`testing`** per language.
- Validate **Terraform/Ansible/Helm** with domain-specific tools in CI.
- Match test depth to **blast radius** and reuse frequency.

---

## 🧪 Lab 19.1 — pytest suite for inventory script

1. Take the EC2 inventory script from Lab 16.1 (or a stub module).
2. Add unit tests with mocked boto3 for empty, single, and paginated responses.
3. Wire pytest into GitHub Actions; fail PR on coverage below 80% for module.

---

## 🧪 Lab 19.2 — bats for bash healthcheck

1. Add bats tests for the healthcheck script from Lab 8.1.
2. Mock `curl` via PATH stub returning 200, 500, and connection failure.
3. Run shellcheck + bats in CI.

---

## Review questions

1. Why are untested deploy scripts risky in DevOps?
2. What belongs in unit vs integration tests for a boto3 script?
3. How can you test bash that wraps curl without hitting real URLs?
4. Name two tools for validating Terraform in CI besides `apply`.
5. When is it acceptable to skip automated tests?

---

*Next: [Chapter 20 — IaC Principles: State, Idempotency, Drift](../part-06-iac/chapter-20-iac-principles.md)*
