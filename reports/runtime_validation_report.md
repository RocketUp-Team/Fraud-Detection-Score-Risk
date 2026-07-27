# Runtime Validation Report

Ngày chạy: 2026-07-27

## Tóm tắt

Runtime validation được thực hiện theo nhiều bước. Không phải mọi bước đều pass ở lần đầu; báo cáo này ghi đúng thứ tự các lần fail, fix và trạng thái cuối cùng.

## Chi tiết lệnh và kết quả

| Command | Status | Result |
| --- | --- | --- |
| `python -m pipeline.fraud_risk_data_pipeline --output-dir .\data\processed\ieee_cis_fraud_risk` | Failed | lần 1 fail do `reports/join_audit.csv` đang là Spark directory cũ, Windows `to_csv` không thể ghi file cùng tên |
| `python -m pipeline.fraud_risk_data_pipeline --output-dir .\data\processed\ieee_cis_fraud_risk` | Failed | lần 2 đi xa hơn, fail ở Matplotlib backend `Tk` trên Windows |
| `docker compose -f docker-compose.preprocessing.yml build` | Failed | lần 1 fail vì `.dockerignore` exclude các file mà Dockerfile cần `COPY` |
| `docker compose -f docker-compose.preprocessing.yml build` | Completed but tool timed out | image `fraud-risk-preprocessor:2.0.0` tồn tại sau khi fix build context |
| `docker image inspect fraud-risk-preprocessor:2.0.0` | Passed | xác nhận image Linux đã build xong |
| `docker compose -f docker-compose.preprocessing.yml run --rm preprocess` | Timed out at tool layer | container không còn chạy sau timeout, nhưng Parquet/artifact/report phần lớn đã được ghi xuống output |
| `python -m pipeline.processed_contract --output-dir .\data\processed\ieee_cis_fraud_risk` | Passed | normalize Spark CSV report directories và regenerate manifest hợp lệ |
| `python -m pipeline.verify_processed_data --output-dir .\data\processed\ieee_cis_fraud_risk` | Passed | status cuối `ready_for_downstream_training`, `checks_passed=82`, `checks_failed=0` |

## Raw dataset validation

Đã xác nhận tồn tại:

- `data/data/ieee-fraud-detection/train_transaction.csv`
- `data/data/ieee-fraud-detection/train_identity.csv`
- `data/data/ieee-fraud-detection/test_transaction.csv`
- `data/data/ieee-fraud-detection/test_identity.csv`

Kích thước quan sát:

- `train_transaction.csv`: 683,351,067 bytes
- `train_identity.csv`: 26,529,680 bytes
- `test_transaction.csv`: 613,194,934 bytes
- `test_identity.csv`: 25,797,161 bytes

Tổng raw CSV > 1.29 GB, đáp ứng yêu cầu dataset >= 500 MB.

## Artifact output xác nhận

Đã đọc được các dataset Parquet:

| Dataset | Rows |
| --- | ---: |
| train_original | 412,956 |
| train_weighted | 412,956 |
| train_balanced | 58,394 |
| validation | 88,490 |
| holdout | 89,094 |
| kaggle_test | 506,691 |

Verifier xác nhận:

- non-empty datasets
- `TransactionID` present
- `isFraud` có ở labeled datasets
- `isFraud` không có ở `kaggle_test`
- `class_weight` chỉ có ở `train_weighted`
- split non-overlap
- temporal order đúng
- schema hash khớp manifest
- feature order artifact tồn tại
- median artifact tồn tại
- required report files tồn tại

## Runtime blockers đã gặp và cách xử lý

1. Windows file-vs-directory conflict cho report CSV

- Nguyên nhân: artifact Spark CSV cũ tạo thư mục tên `*.csv`
- Fix: `write_single_csv()` dọn conflict và ghi atomically trên Windows

2. Matplotlib GUI backend trên Windows

- Nguyên nhân: Pandas plot kéo `Tk` backend
- Fix: khóa `matplotlib.use("Agg")`

3. Docker build context mismatch

- Nguyên nhân: `.dockerignore` exclude file mà Dockerfile cần
- Fix: unignore chính xác các file preprocessing

4. Manifest invalid / stale sau run dài

- Nguyên nhân: run Docker dài không để lại manifest finalized
- Fix: thêm `pipeline.processed_contract` để normalize reports + regenerate manifest atomically

## Kết luận runtime

Trạng thái cuối đã kiểm chứng:

- model-ready Parquet readable: Yes
- manifest hợp lệ: Yes
- verifier pass: Yes
- status cuối: `ready_for_downstream_training`

Điểm cần lưu ý:

- local Windows run vẫn không phải đường chuẩn để sinh Parquet cuối cùng
- Linux Docker path là path chuẩn cho preprocessing đầy đủ
- `processed_contract` hiện đóng vai trò fallback an toàn khi artifact đã ghi xong nhưng manifest/report surface chưa hoàn tất
