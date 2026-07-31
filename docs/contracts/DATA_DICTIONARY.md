# IEEE-CIS Feature Dictionary

| Group | Fields | Meaning / handling |
|---|---|---|
| Keys | `TransactionID`, `TransactionDT` | Business key and relative transaction time. |
| Label | `isFraud` | Binary fraud target; absent from Kaggle test. |
| Amount | `TransactionAmt`, `log_transaction_amount`, `amount_band` | Original amount plus stable transformed/bucketed forms. |
| Presence | `has_identity`, `has_device_info`, `has_p_email`, `has_r_email` | Missingness/presence indicators. |
| Missingness | `selected_missing_count`, `selected_missing_ratio`, `identity_missing_count` | Row-level missingness features. |
| Card entity | `card_entity_key`, `prior_card_transaction_count`, `prior_card_amount_sum` | Training-derived card history features. |
| Email entity | `email_entity_key`, `prior_email_transaction_count`, `prior_email_amount_sum` | Training-derived email history features. |
| Device entity | `device_entity_key`, `prior_device_transaction_count`, `prior_device_amount_sum` | Training-derived device history features. |
| Categories | `ProductCD`, `card4`, `card6`, `DeviceType`, `device_family`, `M4`, `amount_band` | Nulls use an explicit missing category before Spark indexing. |
| Weight | `class_weight` | Present only in `model_ready/train_weighted`; fraud receives inverse-frequency weight. |

The complete generated feature list is in `reports/feature_catalog.csv` after a successful run. High-missing raw fields remain available in curated data but are not automatically promoted to the baseline feature set.

## Anonymised Vesta columns (C, D, M, dist)

The committed model uses 23 columns whose meaning Vesta never published. They are
listed here because they dominate the SHAP explanations shown in the dashboard —
`C13`, `C1` and `C14` are routinely the top contributors — and the first question
anyone asks when they see that is what those names mean.

| Group | Columns in the model | Official description | What can be said |
|---|---|---|---|
| `C1`-`C14` | all 14 | "counting, such as how many addresses are found to be associated with the payment card, etc. The actual meaning is masked." | Counters over entities linked to the transaction (addresses, emails, devices per card). Which entity each column counts is **not disclosed**. |
| `D1`-`D15` | `D1 D2 D3 D4 D5 D10 D15` | "timedelta, such as days between previous transaction, etc." | Time gaps in days. The reference event per column is **not disclosed**. |
| `dist1`, `dist2` | both | "distance" | Distance between two entities on the transaction (e.g. billing vs IP location). Units and endpoints **not disclosed**. |
| `M1`-`M9` | `M4` only | "match, such as names on card and address, etc." | Match flags. `M4` takes `M0`/`M1`/`M2`, which are categories rather than a boolean. |

Source: the column descriptions Vesta published in the IEEE-CIS Fraud Detection
competition. There is no further documentation, so **do not invent a meaning for
an individual column**. When presenting SHAP output, say the column is an
anonymised counter or time delta and that the model found it predictive - that is
the honest and complete answer.

### Reading a SHAP value

SHAP values are contributions in log-odds, not fraud labels:

- Sign is direction: `C13 +1.021` pushes this transaction toward fraud, `-1.021`
  pulls it toward legitimate.
- Magnitude is strength, comparable within one transaction.
- The fraud decision itself is `fraud_probability` / `risk_score` / `risk_band` -
  never a SHAP value.
