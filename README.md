# backup-project

backs up a google cloud sql database to s3 every day.

the flow is simple: cloud sql exports the db to a gcs bucket, then the script picks it up and moves it to s3. old backups get cleaned up automatically and you get a slack message when it's done.

---

## getting started

install dependencies:
```
pip install -r requirements.txt
```

fill in the `.env` file with your real values — everything the scripts need is in there. then run `bucket.py` once to create the gcs bucket, and after that just run `backup-project.py` whenever you want a backup (or put it on a cron job).

---

## scripts

**`backup-project.py`** — the main one. runs the full backup: exports the db, moves it to s3, cleans up gcs, sends a slack notification.

**`bucket.py`** — run this once at the start to create the gcs bucket. you won't need it again after that.

**`test-db.py`** — checks if your cloud sql instance is reachable and prints the details. useful for making sure your credentials work before running anything.

**`generate.py`** — uploads a 200mb random file to gcs. use it to test the transfer without doing a real db export.

**`words.txt`** — a plain text file for quick upload tests.

---

## notes

- the `.env` file is included here for testing purposes only — if you fork this make sure to add `.env` to your `.gitignore` before pushing your own credentials
- you'll need a gcp service account json key, put the path to it in `GCP_KEY_PATH`
- the gcs bucket only ever keeps today's backup, everything older gets deleted
