# Fraud Detection Architecture Diagrams

**Phạm vi:** Data Pipeline và Model Training  
**Trạng thái:** As-built tại ngày 31/07/2026  
**Định dạng:** UML-like diagram-as-code bằng Mermaid 11.16.0 + SVG vector  

Tài liệu này mô tả kiến trúc đã triển khai, không phải kiến trúc đề xuất.
Mỗi sơ đồ chỉ trả lời một câu hỏi ở một mức trừu tượng. GitHub là renderer
chính; phần mô tả dưới mỗi hình là text fallback cho môi trường không render
được Mermaid.

Các bản SVG chất lượng cao nằm tại [`docs/diagrams/`](diagrams/README.md).
Mermaid source trong tài liệu này là source of truth; SVG là generated export.

## 1. Bản đồ kiến trúc tổng thể

**Câu hỏi:** Dữ liệu đi từ IEEE-CIS đến candidate model và serving champion
như thế nào?

[Mở bản SVG](diagrams/01-system-overview.svg)

```mermaid
flowchart TB
    subgraph OFFLINE["Offline data and model plane"]
        RAW[/"IEEE-CIS raw CSV<br/>transaction + identity"/]
        PIPE["Spark Data Pipeline<br/>processing 2.1.0"]
        DATA[("Versioned candidate Parquet<br/>6 datasets · 68 features")]
        VERIFY{"Data contract verifier"}
        TRAIN["Model Training Workflow<br/>Spark-assisted + Python ML"]
        MLFLOW[("MLflow runs<br/>metrics + lineage")]
        BUNDLE[("Candidate bundle<br/>model 0.0.3 + checksum")]
        GATE{"Promotion gate"}
        REVIEW["Explicit human review"]
        NOT_PROMOTED["not_promoted<br/>candidate retained for analysis"]

        RAW -->|"typed ingestion"| PIPE
        PIPE -->|"staging export"| DATA
        DATA -->|"manifest + schemas"| VERIFY
        VERIFY -->|"ready_for_downstream_training"| TRAIN
        TRAIN -->|"stage evidence"| MLFLOW
        TRAIN -->|"freeze model, calibration, thresholds"| BUNDLE
        BUNDLE --> GATE
        GATE -->|"all gates pass"| REVIEW
        GATE -->|"any gate fails"| NOT_PROMOTED
    end

    subgraph ONLINE["Online serving plane"]
        V2[["Serving champion V2"]]
        API["Backend scoring API"]
        UI["Risk scoring dashboard"]

        V2 -->|"score + explanation"| API
        API -->|"risk response"| UI
    end

    REVIEW -.->|"manual promotion only"| V2
    NOT_PROMOTED -.->|"V2 remains unchanged"| V2
```

Điểm chính: offline workflow chỉ tạo candidate. Promotion gate không có quyền
tự thay model đang phục vụ. Candidate `0.0.3` hiện ở trạng thái
`not_promoted`, vì vậy V2 vẫn là champion.

Nguồn triển khai:

- `pipeline/fraud_risk_data_pipeline.py`
- `scripts/train_model.ps1`
- `model/src/fraud_model/package_candidate.py`
- `model/src/fraud_model/promotion_gate.py`

## 2. Data Pipeline chi tiết

**Câu hỏi:** Pipeline tạo model-ready data mà không học statistic từ tương lai
như thế nào?

[Mở bản SVG](diagrams/02-data-pipeline.svg)

