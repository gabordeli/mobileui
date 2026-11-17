#!/usr/bin/env bash
# Compare the local main/tags with the GitHub mirror.
#
#   ./scripts/github_mirror_check.sh
#   GITHUB_TOKEN=... ./scripts/github_mirror_check.sh
#
# A private GitHub repo needs a token with Contents: Read (or Read and write).
# Exit code 1 means the mirror is behind or has diverged.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="${GITHUB_REPO:-https://github.com/gabordeli/mobileui.git}"

if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    URL="https://x-access-token:${GITHUB_TOKEN}@${REPO#https://}"
else
    URL="$REPO"
fi

git -C "$ROOT" fetch -q origin main
LOCAL="$(git -C "$ROOT" rev-parse origin/main)"
REMOTE="$(git ls-remote "$URL" refs/heads/main | awk '{print $1}')"

if [[ -z "$REMOTE" ]]; then
    echo "GitHub main not found at $REPO" >&2
    exit 1
fi

echo "local  main: $LOCAL"
echo "github main: $REMOTE"
if [[ "$LOCAL" != "$REMOTE" ]]; then
    echo "MIRROR BEHIND: GitHub main differs from the GitLab main" >&2
    exit 1
fi

missing=0
while read -r tag; do
    [[ -z "$tag" ]] && continue
    if ! git ls-remote --exit-code --tags "$URL" "refs/tags/$tag" >/dev/null 2>&1; then
        echo "MISSING TAG on GitHub: $tag"
        missing=1
    fi
done < <(git -C "$ROOT" tag --list 'v*')

if [[ "$missing" -ne 0 ]]; then
    exit 1
fi

echo "Mirror OK (main + local v* tags present)."
