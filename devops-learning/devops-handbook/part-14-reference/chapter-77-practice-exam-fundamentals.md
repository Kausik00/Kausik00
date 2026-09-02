# Chapter 77: Practice Exam — Fundamentals

Fifty multiple-choice questions on Linux, Git, and CI fundamentals. Choose **one best answer** unless noted. Explanations follow each question so this chapter is a study guide, not just an answer key.

Suggested protocol: 90 minutes, closed book, then review every miss. A pass mark for this handbook: **40/50**. Wrong-and-understood is more valuable than guessed-right.

---

## 77.1 Linux (Q1–Q22)

**Q1.** A 4-vCPU VM shows load average `12.00, 11.40, 9.10` and `mpstat` `%idle` 70% with `%iowait` 25%. The best first interpretation is:

- A. CPU-bound application
- B. Scheduler bug
- C. Tasks blocked on I/O inflating load
- D. Need more RAM immediately

**Answer: C.** Load includes D-state (uninterruptible I/O). High iowait + high load + idle CPU is storage or NFS, not compute.

**Q2.** `df -h` shows 30% used but `touch` fails with “No space left on device.” Next command:

- A. `reboot`
- B. `df -i`
- C. `swapon -s`
- D. `fsck` on the live root

**Answer: B.** Inode exhaustion. `fsck` on mounted root is not the first move.

**Q3.** Which signal cannot be caught?

- A. SIGTERM
- B. SIGINT
- C. SIGKILL
- D. SIGHUP

**Answer: C.**

**Q4.** `chmod 2775 shared_dir` primarily:

- A. Makes the directory immutable
- B. Sets setgid so new files inherit the directory group
- C. Enables sticky bit
- D. Grants world write

**Answer: B.** 2 is setgid; sticky is 1 (`1777` on `/tmp`).

**Q5.** `getent hosts api` and `dig api` disagree. Why might that happen?

- A. DNSSEC
- B. NSS uses `/etc/hosts` or nsswitch order; `dig` queries DNS only
- C. `dig` uses ICMP
- D. They cannot disagree

**Answer: B.**

**Q6.** Best command to see process syscall stalls in production with lowest overhead among these:

- A. `strace -f -p PID` for an hour
- B. `perf top` or targeted eBPF
- C. `tcpdump -A`
- D. `watch cat /proc/PID/stack` every 1ms from bash

**Answer: B.** Continuous strace is heavy.

**Q7.** systemd `Restart=always` with a crashing binary. You also need:

- A. `KillMode=none`
- B. StartLimitBurst/StartLimitInterval to avoid tight loops
- C. `Type=idle`
- D. Disabling the journal

**Answer: B.**

**Q8.** `ss -lntp` vs `netstat -lntp`:

- A. `ss` uses /proc and is the modern replacement
- B. `ss` only works for UDP
- C. They are identical binaries
- D. `ss` requires X11

**Answer: A.**

**Q9.** A file is `rw-r--r--` owned by `root:root`. User `app` can write if:

- A. Never
- B. They are in group root (still only r)
- C. They have CAP_DAC_OVERRIDE or are root, or ACL grants write
- D. The file is on NFS

**Answer: C.** Mode 644 does not grant app write.

**Q10.** `TIME_WAIT` sockets consume:

- A. Disk inodes
- B. Ephemeral ports / connection tracking resources
- C. GPU
- D. inotify watches

**Answer: B.**

**Q11.** OOM killer selected your sidecar. You can reduce score with:

- A. `nice -n 19`
- B. `oom_score_adj`
- C. `chmod 777`
- D. `ulimit -n`

**Answer: B.**

**Q12.** `ip route get 8.8.8.8` is useful because it:

- A. Rewrites BGP
- B. Shows which path/src the kernel would use
- C. Bypasses firewalls
- D. Flushes conntrack

**Answer: B.**

**Q13.** Hard link characteristics:

- A. Cross-filesystem, can dangle
- B. Same inode, same filesystem, extra directory entry
- C. Always to directories
- D. Encrypted

**Answer: B.**

**Q14.** `journalctl -u nginx -b` means:

- A. Since boot
- B. Binary format
- C. Follow
- D. Priority bulletin

**Answer: A.**

**Q15.** Sticky bit on `/tmp` prevents:

- A. Execution
- B. Users deleting others’ files
- C. Hard links
- D. SUID

**Answer: B.**

**Q16.** `lsof +L1` helps when:

- A. DNS fails
- B. Disk full from deleted-but-open files
- C. CPU steal
- D. Clock skew

**Answer: B.**

**Q17.** cgroups primarily:

- A. Isolate hostnames
- B. Limit and account resources
- C. Replace UID 0
- D. Encrypt disks

**Answer: B.** Namespaces isolate identity/visibility.

**Q18.** `curl -w '%{time_appconnect}'` is closest to:

- A. DNS time
- B. TCP handshake only
- C. TLS handshake complete time
- D. TTFB of body

**Answer: C.** (`time_starttransfer` is TTFB.)

