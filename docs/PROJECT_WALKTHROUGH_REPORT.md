# Fraud Detection & Risk Scoring — Project Walkthrough

**Mục đích:** giải thích project đang làm gì, dữ liệu đi qua hệ thống như thế nào,
model được huấn luyện và phục vụ ra sao, và trạng thái thực tế hiện tại.

**Đối tượng đọc:** người mới làm quen với project nhưng cần đủ chi tiết kỹ thuật
để đọc code, chạy demo và đánh giá giới hạn của hệ thống.

**Evidence snapshot:** 31 July 2026, theo working tree hiện tại và các artifact
trong `reports/official-run/`.

> Đây là hệ thống demonstration/academic end-to-end. Nó chứng minh được một
> pipeline fraud scoring có thể chạy từ dữ liệu lớn đến dashboard điều tra; nó
> chưa phải một nền tảng kiểm soát gian lận production đã được phê duyệt.

## 1. Tóm tắt một phút

Project nhận dữ liệu giao dịch e-commerce IEEE-CIS, kết hợp transaction data với
identity/device data, làm sạch và tạo một bộ 68 feature. Spark chia dữ liệu theo
thời gian để tránh nhìn thấy tương lai, sau đó các model phân loại nhị phân được
huấn luyện và so sánh.

Khi chạy serving, FastAPI gọi trực tiếp package Python `fraud_model` để biến
feature của một giao dịch thành:

1. xác suất gian lận `fraud_probability` trong `[0, 1]`;
2. điểm rủi ro nguyên `risk_score` trong `[0, 100]`;
3. nhóm rủi ro `risk_band`;
4. quyết định tự động `approve`, `review` hoặc `reject`;
5. tối đa năm đóng góp SHAP để reviewer hiểu model dựa vào feature nào.

Kết quả được lưu vào PostgreSQL hoặc SQLite, sau đó React dashboard cho phép
operator xem danh sách, lọc giao dịch, mở chi tiết, xem SHAP, nhập CSV và ghi
nhận kết quả review của con người.

```text
IEEE-CIS CSV
    │
    ▼
Spark preprocessing + validation
    │
    ├── curated data / EDA reports
    ├── chronological model-ready splits
    └── feature contract + preprocessing artifacts
            │
            ▼
Model comparison → calibration/threshold analysis → versioned Joblib artifact
            │
            ▼
fraud_model.score → FastAPI → PostgreSQL/SQLite → React investigation UI
            │                                      │
            └────────────── SHAP evidence ─────────┘
                                                   │
                                                   ▼
                                             Human review/label
```

Sơ đồ chi tiết hiện có: [overall system architecture](diagrams/final/overall-system-architecture.svg).

## 2. Project giải quyết bài toán gì?

### 2.1 Bài toán nghiệp vụ

Trong một tập giao dịch lớn, chỉ một tỷ lệ nhỏ là gian lận. Nếu kiểm tra thủ
công tất cả giao dịch thì tốn nguồn lực; nếu chỉ chặn các giao dịch có điểm rất
cao thì có thể bỏ sót fraud.

Project dùng machine learning để **xếp hạng rủi ro và ưu tiên điều tra**. Ý
nghĩa chính của hệ thống là giúp reviewer trả lời:

- Giao dịch nào đáng chú ý hơn?
- Model ước lượng xác suất gian lận bao nhiêu?
- Những đặc điểm nào làm điểm tăng hoặc giảm?
- Reviewer đã quyết định thế nào và nhãn thực tế sau review là gì?

### 2.2 Project không làm gì

Hệ thống hiện không phải:

- payment gateway hoặc hệ thống settlement;
- hệ thống tự động khóa tài khoản hay hoàn tiền;
- hệ thống quản lý case pháp lý/regulatory;
- hệ thống online learning tự cập nhật model;
- bằng chứng rằng model có hiệu quả production trên dữ liệu live;
- cơ chế phê duyệt tài chính hoặc quyết định tín dụng.

Vì vậy, `approve/review/reject` trong project là decision policy của demo risk
engine, không nên diễn giải thành quyết định nghiệp vụ production.

## 3. Bản đồ repository

| Khu vực | Vai trò | Công nghệ/chủ đề chính |
|---|---|---|
| `pipeline/` | Entry point và contract utilities cho preprocessing | Python, PySpark |
| `data/ieee_cis/pipeline/` | Spark implementation lớn: ingest, join, feature engineering, split, export | PySpark |
| `model/` | Train, compare, calibrate, evaluate, package và score model | pandas, scikit-learn, LightGBM, XGBoost, CatBoost, SHAP, MLflow |
| `backend/` | API scoring, database, import, dataset loading, review workflow | FastAPI, SQLAlchemy, PostgreSQL/SQLite |
| `frontend/` | Dashboard cho operator/reviewer | React, TypeScript, Vite, TanStack Query |
| `config/` | Cấu hình pipeline và các policy mặc định | YAML |
| `docker/`, `docker-compose*.yml` | Chạy preprocessing, training và demo stack | Docker Compose |
| `docs/` | Contract, architecture, API, hướng dẫn và report | Markdown, SVG, PNG, PDF |
| `reports/` | Evidence từ các lần validate/train/official run | JSON, CSV, Markdown |
| `screenshots/` | Ảnh minh họa UI demo | PNG |

### 3.1 Các entrypoint quan trọng

| Việc cần làm | File/lệnh |
|---|---|
| Preprocess raw data | `scripts/run_preprocessing.sh` |
| Train version tùy chọn | `scripts/train_model.sh [local\|cluster] [version]` |
| Official end-to-end workflow | `scripts/run_official_full.sh` |
| Validate processed contract | `model/src/fraud_model/validate_data.py` hoặc verifier trong pipeline |
| Train baseline | `python -m fraud_model.train_baseline` |
| Compare model families | `python -m fraud_model.train_compare` |
| Tune/explain | `python -m fraud_model.tune_and_explain` |
| Calibrate/chọn threshold | `python -m fraud_model.threshold_analysis` |
| Holdout evaluation | `python -m fraud_model.evaluate_holdout` |
| Package artifact | `python -m fraud_model.package_candidate` |
| Promotion gate | `python -m fraud_model.promotion_gate` |
| API service | `fraud-backend` hoặc `uvicorn fraud_backend.main:app` |
| Frontend | `npm run dev` hoặc Docker Compose |

