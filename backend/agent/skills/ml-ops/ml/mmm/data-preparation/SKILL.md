---
name: mmm-data-preparation
description: How to make a client's connector columns ready for MMM training - reading text as numbers, filling blanks, calendar and holiday features, lags and rolling means - and when to ask the user instead.
---

# MMM data preparation

Connector columns are often not model-ready. A spend column can be stored as text (`"1,234.50"`, `"$ 99"`), a date can be a text column, and a channel can have no rows on some days. Profile first, decide second, preview third, and only then call `start_mmm_run`.

## 1. Profile every candidate column

Call `profile_connector_columns` with the connector and the exact column names from `find_connector_columns`. For each column read:

- `blank`: rows that are NULL or empty. These are filled with 0.
- `readable_as_number` and `unreadable`: how many non-blank values parse as numbers after removing spaces, commas and currency signs.
- `unreadable_samples`: the values that will become 0. Check them. A value like `"n/a"` is fine as 0. A value like `"1.2M"` is a unit problem, so ask the user before training.
- `recommendation`: follow it unless the samples say otherwise.

Rules:

- A numeric column is used as it is.
- A text column that holds numbers goes in `preparation.text_to_numeric` under its output name. `start_mmm_run` refuses a text metric that is not declared there.
- A mostly non-numeric column is not a metric. Pick a different column or ask the user.
- A mixed column is a judgement call. Show the user the samples and ask whether unreadable values should count as 0.

## 2. Choose the features

Only add a feature when it has a reason in the data strategy. Each choice goes into the rationale.

- `date_features`: `day_of_week`, `month`, `week_of_year` or `is_weekend`. Use them when the KPI shows weekday or seasonal patterns. Weekly data usually needs only `month` or `week_of_year`.
- `holiday_country`: an ISO alpha-2 code such as `DE`, `US` or `IN`. Use it when the business is country-specific and holidays move sales. Ask the user for the country if the data does not say it.
- `lags`: a channel's effect often lands days or weeks later, for example `{"search": [7, 14]}`. Keep lags at or below 52 days. Never add lags on the KPI, because that leaks the target.
- `rolling_means`: a smoothed spend level, for example `{"search": 7}`. Windows run from 2 to 52 days.

Lags and rolling means need history before the window. The platform reads that history automatically, so the first rows are not blank.

## 3. Preview before training

Call `preview_mmm_dataset` with the same plan you would send to `start_mmm_run`. Check:

- The row count is comfortably above the minimum. The window is refused below 20 usable rows.
- `Days dropped because the KPI had no row` is small. A large number means the KPI table is sparse or the date window is wrong.
- `Blanks filled with 0 per output` is small for the channels that matter. A channel that is blank most of the time should be excluded, not forced through.
- The sample rows look right: spend is in the expected scale, and the lag and holiday columns are populated.

If the preview fails, fix the plan from the error and preview again. Do not start the run with a failing preview.

## 4. When to ask the user

Ask before you train when:

- A text column has unreadable values that carry meaning (units, ranges, "TBD").
- The holiday country is unknown.
- The data has a large gap, or a channel is blank for most of the window.
- The user has not said whether unreadable values should count as 0.

Do not ask about things the profile already answers, such as whether a column is numeric.

## 5. What the run folder keeps

Every run stores `dataset.csv` (with the features), `dataset_log.json` (the plan, row counts, dropped days, blanks filled per output and the feature list), `config.yml`, and `train.py`. Refer to `dataset_log.json` when the user asks how the data was prepared.
