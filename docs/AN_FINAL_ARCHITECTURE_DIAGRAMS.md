# Bộ sơ đồ kiến trúc cuối — AS-BUILT và TARGET

**Status:** HYBRID WITH EXPLICIT LEGEND. Mermaid trong file này là source of truth.

Legend: solid = implemented/evidenced; dashed = target/partially enforced; gray = legacy; gold = governance gate; red = known gap.

## Diagram 1 — Overall System Architecture

**Status:** HYBRID. **Evidence:** `docker-compose.yml`, pipeline entrypoint, model stages, `score.py`, backend scoring và promotion gate.

```mermaid
flowchart LR
  subgraph OFFLINE["OFFLINE PLANE — AS-BUILT"]
    RAW["IEEE-CIS CSV"] --> SPARK["Spark typed ingestion, join, audit, features"]
    SPARK --> DATA[("Model-ready Parquet + manifest + reports")]
    DATA --> TRAIN["Python ML after Spark → Pandas"]
    TRAIN --> BUNDLE[("Model/candidate bundle")]
    BUNDLE --> GATE{{"Promotion gate"}}
    GATE -->|"fail"| KEEP["No serving change\nV2 remains champion"]
    GATE -->|"pass"| APPROVAL["Human approval"]
  end
  subgraph ONLINE["ONLINE PLANE — AS-BUILT"]
    CHAMP["Serving config\nsoftware default v2"] --> API["FastAPI\nin-process model import"]
    API --> DB[("SQLite/PostgreSQL\ntransactions/reviews")]
    API --> UI["React dashboard"]
  end
  APPROVAL -.-> UPDATE["Target: serving-config update"] -.-> CHAMP
  BUNDLE -.-> REG["Target: immutable registry/release"] -.-> CHAMP
  GAP["GAP: current workspace lacks complete proved versioned V2 runtime bundle"]:::gap -.-> CHAMP
  classDef gap fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d
```

Candidate fail never transitions into V2; it leaves serving configuration unchanged.

## Diagram 2 — Layered Data Architecture

**Status:** AS-BUILT, with logical/physical distinction.

```mermaid
flowchart TB
  S["Source Layer\nlogical external IEEE-CIS"] -.-> R[("Raw Data Layer\ndata/data/ieee-fraud-detection")]
  R --> V["Validation Layer\nschema/key/quality checks"] --> C[("Curated Layer\ncurated/ and splits/")]
  C --> A[("Analytics Layer\nreports/ and figures")]
  C --> F[("Feature Layer\nfeature_store/ + preprocessing artifacts")]
  F --> M[("Model-Ready Layer\nmodel_ready/*. Parquet")]
  M --> H[("Handover Layer\nmanifest/schema/verifier")]
```

## Diagram 3 — Detailed Data Processing Pipeline

**Status:** AS-BUILT. **Evidence:** `data/ieee_cis/pipeline/ieee_cis_preprocess.py`, `pipeline_config.yaml`.

```mermaid
flowchart TB
  RAW["Raw CSV"] --> FILES["Required-file, size, header validation"] --> INGEST["Explicit-schema Spark ingestion"]
  INGEST --> NORMALIZE["Identity-column normalization"] --> JOIN["Transaction–identity LEFT JOIN"]
  JOIN --> AUDIT["Key/join/data-quality audit"] --> CLEAN["Stateless cleanup + base features"]
  CLEAN --> SPLIT["Chronological split by TransactionDT"] --> FIT["Train-only fit + point-in-time features"]
  FIT --> VARIANTS["train_original / weighted / balanced\nvalidation / holdout / kaggle_test"] --> PARQUET[("Model-ready Parquet")]
  CLEAN --> EDA["EDA reports and figures"]
  PARQUET --> CONTRACT["Manifest + schema + verifier"]
```

EDA is a reporting branch, not a transformation that must change model-ready data.

## Diagram 4 — Leakage-Controlled Transformation Flow

**Status:** AS-BUILT for batch; online history service is TARGET.