## 4. Dữ liệu đầu vào

Pipeline được xây dựng quanh bộ IEEE-CIS Fraud Detection. Các input chính là:

| File | Vai trò | Evidence hiện có |
|---|---|---:|
| `train_transaction.csv` | Transaction facts có nhãn `isFraud` | 590,540 rows; 394 columns |
| `train_identity.csv` | Identity/device attributes cho một phần transaction | 144,233 rows; 41 columns |
| `test_transaction.csv` | Transaction không có nhãn, dùng cho test/demo | 506,691 rows; 393 columns |
| `test_identity.csv` | Identity/device của test transactions | 141,907 rows; 41 columns |
| `sample_submission.csv` | Template competition, không phải input chính của serving | Có trong source inventory |

Tổng dung lượng bốn CSV chính xấp xỉ 1.29 GB. Dữ liệu raw được mount lúc chạy,
không được đưa vào Docker image hoặc Git. Manifest official lưu checksum, row
count, column count và môi trường đã tạo artifact.

## 5. Data pipeline hoạt động như thế nào?

### 5.1 Đọc và kiểm tra schema

Spark đọc transaction và identity với schema có kiểu dữ liệu được định nghĩa.
Trước khi biến đổi, pipeline kiểm tra file tồn tại, kích thước, schema, key và
các điều kiện cơ bản của dữ liệu.

### 5.2 Join transaction với identity

Transaction là phía giữ toàn bộ dòng. Identity được left join theo
`TransactionID`.

Điều này quan trọng vì identity chỉ có cho một phần giao dịch:

- train: 144,233 identity rows trên 590,540 transactions;
- test: 141,907 identity rows trên 506,691 transactions.

Các giao dịch không có identity không bị loại bỏ. Thay vào đó, pipeline tạo các
feature presence/missingness để model biết thông tin đó có tồn tại hay không.

### 5.3 Làm sạch và tạo feature

Các nhóm feature chính:

| Nhóm | Ví dụ | Ý nghĩa |
|---|---|---|
| Transaction amount | `TransactionAmt`, log amount, capped amount, decimal, amount band | Bắt mức tiền, đuôi phân phối và các giao dịch bất thường |
| Time | `TransactionDT`, day/week/hour, age, night flag | Bắt pattern theo thời điểm |
| Missingness/presence | `has_identity`, `has_device_info`, missing ratios, `has_distance` | Dùng việc thiếu dữ liệu như tín hiệu |
| Amount anomaly | high amount, amount outlier, deviation from card mean | So sánh giao dịch hiện tại với lịch sử/entity |
| Anonymized C/D | `C1`–`C14`, `D1`–`D5`, `D10`, `D15`, distances | Giữ các tín hiệu hành vi được anonymize trong bộ dữ liệu |
| Historical aggregates | prior card/email/device counts, sums, means, stddev, time since previous | Mô tả hành vi trước đó của entity |
| Categorical | `ProductCD`, `card4`, `card6`, `DeviceType`, `device_family`, `M4`, `amount_band` | Mã hóa các nhóm danh mục |

Feature contract canonical hiện có 68 cột. Thứ tự feature được lưu tại
`data/processed/ieee_cis_fraud_risk/artifacts/preprocessing/feature_order.json`.

### 5.4 Missing value và category policy

- Numeric median được tính và lưu thành artifact preprocessing.
- Category mapping được fit trên training.
- Category mới/unseen khi serving nhận một mã unknown riêng.
- Giá trị thiếu ở bước pandas serving được chuyển thành sentinel `-999`.
- Model không nhận các metadata như `TransactionID`, `isFraud`, `class_weight`,
  `split_name`, `processing_version`, `feature_schema_version` hoặc `generated_at`.

Mục tiêu của contract là cùng một quy tắc được dùng ở training và request-time
serving; nếu không, model có thể nhận vector feature khác với vector lúc train.

### 5.5 Chronological split

Project không random split đơn giản. Dữ liệu được chia theo `TransactionDT` để
mô phỏng việc model học từ quá khứ rồi dự đoán tương lai.

| Dataset | Rows | Fraud | Legitimate | Fraud rate |
|---|---:|---:|---:|---:|
| `train_original` | 412,956 | 14,522 | 398,434 | 3.5166% |
| `train_weighted` | 412,956 | 14,522 | 398,434 | 3.5166% |
| `train_balanced` | 58,394 | 14,522 | 43,872 | 24.8690% |
| `validation` | khoảng 88.5k | 3,036 | khoảng 85.5k | khoảng 3.43% |
| `holdout` | khoảng 89.1k | 3,105 | khoảng 86.0k | khoảng 3.48% |
| `kaggle_test` | 506,691 | — | — | — |

Training kết thúc ở `TransactionDT=10,432,902`; validation và holdout là các
window thời gian tiếp theo. Official verifier kiểm tra split không overlap,
chronological order, required columns, uniqueness và row counts.

### 5.6 Xử lý class imbalance

Fraud chỉ chiếm khoảng 3.5% trong train tự nhiên. Project có hai cách:

- `train_weighted`: giữ toàn bộ rows và dùng class weight;
- `train_balanced`: giữ toàn bộ fraud, lấy một phần legitimate theo tỷ lệ khoảng
  3:1.

Validation và holdout giữ prevalence tự nhiên. Đây là điểm cần thiết khi đọc
probability và precision/recall; metric trên tập balanced không thể xem như
metric production tự nhiên.

### 5.7 Output của preprocessing

Pipeline xuất nhiều lớp dữ liệu:

```text
data/processed/ieee_cis_fraud_risk/
├── curated/       dữ liệu sau cleaning/join
├── splits/         các split theo thời gian
├── model_ready/   dữ liệu có contract để train
├── feature_store/ feature/history outputs
├── artifacts/     feature order, medians, mappings, schema, thresholds
├── reports/       EDA, summary, verification
└── demo/          dữ liệu phục vụ dashboard demo
```

Processed-data boundary là một trong những phần chắc nhất của project: official
verification report hiện ghi `94 checks passed` và `0 checks failed`, trạng thái
`ready_for_downstream_training`.

Sơ đồ leakage-controlled hiện có: [leakage-controlled transformation flow](diagrams/final/leakage-controlled-transformation-flow.png).

## 6. Model training hoạt động như thế nào?

### 6.1 Training boundary

