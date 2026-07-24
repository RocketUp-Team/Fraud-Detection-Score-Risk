# Risk Score Data Contract

Downstream scoring should produce `fraud_probability` in `[0, 1]` and `risk_score = round(fraud_probability * 100)` in `[0, 100]`. Suggested, non-final bands are Low (0–19), Guarded (20–39), Medium (40–59), High (60–79), and Critical (80–100). Preserve `TransactionID`, `processing_version`, model version, score timestamp, and feature schema version. These bands are implementation guidance, not approved business policy.
