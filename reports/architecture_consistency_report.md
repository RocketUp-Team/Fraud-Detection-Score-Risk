# Architecture Consistency Report

**Snapshot:** 2026-07-31  
**Scope:** repository code, processed contract, model workflow, serving, diagrams and reports.

## Result

The core architecture is coherent, but the documentation is not yet factually safe for final submission because evidence files are not from one coherent run.

## Verified consistency

## Mermaid và generated exports

- Final Mermaid source: `docs/AN_FINAL_ARCHITECTURE_DIAGRAMS.md`.
- Đã kiểm tra và render thành công 8 Mermaid blocks bằng
  `@mermaid-js/mermaid-cli@11.16.0`.
- Generated outputs: `docs/diagrams/final/01.svg` đến `08.svg` và
  `docs/diagrams/final/01.png` đến `08.png`.
- Các export cũ vẫn được giữ ở các thư mục hiện hữu và đã được đánh dấu là
  historical/superseded; không dùng chúng làm source of truth.

| Area | Finding | Evidence |
|---|---|---|
| Data preparation | Spark typed ingestion, left join, chronological split and Parquet handover exist | `data/ieee_cis/pipeline/ieee_cis_preprocess.py` |
| Feature vector | 68 features; `TransactionDT` included; 7 categorical fields | `feature_order.json`, `model_ready_schema.json` |
| Training boundary | Spark/Pandas boundary exists before Python ML | `model/src/fraud_model/features.py` |
| Serving boundary | Backend imports model package in-process | `backend/src/fraud_backend/scoring.py`, Compose/Dockerfile |
| Governance | package/checksum/gate modules exist; automatic promotion is false | `package_candidate.py`, `promotion_gate.py` |
| Fallback | heuristic fallback is explicit in metadata/logging code | `backend/src/fraud_backend/scoring.py` |

## Inconsistencies requiring correction

| ID | Inconsistency | Evidence | Correction |
|---|---|---|---|
| C-01 | Persisted manifest says `verification_pending` while persisted verification report says `verification_failed` | current processed files | Regenerate manifest and verification atomically from one run |
| C-02 | Persisted report has 88 passed/6 failed, while a later manual verifier invocation returned 94/0 | command output plus report file | Keep both as evidence history; publish only one official snapshot |
| C-03 | Existing architecture docs claim V2/LightGBM metrics, but workspace currently exposes only legacy root joblib artifact | `model/artifacts/`, old docs | Mark claims historical/artifact-reported or provide matching V2 bundle |
| C-04 | Old diagrams describe candidate `0.0.3` and V2 metrics as current | `docs/ARCHITECTURE_DIAGRAMS.md` | Supersede with final diagrams; candidate lifecycle remains generic |
| C-05 | Old diagrams imply calibrated/threshold-aware V2 serving, while `score.py` evidence must be checked separately | old diagrams and serving code | State calibration/policy as active only with runtime artifact evidence |
| C-06 | Current config and processed files agree on 2.1.0, but historical reports contain 2.0.0 | manifest/history | Use 2.1.0 only for the official coherent snapshot |
| C-07 | `scripts/train_model.sh` and PowerShell workflow do not run identical stages | both scripts | Document the difference; do not call both full workflows equivalent |

## Architecture conclusion

Use the new final documents as authoritative. Keep old diagrams/reports as historical until their claims are either corrected or explicitly superseded.
