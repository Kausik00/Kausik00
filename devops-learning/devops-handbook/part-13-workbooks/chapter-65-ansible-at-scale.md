# Chapter 65: Ansible at Scale

*DevOps Handbook — Pages 333–340 of this PDF edition*

*DevOps Handbook — Workbook*
---

## 65.1 The difference between a playbook that works and a fleet that converges

Ansible shines in labs: five VMs, a static inventory, `become: true`, and a play that “installs nginx.” At scale you have **dynamic inventories** across clouds, **Windows and Linux** in one change window, **partial failures**, **AWX/AAP controllers**, rolling updates that must not take the site down, and **idempotency bugs** that only appear on the 400th host because of a race or a drifted fact.

This workbook assumes Chapter 23 (playbooks, roles, inventories). Here the unit of work is the **job** in a controller, the **inventory source**, and the **convergence property** you can prove.

| Scale pressure | What breaks first |
|----------------|-------------------|
| Host count | SSH fan-out, fact gathering, fork RAM on the controller |
| Heterogeneity | `when:` soup, package names, Windows vs POSIX paths |
| Rate of change | Inventory lag, stale groups, “host not found” |
| Governance | Who can run prod? Credential isolation? Audit? |
| Time | Serial batches, health checks, drain vs kill |

---

## 65.2 Inventory architecture

### 65.2.1 Static YAML is not a strategy

Static `hosts.ini` is a snapshot. Production inventory is **derived**:

- AWS: tags `Role=web`, `Env=prod`
- GCP: labels
- CMDB / ServiceNow / Backstage (Chapter 70)
- Kubernetes: not usually Ansible-inventory for pods; use for **nodes** and **bastions**
- Netbox for network devices

```yaml
# inventories/prod/aws_ec2.yml  (plugin)
plugin: amazon.aws.aws_ec2
regions:
  - us-east-1
filters:
  tag:Env: prod
keyed_groups:
  - key: tags.Role
    prefix: role
  - key: tags.Cluster
    prefix: cluster
compose:
  ansible_host: private_ip_address
```

**Group graph** should answer: “all prod web in AZ-a that are not canary.” If you cannot express that without a 40-line `limit` string, your tags are wrong.

### 65.2.2 Constructed groups and limits

```bash
ansible-inventory -i inventories/prod --graph
ansible-inventory -i inventories/prod --host i-0abc
ansible-playbook site.yml -i inventories/prod --limit 'role_web:&az_use1a:!canary'
```

`--limit` is a scalpel. **Empty limit matches** (typo in group name) can mean “run on nothing” or, with some wrappers, “run on all.” AWX has a setting; **fail on empty limit**. Test it.

### 65.2.3 Inventory cache and split-brain

Dynamic plugins cache. A 30-minute cache during an incident means you are targeting **terminated** instances and missing new ones. Tune cache per environment: prod incident jobs should `cache: false` or TTL of minutes, not hours.

Multiple AWX inventory sources merging the same host with different `ansible_host` (public vs private IP) produce random connection targets. **Normalize** in compose and document the jump host pattern.

```ini
[web:vars]
ansible_connection=ssh
ansible_user=ec2-user
ansible_ssh_common_args='-o ProxyJump=bastion.prod.example'
```

---

## 65.3 Execution: forks, mitogen, pull vs push, and the controller as a bottleneck

```bash
ansible-playbook site.yml -f 50
```

Forks are processes. Each gathers facts unless you disable. Memory on the control node is **O(forks × fact size)**. 50 forks against Windows hosts with large facts can OOM the controller—ironically an Ansible outage during a patch window.

Patterns:

| Pattern | When |
|---------|------|
| Push from AWX | Default, audited |
| Pull (`ansible-pull`) | Embedded/edge, flaky WAN; weaker central audit |
| Execution environments (EE) | AAP 2: container image with collections |
| Mitogen / pipelining | SSH throughput; test before you bless it |

```ini
[defaults]
pipelining = True
gathering = smart
fact_caching = jsonfile
fact_caching_connection = /var/lib/awx/facts
fact_caching_timeout = 86400
```

