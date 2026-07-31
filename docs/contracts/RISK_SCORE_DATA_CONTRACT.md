# Risk Score Data Contract

Downstream scoring should produce `fraud_probability` in `[0, 1]` and `risk_score = round(fraud_probability * 100)` in `[0, 100]`. Suggested, non-final bands are Low (0–19), Guarded (20–39), Medium (40–59), High (60–79), and Critical (80–100). Preserve `TransactionID`, `processing_version`, model version, score timestamp, and feature schema version. These bands are implementation guidance, not approved business policy.

The repository now distinguishes two inference paths:

- `scoring_mode = "full_feature"`: input row already follows the full model-ready feature contract and feature order used in training.
- `scoring_mode = "partial_demo"`: input is an ad-hoc subset of fields from UI/demo flows and is not production-equivalent to training-time preprocessing.

Backend `/meta` and `/score` responses should expose `model_version`, `processing_version`, `feature_schema_version`, and `scoring_mode` so downstream consumers can tell whether a score is faithful to the training contract.
