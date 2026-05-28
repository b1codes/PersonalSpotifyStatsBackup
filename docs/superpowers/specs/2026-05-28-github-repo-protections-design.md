# GitHub Repo Protections — Design Spec

**Date:** 2026-05-28
**Repo:** PersonalSpotifyStatsBackup
**Status:** Approved

## Overview

A one-time setup shell script (`scripts/setup_github_protections.sh`) that uses the `gh` CLI to apply branch protection rules, enable security features, and configure general repo settings for `PersonalSpotifyStatsBackup`.

The script is designed to be re-runnable (all operations are idempotent PUT/PATCH calls) and supports a `--dry-run` flag for inspection before applying.

---

## Script Structure

**File:** `scripts/setup_github_protections.sh`

**Behavior:**
- Auto-detects owner/repo from `git remote get-url origin`
- Accepts `--dry-run` flag — prints each `gh` command without executing it
- Validates `gh` is installed and the user is authenticated (`gh auth status`) before proceeding
- Prints a status line for each configuration step (e.g. `[✓] Branch protection applied`)
- Exits with a non-zero code on any failure

---

## Branch Protection Rules

Applied via `gh api --method PUT repos/{owner}/{repo}/branches/main/protection`.

| Rule | Setting |
|---|---|
| Require pull request before merging | Enabled |
| Required approving reviews | 1 |
| Dismiss stale reviews on new commits | Enabled |
| Allow force pushes | Disabled |
| Allow branch deletion | Disabled |
| Enforce rules for admins | **Disabled** (admin bypass preserved) |

The admin bypass (`enforce_admins: false`) means the repo owner can push directly to `main` without a PR. All other contributors must submit a PR with at least one approval.

---

## Security Features

Applied via `gh api` and `gh repo edit`.

| Feature | Method |
|---|---|
| Dependabot alerts | `gh api PUT .../vulnerability-alerts` |
| Dependabot security updates | `gh api PUT .../automated-security-fixes` |
| Secret scanning | `gh api PATCH repos/{owner}/{repo}` via `security_and_analysis` |
| Secret scanning push protection | `gh api PATCH repos/{owner}/{repo}` via `security_and_analysis` |

A `.github/dependabot.yml` file is also created to configure Dependabot version updates for `pip` dependencies (targeting `requirements.txt`). Checks run weekly.

Code scanning (CodeQL) is **excluded** — it requires Actions configuration and adds overhead not proportionate for a Lambda script project.

---

## General Repo Settings

Applied via `gh repo edit`:

| Setting | Value |
|---|---|
| Auto-delete head branches after merge | Enabled |
| Allow squash merges | Enabled |
| Allow merge commits | Disabled |
| Allow rebase merges | Disabled |

Squash-only merging keeps `main` history linear and clean — one commit per PR.

---

## Files Changed

| File | Change |
|---|---|
| `scripts/setup_github_protections.sh` | New — the setup script |
| `.github/dependabot.yml` | New — Dependabot version update config |

---

## Usage

```bash
# Preview all changes without applying
bash scripts/setup_github_protections.sh --dry-run

# Apply all protections
bash scripts/setup_github_protections.sh
```

Requires `gh` CLI installed and authenticated (`gh auth login`).
