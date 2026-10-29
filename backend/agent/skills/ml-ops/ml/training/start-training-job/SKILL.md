---
name: start-training-job
description: Queue a model training job on the bundled sample MMM dataset. Needs the user's approval, edit, or rejection before it runs.
---

# start_training_job

Call this only after you have the model, KPI and channels from the user, and a date range from `resolve_date_range` (never ask the user for dates). The user approves, edits, or rejects the request first. After approval the job is queued and runs locally on the bundled sample MMM dataset. Tell the user to follow progress on the Jobs tab. If the request is invalid, ask the user to correct it.
