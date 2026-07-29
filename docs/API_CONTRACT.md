# Fraud Risk API Contract

**Implementation source:** FastAPI Pydantic schemas and route definitions

**Base URL (local):** `http://localhost:8000`
**Interactive schema:** `http://localhost:8000/docs`

This document describes the backend contract implemented on 30 July 2026.
`backend/src/fraud_backend/schemas.py` and the generated OpenAPI document are
the runtime authorities. Frontend types are maintained manually and must be
checked whenever this contract changes.

## 1. Common conventions

- JSON property names use `snake_case`.
- Timestamps are ISO 8601 values serialized by FastAPI.
- Errors use FastAPI's `{"detail": "..."}` envelope.
- `fraud_probability` is clamped to `[0, 1]`.
- `risk_score = round(fraud_probability × 100)` and is in `[0, 100]`.
- `risk_band` and `decision` are calculated by the backend.
- An automatic `decision` is distinct from a human `review.status`.
- `shap_top5` can be `null` when explainability is unavailable.
- A backend warning indicates fallback operation and must be shown to operators.

## 2. Shared types

```ts
type RiskBand = "low" | "guarded" | "medium" | "high" | "critical"
type Decision = "approve" | "review" | "reject"
type ReviewStatus = "pending" | "approved" | "rejected"
type ReviewLabel = "fraud" | "legit"
type FeatureValue = string | number | null
type ScoringMode = "full_feature" | "partial_demo"

type ShapContribution = {
  feature: string
  shap_value: number
}

type Transaction = {
  transaction_id: number
  amount: number
  fraud_probability: number
  risk_score: number
  risk_band: RiskBand
  decision: Decision
  scored_at: string
  model_version: string
  review_status: ReviewStatus
}

type Review = {
  status: ReviewStatus
  label: ReviewLabel | null
  reviewer: string | null
  note: string | null
  updated_at: string
}

type TransactionDetail = Transaction & {
  features: Record<string, FeatureValue>
  shap_top5: ShapContribution[] | null
  review: Review | null
}
```

## 3. Risk policy

| Score | Band | Automatic decision |
|---:|---|---|
| 0–19 | `low` | `approve` |
| 20–39 | `guarded` | `approve` |
| 40–59 | `medium` | `review` |
| 60–79 | `high` | `review` |
| 80–100 | `critical` | `reject` |

This fixed backend policy is the current decision authority. Threshold metadata
inside a model artifact does not currently override these boundaries.

## 4. Health and model metadata

### `GET /health`

Response `200`:

```json
{"status": "ok"}
```

This is process health, not a strict guarantee that the expected model loaded
without fallback.

### `GET /meta`

Response `200`:

```ts
type Meta = {
  model_version: string
  model_name: string
  processing_version: string | null
  feature_schema_version: string | null
  explainability: boolean
  n_features: number
  required_features: string[]
  optional_features: string[]
  defaultable_features: string[]
  bands: { band: RiskBand; min: number; max: number }[]
  warning: string | null
}
```

`warning` is non-null when the backend uses a non-model heuristic fallback.

## 5. Ad-hoc scoring

### `POST /score`

Scores one feature dictionary without writing a database row.

Request:

```json
{
  "features": {
    "TransactionAmt": 4899.0,
    "ProductCD": "W",
    "card4": "visa",
    "DeviceType": "mobile"
  }
}
```

Response `200`:

```ts
type ScoreResponse = {
  fraud_probability: number
  risk_score: number
  risk_band: RiskBand
  decision: Decision
  scoring_mode: "full_feature" | "partial_demo"
  shap_top5: ShapContribution[] | null
  model_version: string
  processing_version: string | null
  feature_schema_version: string | null
  scored_at: string
}
```

`full_feature` means the request supplied the complete model vector.
`partial_demo` means some model columns were defaulted. Required features that
are neither optional nor defaultable cause a validation error.

## 6. Transaction exploration and review

### `GET /transactions`

Query parameters:

| Parameter | Type/default | Behavior |
|---|---|---|
| `risk_band` | `RiskBand` | Exact band filter |
| `decision` | `Decision` | Exact automatic-decision filter |
| `review_status` | `ReviewStatus` | Missing review maps to `pending` |
| `min_score` | integer 0–100 | Inclusive lower score |
| `max_score` | integer 0–100 | Inclusive upper score |
| `search` | string | Exact numeric transaction ID; non-numeric returns empty |
| `sort` | `-risk_score` | `risk_score`, `-risk_score`, `scored_at`, `-scored_at` |
| `page` | integer ≥1, default 1 | One-based page |
| `page_size` | 1–100, default 20 | Page size |

Response `200`:

