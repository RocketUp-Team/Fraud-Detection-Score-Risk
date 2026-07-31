# Executive Summary — IEEE-CIS Fraud Detection Architecture

**Status:** AS-BUILT REVIEW WITH TARGET LIMITATIONS  
**Evidence snapshot:** 31/07/2026

## Kết luận chính

Repository hiện thực một data pipeline Apache Spark cho IEEE-CIS và một model-development workflow Python sau handover Parquet. Kiến trúc batch là phần mạnh nhất: typed ingestion, transaction–identity left join không làm mất transaction rows, chronological split theo `TransactionDT`, train-only preprocessing và point-in-time history được lưu bằng artifacts có version.

Current manifest ghi processing version `ieee-cis-preprocess-2.1.0`, feature schema `ieee-cis-features-1.1.0`, canonical vector 68 features gồm 61 numeric và 7 categorical; `TransactionDT` nằm trong model vector. Verification report hiện tại có 94 checks passed, 0 failed. Split hiện tại theo manifest là train 412,956, validation 88,490 và holdout 89,094; một copied official split summary vẫn có 88,486/89,098, nên report chính ghi rõ đây là snapshot discrepancy.

Official V2 workflow chọn `catboost__balanced`. Validation PR-AUC là `0.5805986932`, ROC-AUC `0.9081217221`; holdout PR-AUC là `0.4266472301`, ROC-AUC `0.8780747768`. Isotonic calibration được lưu trong artifact và holdout Brier score giảm từ `0.0495279511` raw xuống `0.0248335480`. Candidate có checksum và artifact-load smoke test, nhưng promotion decision là `not_promoted` vì holdout PR-AUC không đạt reference `0.4582` và Git state dirty. Serving version không thay đổi.

Vì vậy, V2 nên được gọi là **configured software serving default**, không phải production-promoted model. Backend dùng in-process import: “In-process model serving inside a modular monolith.” Backend có fixed risk bands và decision mapping; threshold config của candidate chưa phải runtime authority cho approve/review/reject. `partial_demo` default missing features chỉ phục vụ demo continuity, không tương đương full-feature scoring.

## Kiến trúc as-built

```text
IEEE-CIS CSV
  → Spark typed ingestion and normalization
  → transaction–identity left join and quality audit
  → chronological split and train-only fitting
  → point-in-time features and imbalance variants
  → model-ready Parquet + schema/manifest/verifier
  → Pandas boundary
  → single-node Python ML
  → calibrated candidate + checksum + promotion gate
  → configured v2 FastAPI serving path
```

Cụm mô tả chính xác là **“Distributed data preparation with single-node Python model training.”** Không có evidence cho distributed LightGBM/XGBoost/CatBoost training trên Spark workers.

## Target architecture cần giữ tách biệt

Target nên tách Model Bundle và Policy Bundle, bổ sung immutable registry/release, strict readiness khi model không load, và online historical feature service:

```text
Transaction event
  → Online Feature Service / Historical Feature Store
  → Canonical 68-feature vector
  → Approved Model Bundle + Versioned Policy Bundle
  → Backend decision
```

Đây là **Proposed**, chưa phải implementation hiện tại. Các gap có ảnh hưởng nhất là offline–online feature parity, duplicated threshold/policy ownership, driver-memory ceiling ở Pandas boundary, local-only MLflow, in-process coupling và fallback fail-open.

## Khuyến nghị trước khi nộp report

1. Regenerate one coherent evidence snapshot để manifest, split report, verifier, metrics và report facts cùng một run.
2. Chốt runtime policy authority: backend fixed bands hoặc approved Policy Bundle, không để hai nguồn cùng có thể được hiểu là authority.
3. Tách readiness khỏi liveness và báo rõ `model`, `fallback_heuristic`, `full_feature`, `partial_demo`.
4. Giữ holdout sealed; mọi thay đổi sau holdout phải tạo candidate version mới.
5. Đưa checksum, feature/schema version, processing version và Git state vào immutable handover.

Report đầy đủ nằm ở [AN_FINAL_DATA_AND_MODEL_ARCHITECTURE_REPORT.md](AN_FINAL_DATA_AND_MODEL_ARCHITECTURE_REPORT.md). Các chart evidence nằm ở [docs/figures/final_report](figures/final_report/), còn Mermaid exports nằm ở [docs/diagrams/final](diagrams/final/).