```mermaid
flowchart TB
    CONFIG[("pipeline_config.yaml<br/>split · outlier · imbalance · Spark")]

    subgraph INGEST["A. Source validation and ingestion"]
        FILES[/"4 IEEE-CIS CSV files"/]
        SOURCE_GATE{"Required files, size,<br/>schema and key checks"}
        TYPED["Typed Spark DataFrames"]
        NORMALIZE["Normalize identity columns<br/>id-01 → id_01"]
        JOIN["Transaction LEFT JOIN identity<br/>grain = TransactionID"]

        FILES --> SOURCE_GATE --> TYPED --> NORMALIZE --> JOIN
    end

    subgraph PREP["B. Stateless preparation"]
        AUDIT["Join and data-quality audit"]
        CLEAN["Stateless cleaning<br/>type, missing flags, base features"]
        BOUNDARY["Calculate chronological boundaries<br/>70% · 15% · 15%"]

        JOIN --> AUDIT --> CLEAN --> BOUNDARY
    end

    subgraph SAFE["C. Leakage-safe feature construction"]
        TRAIN_ONLY["Training window only"]
        FIT_CAPS["Fit outlier caps"]
        PIT["Point-in-time histories<br/>card · email · device"]
        PRIOR["Window ends at row -1<br/>current and future rows excluded"]
        SPLIT["Materialize chronological<br/>train · validation · holdout"]
        FIT_MEDIAN["Fit numeric median imputer<br/>on train only"]
        APPLY["Apply frozen caps and medians<br/>to every later dataset"]

        BOUNDARY --> TRAIN_ONLY
        TRAIN_ONLY --> FIT_CAPS
        CLEAN --> PIT --> PRIOR --> SPLIT
        SPLIT --> FIT_MEDIAN
        FIT_CAPS --> APPLY
        FIT_MEDIAN --> APPLY
        SPLIT --> APPLY
    end

    subgraph EXPORT["D. Dataset variants and contract export"]
        ORIGINAL["train_original"]
        WEIGHTED["train_weighted<br/>adds class_weight"]
        BALANCED["train_balanced<br/>undersample train only"]
        VALIDATION["validation"]
        HOLDOUT["holdout"]
        TEST["kaggle_test"]
        PARQUET[("model_ready Parquet<br/>canonical 68-feature order")]
        MANIFEST["Atomic manifest finalization"]
        CONTRACT{"Strict contract verifier"}

        APPLY --> ORIGINAL
        APPLY --> WEIGHTED
        APPLY --> BALANCED
        APPLY --> VALIDATION
        APPLY --> HOLDOUT
        APPLY --> TEST
        ORIGINAL & WEIGHTED & BALANCED & VALIDATION & HOLDOUT & TEST --> PARQUET
        PARQUET --> MANIFEST --> CONTRACT
    end

    CONFIG -.->|"authoritative parameters"| SOURCE_GATE
    CONFIG -.-> BOUNDARY
    CONFIG -.-> FIT_CAPS
    CONFIG -.-> BALANCED
```

Điểm chính: split boundary được xác định trước mọi phép fit. Historical
features chạy trên stream theo thời gian nhưng mỗi hàng chỉ nhìn các sự kiện
trước nó. Imputation và outlier caps chỉ học từ training window.

Nguồn triển khai:

- `config/pipeline_config.yaml`
- `data/ieee_cis/pipeline/ieee_cis_preprocess.py`
- `pipeline/temporal_features.py`
- `pipeline/verify_processed_data.py`

## 3. Timeline dữ liệu và các cửa sổ đánh giá

**Câu hỏi:** Mỗi khoảng thời gian được dùng cho quyết định nào?

[Mở bản SVG](diagrams/03-temporal-windows.svg)

```mermaid
flowchart LR
    RAW["Labeled stream<br/>590,540 rows"]
    TRAIN["Training 70%<br/>412,956 rows<br/>fit model + learned transforms"]

    subgraph VAL["Validation 15% · 88,486 rows"]
        SELECT["Selection 50%<br/>44,243 rows<br/>compare + tune"]
        CALIBRATE["Calibration 25%<br/>22,122 rows<br/>fit isotonic calibrator"]
        POLICY["Policy 25%<br/>22,121 rows<br/>choose thresholds"]
        SELECT --> CALIBRATE --> POLICY
    end

    HOLDOUT["Holdout 15%<br/>89,098 rows<br/>one-time final evaluation"]
    KAGGLE["Kaggle test<br/>506,691 rows<br/>unlabeled scoring input"]

    RAW --> TRAIN --> SELECT
    POLICY -->|"model + calibrator + thresholds frozen"| HOLDOUT
    HOLDOUT -.->|"no refit or retuning"| KAGGLE
```

