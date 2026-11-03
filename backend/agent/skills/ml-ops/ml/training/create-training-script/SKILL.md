---
name: create-training-script
description: Create a draft MMM training script for the client's connector data. Use before run_training_script. Creates a draft only; nothing trains until the user approves it.
---

# create_training_script

Use for every new training or retraining request, after you have the KPI, channels, controls, connector tables and columns, and the training window from the user (see mmm-planning).

- For a new model, ask the user for a `model_name`. If the name is taken, the tool returns unique suggestions. Offer them, then call again with the chosen name.
- To retrain an existing model, pass its `model_id` instead. Do not pass a `model_name`.
- The tool returns a `run_id`, a `script_sha256`, and the generated `script`.
- The script starts from the MMM template and is adapted to the confirmed columns and channels. Do not invent column names.
- To change the script, use `edit_training_script` with the `run_id`. Then call `run_training_script` with the new `script_sha256`.
- Show the user the script or a summary of it before running. Training runs only after `run_training_script` is approved.
