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
    return 0
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
    echo "[DRY RUN] gh repo edit $OWNER/$REPO" "$@"
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

if [[ -z "$OWNER" || -z "$REPO" || "$OWNER_REPO" == "$REMOTE_URL" ]]; then
  echo "Error: Could not parse GitHub owner/repo from remote URL: $REMOTE_URL" >&2
  exit 1
fi

echo "Target: $OWNER/$REPO"
[ "$DRY_RUN" = true ] && echo "(dry-run — no changes will be made)"
echo ""

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
[ "$DRY_RUN" = true ] || log "Branch protection applied to main"

# =============================================================================
# Security Features
# =============================================================================

run_api PUT "repos/$OWNER/$REPO/vulnerability-alerts" \
  && { [ "$DRY_RUN" = true ] || log "Dependabot vulnerability alerts enabled"; } \
  || warn "Dependabot alerts unavailable — may require org-level configuration"

run_api PUT "repos/$OWNER/$REPO/automated-security-fixes" \
  && { [ "$DRY_RUN" = true ] || log "Dependabot security updates enabled"; } \
  || warn "Dependabot security updates unavailable — may require org-level configuration"

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
  && log "Secret scanning and push protection configured" \
  || warn "Secret scanning unavailable — requires GitHub Advanced Security on private repos"
fi

# =============================================================================
# General Repo Settings
# =============================================================================

run_repo_edit \
  --delete-branch-on-merge \
  --enable-squash-merge \
  --enable-merge-commit=false \
  --enable-rebase-merge=false \
  && { [ "$DRY_RUN" = true ] || log "Repo settings: auto-delete branches, squash-only merges"; } \
  || warn "Repo settings update failed — check token scopes or repo permissions"

echo ""
echo "Done. All protections applied to $OWNER/$REPO."
