---
name: initiate-ml-training
description: Start a model training job. Needs the user's approval, edit, or rejection before it runs.
---

# initiate_ml_training

Call this only after you have the model, KPI, channels and connector from the user, and a date range from `resolve_date_range` (never ask the user for dates). The user approves, edits, or rejects the request. After approval, say that execution is not connected yet, so no job started.
