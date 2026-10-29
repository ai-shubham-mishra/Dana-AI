---
name: ask-user
description: Ask the user one clarifying question, optionally with short choices, when required input is missing.
---

# ask_user

Use this for each missing input that cannot be resolved with a tool (KPI, channels, connector, currency). Do not ask for dates; resolve them with the calendar tools. Ask one question at a time. Offer options when the answer comes from a known set.

The question is shown as Markdown. When you list several items (a plan, options, settings), use one Markdown bullet per line (`- Model: MMM`), not inline bullet characters.