**Q19.** `set -euo pipefail` in bash:

- A. Makes scripts slower only
- B. Exit on error, unset var, pipeline failure
- C. Enables POSIX-only mode
- D. Disables globbing

**Answer: B.**

**Q20.** `nice` affects:

- A. Disk bandwidth always
- B. CPU scheduling priority
- C. Memory limits
- D. Nice is deprecated and ignored

**Answer: B.**

**Q21.** `/proc/sys/net/ipv4/ip_forward` is 0. The box will:

- A. Not route packets between interfaces
- B. Drop all local sockets
- C. Disable IPv6
- D. Ignore this on systemd

**Answer: A.**

**Q22.** `chattr +i file` then `rm file` as root:

- A. Always succeeds
- B. Fails until `chattr -i`
- C. Wipes the disk
- D. Only works on XFS

**Answer: B.** (On filesystems that support it, e.g. ext4.)

---

## 77.2 Git (Q23–Q36)

**Q23.** A Git commit object contains:

- A. Diffs only
- B. Tree pointer, parents, author, message
- C. The full working tree always
- D. GPG by default

**Answer: B.**

**Q24.** `git reset --hard origin/main` :

- A. Is always safe
- B. Discards local commits and tracked changes to match origin/main
- C. Deletes the remote
- D. Rewrites origin

**Answer: B.** Untracked files may remain.

**Q25.** `git revert` vs `reset` on a shared main branch:

- A. Prefer revert: new commit undoes, history stays
- B. Prefer reset --hard and force-push always
- C. They are aliases
- D. revert deletes the branch

**Answer: A.**

**Q26.** Fast-forward merge means:

- A. Conflicts resolved automatically with theirs
- B. HEAD can move to the tip without a merge commit
- C. Rebase is forbidden
- D. Tags move

**Answer: B.**

**Q27.** `git stash -u` :

- A. Stashes ignored files only
- B. Includes untracked
- C. Pushes to origin
- D. Signs commits

**Answer: B.**

**Q28.** Detached HEAD means:

- A. Corruption
- B. HEAD points at a commit, not a branch name
- C. No remotes
- D. Submodule only

**Answer: B.**

**Q29.** `.gitignore` does not untrack files that are already tracked. You need:

- A. `git rm --cached`
- B. `git prune`
- C. `git clean -fxd` always
- D. Reinit repo

**Answer: A.**

**Q30.** `git blame` is primarily for:

- A. Shaming
- B. Line-to-commit mapping for archaeology
- C. Performance
- D. Signing

**Answer: B.**

**Q31.** A signed commit verifies:

- A. The working tree is clean
- B. The commit object was signed by a key you trust
- C. The remote is HTTPS
- D. CI passed

**Answer: B.**

**Q32.** `git fetch` vs `git pull`:

- A. pull = fetch + merge (or rebase if configured)
- B. fetch writes working tree
- C. pull never fast-forwards
- D. They are identical

**Answer: A.**

**Q33.** Force-pushing `main` is dangerous because:

- A. Git forbids it
- B. Collaborators’ history diverges; CI SHAs change; recoverability suffers
- C. It only affects tags
- D. SSH keys reset

**Answer: B.**

**Q34.** `pre-commit` hooks run:

- A. On the server always
- B. Locally before commit (client-side; can be skipped with `--no-verify`)
- C. After CI
- D. Only on tags

**Answer: B.** Server-side is `pre-receive`.

**Q35.** `git rebase -i` to squash: the risk on a published branch is:

- A. None
- B. Rewriting SHAs others based work on
- C. Losing the remote
- D. Changing author emails always

**Answer: B.**

**Q36.** Submodules store:

- A. Full copy of the other repo’s objects always in parent
- B. A gitlink (commit SHA) and .gitmodules URL
- C. Only branches
- D. LFS pointers only

**Answer: B.**

---

## 77.3 CI/CD fundamentals (Q37–Q50)

**Q37.** “Build once, promote everywhere” means:

- A. Rebuild with different Dockerfiles per env
- B. Promote the same artifact digest through environments
- C. Use `:latest` in prod
- D. Compile on the prod host

**Answer: B.**

**Q38.** Pinning GitHub Actions to a SHA rather than `@v4`:

- A. Breaks Dependabot
- B. Reduces tag-move / supply-chain risk
- C. Is required by YAML spec
- D. Disables caching

**Answer: B.**

**Q39.** Fork pull requests should:

- A. Receive production cloud keys
- B. Run untrusted code without secrets
- C. Use `pull_request_target` by default
- D. Skip tests

**Answer: B.**

**Q40.** A pipeline that stores AWS keys as long-lived repo secrets is weaker than:

- A. Printing them in logs
- B. OIDC federation with scoped IAM roles
- C. Putting keys in the Dockerfile
- D. Committing `.env`

**Answer: B.**

**Q41.** `latest` image tags in production are bad because:

- A. Docker Hub forbids them
- B. The tag is mutable; nodes can run different binaries
- C. They cannot be scanned
- D. Kubernetes rejects them

**Answer: B.**

