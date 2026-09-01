# Chapter 18: JSON/YAML, Jinja2, and Templating

*DevOps Handbook — Part V, Pages 326–345*

---

## 18.1 Structured data in DevOps

Modern infrastructure is **data**, not manual clicking: CI matrices, Kubernetes manifests, Terraform variables, Ansible inventories, and API payloads. **JSON** and **YAML** are the two dominant serialization formats; **Jinja2** (in Ansible and many generators) templates text from variables.

Misformatted YAML has caused production outages—treat config editing as code review with schema validation.

---

## 18.2 JSON essentials

JSON is strict: double quotes, no trailing commas, limited types (object, array, string, number, boolean, null).

```json
{
  "service": "payments-api",
  "replicas": 3,
  "env": {
    "LOG_LEVEL": "info",
    "FEATURE_RETRY": true
  },
  "ports": [8080, 9090]
}
```

### CLI tooling

```bash
echo '{"a":1}' | jq '.a'
jq -r '.items[].name' deploy.json
yq -o=json '.' config.yaml          # yq v4: YAML ↔ JSON
python3 -m json.tool < messy.json   # Pretty-print
```

In Python:

```python
import json
from pathlib import Path

data = json.loads(Path("config.json").read_text(encoding="utf-8"))
data["replicas"] = 5
Path("config.out.json").write_text(
    json.dumps(data, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
```

---

## 18.3 YAML essentials and pitfalls

YAML is human-friendly but ambiguous if abused.

```yaml
service: payments-api
replicas: 3
env:
  LOG_LEVEL: info
  FEATURE_RETRY: true
ports:
  - 8080
  - 9090
```

### Gotchas

| Issue | Example | Fix |
|-------|---------|-----|
| **Norway problem** | `NO: off` → false in some parsers | Quote `"NO"` |
| **Octal numbers** | `0123` misread | Quote strings |
| **Tabs** | Tab indentation | Spaces only (2 spaces common) |
| **Multi-document** | `---` separators | Split or use explicit loader |
| **Anchors** | `&id`, `*id` | Powerful; confusing in reviews |

Kubernetes and GitHub Actions use YAML extensively—run **`yamllint`** in CI.

Python safe load (never `yaml.load` without Loader):

```python
import yaml

with open("deploy.yaml", encoding="utf-8") as f:
    doc = yaml.safe_load(f)
```

---

## 18.4 JSON vs YAML: when to use which

| Choose JSON | Choose YAML |
|-------------|-------------|
| API request/response | Kubernetes, Ansible, docker-compose |
| Machine-generated only | Human-edited config with comments |
| Strict schema validation | Long nested config files |
| jq everywhere | Inline multiline strings (`\|`, `>`) |

Many pipelines **author YAML**, **convert to JSON** for tools that only accept JSON.

---

## 18.5 Templating concepts

**Templates** separate **structure** from **values**:

```
template + variables → rendered config
```

Engines:

| Engine | Context |
|--------|---------|
| **Jinja2** | Ansible, Salt, some CI generators |
| **Go text/template** | Helm charts, some CLIs |
| **Terraform HCL** | Built-in interpolation |
| **envsubst** | Shell-level `$VAR` replacement |

Jinja2 syntax preview:

```jinja2
# nginx.conf.j2
upstream {{ service_name }} {
{% for backend in backends %}
    server {{ backend.host }}:{{ backend.port }};
{% endfor %}
}
```

Rendered with variables:

```python
from jinja2 import Environment, FileSystemLoader, select_autoescape

env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(default=False),
)
template = env.get_template("nginx.conf.j2")
print(template.render(
    service_name="api",
    backends=[{"host": "10.0.1.10", "port": 8080}],
))
```

---

## 18.6 Jinja2 in Ansible

Ansible playbooks are YAML; **templates** live in `templates/` and deploy via `template` module:

```yaml
- name: Deploy nginx config
  ansible.builtin.template:
    src: nginx.conf.j2
    dest: /etc/nginx/conf.d/api.conf
    mode: "0644"
  notify: Reload nginx
```

Variables come from inventory, group_vars, host_vars, and facts:

```yaml
# group_vars/api.yml
service_name: payments-api
backends:
  - host: 10.0.10.5
    port: 8080
  - host: 10.0.10.6
    port: 8080
```

Filters and tests (`| default('')`, `when: env == 'prod'`) keep templates readable—avoid business logic soup in Jinja.

---

## 18.7 Helm and Go templates (brief)

Helm charts template Kubernetes YAML:

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "mychart.fullname" . }}
spec:
  replicas: {{ .Values.replicaCount }}
```

`helm template` renders locally for review before apply—always render in CI and diff against cluster.

---

## 18.8 Schema validation

Prevent bad config from merging:

| Tool | Format |
|------|--------|
| **jsonschema** | JSON Schema for JSON/YAML |
| **kubeconform** | Kubernetes OpenAPI |
| **checkov / tfsec** | IaC policies |
| **ajv** | JSON in Node CI |

Example with Python jsonschema:

```python
from jsonschema import validate

schema = {
    "type": "object",
    "required": ["service", "replicas"],
    "properties": {
        "service": {"type": "string"},
        "replicas": {"type": "integer", "minimum": 1},
    },
}
validate(instance=doc, schema=schema)
```

---

## 18.9 Secrets and templating

Never template **plaintext secrets** into Git-tracked files. Patterns:

- Reference **`{{ vault_db_password }}`** from Ansible Vault or External Secrets.
- Render secrets at deploy time from CI secret store.
- Use **`envsubst`** on runtime-only files in ephemeral CI job.

Redact rendered output in logs (`no_log: true` in Ansible for sensitive tasks).

---

## 18.10 Chapter summary

- **JSON** is strict and universal for APIs; **YAML** powers K8s and Ansible with comment-friendly syntax.
- Watch YAML **gotchas** (types, tabs, unquoted `NO`).
- **Jinja2** separates templates from data—used heavily in Ansible.
- **Validate** structured config with schemas before apply.
- Keep **secrets out** of rendered artifacts in version control.

---

## 🧪 Lab 18.1 — Render nginx from Jinja2

1. Create `templates/upstream.conf.j2` with loop over backends.
2. Write `render.py` reading variables from `vars.yaml`.
3. Add jsonschema validation for `vars.yaml` structure.
4. Break validation intentionally; confirm CI/local script fails.

---

## 🧪 Lab 18.2 — YAML lint pipeline

1. Add `yamllint` config to a repo with sample K8s manifests.
2. Fix indentation and document-start issues.
3. Add GitHub Actions or GitLab job running yamllint on every PR.

---

## Review questions

1. Why is `yaml.safe_load` preferred over bare `yaml.load`?
2. Name two YAML features that cause review confusion.
3. What problem does Jinja2 solve in Ansible?
4. How does Helm differ from plain Jinja2 templating?
5. Why validate config against a schema in CI?

---

*Next: [Chapter 19 — Testing Automation Scripts](./chapter-19-testing-automation.md)*
