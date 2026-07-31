# Final System Architecture

**Classification:** HYBRID WITH EXPLICIT LEGEND  
**Evidence:** repository source, processed manifest/reports, Docker Compose and serving modules.

## As-Built Architecture

Hệ thống hiện tại là một modular monolith có hai workflow:

1. Offline Spark batch workflow đọc IEEE-CIS CSV, chuẩn hóa schema, join transaction–identity, audit, tạo feature và ghi Parquet.
2. Application workflow để FastAPI import trực tiếp model package, lưu transaction/review vào SQLite hoặc PostgreSQL và phục vụ React.

Tên kiến trúc chính xác là **In-process model serving inside a modular monolith**.

Boundary training chính xác là **Distributed data preparation with single-node Python model training**: `to_pandas_xy()` gọi `.toPandas()`, sau đó Logistic Regression/LightGBM/XGBoost/CatBoost chạy trong Python process.

## Four planes

| Plane | Input | Processing | Persisted output | Owner | Limitation |
|---|---|---|---|---|---|
| Data | IEEE-CIS CSV | typed ingestion, normalization, left join, audit, chronological split, feature engineering | curated/splits, feature_store, model_ready, manifest, reports | `pipeline/`, `data/ieee_cis/pipeline/` | manifest/report phải cùng run snapshot |
| Model Development | model-ready Parquet | validation, mapping, baseline, comparison, tuning, calibration/policy workflow | joblib, metadata, metrics, MLflow runs | `model/src/fraud_model/` | `.toPandas()` giới hạn driver memory |
| Governance | candidate bundle | checksum, smoke, metric/data gates | candidate manifest, promotion decision | package/gate modules | human approval/registry update chưa automated |
| Serving | feature dictionary/CSV | mapping, prediction, SHAP, backend risk presentation | API response, database rows, dashboard | `model/score.py`, `backend/`, `frontend/` | fixed backend policy và fallback |

## Evidence snapshot

Processed manifest hiện ghi pipeline `2.1.0`, processing `ieee-cis-preprocess-2.1.0`, feature schema `ieee-cis-features-1.1.0`, six datasets và 68-feature contract. `TransactionDT` có trong feature vector. Persisted verification reports có thể lệch giữa các lần chạy; chỉ dùng snapshot gồm manifest + verification + output schema được tạo cùng run.

Workspace hiện chứng minh artifact legacy `model/artifacts/final_model.joblib` và `model_comparison.json`. Claim về versioned V2 artifact/metric phải là historical hoặc artifact-reported nếu không có file V2 trong evidence bundle.

## Target Architecture

Target giữ batch data plane nhưng bổ sung online historical feature service, immutable model registry/release, model bundle và policy bundle tách riêng, strict readiness, monitoring và audit lineage. Các thành phần này phải vẽ nét đứt.

## Trust boundaries

- raw CSV, browser input và CSV import là untrusted input;
- processed-data mount là trusted handoff nhưng cần verifier;
- `joblib.load()` là code-execution trust boundary;
- local MLflow là tracking/lineage store, không tự động là serving registry;
- heuristic fallback là degraded demo mode, không phải fraud model.
