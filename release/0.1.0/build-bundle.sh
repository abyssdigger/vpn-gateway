#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
VERSION=$(tr -d '\n\r' < "$ROOT/VERSION")
EXPECTED=0.1.0

if [ "$VERSION" != "$EXPECTED" ]; then
    printf '%s\n' "release directory expects $EXPECTED, root VERSION is $VERSION" >&2
    exit 1
fi

OUT=${1:-"$ROOT/dist"}
NAME="vpn-gate-$VERSION"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT HUP INT TERM

mkdir -p "$TMP/$NAME"
cp "$ROOT/VERSION" "$TMP/$NAME/VERSION"
cp -a "$ROOT/design/NG3/code/python/rou" "$TMP/$NAME/rou"
cp "$ROOT/design/NG3/deployment/alpha/vpn-gate-alpha.service" "$TMP/$NAME/vpn-gate-alpha.service"
cp "$ROOT/design/NG3/deployment/alpha/config.example.toml" "$TMP/$NAME/config.example.toml"
cp "$ROOT/release/0.1.0/install.sh" "$TMP/$NAME/install.sh"
cp "$ROOT/release/0.1.0/DEPLOYMENT.md" "$TMP/$NAME/DEPLOYMENT.md"
cp "$ROOT/release/0.1.0/openconnect-policy-neutral.sh" "$TMP/$NAME/openconnect-policy-neutral.sh"
chmod 0755 "$TMP/$NAME/install.sh" "$TMP/$NAME/openconnect-policy-neutral.sh"

mkdir -p "$OUT"
ARCHIVE="$OUT/$NAME.tar.gz"
(
    cd "$TMP"
    tar --sort=name --owner=0 --group=0 --numeric-owner \
        --mtime="@${SOURCE_DATE_EPOCH:-0}" -czf "$ARCHIVE" "$NAME"
)
sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"
printf '%s\n' "$ARCHIVE" "$ARCHIVE.sha256"
