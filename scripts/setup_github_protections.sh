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
