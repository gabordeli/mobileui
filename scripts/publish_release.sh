#!/usr/bin/env bash
# Upload a built .egg and attach it to a GitLab Release.
#
# Requires CI_API_V4_URL, CI_PROJECT_ID and CI_JOB_TOKEN (set by GitLab CI).
set -euo pipefail

VERSION="${1:?usage: publish_release.sh VERSION EGG}"
EGG="${2:?usage: publish_release.sh VERSION EGG}"

: "${CI_API_V4_URL:?CI_API_V4_URL is required}"
: "${CI_PROJECT_ID:?CI_PROJECT_ID is required}"
: "${CI_JOB_TOKEN:?CI_JOB_TOKEN is required}"

VERSION="${VERSION#v}"
EGG="$(realpath "$EGG")"
EGG_NAME="$(basename "$EGG")"
SHA_FILE="$EGG.sha256"
API="$CI_API_V4_URL/projects/$CI_PROJECT_ID"
PACKAGE="$API/packages/generic/mobileui/$VERSION"
AUTH="JOB-TOKEN: $CI_JOB_TOKEN"

if [[ ! -f "$EGG" ]]; then
    echo "egg not found: $EGG" >&2
    exit 1
fi
if [[ ! -f "$SHA_FILE" ]]; then
    (
        cd "$(dirname "$EGG")"
        sha256sum "$EGG_NAME"
    ) > "$SHA_FILE"
fi
SHA="$(awk '{print $1}' "$SHA_FILE")"

echo "uploading $EGG_NAME to $PACKAGE"
curl --fail --silent --show-error --request PUT --header "$AUTH" \
    --upload-file "$EGG" "$PACKAGE/$EGG_NAME"
curl --fail --silent --show-error --request PUT --header "$AUTH" \
    --upload-file "$SHA_FILE" "$PACKAGE/$EGG_NAME.sha256"

DESCRIPTION="$(printf 'MobileUi %s\n\n- egg: %s\n- sha256: %s\n- install: `EGG=%s ./scripts/install.sh`' \
    "$VERSION" "$EGG_NAME" "$SHA" "$EGG_NAME")"

if curl --fail --silent --show-error --header "$AUTH" \
    "$API/releases/v$VERSION" >/dev/null 2>&1; then
    curl --fail --silent --show-error --request PUT --header "$AUTH" \
        --data-urlencode "name=MobileUi $VERSION" \
        --data-urlencode "tag_name=v$VERSION" \
        --data-urlencode "description=$DESCRIPTION" \
        "$API/releases/v$VERSION" >/dev/null
else
    curl --fail --silent --show-error --request POST --header "$AUTH" \
        --data-urlencode "name=MobileUi $VERSION" \
        --data-urlencode "tag_name=v$VERSION" \
        --data-urlencode "description=$DESCRIPTION" \
        "$API/releases" >/dev/null
fi

for name in "$EGG_NAME" "$EGG_NAME.sha256"; do
    curl --fail --silent --show-error --request POST --header "$AUTH" \
        --data-urlencode "name=$name" \
        --data-urlencode "url=$PACKAGE/$name" \
        --data "link_type=package" \
        "$API/releases/v$VERSION/assets/links" >/dev/null || true
done

echo "released MobileUi $VERSION with $EGG_NAME ($SHA)"