Spark xử lý và giữ contract; đến bước train model, `model/src/fraud_model/features.py`
chuyển model-ready DataFrame sang pandas. Đây là điểm chuyển giao duy nhất sang
scikit-learn/LightGBM/XGBoost/CatBoost.

Điều này phù hợp với artifact hiện tại vì training dataset khoảng vài trăm nghìn
rows, nhưng không nên tự động suy ra rằng mọi dataset lớn hơn đều có thể collect
toàn bộ lên driver.

### 6.2 Các stage chính

Official workflow chạy theo thứ tự:

1. `validate_data`: kiểm tra contract trước khi train.
2. `train_baseline`: tạo baseline Logistic Regression.
3. `train_compare`: so sánh các model family và training variants.
4. `tune_and_explain`: chọn/tune candidate và chuẩn bị explainability.
5. `threshold_analysis`: calibration và chọn operating thresholds trên validation.
6. `evaluate_holdout`: đánh giá một lần trên holdout sau khi policy đã frozen.
7. `package_candidate`: đóng gói model, metadata, manifest và checksum.
8. `promotion_gate`: kiểm tra candidate có đạt các gate hay không.

MLflow được dùng để track local training stages. Hiện có evidence run history
local, nhưng chưa có model registry hoặc promotion alias durable.

### 6.3 Model được so sánh

Các family chính là Logistic Regression, LightGBM, XGBoost và CatBoost. Mỗi
family có thể được đánh giá trên weighted hoặc balanced training data. Metric
được quan tâm nhiều là PR-AUC vì fraud là bài toán mất cân bằng; ROC-AUC vẫn
được lưu để đo khả năng xếp hạng tổng quát.

## 7. Kết quả model: đọc artifact hiện tại cho đúng

### 7.1 Artifact official hiện tại

Các file nguồn chính:

- `reports/official-run/training_metadata_v2.json`;
- `reports/official-run/holdout_metrics_v2.csv`;
- `reports/official-run/promotion_decision_v2.json`;
- `model/artifacts/v2/final_model_v2.joblib`.

Official metadata hiện ghi candidate model là **CatBoost**, train trên `balanced`
dataset với 68 feature.

| Metric trên holdout | Giá trị |
|---|---:|
| ROC-AUC | 0.8781 |
| PR-AUC | 0.4266 |
| Precision tại threshold 0.16 | 0.3820 |
| Recall tại threshold 0.16 | 0.5182 |
| F1 | 0.4398 |
| True negatives | 83,390 |
| False positives | 2,603 |
| False negatives | 1,496 |
| True positives | 1,609 |
| Raw Brier score | 0.0495 |
| Calibrated Brier score | 0.0248 |

Calibration được ghi nhận là isotonic. Threshold analysis hiện đề xuất:

- review threshold: `0.16`;
- reject threshold: `0.53`;
- minimum review precision: `0.30`;
- minimum reject precision: `0.60`.

### 7.2 Candidate chưa được promote

`promotion_decision_v2.json` ghi:

```text
status: not_promoted
automatic_promotion: false
serving_version_unchanged: true
failed_gates: holdout_pr_auc, git_clean
```

Candidate đạt một số gate như ROC-AUC, review precision, calibration,
checksum, artifact load smoke và data contract. Tuy nhiên, nó không đạt holdout
PR-AUC so với reference `0.4582`, và official run được ghi nhận là dirty.

Vì vậy cần phân biệt ba khái niệm:

| Khái niệm | Trạng thái |
|---|---|
| Code default serving version | `v2` |
| Artifact candidate hiện có | CatBoost v2, đã package nhưng `not_promoted` |
| Business-approved production promotion | Chưa có bằng chứng |

### 7.3 Vì sao tài liệu cũ có số khác?

Một số report trước đó mô tả V2 theo một lần chạy/contract cũ, trong đó LightGBM
được gọi là offline champion và holdout PR-AUC là `0.4582`. Artifact official mới
hơn hiện có CatBoost candidate và holdout PR-AUC `0.4266`.

Không nên trộn các số này thành một bảng duy nhất. Cách đọc an toàn là:

- `0.4582` là reference cũ được promotion gate dùng để so sánh;
- `0.4266` là holdout metric của candidate official hiện tại;
- V2 vẫn là code default, nhưng điều đó không đồng nghĩa candidate hiện tại đã
  được business/production promotion.

## 8. Từ model probability đến risk decision

### 8.1 Scoring package

`model/src/fraud_model/score.py` làm các bước:

1. tìm final artifact của `FRAUD_MODEL_SERVING_VERSION`;
2. nếu không có final artifact, thử baseline cùng version;
3. encode categorical bằng mapping đã fit trên training;
4. tạo DataFrame đúng thứ tự 68 feature;
5. điền missing bằng `-999`;
6. gọi `predict_proba`;
7. áp dụng calibrator nếu artifact có;
8. tạo TreeSHAP nếu model là tree model;
9. trả probability, SHAP top 5, scoring mode và threshold metadata.

Scoring không cần khởi động Spark. Đây là chủ ý kiến trúc: Spark phục vụ batch
preprocessing/training; request-time inference dùng pandas và artifact đã đóng gói.

### 8.2 Backend risk policy hiện đang dùng

Backend chuyển probability thành score bằng `round(probability * 100)` và clamp
về `[0, 100]`.

| Risk score | Band | Automatic decision |
|---:|---|---|
| 0–19 | `low` | `approve` |
| 20–39 | `guarded` | `approve` |
| 40–59 | `medium` | `review` |
| 60–79 | `high` | `review` |
| 80–100 | `critical` | `reject` |

Policy này được định nghĩa tại `backend/src/fraud_backend/risk.py` và backend là
nơi duy nhất tính band; frontend chỉ hiển thị.

### 8.3 Điểm cần chú ý về threshold

Artifact calibration có review/reject threshold `0.16/0.53`, nhưng backend hiện
ra decision theo các band score `40/80`, tương đương khoảng probability `0.40/0.80`.
Threshold artifact chưa được nối trực tiếp vào decision policy runtime.

Do đó không được nói rằng dashboard đang thực thi đúng threshold calibration
`0.16/0.53`. Hiện tại artifact và backend risk policy là hai lớp khác nhau. Đây
là một trong những việc cần xử lý trước khi gọi policy là production-governed.

## 9. Backend API và database

### 9.1 Runtime

FastAPI khởi động theo lifespan:

