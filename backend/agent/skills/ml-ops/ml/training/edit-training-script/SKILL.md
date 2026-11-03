---
name: edit-training-script
description: Change a draft training script with one exact text replacement. Use only on a draft from create_training_script, before run_training_script.
---

# edit_training_script

Pass the `run_id`, the exact `old_text` to replace, and the `new_text`. The `old_text` must match exactly once in the script. If it matches zero or several times, the edit is refused, so include more surrounding lines.

The tool returns the new `script_sha256`. Show the user what changed, then call `run_training_script` with that sha. Training is refused if the sha does not match the script that was approved.
