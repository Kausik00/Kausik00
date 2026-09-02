# Chapter 17: Go for CLI Tools and Operators

*DevOps Handbook — Pages 74–78 of this PDF edition*
---

## 17.1 Why Go in the DevOps toolchain

Go (Golang) compiles to **single static binaries** with no runtime dependency—ideal for CLIs shipped to servers, minimal container images, and Kubernetes **operators**. The cloud-native ecosystem (Docker, Kubernetes, Terraform, Prometheus, Helm) is largely Go.

| Strength | DevOps use |
|----------|------------|
| Fast compile | Quick iteration in CI |
| Static binary | Copy to jump host, air-gapped env |
| Concurrency | Parallel checks across hosts/regions |
| Strong stdlib | HTTP, TLS, encoding/json |
| kubebuilder ecosystem | Custom controllers and operators |

Python wins for quick scripts; Go wins for **distributable tools** and **control loops**.

---

## 17.2 Module setup

Go 1.21+ with modules (no `$GOPATH` src layout required):

```bash
mkdir -p ~/go/devops-check && cd ~/go/devops-check
go mod init github.com/you/devops-check
```

```
devops-check/
  cmd/
    devops-check/
      main.go
  internal/
    health/
      health.go
  go.mod
  go.sum
```

Build:

```bash
go build -o bin/devops-check ./cmd/devops-check
GOOS=linux GOARCH=amd64 go build -o bin/devops-check-linux ./cmd/devops-check
```

---

## 17.3 A minimal CLI with cobra (pattern)

Many projects use **spf13/cobra** for subcommands and flags:

```go
// cmd/devops-check/main.go
package main

import (
    "fmt"
    "os"

    "github.com/spf13/cobra"
    "github.com/you/devops-check/internal/health"
)

func main() {
    var url string
    var timeout int

    root := &cobra.Command{
        Use:   "devops-check",
        Short: "Operational health utilities",
    }

    checkCmd := &cobra.Command{
        Use:   "http",
        Short: "HTTP health check",
        RunE: func(cmd *cobra.Command, args []string) error {
            ok, err := health.CheckHTTP(url, timeout)
            if err != nil {
                return err
            }
            if !ok {
                return fmt.Errorf("unhealthy response from %s", url)
            }
            fmt.Println("OK")
            return nil
        },
    }
    checkCmd.Flags().StringVar(&url, "url", "", "URL to check")
    checkCmd.Flags().IntVar(&timeout, "timeout", 5, "timeout seconds")
    _ = checkCmd.MarkFlagRequired("url")

    root.AddCommand(checkCmd)
    if err := root.Execute(); err != nil {
        os.Exit(1)
    }
}
```

```go
// internal/health/health.go
package health

import (
    "net/http"
    "time"
)

func CheckHTTP(url string, timeoutSec int) (bool, error) {
    client := &http.Client{Timeout: time.Duration(timeoutSec) * time.Second}
    resp, err := client.Get(url)
    if err != nil {
        return false, err
    }
    defer resp.Body.Close()
    return resp.StatusCode >= 200 && resp.StatusCode < 300, nil
}
```

---

## 17.4 Error handling and exit codes

Go uses explicit error returns—no exceptions:

```go
if err := run(); err != nil {
    fmt.Fprintf(os.Stderr, "error: %v\n", err)
    os.Exit(1)
}
```

Wrap errors for context with Go 1.13+ `%w`:

```go
return fmt.Errorf("fetch config: %w", err)
```

CI systems depend on **non-zero exit** for failures—never swallow errors silently.

---

## 17.5 Concurrency for parallel probes

Checking hundreds of endpoints sequentially is slow. Use goroutines with bounded concurrency:

```go
sem := make(chan struct{}, 10) // max 10 concurrent
var wg sync.WaitGroup

for _, url := range urls {
    wg.Add(1)
    go func(u string) {
        defer wg.Done()
        sem <- struct{}{}
        defer func() { <-sem }()
        // check u
    }(url)
}
wg.Wait()
```

Always cap concurrency—unbounded goroutines against production can cause incidents.

---

## 17.6 Kubernetes operators (conceptual)

An **operator** extends Kubernetes with custom resources (CRDs) and a **control loop**:

```
Observe CR state → Compare desired vs actual → Act (create/update/delete) → Requeue
```

Built with **controller-runtime** or **kubebuilder**:

```bash
kubebuilder init --domain example.com --repo github.com/you/sidecar-operator
kubebuilder create api --group app --version v1 --kind SidecarConfig
```

DevOps engineers operate operators; platform teams author them for domain-specific automation (database failover, certificate renewal, tenant provisioning).

You don't need to write an operator on day one—**understand the pattern** when installing cert-manager, Prometheus operator, or custom internal controllers.

---

## 17.7 Testing Go CLIs

```go
// internal/health/health_test.go
func TestCheckHTTP(t *testing.T) {
    srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.WriteHeader(http.StatusOK)
    }))
    defer srv.Close()

    ok, err := CheckHTTP(srv.URL, 2)
    if err != nil || !ok {
        t.Fatalf("expected ok, got ok=%v err=%v", ok, err)
    }
}
```

Run `go test ./...` in CI; use **`httptest`** for HTTP without network flakiness.

---

## 17.8 Release and distribution

| Method | Notes |
|--------|-------|
| **GitHub Releases** | Attach cross-compiled binaries |
| **Homebrew tap** | macOS/Linux developer installs |
| **Container** | `FROM scratch` + static binary |
| **go install** | Private modules need GOPRIVATE |

Example multi-arch build with GoReleaser or raw `GOOS`/`GOARCH` matrix in Actions.

---

## 17.9 When not to use Go

- One-off 10-line file rename on a laptop → bash.
- Heavy data science or ML pipelines → Python.
- Team lacks Go experience and tool won't be maintained → Python with typed hints (mypy).

Choose Go when **shipping a binary** or **Kubernetes reconciliation** is the core requirement.

---

## 17.10 Chapter summary

- Go produces **static binaries** suited to CLIs and cloud-native tooling.
- Structure projects with **`cmd/`** and **`internal/`** packages.
- Use **cobra** (or flag stdlib) for UX; return proper **exit codes**.
- Bounded **concurrency** speeds checks without overloading targets.
- **Operators** implement control loops for Kubernetes custom resources.

---

## 🧪 Lab 17.1 — Multi-target HTTP checker

1. Implement `devops-check http --url` accepting multiple URLs or a file of URLs.
2. Run checks with max 5 concurrent workers; print failures to stderr.
3. Exit 1 if any fail; add `go test` with httptest server.

---

## 🧪 Lab 17.2 — Cross-compile release

1. Build linux/amd64 and darwin/arm64 binaries in CI (or locally).
2. Compute SHA256 checksums; upload as release artifacts in a practice repo.
3. Document install instructions in README.

---

## Review questions

1. Name two reasons Go is popular for Kubernetes ecosystem tools.
2. What is the purpose of the `internal/` directory convention?
3. Why cap goroutines when probing many hosts?
4. Describe the operator control loop in four steps.
5. When is Python a better choice than Go for DevOps tasks?

---

*Next: [Chapter 18 — JSON/YAML, Jinja2, and Templating](./chapter-18-json-yaml-jinja2.md)*
