# Chapter 23: Ansible — Playbooks, Roles, and Inventories

*DevOps Handbook — Pages 102–107 of this PDF edition*
---

## 23.1 Ansible in the IaC landscape

**Ansible** is an agentless configuration management and automation tool. It connects over SSH (Linux) or WinRM (Windows), pushes **modules** that declare desired state, and exits. Unlike Terraform, Ansible does not maintain a state file—it interrogates each host every run.

| Tool | Primary use | State |
|------|-------------|-------|
| Terraform | Provision cloud resources | Remote state file |
| Ansible | Configure OS, deploy apps, orchestrate | None (facts cache optional) |
| Packer | Build machine images | Ephemeral |
| Kubernetes | Run container workloads | etcd |

Ansible complements Terraform: Terraform creates the VPC and EC2 instances; Ansible installs nginx, agents, and application releases.

---

## 23.2 Inventory — defining targets

An **inventory** lists hosts and groups. Static INI format:

```ini
# inventories/production/hosts.ini
[web]
web01.example.com ansible_host=10.0.1.10
web02.example.com ansible_host=10.0.1.11

[db]
db01.example.com ansible_host=10.0.2.10

[web:vars]
ansible_user=ubuntu
ansible_ssh_private_key_file=~/.ssh/prod.pem

[production:children]
web
db
```

YAML inventory:

```yaml
all:
  children:
    web:
      hosts:
        web01.example.com:
          ansible_host: 10.0.1.10
      vars:
        http_port: 80
    db:
      hosts:
        db01.example.com:
          ansible_host: 10.0.2.10
```

### Dynamic inventory

Query cloud APIs at runtime:

```bash
# AWS EC2 dynamic inventory (ansible-core 2.12+)
ansible-inventory -i aws_ec2.yml --graph
```

`aws_ec2.yml`:

```yaml
plugin: amazon.aws.aws_ec2
regions:
  - us-east-1
filters:
  tag:Environment: production
  instance-state-name: running
keyed_groups:
  - key: tags.Role
    prefix: role
hostnames:
  - private-ip-address
```

Run against a group: `ansible-playbook site.yml -i aws_ec2.yml --limit role_web`

---

## 23.3 Playbooks — ordered automation

A **playbook** is YAML listing **plays** (mapped to host groups) and **tasks** (module calls).

`site.yml`:

```yaml
---
- name: Configure web tier
  hosts: web
  become: true
  vars:
    app_version: "2.4.1"

  pre_tasks:
    - name: Wait for SSH
      wait_for_connection:
        timeout: 300

  roles:
    - common
    - nginx
    - app_deploy

  post_tasks:
    - name: Verify health endpoint
      uri:
        url: "http://localhost/health"
        status_code: 200
      register: health
      retries: 5
      delay: 10
      until: health.status == 200
```

`playbook.yml` for a single concern:

```yaml
---
- name: Patch all production servers
  hosts: production
  become: true
  serial: "25%"          # Rolling update — 25% at a time
  max_fail_percentage: 0

  tasks:
    - name: Update packages (Debian)
      apt:
        update_cache: true
        upgrade: dist
      when: ansible_os_family == "Debian"

    - name: Reboot if required
      reboot:
        msg: "Rebooting after patching"
      when: reboot_required_file.stat.exists
```

---

## 23.4 Modules, idempotency, and handlers

```yaml
- name: Install and configure nginx
  hosts: web
  become: true

  tasks:
    - name: Install nginx package
      apt:
        name: nginx
        state: present
        update_cache: true

    - name: Deploy site config
      template:
        src: templates/nginx.conf.j2
        dest: /etc/nginx/sites-available/default
        validate: nginx -t -c %s
      notify: Reload nginx

    - name: Ensure nginx is running
      service:
        name: nginx
        state: started
        enabled: true

  handlers:
    - name: Reload nginx
      service:
        name: nginx
        state: reloaded
```

**Handlers** run once at the end of the play, only if notified. **Templates** use Jinja2 (`{{ ansible_hostname }}`). The `validate` parameter prevents deploying broken configs.

### Check mode and diff

```bash
ansible-playbook site.yml --check --diff   # Dry run with file diffs
ansible-playbook site.yml --tags deploy    # Run tagged tasks only
```

---

## 23.5 Roles — reusable bundles

Role layout:

```
roles/nginx/
├── defaults/main.yml      # Low precedence variables
├── vars/main.yml          # Role-internal vars
├── tasks/main.yml
├── handlers/main.yml
├── templates/nginx.conf.j2
├── files/ssl.crt
├── meta/main.yml          # Dependencies
└── README.md
```

