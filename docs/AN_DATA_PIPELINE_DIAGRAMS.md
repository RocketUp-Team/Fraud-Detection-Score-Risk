# An Data Pipeline Diagrams — HISTORICAL / SUPERSEDED

> **Authoritative replacement:** [`AN_FINAL_ARCHITECTURE_DIAGRAMS.md`](AN_FINAL_ARCHITECTURE_DIAGRAMS.md).
> The final diagrams correct the as-built/target boundary and leakage wording.

## 1. Layered Data Architecture

```mermaid
flowchart TD
    A[Source Layer<br/>IEEE-CIS CSV]
    B[Raw Data Layer<br/>Typed Spark DataFrames]
    C[Validation Layer<br/>Schema, size, key checks]
    D[Curated Data Layer<br/>Joined and cleaned transaction-identity data]
    E[Analytics Layer<br/>EDA reports and figures]
    F[Feature Engineering Layer<br/>Time, amount, missingness, entity features]
    G[Model-Ready Layer<br/>Parquet datasets for training]
    H[Handover Layer<br/>Manifest, schema, reports, artifacts]

    A --> B --> C --> D --> E
    D --> F --> G --> H
```

## 2. End-to-End Processing Pipeline

```mermaid
flowchart LR
    A[Raw CSV files] --> B[Required-file validation]
    B --> C[Explicit schema Spark ingestion]
    C --> D[Identity-column normalization]
    D --> E[Transaction-identity left join]
    E --> F[Data-quality audit]
    F --> G[Distributed EDA]
    G --> H[Cleaning and base features]
    H --> I[Chronological split]
    I --> J[Train-only fitting]
    J --> K[Feature engineering and aggregates]
    K --> L[Imbalance variants]
    L --> M[Model-ready Parquet export]
```

## 3. Train-Only Transformation Flow

```mermaid
flowchart TD
    A[Chronological train split] --> B[Fit numeric medians]
    A --> C[Fit category policy]
    A --> D[Fit outlier thresholds]
    A --> E[Fit card/email/device aggregates]
    B --> F[Apply to train]
    B --> G[Apply to validation]
    B --> H[Apply to holdout]
    B --> I[Apply to kaggle_test]
    C --> F
    C --> G
    C --> H
    C --> I
    D --> F
    D --> G
    D --> H
    D --> I
    E --> F
    E --> G
    E --> H
    E --> I
```

## 4. Data Leakage Prevention Flow

```mermaid
flowchart TD
    A[Raw labeled train data] --> B[Join and cleanup before split]
    B --> C[Split by TransactionDT]
    C --> D[Train]
    C --> E[Validation]
    C --> F[Holdout]
    D --> G[Fit medians, thresholds, aggregates]
    G --> H[Transform train]
    G --> I[Transform validation only]
    G --> J[Transform holdout only]
    H --> K[train_original / train_weighted / train_balanced]
    I --> L[validation]
    J --> M[holdout]

    N[No target-based aggregates]
    O[No future rows in historical features]
    P[No resampling outside train]

    N -.-> G
    O -.-> G
    P -.-> L
    P -.-> M
```

## 5. Model-Ready Handover Flow

```mermaid
flowchart LR
    A[Model-ready Parquet] --> B[Feature order artifact]
    A --> C[Schema artifact]
    A --> D[Manifest]
    A --> E[EDA and audit reports]
    B --> F[Downstream model training]
    C --> F
    D --> F
    E --> F
```
