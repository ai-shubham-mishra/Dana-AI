---
name: ask-user
description: Ask the user one clarifying question with a typed answer (single select, multi select, text, number, or boolean) when required input is missing.
---

# ask_user

Use this for each missing input that cannot be resolved with a tool. Do not ask for dates; resolve them with the calendar tools. Ask one question at a time.

Pick the `response_type` that matches the answer:

- `single_select` with `options`: one value from a known set, for example the connector to train on or the KPI.
- `multi_select` with `options`: several values, for example the channels to include.
- `number`: a numeric value, for example a budget or a holdout size.
- `boolean`: yes or no.
- `text`: free text the options cannot cover. Options are optional suggestions for text.

For connectors and channels, call `list_connectors` first. Ask a `single_select` question with the connector names as options. Then ask a `multi_select` question with the channel names from `list_channels_within_connector` as options. Never invent option values; use only the names a tool returned.

Typed answers come back as JSON such as `{"answer": ["TV", "YouTube"]}`. Text answers come back as plain text.

The question is shown as Markdown. When you list several items (a plan, options, settings), use one Markdown bullet per line (`- Model: MMM`), not inline bullet characters.