`roles/nginx/tasks/main.yml`:

```yaml
---
- name: Install nginx
  package:
    name: "{{ nginx_package }}"
    state: present

- name: Configure worker processes
  lineinfile:
    path: /etc/nginx/nginx.conf
    regexp: '^worker_processes'
    line: "worker_processes {{ nginx_worker_processes }};"
  notify: Reload nginx
```

`roles/nginx/defaults/main.yml`:

```yaml
nginx_package: nginx
nginx_worker_processes: auto
```

`meta/main.yml` declares dependencies:

```yaml
dependencies:
  - role: common
```

Install from Ansible Galaxy: `ansible-galaxy install geerlingguy.docker`

---

## 23.6 Variables and facts precedence

Ansible merges variables from many sources. Highest wins (simplified):

| Priority (high → low) | Source |
|-----------------------|--------|
| Extra vars (`-e`) | CLI |
| Task vars | `vars:` on task |
| Block/play vars | `vars:` in play |
| Host facts / host_vars | `host_vars/web01.yml` |
| Role defaults | `defaults/main.yml` |

```bash
ansible-playbook site.yml -e "app_version=2.5.0"
```

Gather facts: `setup` module runs automatically. Disable with `gather_facts: false` for speed on large fleets.

Custom facts in `/etc/ansible/facts.d/*.fact` (JSON or executable).

---

## 23.7 Vault, collections, and project structure

Encrypt secrets with **Ansible Vault**:

```bash
ansible-vault create group_vars/production/vault.yml
ansible-vault edit group_vars/production/vault.yml
ansible-playbook site.yml --ask-vault-pass
# Or --vault-password-file for CI
```

```yaml
# group_vars/production/vault.yml (encrypted)
db_password: "s3cr3t"
```

Reference in templates: `{{ db_password }}` — never commit plaintext secrets.

**Collections** package modules and roles (`ansible-galaxy collection install amazon.aws`).

Recommended layout:

```
ansible/
├── ansible.cfg
├── inventories/
│   ├── staging/
│   └── production/
├── group_vars/
├── host_vars/
├── roles/
├── playbooks/
│   └── site.yml
└── requirements.yml
```

`ansible.cfg`:

```ini
[defaults]
inventory = inventories/production
roles_path = roles
host_key_checking = True
retry_files_enabled = False
interpreter_python = auto_silent

[privilege_escalation]
become = True
become_method = sudo
```

---

## 23.8 Ansible in CI/CD

```yaml
# GitHub Actions excerpt
- name: Run Ansible lint
  run: pip install ansible-lint && ansible-lint playbooks/

- name: Molecule test
  run: cd roles/nginx && molecule test

- name: Deploy to staging
  run: |
    ansible-playbook playbooks/site.yml \
      -i inventories/staging \
      --private-key "${{ secrets.SSH_KEY }}" \
      --vault-password-file vault-pass.sh
```

Use **Molecule** for role testing with Docker or cloud drivers. Limit production deploys to tagged releases and `--check` on canary hosts first.

---

## 23.9 Chapter summary

- **Inventory** defines where Ansible runs; use **dynamic inventory** for cloud fleets.
- **Playbooks** orchestrate tasks; **roles** encapsulate reusable configuration.
- Ansible is **idempotent**—second runs should change nothing if state is correct.
- Protect secrets with **Ansible Vault**; test roles with **Molecule** and lint with **ansible-lint**.

---

## 🧪 Lab 23.1

1. Create a static inventory with `web` and `db` groups (use Vagrant or multipass VMs).
2. Write a playbook that installs nginx and deploys a custom `index.html` via template.
3. Extract nginx configuration into a role with defaults and handlers.
4. Encrypt a database password with Ansible Vault and use it in a template.

---

## 🧪 Lab 23.2

1. Configure AWS EC2 dynamic inventory and run `ansible all -m ping`.
2. Add a `serial: 1` rolling restart play for a fake application service.
3. Set up Molecule with the Docker driver to test your nginx role.

---

## Review questions

1. Why is Ansible described as "agentless," and what are the trade-offs?
2. What triggers a handler to run, and when do handlers execute?
3. How does `--check` mode differ from running tasks with `state: absent`?
4. Where should role defaults go versus play-level `vars`?
5. How would you safely store and use production secrets in Ansible?

---

*Next: [Chapter 24 — Packer & Golden Images](./chapter-24-packer-golden-images.md)*