```ts
type PaginatedTransactions = {
  items: Transaction[]
  total: number
  page: number
  page_size: number
}
```

Rows with equal sort values use `transaction_id` ascending as a stable
tie-breaker.

### `GET /transactions/stats`

Response `200`:

```ts
type Stats = {
  total: number
  pending_review: number
  by_band: { band: RiskBand; count: number }[]
  avg_risk_score: number
  high_risk_amount: number
}
```

`by_band` always contains all five bands. `high_risk_amount` sums transaction
amount for `high` and `critical`.

### `GET /transactions/{transaction_id}`

Response `200`: `TransactionDetail`.
Response `404`: transaction does not exist.

### `POST /transactions/{transaction_id}/review`

Request:

```ts
type ReviewRequest = {
  action: "approve" | "reject"
  label: "fraud" | "legit"
  reviewer?: string | null // maximum 64 characters
  note?: string | null     // maximum 1,000 characters
}
```

`action` maps to review status `approved` or `rejected`. A repeated request
overwrites the existing review.

Response `200`: updated `TransactionDetail`.

Response `404`: transaction does not exist.
Response `422`: invalid payload.

## 7. CSV import

### `GET /transactions/import/template`

Query:

- `rows`: integer `1..500`, default `20`.

Returns UTF-8-with-BOM CSV containing:

1. `TransactionID`;
2. every model feature in expected order;
3. up to the requested number of real holdout examples when available.

Response `409` when the backend cannot determine model columns. If processed
Parquet examples are unavailable, the endpoint still returns the header.

### `POST /transactions/import`

Content type: `multipart/form-data`; field `file` must be a UTF-8 `.csv`.
`TransactionID` is required.

The backend scores and upserts each row independently. Empty cells become
`null`; numeric-looking values become numbers; other values remain strings.
Import stops after `MAX_IMPORT_ROWS` attempted rows (default 5,000).

Response `200`:

```ts
type ImportResponse = {
  imported: number
  failed: number
  errors: { row: number; error: string }[] // at most first 50 returned
  matched_features: number
  expected_features: number
  missing_features: string[]               // at most first 60 returned
}
```

Missing feature columns are reported because a raw Kaggle CSV does not contain
all engineered model features. A successful import can therefore still be
`partial_demo` quality.

Common `422` errors:

- non-CSV extension;
- non-UTF-8 file;
- missing `TransactionID` header.

## 8. Processed datasets

### `GET /datasets`

Response `200`:

```ts
type Dataset = {
  name: string
  rows: number
  recommended: boolean
  note: string
  fraud_rate: number | null
  has_labels: boolean
  model_trained_on: boolean
}
```

Dataset availability is discovered from mounted model-ready Parquet rather than
hard-coded.

### `POST /data/load`

Starts one in-memory background load and returns `202`.

```ts
type LoadRequest = {
  dataset?: string             // default "holdout"
  limit?: number               // 1..100000, default 5000
  reset?: boolean              // default false
  mode?: "head" | "sample" | "coverage" // default "head"
  per_band?: number            // 1..500, default 20
  seed?: number                // >=0, default 42
}
```

Mode behavior:

- `head`: first `limit` rows;
- `sample`: deterministic sample using `seed`;
- `coverage`: up to `per_band` examples for each of five risk bands.

Requested `limit` is capped at the actual dataset size. `reset` occurs inside
the background task after the source is readable.

Response:

```ts
type Job = {
  id: string
  status: "running" | "done" | "error" | "cancelled"
  processed: number
  total: number
  percent: number
  error: string | null
  started_at: string
  finished_at: string | null
}
```

Errors:

- `409` when no processed datasets exist;
- `409` when another job is already active;
- `422` for an unknown dataset or invalid request.

## 9. Job control

### `GET /jobs/{job_id}`

Returns a `Job`; `404` also covers job history lost after a backend restart.

### `GET /jobs/active/current`

Returns the active `Job` or `null`. The frontend uses this to reconnect polling
after a page refresh.

### `POST /jobs/{job_id}/cancel`

Requests cooperative cancellation.

- `200`: updated `Job`;
- `404`: unknown job;
- `409`: job is already terminal.

The registry is in process memory and is correct only for a single backend
worker.

## 10. Compatibility and change procedure

When changing a wire shape:

1. change the Pydantic schema and route behavior;
2. regenerate/review FastAPI OpenAPI;
3. update `frontend/src/types/api.ts`;
4. update mocks and callers;
5. update this document;
6. run backend API and frontend build tests in the same change.

Known synchronization gap at this evidence snapshot: frontend TypeScript types
do not yet declare all backend metadata/version fields or `scoring_mode`.
Runtime JSON tolerates these extra properties, but generated OpenAPI types are
recommended.