- tạo database tables bằng `Base.metadata.create_all`;
- load model và SHAP explainer trước request đầu tiên;
- mở các API route.

Database mặc định trong Docker là PostgreSQL 16. Khi chạy local không có Docker,
SQLite là đường fallback.

### 9.2 API groups

| Route | Mục đích |
|---|---|
| `GET /health` | Health check đơn giản |
| `GET /meta` | Model version, feature contract, bands, SHAP availability, warning |
| `POST /score` | Chấm một payload ad-hoc, không ghi DB |
| `GET /transactions` | Danh sách, filter, search, pagination, sort |
| `GET /transactions/stats` | Số lượng, average score, high-risk amount, review counts |
| `GET /transactions/{id}` | Chi tiết một giao dịch và SHAP |
| `POST /transactions/{id}/review` | Ghi/rewrite human review |
| `GET /transactions/import/template` | Tạo CSV template |
| `POST /transactions/import` | Import và score batch CSV vào DB |
| `GET /datasets` | Liệt kê processed datasets |
| `POST /data/load` | Bắt đầu nạp dataset trong background |
| `GET /jobs/{job_id}` | Theo dõi tiến độ nạp |
| `POST /jobs/{job_id}/cancel` | Hủy job nạp |

### 9.3 Data model

`Transaction` lưu:

- IEEE-CIS `TransactionID` làm primary key;
- amount;
- probability, score, band, automatic decision;
- timestamp và model version;
- raw feature JSON;
- SHAP top 5.

`Review` là bảng riêng, liên kết một-một với transaction, lưu:

- human status `approved/rejected`;
- label `fraud/legit` nếu có;
- reviewer;
- note;
- updated time.

Thiết kế tách automatic decision khỏi human review để biết hệ thống đã đề xuất
gì và con người đã quyết định gì.

### 9.4 Loading/import

Có hai cách đưa dữ liệu vào dashboard:

- dataset loader đọc processed Parquet và score các rows được chọn;
- CSV import đọc từng dòng, kiểm tra cột, tách `TransactionID`, score và upsert
  vào DB.

Background job hiện được lưu trong memory và chỉ hỗ trợ một loader active. Đây là
đủ cho demo local, chưa phải queue bền vững cho production.

## 10. Frontend và user journey

React app hiện có năm luồng chính:

1. **Giao dịch** — xem danh sách, filter theo band/decision/review status,
   sort theo risk score.
2. **Chi tiết giao dịch** — xem amount, score, model version, SHAP top 5 và
   review state.
3. **Hàng chờ** — ưu tiên các giao dịch cần reviewer xử lý.
4. **Chấm điểm thử** — gửi feature payload tới `POST /score`; kết quả ad-hoc
   không lưu DB.
5. **Nạp dữ liệu** — chọn dataset hoặc upload CSV, theo dõi tiến độ load.

Frontend dùng TanStack Query để gọi API, React Router cho navigation và có hỗ trợ
responsive drawer, theme switch, keyboard/skip link và static UI checks.

Sơ đồ ảnh UI hiện có trong `screenshots/demo/`, gồm transactions, score result,
detail, review, import và API docs.

Chat assistant trong `ChatDock` là hỗ trợ rule-based cho dashboard; không nên
nhầm nó với một autonomous fraud investigation agent.

## 11. Deployment bằng Docker

### 11.1 Demo application stack

`docker-compose.yml` có các service chính:

```text
PostgreSQL ──► FastAPI backend ──► React frontend
                    │
                    └── read-only mount: data/processed
```

Processed Parquet không nằm trong backend image. Backend cần volume mount
`./data/processed:/app/data/processed:ro`; nếu thiếu mount này, màn “Nạp dữ
liệu” không thấy model-ready datasets.

### 11.2 Training topology

Training có thể chạy:

- `model-training-local` với Spark `local[*]`;
- Spark standalone master/worker trong profile `training`.

Training image mount model artifacts và processed data. Serving demo không cần
Spark cluster.

### 11.3 Environment quan trọng

| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `FRAUD_MODEL_SERVING_VERSION` | Artifact version được serve | `v2` |
| `FRAUD_MODEL_TRAINING_VERSION` | Thư mục version khi train | `v2` trong official run |
| `FRAUD_MODEL_DATA_ROOT` | Root processed data | repo `data/processed/...` |
| `DATABASE_URL` | PostgreSQL/SQLite URL | phụ thuộc môi trường |
| `DATA_PROCESSED_DIR` | Host path mount processed data | `./data/processed` |
| `CORS_ORIGINS` | Origin được phép gọi backend | localhost frontend |

## 12. Testing và verification

### 12.1 Data

Official processed verification hiện kiểm tra:

- manifest version và schema version;
- dataset tồn tại, không rỗng;
- required columns và labels;
- row count và unique `TransactionID`;
- split không overlap;
- chronological order;
- feature order/schema hash;
- imbalance policy;
- artifact presence.

Kết quả official snapshot: **94 passed, 0 failed**.

### 12.2 Model

`model/tests/` cover feature handling, scoring, model quality, temporal
validation, evaluation policy và MLflow tracking. GitHub Actions hiện cài Java,
uv, dependencies, chạy Ruff và pytest cho model subsystem.

### 12.3 Backend

Backend hiện có 23 test được collect trong `backend/tests/`, gồm:

- health/meta;
- list/search/stats;
- detail 404;
- review create/update;
- score không ghi DB;
- CSV import;
- risk band boundary và clamp.

### 12.4 Frontend

Frontend có TypeScript build, lint và static UI checker. Chưa có browser/component
test coverage tương đương backend. Đây là khoảng trống nếu muốn chứng minh toàn
bộ user journey hoạt động ổn định sau mỗi thay đổi.

### 12.5 Cách hiểu về evidence

| Loại evidence | Có nghĩa là |
|---|---|
| Source code tồn tại | Capability được implement hoặc dự kiến |
| JSON/CSV artifact tồn tại | Một lần chạy đã ghi kết quả |
| Saved verification report | Một lần verification cụ thể đã pass |
| Unit/API test pass | Code path được test trong test environment |
| Docker smoke test | Một topology cụ thể đã khởi động và phản hồi |
| Production readiness | Cần thêm security, operations, monitoring, governance và business approval |

Không nên nâng một loại evidence thành loại mạnh hơn.

## 13. Điểm mạnh của project