**Q42.** Trunk-based development typically uses:

- A. Year-long release branches
- B. Short-lived branches and frequent integration to main
- C. No tests
- D. Mandatory GitFlow

**Answer: B.**

**Q43.** The DORA metric “change fail rate” is:

- A. CPU throttling
- B. Percentage of deployments causing incidents or rollbacks
- C. Number of linters
- D. Sprint velocity

**Answer: B.**

**Q44.** Caching `~/.m2` on a shared self-hosted runner across untrusted jobs risks:

- A. Faster builds only
- B. Poisoned caches / cross-job contamination
- C. Nothing
- D. DNS poisoning exclusively

**Answer: B.**

**Q45.** A required CI check that can be skipped with an empty commit message is:

- A. Fine
- B. A broken control; branch protection must be actually required
- C. Required by Git
- D. The same as CODEOWNERS

**Answer: B.**

**Q46.** Artifact attestation / provenance answers:

- A. Who paged
- B. How and where the binary was built
- C. The SLO
- D. Terraform lockfile only

**Answer: B.**

**Q47.** Flaky tests in CI should be:

- A. Ignored with `continue-on-error` forever
- B. Quarantined with owners and SLAs, not silently skipped
- C. Deleted immediately without data
- D. Run only on Fridays

**Answer: B.**

**Q48.** Database migrations in the same pipeline as the app deploy should be:

- A. Drop column immediately
- B. Expand/contract and backward compatible
- C. Manual SSH
- D. Unversioned SQL in Slack

**Answer: B.**

**Q49.** The main reason to use a lockfile (`package-lock.json`, `go.sum`):

- A. Pretty diffs
- B. Reproducible installs and reviewable upgrades
- C. Faster DNS
- D. Replace tests

**Answer: B.**

**Q50.** A green CI pipeline proves:

- A. Production will not fail
- B. The checks you configured passed on that commit
- C. Security forever
- D. Load capacity

**Answer: B.** Humility question—always.

---

## 77.4 Answer grid

| Q | Ans | Q | Ans | Q | Ans | Q | Ans | Q | Ans |
|---|-----|---|-----|---|-----|---|-----|---|-----|
| 1 | C | 11 | B | 21 | A | 31 | B | 41 | B |
| 2 | B | 12 | B | 22 | B | 32 | A | 42 | B |
| 3 | C | 13 | B | 23 | B | 33 | B | 43 | B |
| 4 | B | 14 | A | 24 | B | 34 | B | 44 | B |
| 5 | B | 15 | B | 25 | A | 35 | B | 45 | B |
| 6 | B | 16 | B | 26 | B | 36 | B | 46 | B |
| 7 | B | 17 | B | 27 | B | 37 | B | 47 | B |
| 8 | A | 18 | C | 28 | B | 38 | B | 48 | B |
| 9 | C | 19 | B | 29 | A | 39 | B | 49 | B |
| 10 | B | 20 | B | 30 | B | 40 | B | 50 | B |

---

## 77.5 How to review misses

Group misses: filesystem vs process vs Git history vs CI trust. For each miss, write one command you will actually run this week (`df -i`, `git revert`, OIDC trust policy). Fundamentals exams reward **precise mental models** (load vs CPU, fetch vs pull, tag vs digest). Re-sit in three days without looking at the grid first.

---

## 77.6 Mini-labs that lock in the answers

**Lab A (inodes).** `mkdir t; cd t; for i in $(seq 1 100000); do touch $i; done` on a small loop filesystem if you have one; watch `df -i`. Delete and confirm `touch` works again. This is Q2 in muscle memory.

**Lab B (NSS vs DNS).** Add `10.0.0.1 not-real.example` to `/etc/hosts` (lab VM). Compare `getent hosts not-real.example` and `dig not-real.example`. Remove the line.

**Lab C (Git revert).** Make three commits on a throwaway repo; `git revert HEAD~1`; explain why the bad change is still in history. Then try `reset --hard` on a clone you never pushed.

**Lab D (CI digest).** Build an image twice with the same Dockerfile; compare IDs with and without `--sbom`/reproducible flags. Tag both `latest` and observe how unhelpful that name is.

---

## 77.7 Distractor patterns on this exam

Interview and exam authors love:

- **Wrong layer:** answering CPU when the stem says iowait.
- **Wrong Git verb:** reset on shared main vs revert.
- **Wrong proof:** “CI green” as a synonym for production-safe.
- **Wrong permission fix:** 777 instead of owner/ACL.

When two answers look right, pick the one that names **blast radius and reversibility**.

---

## 77.8 Scoring interpretation

| Score | Meaning | Next |
|-------|---------|------|
| 45–50 | Fundamentals solid | Chapter 78 |
| 40–44 | Pass; drill misses | Mini-labs |
| 30–39 | Gaps in Linux or Git | Chapters 5–11 |
| <30 | Do not memorize the grid | Work through encyclopedia with a VM |

A 50 with no labs is still fragile. Pair this exam with Chapter 72’s incident command block until you can type it without looking.
