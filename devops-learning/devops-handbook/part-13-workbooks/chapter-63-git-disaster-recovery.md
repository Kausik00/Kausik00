# Chapter 63: Git Disaster Recovery

*DevOps Handbook — Workbook*
---

## 63.1 Disasters Git will not magically undo

Git is an object database plus pointers (refs). Most “lost work” is a **ref** problem, not a missing object problem. The objects often still exist as dangling commits, reflog entries, or packfiles on another clone. This workbook covers recovering commits, rewriting history safely, splitting and grafting repositories, large-file disasters, commit signing, and monorepo workflows that do not require heroics.

Golden rule: **if it was ever pushed and you do not own every clone, do not `reset --hard` shared branches.** Recover with revert, revert-of-revert, or a recovery branch. Force-push is a coordination protocol, not a delete key.

| Situation | Safe default | Dangerous default |
|-----------|--------------|-------------------|
| Bad commit on `main` (pushed) | `git revert` | `reset --hard` + force-push |
| Unpushed local mess | reflog + `reset` | deleting `.git` |
| Secrets committed | rotate secret + history rewrite **if** policy allows | “it’s only in git for 5 minutes” |
| Huge binary committed | LFS migrate or `git filter-repo` | endless `git gc` prayers |
| Split a monolith | `git filter-repo --path` | copy files without history |

---

## 63.2 Mental model for recovery: objects, refs, reflog

```
blob (file bytes) ← tree (directory) ← commit (snapshot + parents) ← tag
                                                      ↑
                                         refs/heads/*, refs/tags/*, HEAD
                                         refs/stash, refs/notes
```

```bash
git cat-file -t HEAD
git log --oneline --decorate --graph --all | head
git reflog | head -30
git fsck --lost-found
```

The **reflog** is per-repository, typically 90 days (`gc.reflogExpire`). It is your local time machine. CI ephemeral clones often have **no** useful reflog. Recover from:

1. The developer laptop that had the commit.
2. The remote’s reflog if the host provides it (GitHub does not expose server reflog to you; GitLab sometimes has events).
3. Other remotes/forks.
4. CI artifacts that ran `git clone` *before* the force-push and still sit on a runner disk (rare, lucky).

```bash
# Recover a commit you had locally ten minutes ago
git reflog
git checkout -b recover/lost-feature HEAD@{12}
# or
git merge ORIG_HEAD
```

`ORIG_HEAD` is set by destructive operations (`reset`, `merge`). It is a one-slot undo. Do not overwrite it by running another reset before you inspect it.

---

## 63.3 Recovering commits: a ranked playbook

### 63.3.1 Dangling commits after reset

```bash
git reset --hard HEAD~3          # oops, unpushed
git reflog
git cherry-pick <old-sha>
# or restore the branch pointer
git reset --hard <old-sha>
```

### 63.3.2 Recover a deleted branch on the remote

If deletion was recent, the SHA is in the PR, the bot comment, or `git fetch origin refs/pull/123/head` (GitHub).

```bash
git fetch origin pull/123/head:pr-123
git checkout -b restore/feature pr-123
git push -u origin restore/feature
```

GitHub/GitLab **events** and **activity** UIs often list the SHA after branch deletion. Write that SHA in the incident ticket immediately.

### 63.3.3 Recover after a bad rebase

Rebase copies commits; old SHAs remain until GC.

```bash
git reflog | grep rebase
git fsck --unreachable | head
git checkout -b recover/pre-rebase <sha-before-rebase>
```

If the rebase was pushed with lease:

```bash
git push --force-with-lease origin feature
```

`--force-with-lease` fails if someone else pushed. Bare `--force` is how you delete a colleague’s commits.

### 63.3.4 Recover a single file from history

```bash
git log --all -- full/path/to/file
git checkout <sha> -- full/path/to/file
git restore --source=<sha> -- full/path/to/file
```

### 63.3.5 Stash disasters

```bash
git stash list
git stash show -p stash@{2}
git stash apply stash@{2}     # keep stash
# Dropped stash: still in reflog
git fsck --unreachable | grep commit
```

