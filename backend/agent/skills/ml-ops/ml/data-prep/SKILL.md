---
name: data-prep
description: Prepare the client's training data - select the connector, channels and date range, build evaluators, and update the dataset.
---

# Data preparation

List the channels in the chosen connector, prepare the training dataset, define evaluators, and apply adjustments the user asks for. Do not guess column names. Read them from the connector, using `list_channels_within_connector` or `find_connector_columns` for a fuzzy match.