Quy tắc đọc:

1. model family và hyperparameters chỉ được chọn trên `selection`;
2. calibrator chỉ fit trên `calibration`;
3. review/reject thresholds chỉ chọn trên `policy`;
4. holdout chỉ mở sau khi ba quyết định trên đã freeze;
5. không quay lại tune sau khi xem holdout.

## 4. Data contract và handover

**Câu hỏi:** Model team nhận những gì, và không cần làm lại những gì?

[Mở bản SVG](diagrams/04-data-contract.svg)

```mermaid
flowchart TB
    ROOT[("candidate data root<br/>ieee_cis_fraud_risk_2_1_0")]

    subgraph READY["model_ready/"]
        R1["train_original"]
        R2["train_weighted"]
        R3["train_balanced"]
        R4["validation"]
        R5["holdout"]
        R6["kaggle_test"]
    end

    subgraph PREPROCESS["artifacts/preprocessing/"]
        P1["numeric_medians.json"]
        P2["outlier_thresholds.json"]
        P3["split_thresholds.json"]
    end

    subgraph SCHEMA["artifacts/schema/"]
        S1["feature_order.json"]
        S2["selected_features.json"]
        S3["model_ready_schema.json"]
    end

    subgraph EVIDENCE["reports/"]
        E1["data quality + join audit"]
        E2["split + imbalance summary"]
        E3["verification_report.json"]
    end

    MANIFEST["manifest.json<br/>versions · row counts · schema hashes"]
    VERIFY{"verify_processed_data<br/>94 checks passed"}
    MODEL["Model training contract gate"]

    ROOT --> READY
    ROOT --> PREPROCESS
    ROOT --> SCHEMA
    ROOT --> EVIDENCE
    ROOT --> MANIFEST

    READY --> VERIFY
    PREPROCESS --> VERIFY
    SCHEMA --> VERIFY
    EVIDENCE --> VERIFY
    MANIFEST --> VERIFY
    VERIFY -->|"exact versions + canonical order"| MODEL
```

Model workflow đọc trực tiếp model-ready Parquet. Nó không join lại raw CSV,
không chia lại train/validation/holdout và không fit lại preprocessing của data
pipeline.

## 5. Model Training lifecycle

**Câu hỏi:** Candidate được chọn, hiệu chỉnh, đánh giá và đóng gói như thế nào?

[Mở bản SVG](diagrams/05-model-training-lifecycle.svg)

```mermaid
flowchart TB
    DATA_GATE{"Validate six datasets<br/>68 features + exact versions"}
    INDEXER["Fit categorical mapping<br/>on weighted training population"]

    subgraph COMPARE["Selection window"]
        BASELINE["Logistic Regression baseline"]
        WEIGHTED["Compare 4 families<br/>weighted train"]
        BALANCED["Compare 4 families<br/>balanced train"]
        CHOOSE{"Best validation PR-AUC"}
        TUNE["Tune chosen family"]

        BASELINE --> CHOOSE
        WEIGHTED --> CHOOSE
        BALANCED --> CHOOSE
        CHOOSE -->|"CatBoost balanced"| TUNE
    end

    CALIBRATION["Fit isotonic calibration<br/>calibration window"]
    THRESHOLDS["Choose review/reject thresholds<br/>policy window"]
    FREEZE["Freeze model + category mapping<br/>calibrator + thresholds"]
    HOLDOUT["One-time holdout evaluation"]
    PACKAGE["Package candidate<br/>model + metadata + reports"]
    CHECKSUM["SHA-256 + artifact load smoke"]
    LINEAGE[("MLflow run IDs<br/>Git + data + Spark lineage")]
    GATE{"Promotion gate"}
    CURRENT["not_promoted<br/>V2 unchanged"]

    DATA_GATE --> INDEXER
    INDEXER --> BASELINE
    INDEXER --> WEIGHTED
    INDEXER --> BALANCED
    TUNE --> CALIBRATION --> THRESHOLDS --> FREEZE --> HOLDOUT
    HOLDOUT --> PACKAGE --> CHECKSUM --> GATE
    BASELINE & TUNE & CALIBRATION & HOLDOUT -.-> LINEAGE
    GATE -->|"PR-AUC 0.4342 < 0.4582"| CURRENT
```

