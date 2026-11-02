#!/usr/bin/env bash
# Prints the content hash an image tag carries (PLAN.md D16): 12 hex of git's hashes of the image's build inputs.
# Usage: image-tag.sh <pathspec>... [-- <salt>]
#   <pathspec>  the build contexts (and any --build-context), and ':!<path>' for what the build never reads
#   <salt>      anything else that picks the build's contents, e.g. its build args
# The working tree counts, committed or not (tracked and untracked files, not git-ignored ones), staged in a copy of
# the index so the real one is never written.
set -euo pipefail

paths=()
while [ $# -gt 0 ] && [ "$1" != -- ]; do paths+=("$1"); shift; done
[ $# -gt 0 ] && shift
[ ${#paths[@]} -gt 0 ] || { echo "usage: image-tag.sh <pathspec>... [-- <salt>]" >&2; exit 2; }

cd "$(git rev-parse --show-toplevel)"
index=$(git rev-parse --git-path index)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
# Its stat cache spares re-reading unchanged files; -p keeps its mtime, which git needs to catch same-second edits.
[ ! -f "$index" ] || cp -p "$index" "$tmp/index"
export GIT_INDEX_FILE="$tmp/index"

git add -A -- "${paths[@]}"
files=$(git ls-files -s -- "${paths[@]}")
[ -n "$files" ] || { echo "image-tag.sh: no files match ${paths[*]}" >&2; exit 2; }
printf '%s\n%s\n' "$files" "$*" | git hash-object --stdin | cut -c1-12
