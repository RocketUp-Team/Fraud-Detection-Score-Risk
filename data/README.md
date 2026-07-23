# data/ — IEEE-CIS Data Processing & EDA

Phạm vi: khảo sát, làm sạch, phân tích bộ IEEE-CIS (`transaction` + `identity`), xử lý mất cân bằng lớp/missing values, chia train/validation/holdout theo thời gian (`TransactionDT`), feature engineering theo card/email/device, và chuẩn bị bộ ca demo.

Xem chi tiết phân công & lịch: [`../docs/RISK_SCORING_PLAN.md`](../docs/RISK_SCORING_PLAN.md) mục 2 và 4.

**Bàn giao cho Quân:** chạy Docker preprocessing rồi đọc `data/processed/ieee_cis_spark/HANDOVER_TO_QUAN.md`. Feature contract nằm trong `model_ready/` và manifest.

Notebook: `ieee_cis/ieee_cis_data_processing_eda.ipynb`.

Docker guide: `ieee_cis/README_DATA_PROCESSING_EDA.md`.

Handover contract: `ieee_cis/HANDOVER_TO_QUAN.md`.

Results report: `ieee_cis/RESULTS_REPORT.md`.
