# ledger.d

Frozen history, like [`LEDGER.md`](../LEDGER.md): no new fragments are added (`CLAUDE.md` § Where things are recorded); a change's record is its PR body.
Each file here is one earlier PR's `LEDGER.md` entry, named `YYYY-MM-DD-<issue-or-pr>-<slug>.md`, in the format `LEDGER.md` describes.
`make ledger` appends them to `LEDGER.md` in name order and deletes them; until the follow-up that moves the history onto the tracker decides, they stay here.
