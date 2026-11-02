#!/usr/bin/env bash
# Checks scripts/image-tag.sh (PLAN.md D16) on a throwaway repository: a tag follows its image's build inputs, committed
# or not, and nothing else; and the real index is never touched. Offline, a second or so.
set -euo pipefail
script="$(cd "$(dirname "$0")/../.." && pwd)/scripts/image-tag.sh"
repo=$(mktemp -d)
trap 'rm -rf "$repo"' EXIT
cd "$repo"
git init -q
git config user.email test@example.com
git config user.name test

fails=0
tag() { "$script" "$@"; }
same() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1: $2 != $3"; fails=$((fails + 1)); fi; }
differ() { if [ "$2" != "$3" ]; then echo "ok   $1"; else echo "FAIL $1: both $2"; fails=$((fails + 1)); fi; }
refused() { if tag "${@:2}" >/dev/null 2>&1; then echo "FAIL $1"; fails=$((fails + 1)); else echo "ok   $1"; fi; }

mkdir -p app/src app/tests lib other
printf 'FROM scratch\nCOPY src /src\n' >app/Dockerfile
echo 'print(1)' >app/src/main.py
echo 'assert True' >app/tests/test_main.py
echo 'shared' >lib/shared.txt
echo 'elsewhere' >other/file.txt
echo '*.tmp' >.gitignore
git add -A && git commit -qm init

app=(app ':!app/tests')
base=$(tag "${app[@]}")
same "the tag is 12 hex" "$(grep -cE '^[0-9a-f]{12}$' <<<"$base")" 1
same "it is stable" "$(tag "${app[@]}")" "$base"

echo 'print(2)' >app/src/main.py
edited=$(tag "${app[@]}")
differ "an uncommitted edit changes the tag" "$edited" "$base"
git add app/src/main.py
same "staging it keeps the tag" "$(tag "${app[@]}")" "$edited"
git commit -qm edit
same "committing it keeps the tag" "$(tag "${app[@]}")" "$edited"

echo 'new' >app/src/extra.py
differ "an untracked file changes the tag" "$(tag "${app[@]}")" "$edited"
rm app/src/extra.py
same "removing it restores the tag" "$(tag "${app[@]}")" "$edited"
echo 'scratch' >app/src/notes.tmp
same "a git-ignored file does not change it" "$(tag "${app[@]}")" "$edited"
chmod +x app/src/main.py
differ "a mode change does" "$(tag "${app[@]}")" "$edited"
chmod -x app/src/main.py

echo 'elsewhere, changed' >other/file.txt
same "a change outside the inputs does not" "$(tag "${app[@]}")" "$edited"
echo 'assert False' >app/tests/test_main.py
same "nor one under an excluded path" "$(tag "${app[@]}")" "$edited"
differ "which counts when not excluded" "$(tag app)" "$(git stash -q && tag app; git stash pop -q)"

two=$(tag "${app[@]}" lib)
differ "a second context makes another tag" "$two" "$edited"
echo 'shared, changed' >lib/shared.txt
differ "and a change in it changes the tag" "$(tag "${app[@]}" lib)" "$two"
differ "a salt changes the tag" "$(tag "${app[@]}" -- --build-arg X=1)" "$edited"
same "the same salt gives the same tag" "$(tag "${app[@]}" -- --build-arg X=1)" "$(tag "${app[@]}" -- --build-arg X=1)"

cached=$(git diff --cached --name-only)
same "paths are from the repository root, wherever it runs" "$(cd other && "$script" "${app[@]}")" "$(tag "${app[@]}")"
same "the real index is untouched" "$(git diff --cached --name-only)" "$cached"
refused "a path that matches nothing is refused" missing
refused "no path at all is refused" -- salt

[ "$fails" -eq 0 ] || { echo "$fails failed" >&2; exit 1; }
echo "image-tag: all passed"
