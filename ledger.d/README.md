# ledger.d

One file per PR: its `LEDGER.md` entry, named `YYYY-MM-DD-<issue-or-pr>-<slug>.md`, in the format `LEDGER.md` describes.
Parallel PRs never conflict on `LEDGER.md` this way (the towncrier / changesets pattern).
`make ledger` on `main` appends the fragments to `LEDGER.md` in name order and deletes them.
Until then, the newest entries are `LEDGER.md`'s tail plus the files here.