Smart gathering + cache speeds jobs but **stale facts** cause package architecture mistakes. Invalidate facts after AMI bake or major upgrade.

**Callback plugins** and ARA records are how you answer “what changed on host X last Tuesday.” Enable them before you need them.

---

## 65.4 AWX / Ansible Automation Platform

AWX is the open upstream of AAP. Production concerns:

### 65.4.1 Objects you must model

| Object | Purpose |
|--------|---------|
| Organization | Tenant (see also Chapter 70 tenancy) |
| Inventory | Hosts + groups + sources |
| Credential | Machine, cloud, Vault, Git |
| Project | Git repo of playbooks (SCM) |
| Job template | Playbook + inventory + creds + extra vars |
| Workflow | Graph of templates, pass/fail branches |
| Notification | Slack/PagerDuty on failure |
| RBAC | Who can execute prod vs who can edit |

**Separation of duties:** developers merge playbooks; platform team owns credentials; app owners have **execute** on job templates, not **admin** on credentials.

### 65.4.2 Extra vars vs survey vs SCM

Extra vars in the UI are convenient and **unreviewed**. Prefer:

- Variables in SCM (`group_vars/prod.yml`)
- Ansible Vault or a secret lookup (`hashi_vault`, AWS SSM)
- AWX survey only for **non-secret** runtime choices (batch size, ticket ID)

If a human can paste `pkg_version=0.0.0` into extra vars and prod rolls back, you do not have production controls—you have a GUI.

### 65.4.3 Instance groups and isolated nodes

Hybrid cloud: run jobs **near** the targets (execution nodes in the VPC) instead of hairpinning SSH from a SaaS controller through the internet. Isolated nodes also keep Windows WinRM inside the network.

### 65.4.4 Idempotent re-runs and AWX job slicing

Job slicing splits the inventory across workers. A play that assumes **all hosts in one play** for a rolling lock (`serial` with a custom lock in memory) can break when sliced. Document “this template is not slice-safe.”

---

## 65.5 Rolling updates that respect health

`serial` is necessary but not sufficient.

```yaml
- hosts: role_web
  serial: "20%"
  max_fail_percentage: 10
  any_errors_fatal: false
  pre_tasks:
    - name: Drain from load balancer
      include_role: { name: lb_drain }
  tasks:
    - name: Upgrade package
      ansible.builtin.package:
        name: myapp
        state: "{{ myapp_version }}"
    - name: Wait for health
      ansible.builtin.uri:
        url: "http://{{ ansible_host }}:8080/healthz"
        status_code: 200
      register: health
      until: health.status == 200
      retries: 30
      delay: 2
  post_tasks:
    - name: Attach to load balancer
      include_role: { name: lb_attach }
```

**max_fail_percentage** without a drain is how you serve 500s from half-upgraded nodes. **any_errors_fatal: true** aborts the remaining batches—correct for schema migrations, wrong for “one noisy host.”

Coordinate with:

- Load balancer connection draining
- Kubernetes: this chapter is for VMs; for k8s use rolling Deployments (Chapter 41/66)
- Database migrations **out of band** (expand/contract), not inside the same serial batch as binary replace unless you are sure

**Check mode (`--check`)** does not simulate `uri` health or `command` scripts unless you write `check_mode:` stubs. Do not sell check mode as a production dry-run of a rolling deploy.

---

## 65.6 Windows at scale

Windows remoting is **WinRM** (or SSH on newer Windows). It is not “SSH with backslashes.”

```yaml
ansible_connection: winrm
ansible_winrm_transport: ntlm   # or kerberos / credssp
ansible_winrm_server_cert_validation: validate
ansible_user: "{{ vault_win_user }}"
ansible_password: "{{ vault_win_password }}"
```

Production Windows patterns:

