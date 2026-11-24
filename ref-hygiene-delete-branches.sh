#!/usr/bin/env bash
# Apply DEL_BRANCH rows from REF-HYGIENE.tsv in file order.
#
# Row format:
#   DEL_BRANCH<TAB>branch
#
# Before deleting a remote branch, the script reads its current origin tip and
# requires at least one remote tag to point to that exact commit. Annotated tags
# are accepted through their peeled ^{} refs; lightweight tags are accepted
# directly. If no exact-tip tag exists, the branch is left in place and a
# prominent diagnostic is printed.
#
# Git command stdout/stderr is not rewritten. The final summary lists branches
# left in place because the exact-tip tag gate failed or deletion itself failed.
# A DEL_BRANCH entry for a branch already absent from origin is simply skipped.
#
# The ledger is input only and is never modified by this script.

set -u

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ledger="${1:-$script_dir/REF-HYGIENE.tsv}"
tag_refs="$(git ls-remote --tags origin)"
kept=()

while IFS=$'\t' read -r command branch_name rest; do
    [[ -z "${command:-}" || "$command" == \#* ]] && continue
    [[ "$command" == "DEL_BRANCH" ]] || continue

    branch_line="$(git ls-remote --heads origin "refs/heads/$branch_name")"
    if [[ -z "$branch_line" ]]; then
        continue
    fi
    printf '%s\n' "$branch_line"

    tip="${branch_line%%$'\t'*}"

    if ! awk -v tip="$tip" '
        $1 == tip && $2 ~ /^refs\/tags\// { found = 1 }
        END { exit(found ? 0 : 1) }
    ' <<< "$tag_refs"; then
        printf '\n'
        printf '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n'
        printf 'KEEP BRANCH: %s\n' "$branch_name"
        printf 'NO REMOTE TAG POINTS TO EXACT BRANCH TIP: %s\n' "$tip"
        printf '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n'
        printf '\n'
        kept+=("$branch_name — no tag on exact tip $tip")
        continue
    fi

    if ! git push origin --delete "$branch_name"; then
        kept+=("$branch_name — git push --delete failed")
    fi
done < "$ledger"

printf '\n'
printf '================ REF HYGIENE BRANCH SUMMARY ================\n'
if (("${#kept[@]}" == 0)); then
    printf 'No DEL_BRANCH entries were left in place by this run.\n'
else
    printf 'LEFT IN PLACE:\n'
    for item in "${kept[@]}"; do
        printf '  %s\n' "$item"
    done
fi
