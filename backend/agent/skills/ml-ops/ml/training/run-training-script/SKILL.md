---
name: run-training-script
description: Start training from a reviewed draft script. Needs the user's approve or reject before it runs. Training is refused if the script changed after review.
---

# run_training_script

Call this only with the `run_id` and `script_sha256` from the latest `create_training_script` or `edit_training_script` result, after the user has seen the script. The user approves or rejects the request. The approval shows the script and its sha.

After approval, the job is queued and the user can follow progress on the Jobs tab. If the user rejects, nothing starts, and the draft stays ready for changes.
