# Final Architecture Review

## 1. Executive Summary

Kiến trúc lõi phù hợp cho BDA501: Spark batch data plane, chronological split, model-ready Parquet contract và champion–challenger gate là các quyết định đúng hướng. Hệ thống chưa nên được gọi là production-ready.

Ba vấn đề lớn nhất là offline–online feature parity, duplicated policy ownership và việc tài liệu cũ trộn as-built với target. Evidence cũng cần được gom theo một run snapshot vì manifest và verification report có thể được tạo ở các thời điểm khác nhau.

## 2. Review Scope

Review dựa trên pipeline source, processed contract/verifier, model training modules, scoring/backend/frontend source, Compose/Docker, current manifest/reports và architecture documents/exports. Task này không retrain, tune, promote hoặc đổi runtime policy.

## 3. Current As-Built Architecture

Đây là modular monolith: Spark preprocessing offline, Python ML single-node sau `.toPandas()`, FastAPI import model in-process, database persistence và React dashboard. Không có evidence để gọi đây là microservices hoặc distributed LightGBM training.

## 4. Target Architecture

Target bổ sung online historical feature service, immutable registry/release, model-policy separation, strict readiness, approval state và monitoring. Tất cả phải được đánh dấu proposed/target.

## 5. Data Plane

Pipeline có explicit schema, identity normalization, transaction–identity left join, audit, chronological split, point-in-time historical features và model-ready Parquet. EDA là nhánh báo cáo, không phải transformation bắt buộc.

## 6. Layered Data Architecture

Physical evidence gồm raw input, curated/splits, reports, feature_store, model_ready và preprocessing artifacts. Source/validation/handover là logical concepts được persisted bằng manifest/verifier.

## 7. Detailed Data Pipeline

Transformation order phải lấy từ code: validation → typed ingestion → normalization → left join → audit/cleanup → split → train-only fit/PIT features → variants → Parquet → manifest/verifier.

## 8. Leakage-Controlled Transformations

Historical window sắp theo `TransactionDT, TransactionID` và kết thúc ở previous row. Validation/holdout không resample. Metadata/label/weight không thuộc canonical model vector. Holdout reuse sau khi mở vẫn là process risk.

## 9. Data, Feature and Evaluation Contracts

Current processed contract ghi sáu datasets và canonical 68-feature order; `TransactionDT` đang trong vector; bảy categorical gồm `ProductCD`, `card4`, `card6`, `DeviceType`, `device_family`, `M4`, `amount_band`. Mọi report cuối phải dùng manifest, schema và verification từ cùng snapshot.

## 10. Model Development Plane

Training là Python single-node sau Spark/Pandas boundary. Có baseline, comparison, tuning, calibration/threshold workflow, holdout evaluation, packaging và gate.

## 11. Temporal Development Windows

Candidate code có selection, calibration và policy windows. Không retroactively gán workflow này cho mọi historical V1/V2 artifact nếu artifact không chứng minh metadata tương ứng.

## 12. Calibration and Threshold Policy

Calibrator/threshold artifact có trong training workflow không đồng nghĩa runtime active. Backend fixed risk bands/decision logic là authority nếu backend không load threshold config để quyết định approve/review/reject. Calibrated serving chỉ được claim khi scoring path và runtime metadata chứng minh calibrator được load.

## 13. Model Governance Plane

`package_candidate.py` tạo package/checksum/smoke evidence; `promotion_gate.py` ghi gates với automatic promotion false. Human approval và registry update là target process.

## 14. Champion–Challenger and Promotion

Candidate fail phải đi tới failure/archive state; serving configuration giữ nguyên và V2 remains champion. Candidate fail không “chuyển thành” V2. V1 chỉ là rollback target sau compatibility evidence.

## 15. Serving Plane

`score()` xử lý mapping, missing values, prediction, SHAP và `scoring_mode`; backend chịu API, persistence, risk presentation và fallback. Partial-demo default feature không phải full-feature online inference.

## 16. Full-Feature and Partial-Demo Scoring

Batch full-feature có Spark context; full-feature API yêu cầu vector đã feature-engineered; partial-demo dùng default và phải gắn label `partial_demo`. Online historical feature service chỉ là target.

## 17. Spark and Python ML Boundary

Spark đảm nhiệm distributed preparation. `.toPandas()` tạo single-node driver boundary và scaling risk. Đây là tradeoff phù hợp assignment, không phải distributed model fitting.

## 18. Deployment Architecture

Compose tách preprocessing, training/local hoặc standalone Spark, backend, frontend và database. Backend copy/import model artifact vào image; model không là network service riêng.

## 19. Architecture Tradeoffs

| Decision | Benefit | Cost |
|---|---|---|
| Spark → Parquet → Pandas | rõ handover, dùng estimator Python | driver-memory limit |
| Monorepo/path dependency | đơn giản cho BDA501 | backend/model coupling |
| In-process serving | đơn giản, ít serialization | scale/rollback coupling |
| Fixed backend bands | UI ổn định | không tự phản ánh candidate policy |
| Local MLflow | offline lineage/tracking | chưa là registry |
| Joblib | package đơn giản | deserialization trust boundary |

## 20. Architecture Gaps

Chi tiết ở `docs/AN_FINAL_ARCHITECTURE_GAPS_AND_ACTIONS.md`; critical gaps là feature parity, evidence snapshot consistency và as-built/target separation.

## 21. Recommended Final Architecture

Giữ batch data plane + modular monolith cho BDA501. Trình bày online feature service, policy bundle và registry là future evolution, không đưa vào current architecture.

## 22. Required Actions Before Submission

1. Tạo evidence snapshot gồm manifest, verification, schema, model metadata, metrics và checksum cùng run.
2. Chỉ đưa V2 metrics vào thesis khi có artifact/metadata evidence tương ứng.
3. Đánh dấu diagram cũ historical hoặc thay bằng final Mermaid source.
4. Đồng bộ claim calibration, threshold, fallback và MLflow với runtime code.

## 23. Final Assessment

The core architecture is appropriate for BDA501. The strongest parts are the Spark batch data plane, chronological leakage control, model-ready data contract and champion–challenger workflow. The main gaps are offline–online feature parity, duplicated policy ownership, incomplete separation between as-built and target architecture, and inconsistent evidence snapshots.