1. **Data handoff rõ ràng:** feature order, medians, category policy, schema và
   split artifacts giúp model biết mình nhận dữ liệu gì.
2. **Có leakage control:** chronological split và train-only fitting được thể
   hiện trong pipeline/model code.
3. **Có đường đi end-to-end:** raw data → preprocessing → model → API → DB → UI.
4. **Có explainability:** tree model có TreeSHAP top features trong API/UI.
5. **Có human-in-the-loop:** automatic decision được lưu riêng với review result.
6. **Có version/checksum:** artifact package có metadata, manifest và SHA-256.
7. **Có contract verification:** processed data không chỉ được tạo ra mà còn
   được kiểm tra trước training.

## 14. Giới hạn và rủi ro hiện tại

### 14.1 Model governance

- Chưa có registry production, promotion alias hoặc rollback record bền vững.
- MLflow evidence chủ yếu local/ignored.
- Model candidate official hiện `not_promoted`.
- V1 và V2 dùng feature contract khác nhau nên việc so sánh không chỉ phản ánh
  hyperparameter.
- Một số metric trong tài liệu cũ không còn khớp artifact official hiện tại.

### 14.2 Decision policy

- Threshold calibration artifact chưa điều khiển trực tiếp backend band policy.
- `approve/review/reject` chưa được gắn với cost của false positive/false negative
  hoặc capacity của reviewer.
- Không có evidence rằng band policy đã được business phê duyệt.

### 14.3 Runtime safety

- Nếu model/dependency không load được, demo có thể dùng fallback scorer.
- Fallback giúp demo tiếp tục chạy nhưng có thể làm người dùng tưởng đây là model
  thật; production nên fail-closed hoặc bắt buộc bật demo mode.
- `health` hiện khá đơn giản và chưa thể hiện đầy đủ readiness/model state.

### 14.4 Operations và security

- Chưa có authentication/authorization.
- Chưa có rate limiting, audit event history hoặc secret management hoàn chỉnh.
- Database schema tạo trực tiếp, chưa dùng migration lifecycle đầy đủ.
- Background jobs in-memory, không durable.
- Chưa có SLO, drift monitoring, data freshness monitoring hoặc alerting.
- CORS/password trong Docker Compose phù hợp local demo, không phù hợp public deployment.

## 15. Roadmap ưu tiên

### P0 — làm rõ source-of-truth và ngăn quyết định sai

1. Chọn và ghi rõ artifact/version thật sự được serve.
2. Đồng bộ README, system documentation, model reports và official artifacts.
3. Quyết định dứt khoát threshold runtime: dùng calibrated threshold artifact hay
   giữ band policy độc lập; sau đó nối code, `/meta`, UI và tests cùng một policy.
4. Tắt silent heuristic fallback trong deployment không phải demo.

### P1 — reproducibility và promotion

1. Chạy artifact load smoke trong frozen container có đầy đủ LightGBM/CatBoost/
   XGBoost/SHAP dependencies.
2. Lưu run ID, artifact URI, checksum và approval/rollback record ở nơi durable.
3. Có controlled promotion workflow và test rollback sang version trước.
4. Đo operating-point metrics theo review capacity và business costs.

### P2 — production operations

1. Authentication, authorization, secret management, audit log và rate limiting.
2. Alembic/database migrations.
3. Durable queue cho load/import/re-score jobs.
4. Model/data drift, calibration monitoring và SLO dashboards.
5. Frontend browser tests và API contract integration tests.

## 16. Cách đọc project theo thứ tự khuyến nghị

Nếu mới vào project, nên đọc theo thứ tự này:

1. File này để nắm toàn cảnh.
2. `README.md` để biết quick start và demo surface.
3. `docs/SYSTEM_DOCUMENTATION.md` để xem as-built details.
4. `docs/contracts/DATA_DICTIONARY.md` và `docs/contracts/MODEL_READY_DATA_CONTRACT.md`
   để hiểu data boundary.
5. `data/ieee_cis/pipeline/ieee_cis_preprocess.py` để xem processing thật.
6. `model/src/fraud_model/features.py`, `score.py`, `config.py` để hiểu model
   contract và serving.
7. `backend/src/fraud_backend/main.py`, `risk.py`, `service.py`, `models.py` để
   hiểu API/DB/risk policy.
8. `frontend/src/App.tsx` và các page trong `frontend/src/pages/` để hiểu UI.
9. `reports/official-run/` để kiểm tra artifact và metric của lần chạy hiện tại.

## 17. Kết luận

Đây là một hệ thống fraud risk scoring có đầy đủ các lớp chính của một sản phẩm
ML demo: dữ liệu lớn, preprocessing phân tán, feature contract, train/evaluate,
versioned model, scoring API, persistence, SHAP, dashboard và human review.

Phần đã trưởng thành nhất là data contract và processed-data verification. Phần
cần thận trọng nhất là ranh giới giữa **model artifact đã tạo**, **model đang là
default trong code**, **candidate đã qua offline evaluation** và **model được
production-approved**. Bốn khái niệm này hiện không hoàn toàn giống nhau.

Tóm lại: project đang chứng minh cách xây dựng một hệ thống ưu tiên điều tra fraud
end-to-end; nó chưa chứng minh rằng mọi decision policy, model promotion và control
security đã đủ an toàn để triển khai production.

## Phụ lục: source inventory

Các nguồn chính được dùng để viết report này:

- [README](../README.md)
- [As-built system documentation](SYSTEM_DOCUMENTATION.md)
- [Project review report](PROJECT_REVIEW_REPORT.md)
- [Model training review](../reports/MODEL_TRAINING_REVIEW_REPORT.md)
- [Official training metadata](../reports/official-run/training_metadata_v2.json)
- [Official holdout metrics](../reports/official-run/holdout_metrics_v2.csv)
- [Official promotion decision](../reports/official-run/promotion_decision_v2.json)
- [Official verification report](../reports/official-run/verification_report.json)
- [Pipeline config](../config/pipeline_config.yaml)
- [Model package](../model/src/fraud_model/)
- [Backend package](../backend/src/fraud_backend/)
- [Frontend source](../frontend/src/)
- [Docker Compose](../docker-compose.yml)

## Phụ lục A — Luồng dữ liệu chi tiết theo từng bước

Phần này mô tả một transaction từ lúc xuất hiện trong CSV cho tới lúc reviewer
nhìn thấy nó trên dashboard.

