# Chapter 9: Git Internals — Objects, Refs, and the DAG

*DevOps Handbook — Part III, Pages 141–158*

---

## 9.1 Git is a content-addressable filesystem

At its core, Git stores **snapshots** of your project, not just diffs. Every piece of content is identified by a **SHA-1 hash** (Git is migrating to SHA-256).

Four object types:

| Type | Contains |
|------|----------|
| **blob** | File content |
| **tree** | Directory listing (names → blobs/trees) |
| **commit** | Snapshot + metadata (author, message, parent) |
| **tag** | Named pointer to a commit (annotated tags) |

---

## 9.2 How a commit is stored

When you `git add` and `git commit`:

1. Git compresses file content into **blobs**.
2. Directory structure becomes **trees**.
3. A **commit** object points to the root tree and parent commit(s).
4. Branch name (e.g., `main`) is a **ref** — a pointer to the latest commit.

```
main → commit C3 → tree → blob (README.md)
              ↓
           commit C2 → ...
              ↓
           commit C1 (root)
```

This forms a **DAG** (directed acyclic graph). Merge commits have two parents.

---

## 9.3 Essential Git commands (beyond basics)

```bash
git log --oneline --graph --all
git show <commit>              # Commit details + diff
git diff HEAD~1                # Compare with previous commit
git stash push -m "wip"
git stash pop
git cherry-pick <commit>
git rebase main                # Replay commits on top of main
git reflog                     # History of HEAD movements (recovery!)
```

### Undoing mistakes

```bash
git restore file.txt           # Discard working tree changes
git restore --staged file.txt  # Unstage
git reset --soft HEAD~1        # Undo commit, keep changes staged
git reset --hard HEAD~1        # Undo commit, discard changes (dangerous)
git revert <commit>            # New commit that undoes a commit (safe for shared branches)
```

---

## 9.4 Branches and merging

```bash
git branch feature/login
git switch feature/login       # or: git checkout feature/login
git merge feature/login        # Merge into current branch
git merge --no-ff feature/login  # Always create merge commit
```

### Merge vs rebase

| Merge | Rebase |
|-------|--------|
| Preserves history | Linear history |
| Creates merge commits | Rewrites commits |
| Safe for shared branches | Use only on local/feature branches |

**Golden rule:** Never rebase commits that others have pulled.

---

## 9.5 Remote repositories

```bash
git remote -v
git fetch origin               # Download objects, don't merge
git pull origin main           # fetch + merge
git push origin main
git push -u origin feature/x   # Set upstream
```

### Tracking branches

`origin/main` is a **remote-tracking branch** — your local copy of what's on the server.

---

## 9.6 .gitignore and hooks

### .gitignore

```
node_modules/
*.log
.env
dist/
.terraform/
```

### Git hooks (`.git/hooks/`)

Scripts that run on events: `pre-commit`, `commit-msg`, `pre-push`. Used for linting, tests, and commit message format.

Example with **pre-commit** framework:

```bash
pip install pre-commit
# .pre-commit-config.yaml defines hooks
pre-commit install
```

---

## 9.7 Chapter summary

- Git stores blobs, trees, commits, and tags; branches are movable pointers.
- Use `reflog` to recover "lost" commits.
- Prefer **merge** on shared branches; **rebase** to clean up local work.
- Automate quality with hooks and `.gitignore`.

---

## 🧪 Lab 9.1

1. Create a repo with 5 commits on `main`.
2. Create a feature branch, make 2 commits, merge with `--no-ff`.
3. Use `git log --graph --oneline --all` to visualize the DAG.
4. Reset hard to an earlier commit, then recover using `git reflog`.

---

*Next: [Chapter 20 — IaC Principles](../part-06-iac/chapter-20-iac-principles.md)*
