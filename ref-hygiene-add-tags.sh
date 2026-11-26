#!/usr/bin/env bash
# Apply ADD_TAG rows from REF-HYGIENE.tsv in file order.
#
# Row format:
#   ADD_TAG<TAB>tag<TAB>target<TAB>annotation
#
# target is passed directly to "git tag" and may be a commit SHA or another
# Git revision such as a current remote-tracking branch ref. The script does
# not fetch or refresh refs itself.
#
# The script deliberately performs no tag-existence preflight and does not
# interpret command failures. It attempts every local git tag operation in file
# order, collects the corresponding refs, then publishes all listed tag refs in
# one git push invocation. A local tag failure does not stop later rows from
# being attempted; Git's stdout/stderr and final push result remain unchanged.
#
# The ledger is input only and is never modified by this script.

set -u

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ledger="${1:-$script_dir/REF-HYGIENE.tsv}"
tag_refs=()

while IFS=\t' read -r command tag target annotation; do
    [[ -z "${command:-}" || "$command" == \#* ]] && continue
    [[ "$command" == "ADD_TAG" ]] || continue

    git tag -a "$tag" "$target" -m "$annotation"
    tag_refs+=("refs/tags/$tag")
done < "$ledger"

if (("${#tag_refs[@]}")); then
    git push origin "${tag_refs[@]}"
fi