### A.1 Batch path: raw CSV đến model-ready Parquet

```text
1. Raw discovery
   Kiểm tra train/test transaction và identity tồn tại, checksum, schema, size.
        │
2. Typed ingestion
   Spark đọc CSV với kiểu dữ liệu phù hợp thay vì để mọi cột thành string.
        │
3. Key/join audit
   Kiểm tra TransactionID, duplicate key và row-preserving left join.
        │
4. Curated layer
   Kết hợp transaction + identity, chuẩn hóa null/category và ghi curated data.
        │
5. Feature engineering
   Tạo amount/time/missingness/history/categorical features.
        │
6. Chronological split
   Tạo train, validation, holdout và test theo TransactionDT.
        │
7. Train-only fitting
   Fit median, category policy, entity lookup và outlier thresholds trên train.
        │
8. Frozen transformation
   Áp dụng cùng policy đã fit cho validation, holdout và test.
        │
9. Contract export
   Ghi Parquet, schema, feature order, medians, policies, manifests và reports.
        │
10. Verification
    Chỉ bàn giao cho model khi contract verifier pass.
```

Điểm cần nhớ là bước 7 xảy ra sau khi split. Nếu median, category mapping hoặc
historical aggregate được tính bằng cả validation/holdout, thông tin tương lai
có thể lọt vào training và metric sẽ đẹp giả tạo.

### A.2 Training path: model-ready đến artifact

```text
model_ready/train_weighted hoặc train_balanced
        │
        ▼
Load Spark DataFrame
        │
        ▼
Select đúng 68 canonical features
        │
        ▼
Convert sang pandas ở training boundary
        │
        ├── Logistic Regression baseline
        ├── LightGBM
        ├── XGBoost
        └── CatBoost
                │
                ▼
        Chọn model trên validation selection window
                │
                ▼
        Fit isotonic calibration trên calibration window
                │
                ▼
        Chọn review/reject policy trên policy window
                │
                ▼
        Đánh giá một lần trên holdout
                │
                ▼
        Joblib + metadata + metrics + checksum + promotion decision
```

### A.3 Request path: API đến response

Với một request `POST /score`, các lớp chạy theo thứ tự:

1. Pydantic nhận `features: dict[str, str | float | int | None]`.
2. `service.score_features()` gọi singleton `backend.scoring.scorer`.
3. `Scorer` gọi `fraud_model.score()` nếu model load thành công.
4. `fraud_model.score()` encode category, align feature columns, fill missing,
   gọi `predict_proba` và tính SHAP nếu có thể.
5. Backend lấy probability và gọi `risk.classify()`.
6. `risk.classify()` tạo score, band và automatic decision.
7. FastAPI serialize response theo `ScoreResponse`.

`POST /score` không ghi database. Giao dịch chỉ được lưu khi đi qua dataset
loader, CSV import hoặc service upsert path.

### A.4 Persistent path: import/loader đến review

```text
CSV upload hoặc processed dataset
        │
        ▼
Kiểm tra header / chọn rows / giới hạn số dòng
        │
        ▼
Tách TransactionID khỏi feature dictionary
        │
        ▼
score_features(features)
        │
        ▼
Tạo hoặc update Transaction
        │
        ▼
Commit vào PostgreSQL/SQLite
        │
        ▼
Frontend gọi list/detail/stats
        │
        ▼
Reviewer gửi POST /transactions/{id}/review
        │
        ▼
Review record được lưu tách khỏi automatic decision
```

## Phụ lục B — API contract bằng ví dụ

### B.1 Kiểm tra service

Request:

```bash
curl http://localhost:8000/health
```

Response tối thiểu:

```json
{"status":"ok"}
```

`/health` chỉ cho biết HTTP app trả lời. Muốn biết model nào đang được dùng,
phải đọc thêm `/meta`.

### B.2 Đọc model metadata

```bash
curl http://localhost:8000/meta
```

Response có các nhóm thông tin:

```json
{
  "model_version": "v2",
  "model_name": "catboost",
  "processing_version": "ieee-cis-preprocess-2.1.0",
  "feature_schema_version": "ieee-cis-features-1.1.0",
  "explainability": true,
  "n_features": 68,
  "required_features": [],
  "optional_features": [],
  "defaultable_features": [],
  "bands": [
    {"band":"low","min":0,"max":19},
    {"band":"guarded","min":20,"max":39},
    {"band":"medium","min":40,"max":59},
    {"band":"high","min":60,"max":79},
    {"band":"critical","min":80,"max":100}
  ],
  "warning": null
}
```

Các list feature trong response có thể thay đổi theo artifact. Không nên hardcode
`53` hoặc `68` ở frontend; UI nên lấy `n_features` và feature contract từ `/meta`.

### B.3 Ad-hoc scoring

Request rút gọn:

```bash
curl -X POST http://localhost:8000/score \
  -H 'Content-Type: application/json' \
  -d '{
    "features": {
      "TransactionAmt": 250.0,
      "ProductCD": "W",
      "card4": "visa",
      "card6": "debit",
      "DeviceType": "mobile"
    }
  }'
```

Response conceptually:

```json
{
  "fraud_probability": 0.18,
  "risk_score": 18,
  "risk_band": "low",
  "decision": "approve",
  "scoring_mode": "partial_demo",
  "shap_top5": [
    {"feature":"TransactionAmt","shap_value":0.42}
  ],
  "model_version":"v2",
  "processing_version":"ieee-cis-preprocess-2.1.0",
  "feature_schema_version":"ieee-cis-features-1.1.0",
  "scored_at":"2026-08-01T00:00:00Z"
}
```

Đây là ví dụ shape, không phải output cố định. Giá trị probability và SHAP phụ
thuộc artifact/model. Vì request chỉ có vài cột nên `scoring_mode` là
`partial_demo`; các feature còn thiếu dùng default/sentinel của scoring path.
Không nên dùng điểm partial demo để đánh giá model như một prediction đầy đủ.

### B.4 Transaction list/detail

`GET /transactions` trả pagination:

