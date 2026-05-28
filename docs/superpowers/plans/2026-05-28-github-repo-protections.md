# GitHub Repo Protections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a `gh`-CLI shell script that applies branch protection rules, enables security features, and configures general repo settings on `PersonalSpotifyStatsBackup` in one idempotent run.

**Architecture:** A single shell script (`scripts/setup_github_protections.sh`) that calls the GitHub REST API via `gh api` and `gh repo edit`. A `.github/dependabot.yml` file configures weekly dependency version-update PRs. Both files are new additions — no existing files are modified.

**Tech Stack:** `bash`, `gh` CLI (authenticated), GitHub REST API v3

---

## File Map

| File | Change | Responsibility |
|---|---|---|
| `scripts/setup_github_protections.sh` | Create | Prereq checks, repo detection, all API calls, dry-run support |
| `.github/dependabot.yml` | Create | Dependabot weekly version-update schedule for `pip` |

---

### Task 1: Script scaffold — args, helpers, prereq checks, repo detection

**Files:**
- Create: `scripts/setup_github_protections.sh`

- [ ] **Step 1: Create the file with the scaffold below**

```bash
#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false

for arg in "$@"; do
  case $arg in
    --dry-run) DRY_RUN=true ;;
    *) echo "Error: Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

log()  { echo "[✓] $*"; }
warn() { echo "[!] $*" >&2; }

# Wraps `gh api`. Accepts: method, endpoint, optional JSON payload string.
run_api() {
  local method=$1 endpoint=$2 payload=${3:-}
  if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] gh api --method $method $endpoint"
    [ -n "$payload" ] && echo "          $payload"
    return
  fi
  if [ -n "$payload" ]; then
    echo "$payload" | gh api \
      --method "$method" \
      --header "Accept: application/vnd.github+json" \
      "$endpoint" \
      --input - > /dev/null
  else
    gh api \
      --method "$method" \
      --header "Accept: application/vnd.github+json" \
      "$endpoint" > /dev/null
  fi
}

# Wraps `gh repo edit` for the detected repo. Pass flags as arguments.
run_repo_edit() {
  if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] gh repo edit $OWNER/$REPO $*"
    return
  fi
  gh repo edit "$OWNER/$REPO" "$@"
}

# --- Prereq checks ---
if ! command -v gh &>/dev/null; then
  echo "Error: gh CLI is not installed. See https://cli.github.com" >&2
  exit 1
fi
if ! gh auth status &>/dev/null 2>&1; then
  echo "Error: Not authenticated with gh. Run: gh auth login" >&2
  exit 1
fi

# --- Repo detection ---
REMOTE_URL=$(git remote get-url origin 2>/dev/null) || {
  echo "Error: No git remote 'origin' found." >&2
  exit 1
}
# Handles both HTTPS (https://github.com/owner/repo.git)
# and SSH (git@github.com:owner/repo.git) remote formats.
OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's|.*github\.com[:/]||; s|\.git$||')
OWNER=$(echo "$OWNER_REPO" | cut -d/ -f1)
REPO=$(echo "$OWNER_REPO" | cut -d/ -f2)

echo "Target: $OWNER/$REPO"
[ "$DRY_RUN" = true ] && echo "(dry-run — no changes will be made)"
echo ""
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/setup_github_protections.sh
```

- [ ] **Step 3: Verify prereq checks pass and repo is detected correctly**

```bash
bash scripts/setup_github_protections.sh --dry-run
```

Expected output:
```
Target: b1codes/PersonalSpotifyStatsBackup
(dry-run — no changes will be made)
```

If you see `Error: Not authenticated`, run `gh auth login` first.

- [ ] **Step 4: Commit**

```bash
git add scripts/setup_github_protections.sh
git commit -m "feat: add setup_github_protections.sh scaffold"
```

---

### Task 2: Branch protection rules

**Files:**
- Modify: `scripts/setup_github_protections.sh` — append after the `echo ""` line

- [ ] **Step 1: Append the branch protection section to the script**

Add this block at the end of `scripts/setup_github_protections.sh`:

```bash
# =============================================================================
# Branch Protection
# =============================================================================

run_api PUT "repos/$OWNER/$REPO/branches/main/protection" '{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}'
log "Branch protection applied to main"
```

`enforce_admins: false` preserves your ability to push directly to main as repo admin. All other contributors must submit a PR with at least 1 approval.

- [ ] **Step 2: Dry-run to verify the API call looks correct**

```bash
bash scripts/setup_github_protections.sh --dry-run
```

Expected output includes:
```
[DRY RUN] gh api --method PUT repos/b1codes/PersonalSpotifyStatsBackup/branches/main/protection
          { "required_status_checks": null, ...
[✓] Branch protection applied to main
```

- [ ] **Step 3: Commit**

```bash
git add scripts/setup_github_protections.sh
git commit -m "feat: add branch protection rules to setup script"
```

---

### Task 3: Security features — Dependabot and secret scanning

**Files:**
- Modify: `scripts/setup_github_protections.sh` — append after branch protection block

- [ ] **Step 1: Append the security features section**

Add this block at the end of `scripts/setup_github_protections.sh`:

