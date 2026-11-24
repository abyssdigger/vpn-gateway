#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
VERSION=$(tr -d '\n\r' < "$ROOT/VERSION")
EXPECTED=0.1.0

if [ "$VERSION" != "$EXPECTED" ]; then
    printf '%s\n' "release directory expects $EXPECTED, root VERSION is $VERSION" >&2
    exit 1
fi

SNAP="$ROOT/release/0.1.0/project-snapshot"
for file in requirements.md architecture-ng.md CHANGELOG-NG3.md; do
    [ -f "$SNAP/$file" ] || {
        printf '%s\n' "missing project snapshot file: $SNAP/$file" >&2
        exit 1
    }
done

OUT=${1:-"$ROOT/dist"}
NAME="vpn-gate-$VERSION-project-snapshot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT HUP INT TERM

mkdir -p "$TMP/$NAME"
cp "$SNAP/requirements.md" "$TMP/$NAME/requirements.md"
cp "$SNAP/architecture-ng.md" "$TMP/$NAME/architecture-ng.md"
cp "$SNAP/CHANGELOG-NG3.md" "$TMP/$NAME/CHANGELOG-NG3.md"

mkdir -p "$OUT"
ARCHIVE="$OUT/$NAME.tar.gz"
(
    cd "$TMP"
    tar --sort=name --owner=0 --group=0 --numeric-owner \
        --mtime="@${SOURCE_DATE_EPOCH:-0}" -czf "$ARCHIVE" "$NAME"
)
(
    cd "$OUT"
    sha256sum "$NAME.tar.gz" > "$NAME.tar.gz.sha256"
)
printf '%s\n' "$ARCHIVE" "$ARCHIVE.sha256"
