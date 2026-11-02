"""The file sources: NYC TLC trip files, fetched and loaded chunk by chunk (PLAN.md D34-D35).

The Airflow lab's TLC pipeline, kept out of what runs on GCP (semantic/PLAN.md SL-19): the app
imports this package only where the warehouse keeps a file ledger (`FileLedger`, Postgres only),
and needs it installed with pyarrow (the `files` extra), so the GCP build carries neither.
`routes.FileSources` is what the app sees: the entities, the `/extract` of a file source, and a
blueprint with `/publication`, `/months` and `/retire`.
"""
