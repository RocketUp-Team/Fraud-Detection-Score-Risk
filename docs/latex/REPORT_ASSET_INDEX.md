# Thesis Report Asset Index

Mục đích: đối soát nhanh các hình, sơ đồ, source LaTeX, pipeline và artifact được sử dụng trong `docs/latex/report.tex`.

## 1. PDF và source chính

| Thành phần | Đường dẫn |
|---|---|
| LaTeX entrypoint | `docs/latex/report.tex` |
| PDF build output | `docs/latex/report.pdf` |
| Metadata | `docs/latex/metadata.tex` |
| Abstract | `docs/latex/frontmatter/abstract.tex` |
| Main chapters | `docs/latex/chapters/` |
| Appendices | `docs/latex/appendices/appendices.tex` |

## 2. Tám sơ đồ chính trong phần thân report

| Figure | Chapter | LaTeX source | Rendered asset / source evidence |
|---|---:|---|---|
| Overall system architecture | 3 | `docs/latex/figures/final_overall_system.tex` | `docs/diagrams/final/overall-system-architecture.png` |
| Layered data architecture | 3 | `docs/latex/figures/final_layered_data.tex` | `docs/diagrams/final/Layered data architecture.png` |
| Data, feature, evaluation contracts | 3 | `docs/latex/figures/final_contracts.tex` | Corrected TikZ in thesis; PNG retained as visual reference pending semantic correction |
| Detailed data processing pipeline | 4 | `docs/latex/figures/final_detailed_pipeline.tex` | Corrected TikZ with canonical dataset names; PNG retained as visual reference pending semantic correction |
| Leakage-controlled transformation flow | 4 | `docs/latex/figures/final_leakage_flow.tex` | `docs/diagrams/final/leakage-controlled-transformation-flow.png` |
| Model training lifecycle | 5 | `docs/latex/figures/final_training_lifecycle.tex` | `docs/diagrams/final/End-to-End-Model-Training-Lifecycle.png` |
| Temporal development windows | 5 | `docs/latex/figures/final_temporal_windows.tex` | `docs/diagrams/final/temporal-development-windows.png` |
| Promotion state machine | 5 | `docs/latex/figures/final_promotion_state.tex` | `docs/diagrams/final/promotion-state-machine.png` |

Các Mermaid/SVG/PNG exports của tám sơ đồ nằm tại `docs/diagrams/final/`. Source of truth của bộ diagram là `docs/AN_FINAL_ARCHITECTURE_DIAGRAMS.md`.

## 3. Charts trong phần thân report

| Chart | Chapter | LaTeX source | Image |
|---|---:|---|---|
| Class distribution | 7 | `docs/latex/figures/final_result_charts.tex` | `docs/figures/final_report/class-distribution.png` |
| Fraud rate by ProductCD | 7 | `docs/latex/figures/final_result_charts.tex` | `docs/figures/final_report/fraud-rate-by-product.png` |
| Fraud rate by identity presence | 7 | `docs/latex/figures/final_result_charts.tex` | `docs/figures/final_report/fraud-rate-by-identity-presence.png` |
| Fraud rate by transaction hour | 7 | `docs/latex/figures/final_result_charts.tex` | `docs/figures/final_report/fraud-rate-by-transaction-hour.png` |

Các charts evidence mới trong phần model:

| Chart | Chapter | Image |
|---|---:|---|
| Model-family comparison | 5 | `docs/figures/final_report/model-family-comparison.png` |
| Current candidate validation vs holdout | 5 | `docs/figures/final_report/candidate-validation-holdout.png` |
| Holdout confusion matrix | 5 | `docs/figures/final_report/holdout-confusion-matrix.png` |
| Raw vs isotonic Brier score | 5 | `docs/figures/final_report/calibration-brier.png` |

Historical V1/V2 comparison is now placed in the appendix and is not used as
the current candidate performance figure.

Chart generation script: `scripts/build_final_report_figures.py`.

## 4. Diagram implementation-level trong appendix

| Nội dung | Đường dẫn |
|---|---|
| Application deployment diagram | `docs/latex/figures/deployment.tex` |
| Appendix placement | `docs/latex/appendices/appendices.tex` |
| API field and endpoint reference | `docs/latex/appendices/appendices.tex` |
| Feature and risk contract tables | `docs/latex/appendices/appendices.tex` |
| Reproduction commands | `docs/latex/appendices/appendices.tex` |