Dropped stashes are commits. `git fsck` plus `git show` recovers them until GC.

---

## 63.4 When rewriting history is justified

History rewrite (`filter-repo`, `rebase -i`, `commit --amend` on a shared SHA) is justified for:

- Secrets that must not remain fetchable (plus **rotation**—rewrite is not encryption).
- Illegal/copyrighted blobs.
- Splitting a repository with a clean path filter.
- Converting a project to Git LFS **before** wide clone adoption.

It is **not** justified for “the commit message has a typo on main.”

### 63.4.1 BFG / git-filter-repo

`git filter-repo` is the current recommendation (BFG is older but still seen).

```bash
# Remove a file from all history (destructive; coordinate)
git filter-repo --invert-paths --path secrets.env

# Keep only one subdirectory as new root (repo split)
git filter-repo --path src/billing/ --path-rename src/billing/:
```

After rewrite:

1. All SHAs change. Open PRs are toast.
2. Every clone must re-clone or hard-reset to the new history.
3. Announce a **cutover window**.
4. Run `git reflog expire --expire=now --all && git gc --prune=now` only after backups exist.

Mirror backup **before** rewrite:

```bash
git clone --mirror git@github.com:org/app.git app.git.bak
```

---

## 63.5 Split repositories without losing blame

Monolith → multi-repo is a **filter** plus **remote** plus **CI** cutover, not a folder copy.

**Method A — filter-repo (preserve billing history):**

```bash
git clone --no-local monolith billing-tmp
cd billing-tmp
git filter-repo --path services/billing/ --path-rename services/billing/:
git remote add origin git@github.com:org/billing.git
git push -u origin main
```

**Method B — subtree split (repeatable extracts):**

```bash
git subtree split -P services/billing -b split/billing
git push origin split/billing:main
```

**Method C — keep a monorepo** (often correct): use CODEOWNERS, path-filtered CI, and sparse checkout instead of splitting. Splitting is expensive socially (issues, permissions, versioning).

| Need | Prefer |
|------|--------|
| Independent lifecycle + different access | Split |
| Shared types and atomic cross-service change | Monorepo |
| Accidental coupling via relative imports | Split *after* API boundaries exist |

Move **tags** and **release notes** explicitly; filter-repo can keep tags that point at rewritten commits.

---

## 63.6 Large-file issues: the clone that never finishes

Git stores snapshots. A 200 MB video committed once lives **forever** in packfiles unless rewritten. Symptoms: 10-minute clones, LFS pointer confusion, `GH001: Large files detected`, runner disk full.

```bash
git rev-list --objects --all \
  | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' \
  | awk '/^blob/ {print $3, $4}' \
  | sort -n | tail -20
```

Or:

```bash
git verify-pack -v .git/objects/pack/*.idx | sort -k3 -n | tail
```

### 63.6.1 Git LFS

```bash
git lfs install
git lfs track "*.psd" "*.mp4" "*.pt"
git add .gitattributes
```

**Migrating existing history** requires `git lfs migrate import --include='*.psd' --everything` and a coordinated force-push. Partial migration (only new commits) leaves old blobs in history—clones stay huge.

**Pointer files:** if you see 130-byte files instead of binaries, LFS smudge did not run (`git lfs pull`). CI must install LFS **before** checkout (GitHub Action `lfs: true`).

### 63.6.2 Partial clone and sparse checkout

```bash
git clone --filter=blob:none --sparse git@github.com:org/mono.git
cd mono
git sparse-checkout set services/billing
```

Monorepos should document this as the **default developer clone**, not an expert trick.

### 63.6.3 GitHub/GitLab file size limits

Even with LFS, some hosts cap LFS bandwidth. Design artifact storage (S3, package registries) for build outputs; Git is for source.

---

## 63.7 Signing: commits, tags, and verifying what you ship

Signing proves **who** created a commit/tag with a key you trust—not that the code is correct.

