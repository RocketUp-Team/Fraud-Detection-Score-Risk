# model/ — Quân (Huấn luyện & đóng gói mô hình)

Nhận feature pipeline từ An, train baseline (Logistic Regression), so sánh
LightGBM/XGBoost/CatBoost theo PR-AUC/ROC-AUC, tuning model tốt nhất, sinh
giải thích SHAP, và đóng gói thành module `score(features) -> {proba, shap}`
để Trung gọi từ backend.

Chi tiết phân công & lịch: [`../docs/RISK_SCORING_PLAN.md`](../docs/RISK_SCORING_PLAN.md) mục 2 và 4.

## Setup

```bash
cd model
uv sync
```

## Tải dataset (IEEE-CIS Fraud Detection)

```bash
bash scripts/download_data.sh
```

Cần Kaggle API token (`~/.kaggle/kaggle.json`) và đã tham gia competition
`ieee-fraud-detection`. Chi tiết trong script. Sau khi tải, kỳ vọng có:

```
data/raw/train_transaction.csv
data/raw/train_identity.csv
```

## Chạy baseline (Ngày 1)

```bash
uv run python -m fraud_model.train_baseline
```

In ROC-AUC/PR-AUC trên tập validation (chia theo thời gian `TransactionDT`,
xem `docs/RISK_SCORING_PLAN.md` mục 5 — không dùng random split để tránh
leakage) và lưu model tại `artifacts/baseline_logreg.joblib`.

## Cấu trúc

```
model/
├── src/fraud_model/
│   ├── config.py      # đường dẫn, hằng số (cột ID/target/thời gian)
│   ├── data.py         # load + merge transaction/identity, time-based split
│   ├── features.py     # feature prep tạm thời (sẽ thay bằng pipeline của An, Ngày 3)
│   ├── train_baseline.py  # baseline Logistic Regression (Ngày 1)
│   └── score.py         # module bàn giao cho Trung: score(features) -> {proba, shap} (Ngày 5)
├── scripts/download_data.sh
├── data/raw/            # dataset thô (gitignored)
├── data/processed/      # dataset đã xử lý (gitignored)
├── artifacts/           # model đã train (gitignored)
└── tests/
```

## Lộ trình tiếp theo

Theo `docs/RISK_SCORING_PLAN.md` mục 3 và 4:

- **Ngày 2:** train baseline với feature pipeline theo EDA của An
- **Ngày 3:** nhận feature pipeline chính thức từ An → so sánh LightGBM/XGBoost/CatBoost
- **Ngày 4:** tuning model tốt nhất + SHAP explainability thật
- **Ngày 5:** đóng gói model cuối + hàm `score()` hoàn chỉnh, bàn giao cho Trung
- **Ngày 6-7:** hỗ trợ tích hợp, theo dõi latency, bug bash
