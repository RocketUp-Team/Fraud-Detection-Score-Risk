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