```mermaid
flowchart LR
  DATA["Joined data + stateless cleanup"] --> SPLIT["Split by TransactionDT"]
  SPLIT --> T["Train"] & V["Validation"] & H["Holdout/test"]
  T --> FIT["Fit medians, outlier thresholds, category policy"]
  T --> PIT["PIT history\nordered by TransactionDT, TransactionID\nwindow ends at previous row"]
  FIT --> T2["Transform train"]
  FIT -.-> V2["Transform validation only"]
  FIT -.-> H2["Transform holdout/test only"]
  PIT --> T2
  PIT -.-> V2
  PIT -.-> H2
  RULE["No target aggregate; no non-train resampling; no current/future row"]:::gap -.-> PIT
  ONLINE["Target: online historical feature service"]:::target -.-> V2
  classDef gap fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d
  classDef target fill:#f3f4f6,stroke:#6b7280,color:#374151
```

## Diagram 5 — Data, Feature and Evaluation Contracts

**Status:** AS-BUILT.

```mermaid
flowchart TB
  DATA["Data Contract\n6 datasets; labels; metadata; null policy; class_weight"]
  FEATURE["Feature Contract\n68 ordered features; 61 numeric; 7 categorical; mappings; versions"]
  EVAL["Evaluation Contract\ntrain roles; validation windows; holdout restriction"]
  OUT[("model_ready Parquet")]
  ART[("feature_order, selected_features, schema, medians, policies")]
  EVID[("manifest + reports + verification")]
  OUT --> DATA
  ART --> FEATURE
  EVID --> DATA
  EVID --> EVAL
  DATA --> GATE{{"Model training contract gate"}}
  FEATURE --> GATE
  EVAL --> GATE
```

## Diagram 6 — Model Training Lifecycle

**Status:** HYBRID. Stages implemented; serving policy/registry authority is partly target.

```mermaid
flowchart TB
  VALIDATE["Validate contract"] --> MAP["Fit categorical mappings on train only"]
  MAP --> BASE["LogReg baseline"]
  MAP --> COMP["Compare LogReg, LightGBM, XGBoost, CatBoost"] --> SELECT["Select on validation"]
  SELECT --> TUNE["Tune selected family"] --> CAL["Fit calibrator"] --> POLICY["Select review/reject thresholds"]
  POLICY --> FREEZE["Freeze estimator + mappings + calibrator + policy"]
  FREEZE --> HOLD["Evaluate holdout once"] --> PACKAGE["Package bundle"] --> CHECK["Checksum + load smoke"] --> GATE{{"Gates"}}
  NOTE["Distributed data preparation\n→ single-node Python ML via .toPandas()"]:::note -.-> COMP
  classDef note fill:#fff7ed,stroke:#c2410c,color:#7c2d12
```

## Diagram 7 — Temporal Development Windows

**Status:** TARGET/AS-BUILT HYBRID. `split_validation_windows()` proves the candidate workflow; do not retrofit it to historical artifacts without metadata.

```mermaid
flowchart LR
  TRAIN["Training window\nfit model and mappings"] --> SEL["Selection\nfamily + hyperparameters"]
  SEL --> CAL["Calibration\ncalibrator"] --> POL["Policy\nthresholds"] --> HOLD["Final holdout\none-time evaluation"]
  HOLD -.-> NEW["Further tuning requires a new candidate version"]:::target
  V2["Historical V2 workflow"] -.->|"do not infer enhanced windows without evidence"| SEL
  classDef target fill:#f3f4f6,stroke:#6b7280,color:#374151
```

## Diagram 8 — Promotion State Machine

**Status:** TARGET/AS-BUILT HYBRID. Human approval and registry update are not automated runtime services.

```mermaid
stateDiagram-v2
  [*] --> CREATED
  CREATED --> DATA_VALIDATED --> TRAINED --> CALIBRATED --> POLICY_DEFINED --> HOLDOUT_EVALUATED --> PACKAGED
  PACKAGED --> GATE_PASSED --> AWAITING_APPROVAL --> PROMOTED
  CREATED --> DATA_INVALID
  TRAINED --> TRAINING_FAILED
  PACKAGED --> GATE_FAILED --> ARCHIVED
  AWAITING_APPROVAL --> REJECTED --> ARCHIVED
  GATE_FAILED -->|"serving unchanged"| V2["V2 remains champion"]
  PROMOTED --> ROLLBACK_REQUESTED --> PREVIOUS_CHAMPION_RESTORED
```

## Appendix catalogue

Full-feature versus partial-demo scoring, Spark deployment, single-node training deployment, version lineage, rollback, trust boundaries, training sequence và policy ownership nên đặt ở appendix. Chúng không được dùng để làm as-built claim nếu chỉ là target.