```bash
git config --global commit.gpgsign true
git config --global user.signingkey <KEYID>
git commit -S -m "feat: enable widget"
git tag -s v1.2.3 -m "release 1.2.3"
git log --show-signature
git verify-tag v1.2.3
```

**SSH signing** (Git 2.34+ / GitHub):

```bash
git config gpg.format ssh
git config user.signingkey ~/.ssh/id_ed25519.pub
```

**Disaster modes:**

| Problem | Recovery |
|---------|----------|
| Unsigned commits on a protected branch | Branch protection: require signed commits; rebase only on unpushed branches |
| Expired GPG key | Extend expiry, or rotate and keep old key for verify |
| Bot cannot sign | Dedicated bot key in HSM/KMS; never share a human key |
| `gpg failed to sign` in CI | Missing pinentry/TTY; use `gpg --batch` and a secret agent |
| Verified badge missing | Email in commit must match identity bound to the key |

Protected branches should **require** signatures *and* linear history if you need an auditable main. Unsigned merge commits from the UI may bypass local `gpgsign`.

Merge commits from GitHub’s “merge” button are signed by GitHub’s key when “vigilant mode” / web signing is enabled—understand whose key you trust.

---

## 63.8 Monorepo workflows that survive 2,000 engineers

A monorepo disaster is usually **CI cost**, **acl**, or **accidental atomicity**, not Git physics.

### 63.8.1 Path-filtered CI

```yaml
# GitHub Actions example
on:
  pull_request:
    paths:
      - 'services/billing/**'
      - 'packages/billing-sdk/**'
      - '.github/workflows/billing.yml'
```

Without path filters, a docs typo rebuilds 400 services. That is an availability incident for the engineering org.

### 63.8.2 CODEOWNERS and merge queues

```
/services/billing/  @org/billing-oncall
/infra/terraform/   @org/platform
```

Merge queues (GitHub merge queue, GitLab merge trains) reduce “main is red because two green PRs conflict in spirit.”

### 63.8.3 Sparse checkout + partial clone (developer default)

Document a `tools/bootstrap` that sets:

- `core.fsmonitor` / Watchman on macOS
- `feature.manyFiles`
- sparse patterns per team

### 63.8.4 Cross-service changes

The point of a monorepo is **one commit** can update API producer and consumer. Disaster: people split that into two PRs “to look smaller” and deploy the consumer first. Use merge queues + deployment order tooling, or explicitly allow proto-breaking changes only with versioned packages.

### 63.8.5 Submodules vs subtrees vs packages

| Mechanism | Disaster mode |
|-----------|---------------|
| Submodules | Detached SHA, uninitialized clones, “works on my machine” |
| Subtree | Duplicate history, messy merges |
| Package registry | Version skew, but bisect stays sane |

Prefer packages for shared libraries unless you truly need a single SHA across all services.

---

## 63.9 Bisect, blame, and recovering *understanding*

Disaster recovery includes **finding the commit that broke prod**.

```bash
git bisect start
git bisect bad HEAD
git bisect good v1.44.0
git bisect run ./scripts/repro.sh
```

`repro.sh` must be **deterministic** (no live network flake). For monorepos, bisect across unrelated paths is noisy—limit with `-- path/`.

```bash
git log -S 'DangerousFlag' --oneline
git blame -L 40,80 src/foo.c
git log -p --follow -- src/renamed.go
```

---

## 63.10 Worked incident: “main was force-pushed”

**Timeline:** A maintainer rebased `main` locally onto an experimental branch and `git push --force` (no lease). Two hours of commits vanished from `origin/main`. CI deployed the rewritten history. Customer-facing rollback to “previous main” is now ambiguous.

**Response:**

1. Freeze deploys.
2. Collect SHAs from GitHub compare view, Slack paste, and a laptop that had not fetched (`git reflog` on that laptop shows `origin/main@{1}`).
3. Push recovered chain to `main-recovered`.
4. Fast-forward or merge `main-recovered` into `main` **without** another force if possible (merge commit documents the incident).
5. If force is required, use a documented window, `--force-with-lease`, and a backup tag `incident/main-pre-rewrite`.
6. Enable branch protection: deny force push, require linear history *or* merge commits—pick one and enforce it.
7. Rotate any credentials that existed only in the dropped commits if those commits were public.

