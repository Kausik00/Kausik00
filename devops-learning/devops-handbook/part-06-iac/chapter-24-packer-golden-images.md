# Chapter 24: Packer & Golden Images

*DevOps Handbook — Pages 108–112 of this PDF edition*
---

## 24.1 Golden images and the immutable infrastructure pattern

A **golden image** (or **machine image**) is a pre-baked AMI, Azure image, or GCP image with the OS hardened, agents installed, and dependencies cached. New instances launch from the image instead of running lengthy bootstrap scripts on every boot.

| Approach | Boot time | Drift risk | Rollback |
|----------|-----------|------------|----------|
| **Configure at boot** (cloud-init, Ansible) | Slower | Higher (scripts change) | Harder |
| **Golden image** (Packer) | Fast | Lower (versioned AMIs) | Revert launch template |
| **Containers** | Fastest | Lowest for app layer | Image tag/digest |

**Packer** (HashiCorp) builds images across providers from a single template. Pair Packer with Terraform (provision infrastructure) and Ansible (configure during build) for a complete pipeline.

---

## 24.2 Packer workflow

```bash
packer init .                    # Install plugins
packer validate amazon-linux.pkr.hcl
packer build amazon-linux.pkr.hcl
packer build -var "region=us-west-2" amazon-linux.pkr.hcl
```

Packer launches a temporary builder instance, runs **provisioners**, creates an image snapshot, then terminates the builder.

---

## 24.3 AWS EBS builder example

`amazon-linux.pkr.hcl`:

```hcl
packer {
  required_version = ">= 1.10.0"
  required_plugins {
    amazon = {
      version = ">= 1.2.8"
      source  = "github.com/hashicorp/amazon"
    }
    ansible = {
      version = ">= 1.1.0"
      source  = "github.com/hashicorp/ansible"
    }
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "ami_prefix" {
  type    = string
  default = "acme-base"
}

locals {
  timestamp = regex_replace(timestamp(), "[- TZ:]", "")
}

source "amazon-ebs" "base" {
  ami_name      = "${var.ami_prefix}-${local.timestamp}"
  instance_type = "t3.small"
  region        = var.region

  source_ami_filter {
    filters = {
      name                = "al2023-ami-*-x86_64"
      root-device-type    = "ebs"
      virtualization-type = "hvm"
    }
    owners      = ["amazon"]
    most_recent = true
  }

  ssh_username = "ec2-user"

  tags = {
    Name        = "${var.ami_prefix}-${local.timestamp}"
    BuiltBy     = "packer"
    Environment = "shared"
  }
}

build {
  sources = ["source.amazon-ebs.base"]

  provisioner "shell" {
    inline = [
      "sudo dnf update -y",
      "sudo dnf install -y amazon-cloudwatch-agent jq"
    ]
  }

  provisioner "ansible" {
    playbook_file = "./ansible/base.yml"
    extra_arguments = [
      "--become",
      "-e", "ansible_python_interpreter=/usr/bin/python3"
    ]
  }

  provisioner "shell" {
    inline = [
      "sudo cloud-init clean --logs",
      "sudo rm -f /root/.ssh/authorized_keys /home/ec2-user/.ssh/authorized_keys",
      "sudo shred -u /etc/ssh/ssh_host_* || true"
    ]
  }
}
```

The final **cleanup provisioner** removes SSH host keys and authorized keys so clones do not share credentials.

---

## 24.4 Provisioners

| Provisioner | Use case |
|-------------|----------|
| `shell` | Inline scripts, package installs |
| `ansible` / `ansible-local` | Configuration management during build |
| `file` | Upload static files |
| `windows-shell` / `powershell` | Windows images |
| `docker` | Build Docker images (different builder) |

Order matters: install packages before Ansible, clean secrets last.

`ansible/base.yml`:

