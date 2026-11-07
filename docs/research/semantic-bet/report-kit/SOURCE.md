# report-kit, vendored

A copy of the report kit the semantic-bet pages are built with: claude-dotfiles `skills/report-kit` at commit 69b1667 (its PR 52, not yet merged: re-vendor at the merge commit once it lands).
Only what the pages need is here: the components (`kit/`), the build that inlines them (`bin/build.cjs`) and the checker (`bin/check.cjs`).
The kit's docs (`SKILL.md`, `STANDARDS.md`, `REFERENCE.md`) stay upstream; read them there.

## Never edit the copy

Every file here is listed with its sha256 in [`MANIFEST.sha256`](MANIFEST.sha256), and `services/semantic-agent/tests/test_report_kit_vendored.py` fails when a file differs from it, is missing, or is not listed.
A change the pages need goes upstream into claude-dotfiles first, then comes here as an update.
Page-specific styles stay in the page's own template, never in `kit/`.

## Updating

From the repo root, with a claude-dotfiles clone at `$DOTFILES` checked out at the new commit:

```sh
cd docs/research/semantic-bet/report-kit
rm -r bin kit && mkdir -p bin kit/vendor
cp "$DOTFILES"/skills/report-kit/bin/build.cjs "$DOTFILES"/skills/report-kit/bin/check.cjs bin/
cp "$DOTFILES"/skills/report-kit/kit/*.css "$DOTFILES"/skills/report-kit/kit/*.js kit/
cp "$DOTFILES"/skills/report-kit/kit/vendor/* kit/vendor/
find bin kit -type f | sort | xargs sha256sum > MANIFEST.sha256
```

Then put the new commit in the first paragraph above, rebuild both pages (`python3 ../brief/build.py` and `python3 ../report/build.py ../results.json`, which run `bin/build.cjs`), and run `node bin/check.cjs ../brief/index.html` until it prints `0 problems`.

## Running

- Build: the pages' `build.py` call `node bin/build.cjs <page.html>` after writing the page with its markers.
- Check: `node bin/check.cjs <page.html>` (`--quick` for 400 and 1280 px only, `--shots <dir>` for screenshots); it needs Node and Playwright with Chromium.