Các source cũ `docs/latex/figures/system_architecture.tex` và `docs/latex/figures/data_pipeline.tex` vẫn được giữ để bảo toàn lịch sử nhưng không còn được gọi trong report chính.

## 5. Pipeline source được report mô tả

| Chức năng | Đường dẫn |
|---|---|
| Pipeline entrypoint | `pipeline/fraud_risk_data_pipeline.py` |
| Contract utilities | `pipeline/contract_utils.py` |
| Processed-data contract | `pipeline/processed_contract.py` |
| Temporal features | `pipeline/temporal_features.py` |
| Processed-data verifier | `pipeline/verify_processed_data.py` |
| IEEE-CIS Spark preprocessing | `data/ieee_cis/pipeline/ieee_cis_preprocess.py` |
| Pipeline configuration | `config/pipeline_config.yaml` |

## 6. Model-training source được report mô tả

| Chức năng | Đường dẫn |
|---|---|
| Model configuration | `model/src/fraud_model/config.py` |
| Data loading | `model/src/fraud_model/data.py` |
| Feature mapping/alignment | `model/src/fraud_model/features.py` |
| Baseline | `model/src/fraud_model/train_baseline.py` |
| Model comparison | `model/src/fraud_model/train_compare.py` |
| Tuning/explanation | `model/src/fraud_model/tune_and_explain.py` |
| Data validation | `model/src/fraud_model/validate_data.py` |
| Threshold analysis | `model/src/fraud_model/threshold_analysis.py` |
| Holdout evaluation | `model/src/fraud_model/evaluate_holdout.py` |
| Candidate packaging | `model/src/fraud_model/package_candidate.py` |
| Promotion gate | `model/src/fraud_model/promotion_gate.py` |
| Runtime scoring | `model/src/fraud_model/score.py` |

## 7. Serving source được report mô tả

| Thành phần | Đường dẫn |
|---|---|
| FastAPI application | `backend/src/fraud_backend/main.py` |
| Scoring integration | `backend/src/fraud_backend/scoring.py` |
| Runtime risk policy | `backend/src/fraud_backend/risk.py` |
| Persistence models | `backend/src/fraud_backend/models.py` |
| Transaction routes | `backend/src/fraud_backend/routers/transactions.py` |
| Data/job routes | `backend/src/fraud_backend/routers/data.py` |
| React entrypoint | `frontend/src/App.tsx` |
| Frontend API/types | `frontend/src/lib/api.ts`, `frontend/src/types/api.ts` |
| API contract | `docs/API_CONTRACT.md` |

## 8. Official-run evidence

| Evidence | Đường dẫn |
|---|---|
| Verification report | `reports/official-run/verification_report.json` |
| Split summary | `reports/official-run/split_summary.csv` |
| Training metadata | `reports/official-run/training_metadata_v2.json` |
| Validation metrics | `reports/official-run/validation_metrics_v2.csv` |
| Holdout metrics | `reports/official-run/holdout_metrics_v2.csv` |
| Threshold configuration | `reports/official-run/threshold_config_v2.json` |
| Promotion decision | `reports/official-run/promotion_decision_v2.json` |
| Candidate manifest | `reports/official-run/candidate_manifest_v2.json` |
| SHA-256 checksum | `reports/official-run/checksum_v2.sha256` |
| Official run logs | `reports/official-run/*.log` |

## 9. Data output paths referenced by the report

| Output | Đường dẫn |
|---|---|
| Raw IEEE-CIS input | `data/data/ieee-fraud-detection/` |
| Processed root | `data/processed/ieee_cis_fraud_risk/` |
| Model-ready datasets | `data/processed/ieee_cis_fraud_risk/model_ready/` |
| Feature store | `data/processed/ieee_cis_fraud_risk/feature_store/` |
| Processed reports | `data/processed/ieee_cis_fraud_risk/reports/` |
| Processed artifacts | `data/processed/ieee_cis_fraud_risk/artifacts/` |

## 10. Kiểm tra nhanh

```bash
# Liệt kê tất cả source hình được report gọi
grep -RInE '\\input\{figures/|includegraphics' docs/latex --include='*.tex'

# Kiểm tra asset hình tồn tại
find docs/diagrams/final docs/figures/final_report -type f | sort

# Kiểm tra reference lỗi trong log sau build
grep -E 'undefined|There were undefined' docs/latex/report.log || true

# Build lại report
cd docs/latex
tectonic --keep-logs report.tex
```