```yaml
---
- hosts: default
  become: true
  tasks:
    - name: Harden sshd
      lineinfile:
        path: /etc/ssh/sshd_config
        regexp: '^PermitRootLogin'
        line: 'PermitRootLogin no'
      notify: restart sshd

    - name: Install node exporter
      unarchive:
        src: https://github.com/prometheus/node_exporter/releases/download/v1.8.2/node_exporter-1.8.2.linux-amd64.tar.gz
        dest: /usr/local/bin
        remote_src: true
        extra_opts: [--strip-components=1]
        include: ['node_exporter']

    - name: Enable node exporter systemd unit
      copy:
        dest: /etc/systemd/system/node_exporter.service
        content: |
          [Unit]
          Description=Node Exporter
          [Service]
          ExecStart=/usr/local/bin/node_exporter
          [Install]
          WantedBy=multi-user.target
      notify: daemon reload

  handlers:
    - name: restart sshd
      service: { name: sshd, state: restarted }
    - name: daemon reload
      systemd: { daemon_reload: true }
```

---

## 24.5 Multi-region and shared images

```hcl
build {
  sources = [
    "source.amazon-ebs.us_east",
    "source.amazon-ebs.eu_west"
  ]
  # Same provisioners run in each region
}
```

Use **AMI sharing** across accounts via `ami_users` or AWS Organizations. In Terraform, data source the latest Packer AMI:

```hcl
data "aws_ami" "app_base" {
  most_recent = true
  owners      = ["self"]

  filter {
    name   = "name"
    values = ["acme-base-*"]
  }

  filter {
    name   = "tag:BuiltBy"
    values = ["packer"]
  }
}

resource "aws_launch_template" "app" {
  name          = "app-lt"
  image_id      = data.aws_ami.app_base.id
  instance_type = "t3.medium"
}
```

---

## 24.6 Versioning, promotion, and CI

Image naming strategy:

```
acme-base-20250901120000   # Timestamp build
acme-base-v1.4.2           # Semantic version tag
```

Pipeline stages:

1. **Build** on merge to `main` (Packer)
2. **Scan** AMI or exported container with **Inspector**, **Trivy**, or **ECR scan**
3. **Promote** to staging launch template
4. **Bake period** — run integration tests
5. **Promote** to production; keep last N AMIs for rollback

```yaml
# CI excerpt
- run: packer build -machine-readable . | tee build.log
- run: |
    AMI_ID=$(grep 'artifact,0,id' build.log | cut -d, -f6 | cut -d: -f2)
    aws ec2 create-tags --resources "$AMI_ID" --tags Key=Version,Value=${{ github.sha }}
```

Store Packer variables and plugin versions in Git; pin plugin versions in `required_plugins`.

---

## 24.7 Security and compliance

- **No secrets in images** — use instance roles and secrets managers at runtime
- **CIS benchmarks** — apply hardening roles (DevSec hardening collection)
- **SBOM** — document packages; scan for CVEs before promotion
- **Immutable updates** — new AMI + rolling instance refresh, not SSH patching in prod
- **Signed AMIs** — AWS EC2 Image Builder supports compliance pipelines

| Anti-pattern | Better approach |
|--------------|-----------------|
| Embedding API keys in image | IAM instance profile |
| `:latest` untagged AMIs | Explicit version tags + lifecycle policy |
| Manual AMI copies | Automated pipeline with scan gates |

---

## 24.8 Chapter summary

- **Golden images** reduce boot time and configuration drift; Packer automates their creation.
- Use **provisioners** in order: update OS, configure, then **sanitize** SSH keys and logs.
- Integrate Packer with **CI scan gates** and Terraform **launch templates** referencing latest approved AMI.
- Treat images as **versioned artifacts** with promotion and rollback paths.

---

## 🧪 Lab 24.1

1. Install Packer and initialize the Amazon plugin.
2. Build an Amazon Linux 2023 AMI with nginx and the CloudWatch agent.
3. Launch an EC2 instance from the AMI and verify services without extra user-data.
4. Add a cleanup provisioner that removes build-time SSH artifacts.

---

## 🧪 Lab 24.2

1. Wire Packer to Ansible for CIS-style sshd hardening.
2. Output the AMI ID from CI and pass it to a Terraform `aws_launch_template`.
3. Implement AMI retention: keep last 5 images, deregister older AMIs.

---

## Review questions

1. Why should SSH host keys be regenerated (or removed) during the Packer build?
2. When would you choose cloud-init bootstrap over golden images?
3. How does Terraform discover the latest Packer-built AMI safely?
4. What security risks exist if secrets are baked into an AMI?
5. Describe a promotion pipeline from build to production launch template.

---

*Next: [Chapter 25 — Policy as Code](./chapter-25-policy-as-code.md)*