---

## 63.11 Backup architecture for Git

Git hosting is not your only backup:

| Layer | What it saves |
|-------|----------------|
| Forge (GitHub) | Primary collaboration |
| Mirror clone cron | Independent object store |
| Developer laptops | Reflog, stashes, unpushed work |
| Artifact storage | Built images; not a Git substitute |
| Legal hold / archive | Compliance copies |

```bash
# hourly mirror (read-only credentials)
git clone --mirror --filter=blob:none git@github.com:org/app.git || git -C app.git fetch --prune
```

Test **restore** quarterly: provision a new empty repo, push the mirror, run CI. Unrestorable backups are theater.

---

## 🧪 Lab 63.1 — Reflog rescue

1. Create a repo, make five commits on `feature`.
2. `git reset --hard HEAD~4`.
3. Recover all five commits using only `git reflog`.
4. Delete the branch, expire reflog (`git reflog expire --expire=now --all && git gc --prune=now`) on a **copy**. Confirm recovery is impossible. This is why you backup before GC.

---

## 🧪 Lab 63.2 — Split a path into a new repository

1. Create a repo with `svc/a` and `svc/b` files with distinct commit messages.
2. Use `git filter-repo --path svc/a/ --path-rename svc/a/:` (or subtree split).
3. Verify `git log` in the new repo contains only `svc/a` commits.
4. Confirm `git blame` still attributes lines.

---

## 🧪 Lab 63.3 — LFS pointer confusion

1. Track `*.bin` with LFS, commit a 5 MB file.
2. Clone **without** LFS installed; inspect the pointer file.
3. Install LFS, `git lfs pull`, confirm smudge.
4. Add the same large file **without** LFS on a branch; push to a test remote if available and observe rejection.

---

## 🧪 Lab 63.4 — Signed tags and a “forged” unsigned tag

1. Create a GPG or SSH signing key in the lab.
2. Tag `v0.1.0` signed and `v0.1.1` unsigned.
3. `git verify-tag` both.
4. Enable a dummy policy: a `pre-receive` or CI job that fails unsigned tags.

---

## 63.12 Command cheat sheet

| Intent | Command |
|--------|---------|
| Undo unpushed commit, keep files | `git reset --soft HEAD~1` |
| Undo unpushed commit, discard files | `git reset --hard HEAD~1` |
| Undo pushed commit | `git revert <sha>` |
| Find lost SHA | `git reflog`, `git fsck` |
| Recover file | `git restore --source=<sha> -- path` |
| Safer force | `git push --force-with-lease` |
| History purge | `git filter-repo` |
| Size hunt | `git rev-list --objects --all` + cat-file |
| Bisect | `git bisect run ./repro.sh` |

---

## Review questions

1. Why does `git reset --hard origin/main` on a laptop not prove the commit is gone from the universe?
2. Contrast `revert` and `reset` for a pushed commit on a shared branch.
3. What does `--force-with-lease` protect that `--force` does not?
4. After `git filter-repo`, why must every developer re-clone? What breaks if they `pull`?
5. List two reasons splitting a monorepo can reduce velocity even if clones get faster.
6. A clone contains 130-byte `.pt` files. What is wrong, and how do you fix CI?
7. How do you recover a dropped stash after `git stash drop` but before GC?
8. Who is the signer when a commit is made via the GitHub web UI versus `git commit -S` locally?
9. Design a backup test for a critical repository. What is the pass criterion?
10. A 4 GB ISO was committed six months ago and deleted in a later commit. Clones are still 4 GB. Why, and what tool class rewrites that?

---

## Further practice

Pair with Chapter 9 (Git internals) and Chapter 10 (branching). Disaster recovery is internals under time pressure plus social protocol (force-push windows, signing policy).