| Topic | Guidance |
|-------|----------|
| Kerberos | Prefer domain join + Kerberos over stored local admin passwords |
| HTTPS WinRM | Certificates; do not `ignore` validation in prod |
| Become | `ansible.builtin.runas` with a service account |
| Package | `win_chocolatey`, `win_feature`, `win_updates` |
| Pathing | Always use `win_*` modules; `copy` vs `win_copy` |
| Reboots | `win_reboot` with `connect_timeout`; inventory can look “dead” mid-patch |
| Execution policy | Signed scripts vs `bypass`—do not globally bypass |

```yaml
- name: Install IIS
  ansible.windows.win_feature:
    name: Web-Server
    state: present
    include_management_tools: true

- name: Windows updates (lab window)
  ansible.windows.win_updates:
    category_names: ['SecurityUpdates']
    reboot: true
```

Patching 2,000 Windows hosts on a single job without **serial + reboot batches** will knock over AD-dependent apps. Treat AD, DNS, and certificate authorities as **their own** rolling plans.

**PowerShell remoting quotas** and WinRM `MaxConcurrentOperationsPerUser` will throttle you. The failure looks like random `401`/`500` from WinRM. Tune the hosts **or** reduce forks.

---

## 65.7 Idempotency bugs that survive code review

Idempotency means: second run reports **ok, not changed**, and the system is already in the desired state. Bugs:

### 65.7.1 `command` / `shell` without `creates`/`removes`

```yaml
# bad
- command: /usr/local/bin/migrate.sh

# better
- command: /usr/local/bin/migrate.sh
  args:
    creates: /var/lib/myapp/migrate.done
```

Better still: a module or a migration tool that is itself idempotent.

### 65.7.2 Templates that include timestamps or random IDs

Every run rewrites the file, restarts the service, flaps connections. Use `{{ ansible_managed }}` without a clock, or `force: false` patterns carefully.

### 65.7.3 `latest` package state

`state: latest` is not deterministic across a two-hour rolling window. Pin versions. Bake AMIs (Chapter 24) for the base layer; Ansible configures **instance-specific** data.

### 65.7.4 Non-commutative tasks

Task A then B works; B then A fails. Parallel `async` with `poll: 0` on dependent tasks is a classic. `serial: 1` is not a substitute for explicit `dependencies` in roles.

### 65.7.5 Facts that lie

`ansible_memory_mb` on a containerized execution environment is the **EE**, not the target, if you mixed connections. Always verify `inventory_hostname` in debug when writing `when:` on memory size.

### 65.7.6 `lineinfile` wars

Two roles editing the same file with `lineinfile` cause oscillation. Use a **template** owned by one role, or `blockinfile` with unique markers, or `ini_file`/`xml` modules.

### 65.7.7 Handlers that never fire or fire too much

Handlers run once at end by default. A notify from a `changed` task that **always** changes (see 65.7.2) restarts nginx every run. Conversely, `meta: flush_handlers` mid-play is required if the next task needs the restarted service.

```yaml
- name: Deploy unit
  copy: { src: app.service, dest: /etc/systemd/system/app.service }
  notify: reload systemd

- meta: flush_handlers

- name: Start app
  service: { name: app, state: started }
```

### 65.7.8 Checksums vs `remote_src`

`get_url` with a URL that returns a new object every time (latest) always changes. Pin artifact URLs to versioned object storage.

---

## 65.8 Collections, execution environments, and dependency hell

Pin collections in `requirements.yml`:

```yaml
collections:
  - name: ansible.windows
    version: ">=2.2.0,<3.0.0"
  - name: community.general
    version: "8.6.1"
```

AWX projects should install collections into the EE image or a documented `collections/requirements.yml` at job start. “Works on my laptop collection set” is not prod.

Python deps for modules (boto3, pywinrm) belong in the **EE**, not `pip install` on a shared controller during the change window.

---

## 65.9 Secrets, Vault, and lookup plugins

Ansible Vault in Git: decrypt in AWX via vault credential. **Do not** put prod Vault passwords in the project.

Better: `ansible.builtin.unvault` only for small secrets; prefer HashiCorp Vault / AWS SSM lookups at runtime with **AppRole or IAM** on the execution node.