Candidate `0.0.3` đạt ROC-AUC, precision, calibration, checksum, artifact-load,
data-contract, version và lineage gates. Nó không đạt holdout PR-AUC gate nên
không được promote.

Nguồn triển khai:

- `model/src/fraud_model/validate_data.py`
- `model/src/fraud_model/train_baseline.py`
- `model/src/fraud_model/train_compare.py`
- `model/src/fraud_model/tune_and_explain.py`
- `model/src/fraud_model/threshold_analysis.py`
- `model/src/fraud_model/evaluate_holdout.py`
- `model/src/fraud_model/package_candidate.py`
- `model/src/fraud_model/promotion_gate.py`

## 6. Runtime sequence của một training run

**Câu hỏi:** Các thành phần tương tác theo thứ tự nào khi chạy workflow?

[Mở bản SVG](diagrams/06-training-sequence.svg)

```mermaid
sequenceDiagram
    autonumber
    actor Owner as Model Owner
    participant Script as train_model.ps1
    participant Driver as Docker Training Driver
    participant Spark as Spark Runtime
    participant Store as Artifacts and MLflow
    participant Gate as Promotion Gate

    Owner->>Script: Mode + version + candidate data root
    Script->>Script: Resolve Git commit and dirty state
    Script->>Driver: Build pinned Python 3.11 + Java 17 image
    Driver->>Spark: Validate data contract and temporal ordering
    Spark-->>Store: data_validation_v3.json
    Driver->>Spark: Load train and selection windows
    Driver->>Driver: Baseline, comparison and tuning
    Driver-->>Store: Metrics, model comparison and MLflow runs
    Driver->>Spark: Load calibration and policy windows
    Driver->>Driver: Fit calibrator and select thresholds
    Note over Driver,Spark: Model, mapping, calibrator and thresholds are now frozen
    Driver->>Spark: Read holdout exactly once
    Driver-->>Store: Holdout metrics and final candidate bundle
    Script->>Gate: Run checksum, smoke and metric gates
    Gate-->>Store: promotion_decision_0.0.3.json
    Gate-->>Owner: not_promoted, serving V2 unchanged
```

## 7. Deployment topology: local và standalone cluster

**Câu hỏi:** Local mode và cluster mode khác nhau ở đâu, và cùng đọc data như
thế nào?

[Mở bản SVG](diagrams/07-spark-deployment.svg)

```mermaid
flowchart TB
    HOST_DATA[("Host read-only data<br/>./data/processed")]
    HOST_ARTIFACTS[("Host read-write artifacts<br/>./model/artifacts")]

    subgraph LOCAL["Local mode"]
        LOCAL_DRIVER["model-training-local<br/>Python 3.11 · Java 17"]
        LOCAL_SPARK["Spark local[*]<br/>driver + executors in one container"]

        LOCAL_DRIVER --> LOCAL_SPARK
    end

    subgraph CLUSTER["Standalone cluster mode"]
        DRIVER["model-training<br/>Python driver · Java 17"]
        MASTER["spark-master<br/>apache/spark:3.5.1<br/>7077 · UI 8080"]
        WORKER["spark-worker<br/>apache/spark:3.5.1<br/>2 cores · 2 GiB"]

        DRIVER -->|"SPARK_MASTER_URL"| MASTER
        WORKER -->|"register"| MASTER
        MASTER -->|"schedule tasks"| WORKER
    end

    HOST_DATA -->|"/data/processed:ro"| LOCAL_DRIVER
    HOST_DATA -->|"/data/processed:ro"| DRIVER
    HOST_DATA -->|"/data/processed:ro"| WORKER
    LOCAL_DRIVER <-->|"/app/artifacts"| HOST_ARTIFACTS
    DRIVER <-->|"/app/artifacts"| HOST_ARTIFACTS
```

