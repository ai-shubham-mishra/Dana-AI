---
name: initiate-ml-training
description: Start a model training job. Needs the user's approval, edit, or rejection before it runs.
---

# initiate_ml_training

Call this only after you have the model, KPI, channels and connector from the user, and the training window from the user (ask it first, see mmm-planning), converted with `resolve_date_range` or the data's earliest and latest dates. The user approves, edits, or rejects the request. After approval, say that execution is not connected yet, so no job started.