Log redaction: AWX may still print `changed` diffs. `no_log: true` on tasks that handle passwords. Test that failed jobs do not dump secrets in stderr.

---

## 65.10 Worked incident: rolling update of a Python app

**Symptom:** After a job template run, 15% of hosts serve old code, 5% error with missing wheel.

**Causes found:**

1. Inventory cache omitted new ASG instances; they never got the job.
2. `pip` module without `version:` installed different versions from PyPI mid-window (`latest`).
3. `serial: 100%` because someone copied a debug template.
4. Health check hit the **local** nginx default page (`uri` to localhost vs `ansible_host`).

**Fix:** cache off, pin wheels on internal artifactory, `serial: 20%`, health check to LB target, fail on empty host list, extra-var `release_sha` from SCM tag only.

---

## 65.11 Observability of configuration management

Export AWX job events to the same SIEM as SSH. Alert on:

- Job failure rate
- `changed` count spikes (unexpected drift or idempotency bug)
- Playbook runtime SLO (Chapter 68) for the patch window

`changed` should be **rare** on a converged fleet except during planned releases. A nightly cron that changes 2,000 files is a bug.

---

## 🧪 Lab 65.1 — Dynamic groups and empty limit

1. Create two inventory groups `web` and `web_canary` with dummy hosts (`ansible_connection=local`).
2. Run a playbook with `--limit web_canaryy` (typo). Record whether zero hosts ran.
3. Add a fail task when `play_hosts | length == 0` (or AWX “prevent empty”).
4. Graph inventory with `ansible-inventory --graph`.

---

## 🧪 Lab 65.2 — Serial with a fake health check

1. Three local hosts as `connection: local` with different `ansible_host`.
2. Play with `serial: 1` that writes a version file and “health checks” it.
3. Make host 2 fail the check. Confirm host 3 never starts (`max_fail_percentage` / `any_errors_fatal` variants).
4. Write which setting matches your production risk appetite.

---

## 🧪 Lab 65.3 — Idempotency hunt

1. Write a role that uses `lineinfile` twice on `/tmp/demo.conf` from two files (simulate two roles).
2. Run three times; observe oscillation (`changed` forever).
3. Replace with a single `template`.
4. Prove second run is `ok`.

---

## 🧪 Lab 65.4 — Windows dry-run (if you have a lab VM)

1. Enable WinRM HTTPS with a real cert (or a lab CA).
2. Run `win_ping`.
3. Install a feature; re-run; confirm `changed=0`.
4. If you have no Windows VM, write the playbook anyway and peer-review `ansible_connection` vars.

---

## 65.12 Controller hardening checklist

| Control | Why |
|---------|-----|
| SSO + MFA to AWX | Shared local admin is an incident |
| Credential plugins (HashiVault) | No static SSH keys in DB if avoidable |
| Project update before job | Prevents running stale Git |
| Approval node in workflow for prod | Human gate |
| Disable extra vars on prod templates | Or allowlist keys |
| Isolated EE images, scanned | Supply chain (Chapter 69) |
| Backup AWX DB | Controller loss = no audited remediations |

---

## Review questions

1. Why can a 30-minute inventory cache be as dangerous as a wrong playbook?
2. What is job slicing, and when does it break rolling-update assumptions?
3. Contrast `serial`, `max_fail_percentage`, and `any_errors_fatal` with a concrete example.
4. Give three distinct idempotency bugs and a test that would catch each.
5. Why is `state: latest` incompatible with a two-hour rolling window?
6. What RBAC split belongs between playbook authors and credential owners in AWX?
7. How does WinRM throttling present in logs, and what are two mitigations?
8. Why is `--check` a weak guarantee for rolling deploys?
9. Where should collection versions be pinned, and what happens if AWX uses a different EE than developers?
10. Design an AWX workflow for prod: lint → check mode on canary inventory → approval → serial prod. What extra var is forbidden?

---

## Further practice

Chapter 23 for role layout; Chapter 24 for “Ansible should not bake every package every night”; Chapter 67 for how GitOps and Ansible jobs coexist without fighting.