```json
{
  "items": [
    {
      "transaction_id": 2987000,
      "amount": 68.5,
      "fraud_probability": 0.74,
      "risk_score": 74,
      "risk_band": "high",
      "decision": "review",
      "scored_at": "2026-08-01T00:00:00Z",
      "model_version": "v2",
      "review_status": "pending"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

`GET /transactions/{id}` mở rộng thêm raw feature dictionary, SHAP top 5 và
review record. Raw features được lưu để UI hiển thị và để có khả năng re-score
sau này; hiện chưa có quy trình re-score hoàn chỉnh.

### B.5 Review request

```bash
curl -X POST http://localhost:8000/transactions/2987000/review \
  -H 'Content-Type: application/json' \
  -d '{
    "action": "reject",
    "label": "fraud",
    "reviewer": "analyst-01",
    "note": "Identity/device pattern is inconsistent with prior activity."
  }'
```

`action` là trạng thái xử lý của reviewer; `label` là nhận định fraud/legit.
Hai trường này không thay thế `Transaction.decision`, vốn là decision tự động
tại thời điểm score.

### B.6 Dataset loading request

```bash
curl -X POST http://localhost:8000/data/load \
  -H 'Content-Type: application/json' \
  -d '{
    "dataset": "holdout",
    "limit": 5000,
    "reset": true,
    "mode": "coverage",
    "per_band": 20,
    "seed": 42
  }'
```

Các mode có ý nghĩa khác nhau:

| Mode | Hành vi | Khi dùng |
|---|---|---|
| `head` | Lấy N dòng đầu | Smoke test nhanh |
| `sample` | Lấy mẫu ngẫu nhiên có seed | Demo đại diện hơn |
| `coverage` | Cố gắng lấy đủ các band | Demo UI đủ low đến critical |

`limit` bị giới hạn ở 100,000 để tránh một cú click nạp toàn bộ dữ liệu vào demo
database.

## Phụ lục C — File/function map cho người đọc code

### C.1 Preprocessing

| File | Cần đọc để hiểu |
|---|---|
| `pipeline/fraud_risk_data_pipeline.py` | Root entrypoint/điểm gọi pipeline |
| `pipeline/processed_contract.py` | Các quy tắc contract ở boundary |
| `pipeline/temporal_features.py` | Logic feature phụ thuộc thời gian |
| `pipeline/verify_processed_data.py` | Cách kiểm tra processed output |
| `data/ieee_cis/pipeline/ieee_cis_preprocess.py` | Spark flow lớn: schema, join, feature, split, export |
| `data/ieee_cis/pipeline/verify_processed.py` | Verification implementation cho output |
| `config/pipeline_config.yaml` | Split ratio, Spark config, imbalance và report limits |

### C.2 Model

| File | Cần đọc để hiểu |
|---|---|
| `model/src/fraud_model/config.py` | Artifact paths, serving/training version, feature constants |
| `model/src/fraud_model/data.py` | Load train/validation/holdout và validation windows |
| `model/src/fraud_model/features.py` | Canonical feature selection, category mapping, pandas boundary |
| `model/src/fraud_model/train_baseline.py` | Baseline training |
| `model/src/fraud_model/train_compare.py` | Model family comparison |
| `model/src/fraud_model/tune_and_explain.py` | Tuning, candidate selection, SHAP preparation |
| `model/src/fraud_model/threshold_analysis.py` | Calibration và threshold selection |
| `model/src/fraud_model/evaluate_holdout.py` | Final holdout evaluation |
| `model/src/fraud_model/package_candidate.py` | Manifest/checksum/artifact packaging |
| `model/src/fraud_model/promotion_gate.py` | Gate decision và failed gates |
| `model/src/fraud_model/score.py` | Serving inference và TreeSHAP |
| `model/src/fraud_model/tracking.py` | MLflow local tracking |

### C.3 Backend

| File | Cần đọc để hiểu |
|---|---|
| `backend/src/fraud_backend/main.py` | FastAPI app, lifespan, CORS và top-level routes |
| `backend/src/fraud_backend/scoring.py` | Model adapter và heuristic fallback |
| `backend/src/fraud_backend/service.py` | Score-to-DB business flow |
| `backend/src/fraud_backend/risk.py` | Probability → score → band → decision |
| `backend/src/fraud_backend/schemas.py` | Public request/response contract |
| `backend/src/fraud_backend/models.py` | SQLAlchemy Transaction/Review tables |
| `backend/src/fraud_backend/routers/transactions.py` | List/detail/stats/import/review endpoints |
| `backend/src/fraud_backend/routers/data.py` | Dataset/job endpoints |
| `backend/src/fraud_backend/loader.py` | Parquet loading và scoring batches |
| `backend/src/fraud_backend/jobs.py` | In-memory job state |

### C.4 Frontend

| File | Cần đọc để hiểu |
|---|---|
| `frontend/src/App.tsx` | Shell, navigation và route map |
| `frontend/src/hooks/queries.ts` | Query/mutation gọi backend |
| `frontend/src/lib/api.ts` | HTTP client và API URL |
| `frontend/src/types/api.ts` | Frontend view of API contract |
| `frontend/src/pages/TransactionsPage.tsx` | Transaction queue |
| `frontend/src/pages/TransactionDetailPage.tsx` | Detail + SHAP + review |
| `frontend/src/pages/ReviewQueuePage.tsx` | Pending review flow |
| `frontend/src/pages/ScorePage.tsx` | Ad-hoc score form |
| `frontend/src/pages/ImportPage.tsx` | CSV/dataset loading UI |
| `frontend/src/components/ShapChart.tsx` | SHAP presentation |
| `frontend/src/components/ReviewPanel.tsx` | Human decision UI |

## Phụ lục D — Định nghĩa metric model

### D.1 Confusion matrix

Ở một threshold cụ thể:

| | Thực tế legitimate | Thực tế fraud |
|---|---:|---:|
| Dự đoán legitimate | TN | FN |
| Dự đoán fraud | FP | TP |

- **TP:** bắt đúng fraud.
- **FN:** bỏ sót fraud, thường là rủi ro nghiệp vụ lớn.
- **FP:** đánh nhầm legitimate thành fraud, tạo thêm review/ảnh hưởng khách hàng.
- **TN:** xử lý đúng legitimate.

### D.2 Precision, recall, F1

```text
precision = TP / (TP + FP)
recall    = TP / (TP + FN)
F1        = 2 × precision × recall / (precision + recall)
```

Trong fraud detection, tăng recall thường làm tăng false positives. Vì vậy
không thể chọn threshold chỉ bằng một metric; cần biết reviewer chịu được bao
nhiêu case và business coi FN/FP tốn kém thế nào.

### D.3 ROC-AUC và PR-AUC

- **ROC-AUC** đo khả năng xếp hạng giữa positive và negative trên nhiều threshold.
- **PR-AUC** tập trung vào precision/recall của positive class và hữu ích hơn
  khi fraud hiếm.

PR-AUC không phải là precision tại threshold runtime. Một model có PR-AUC cao
vẫn có thể có operating point không phù hợp với review capacity.

### D.4 Brier score và calibration

Brier score đo sai số bình phương giữa probability dự đoán và nhãn thật:

```text
Brier = mean((predicted_probability - actual_label)^2)
```

Score càng thấp càng tốt. Calibration không nhất thiết làm model xếp hạng tốt
hơn; nó làm probability dễ diễn giải hơn, ví dụ nhóm giao dịch có probability
0.2 nên có fraud rate gần 20% nếu calibration tốt.

Trong artifact hiện tại, Brier score sau isotonic calibration thấp hơn raw Brier
score. Đây là evidence cho calibration window, không tự động chứng minh rằng
probability sẽ calibrated trên dữ liệu production.

### D.5 Vì sao không dùng accuracy làm metric chính?

Nếu fraud rate khoảng 3.5%, model đoán tất cả là legitimate có thể có accuracy
gần 96.5% nhưng bắt được zero fraud. Vì vậy accuracy không nói đúng trade-off
của bài toán này và không phải metric chính trong các artifact hiện tại.

## Phụ lục E — Failure modes và cách nhận biết

| Tình huống | Biểu hiện | Cách kiểm tra | Ý nghĩa |
|---|---|---|---|
| Thiếu processed Parquet | `/datasets` rỗng hoặc loader báo chưa có dữ liệu | Kiểm tra volume `data/processed` và manifest | Backend không thấy output preprocessing |
| Thiếu model dependency/artifact | `/meta` có warning, model name `unavailable-heuristic` | Đọc `/meta` và backend logs | Score không phải model thật |
| CSV thiếu feature | Import response có `missing_features` | So header với `/meta`/template | Điểm có thể là partial/defaulted |
| Model version sai | Artifact không tìm thấy hoặc load nhầm fallback | Kiểm tra `FRAUD_MODEL_SERVING_VERSION` và model paths | Serving không đúng version mong muốn |
| SHAP unavailable | `explainability=false`, `shap_top5=null` | Đọc `/meta` và transaction detail | Có score nhưng không có local explanation |
| DB chưa sẵn sàng | Container backend fail startup/connection error | `docker compose ps`, backend logs | API phụ thuộc database ở runtime |
| Job bị mất sau restart | Job ID không còn trong memory | Kiểm tra process/container lifecycle | Job store chưa durable |
| Threshold mismatch | Artifact threshold khác band decision | So threshold config với `risk.py` | Calibration chưa điều khiển runtime policy |
| Holdout metric giảm | Promotion gate fail `holdout_pr_auc` | Đọc `promotion_decision_v2.json` | Candidate chưa vượt reference |

### E.1 Dấu hiệu cần dừng demo

Không nên tiếp tục trình bày score như model thật khi:

- `/meta.warning` khác `null`;
- `model_name` là `unavailable-heuristic`;
- `model_version` không đúng version được công bố;
- processed data chưa pass verification;
- frontend hiển thị SHAP nhưng API trả `null` mà không cảnh báo;
- candidate promotion status bị đọc nhầm thành production approval.

## Phụ lục F — Quy trình chạy local có kiểm soát

### F.1 Chỉ chạy backend/frontend demo

Điều kiện: đã có processed data và model artifact phù hợp.

```bash
docker compose up --build -d
curl http://localhost:8000/health
curl http://localhost:8000/meta
```

Sau đó mở frontend tại `http://localhost:5173`.