Invariant quan trọng: driver và worker phải thấy cùng Parquet tại cùng absolute
path `/data/processed`. Arrow collection mặc định tắt; có thể opt-in bằng
`FRAUD_SPARK_ARROW_ENABLED=true` khi benchmark.

Nguồn triển khai:

- `docker-compose.yml`
- `model/Dockerfile`
- `model/src/fraud_model/spark_session.py`
- `scripts/train_model.ps1`

## 8. Candidate promotion state machine

**Câu hỏi:** Candidate được phép chuyển qua những trạng thái nào?

[Mở bản SVG](diagrams/08-promotion-state-machine.svg)

```mermaid
stateDiagram-v2
    [*] --> DataStaging
    DataStaging --> DataVerified: verifier passes
    DataStaging --> DataRejected: verifier fails
    DataVerified --> Training
    Training --> CandidatePackaged: all training stages complete
    Training --> TrainingFailed: any stage fails
    CandidatePackaged --> GateEvaluation
    GateEvaluation --> EligibleForReview: every gate passes
    GateEvaluation --> NotPromoted: one or more gates fail
    EligibleForReview --> Promoted: explicit human approval
    EligibleForReview --> NotPromoted: review rejects candidate
    Promoted --> ServingChampion: serving version updated explicitly
    DataRejected --> [*]
    TrainingFailed --> [*]
    NotPromoted --> [*]
    ServingChampion --> [*]

    note right of NotPromoted
        Candidate 0.0.3 is here.
        Failed gate: holdout PR-AUC.
        Serving V2 remains unchanged.
    end note
```

Không có transition tự động từ `CandidatePackaged` hoặc
`EligibleForReview` sang `ServingChampion`.

## 9. Traceability và cách duy trì

| View | Source of truth | Khi nào cập nhật |
| --- | --- | --- |
| Tổng quan | pipeline entry point, training script, promotion gate | Khi boundary hoặc ownership đổi |
| Data Pipeline | pipeline config, preprocess module, verifier | Khi split/feature/export contract đổi |
| Timeline | split config, temporal validation module | Khi ratio hoặc validation policy đổi |
| Data contract | processed manifest và verifier | Khi dataset/artifact/schema đổi |
| Model lifecycle | các training stage modules | Khi thêm/bỏ/reorder stage |
| Runtime sequence | training scripts và tracking module | Khi orchestration hoặc lineage đổi |
| Deployment | Dockerfile và Compose | Khi image, Spark mode hoặc mount đổi |
| Promotion states | package candidate và promotion gate | Khi approval/promotion policy đổi |

### Accessibility và export

- Các quan hệ đều có nhãn; không phụ thuộc vào màu để truyền đạt trạng thái.
- Mỗi sơ đồ có text summary và source paths làm fallback.
- Các flow chính dùng hướng trên-xuống để đọc tốt hơn trên màn hình hẹp.
- Mermaid source là artifact chuẩn. Khi cần nhúng vào báo cáo/slide, export
  sang SVG để giữ chữ sắc nét; dùng PNG chỉ khi công cụ đích không hỗ trợ SVG.
- Sau mỗi thay đổi kiến trúc, render lại toàn bộ Mermaid blocks và kiểm tra:
  syntax, nhãn bị cắt, edge crossing, khả năng đọc ở desktop và mobile.