```bash
# =============================================================================
# Security Features
# =============================================================================

run_api PUT "repos/$OWNER/$REPO/vulnerability-alerts"
log "Dependabot vulnerability alerts enabled"

run_api PUT "repos/$OWNER/$REPO/automated-security-fixes"
log "Dependabot security updates enabled"

# Secret scanning is free on public repos. Private repos require GitHub Advanced Security.
# This call is intentionally not routed through run_api so failures warn rather than abort.
if [ "$DRY_RUN" = true ]; then
  echo "[DRY RUN] gh api --method PATCH repos/$OWNER/$REPO (security_and_analysis)"
else
  echo '{
    "security_and_analysis": {
      "secret_scanning": {"status": "enabled"},
      "secret_scanning_push_protection": {"status": "enabled"}
    }
  }' | gh api \
    --method PATCH \
    --header "Accept: application/vnd.github+json" \
    "repos/$OWNER/$REPO" \
    --input - > /dev/null \
  || warn "Secret scanning unavailable — requires GitHub Advanced Security on private repos"
fi
log "Secret scanning and push protection configured"
```

- [ ] **Step 2: Dry-run to verify**

```bash
bash scripts/setup_github_protections.sh --dry-run
```

Expected new lines in output:
```
[DRY RUN] gh api --method PUT repos/b1codes/PersonalSpotifyStatsBackup/vulnerability-alerts
[✓] Dependabot vulnerability alerts enabled
[DRY RUN] gh api --method PUT repos/b1codes/PersonalSpotifyStatsBackup/automated-security-fixes
[✓] Dependabot security updates enabled
[DRY RUN] gh api --method PATCH repos/b1codes/PersonalSpotifyStatsBackup (security_and_analysis)
[✓] Secret scanning and push protection configured
```

- [ ] **Step 4: Commit**

```bash
git add scripts/setup_github_protections.sh
git commit -m "feat: add security features to setup script"
```

---

### Task 4: General repo settings

**Files:**
- Modify: `scripts/setup_github_protections.sh` — append after security features block

- [ ] **Step 1: Append the general settings section**

Add this block at the end of `scripts/setup_github_protections.sh`:

```bash
# =============================================================================
# General Repo Settings
# =============================================================================

run_repo_edit \
  --delete-branch-on-merge \
  --enable-squash-merge \
  --enable-merge-commit=false \
  --enable-rebase-merge=false
log "Repo settings: auto-delete branches, squash-only merges"
```

- [ ] **Step 2: Append a completion message at the very end**

```bash
echo ""
echo "Done. All protections applied to $OWNER/$REPO."
```

- [ ] **Step 3: Dry-run to verify**

```bash
bash scripts/setup_github_protections.sh --dry-run
```

Expected new lines:
```
[DRY RUN] gh repo edit b1codes/PersonalSpotifyStatsBackup --delete-branch-on-merge --enable-squash-merge --enable-merge-commit=false --enable-rebase-merge=false
[✓] Repo settings: auto-delete branches, squash-only merges

Done. All protections applied to b1codes/PersonalSpotifyStatsBackup.
```

- [ ] **Step 4: Commit**

```bash
git add scripts/setup_github_protections.sh
git commit -m "feat: add general repo settings to setup script"
```

---

### Task 5: Create `.github/dependabot.yml`

**Files:**
- Create: `.github/dependabot.yml`

- [ ] **Step 1: Create the directory and file**

```bash
mkdir -p .github
```

Create `.github/dependabot.yml` with this content:

```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: "/"
    schedule:
      interval: weekly
```

This configures Dependabot to open PRs for outdated `pip` packages (from `requirements.txt`) once a week.

- [ ] **Step 2: Verify the file is valid YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/dependabot.yml'))" && echo "Valid YAML"
```

Expected: `Valid YAML`

- [ ] **Step 3: Commit**

```bash
git add .github/dependabot.yml
git commit -m "chore: add dependabot version update config for pip"
```

---

### Task 6: Apply the script and verify

- [ ] **Step 1: Final dry-run — review the full output**

```bash
bash scripts/setup_github_protections.sh --dry-run
```

Confirm all 5 sections appear:
1. `[DRY RUN] gh api --method PUT .../branches/main/protection`
2. `[DRY RUN] gh api --method PUT .../vulnerability-alerts`
3. `[DRY RUN] gh api --method PUT .../automated-security-fixes`
4. `[DRY RUN] gh api --method PATCH repos/b1codes/PersonalSpotifyStatsBackup (security_and_analysis)`
5. `[DRY RUN] gh repo edit b1codes/PersonalSpotifyStatsBackup ...`

- [ ] **Step 2: Apply for real**

```bash
bash scripts/setup_github_protections.sh
```

Expected output (no `[DRY RUN]` prefix):
```
Target: b1codes/PersonalSpotifyStatsBackup

[✓] Branch protection applied to main
[✓] Dependabot vulnerability alerts enabled
[✓] Dependabot security updates enabled
[✓] Secret scanning and push protection configured
[✓] Repo settings: auto-delete branches, squash-only merges

Done. All protections applied to b1codes/PersonalSpotifyStatsBackup.
```

- [ ] **Step 3: Verify branch protection was applied**

```bash
gh api repos/b1codes/PersonalSpotifyStatsBackup/branches/main/protection \
  --jq '{enforce_admins: .enforce_admins.enabled, required_reviews: .required_pull_request_reviews.required_approving_review_count, dismiss_stale: .required_pull_request_reviews.dismiss_stale_reviews, force_push: .allow_force_pushes.enabled}'
```

Expected:
```json
{
  "enforce_admins": false,
  "required_reviews": 1,
  "dismiss_stale": true,
  "force_push": false
}
```

- [ ] **Step 4: Verify Dependabot alerts are on**

```bash
gh api repos/b1codes/PersonalSpotifyStatsBackup --jq '.security_and_analysis'
```

Expected: `secret_scanning` and `secret_scanning_push_protection` both show `"status": "enabled"`.

- [ ] **Step 5: Confirm all commits are in order**

```bash
git log --oneline -6
```

Expected: 5 commits from Tasks 1–5 appear on top of main. No uncommitted changes.