### F.2 Preprocess từ raw data

```bash
bash scripts/run_preprocessing.sh
```

Lệnh này build/run preprocessing container và chạy verifier. Cần raw files ở
đúng input path; quá trình có thể cần nhiều RAM/disk vì dữ liệu hơn 1 GB và Spark
tạo nhiều Parquet partitions.

### F.3 Train version mới

```bash
bash scripts/train_model.sh local 0.0.4
```

Training version mới không tự động có nghĩa là serving version đổi. Cần kiểm tra
đủ metadata, holdout, checksum, promotion decision và chỉ đổi
`FRAUD_MODEL_SERVING_VERSION` sau khi policy release được xác nhận.

### F.4 Official workflow

```bash
bash scripts/run_official_full.sh
```

Script này nối preprocessing, verification, training stages, packaging, model
tests, app startup và HTTP smoke checks. Nó tạo evidence tại `reports/official-run/`.

### F.5 Kiểm tra mà không chạy full pipeline

```bash
git diff --check
(cd model && .venv/bin/pytest -q)
(cd backend && .venv/bin/pytest -q)
(cd frontend && npm run build)
```

Các lệnh trên chỉ kiểm tra một phần. Chúng không thay thế full artifact load,
Docker smoke test hoặc production validation.

## Phụ lục G — Glossary

| Thuật ngữ | Nghĩa trong project |
|---|---|
| Transaction | Một giao dịch e-commerce có `TransactionID` |
| Identity | Bảng thuộc tính identity/device nối với transaction |
| Feature | Một biến đầu vào cho model |
| Feature contract | Danh sách, thứ tự, kiểu và policy của feature |
| Model-ready | Dataset đã qua processing và đủ contract để train |
| Chronological split | Chia train/validation/holdout theo thời gian |
| Leakage | Thông tin từ tương lai hoặc label lọt vào training |
| Imbalance | Fraud class ít hơn rất nhiều so với legitimate class |
| Calibration | Điều chỉnh probability để dễ diễn giải hơn |
| Threshold | Mốc probability dùng để biến score liên tục thành decision |
| SHAP | Phương pháp giải thích đóng góp feature cho một prediction |
| Artifact | File model/metadata/metrics dùng cho reproduce hoặc serving |
| Candidate | Model package đang được đánh giá, chưa nhất thiết được serve |
| Promotion | Quyết định đưa candidate thành serving model chính thức |
| Holdout | Tập chỉ dùng đánh giá sau khi model/policy đã frozen |
| Human review | Quyết định của analyst lưu trong bảng `reviews` |
| Partial demo | Request không cung cấp đủ feature vector canonical |

