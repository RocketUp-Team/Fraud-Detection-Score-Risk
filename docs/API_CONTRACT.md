# Hợp đồng API — Backend (Trung) ↔ Frontend (Long)

Chốt theo `docs/RISK_SCORING_PLAN.md` mục 2. Nguồn sự thật duy nhất cho cả hai
phía: backend implement đúng shape này, frontend mock đúng shape này
(`frontend/src/mocks/`), TypeScript types sinh tay tại
`frontend/src/types/api.ts`.

Base URL: `http://localhost:8000` (frontend đọc từ `VITE_API_URL`).

## Quy ước chung

- `fraud_probability` ∈ [0, 1] — output thô của model.
- `risk_score` = `round(fraud_probability * 100)` ∈ [0, 100].
- `risk_band` do **backend** tính, frontend không tự suy ra (tránh lệch logic).
  Bands theo `RISK_SCORE_DATA_CONTRACT.md`:

  | band | risk_score |
  |---|---|
  | `low` | 0–19 |
  | `guarded` | 20–39 |
  | `medium` | 40–59 |
  | `high` | 60–79 |
  | `critical` | 80–100 |

- `decision` ∈ `approve` \| `review` \| `reject` — quyết định tự động của hệ
  thống theo band (`low`/`guarded` → approve, `medium`/`high` → review,
  `critical` → reject). Khác với `review.status` là quyết định **của người rà soát**.
- Mọi timestamp là ISO 8601 UTC (`2026-07-26T09:12:33Z`).
- Lỗi trả về theo mặc định FastAPI: `{"detail": "..."}` với HTTP status tương ứng.

## Kiểu dữ liệu

```ts
type RiskBand = "low" | "guarded" | "medium" | "high" | "critical"
type Decision = "approve" | "review" | "reject"
type ReviewStatus = "pending" | "approved" | "rejected"
type ReviewLabel = "fraud" | "legit"

type Transaction = {
  transaction_id: number
  amount: number
  fraud_probability: number
  risk_score: number
  risk_band: RiskBand
  decision: Decision
  scored_at: string
  model_version: string
  review_status: ReviewStatus     // để list hiển thị được mà không cần gọi detail
}

type ShapContribution = {
  feature: string
  shap_value: number              // >0 đẩy về fraud, <0 kéo về legit
}

type Review = {
  status: ReviewStatus
  label: ReviewLabel | null
  reviewer: string | null
  note: string | null
  updated_at: string
}

type TransactionDetail = Transaction & {
  features: Record<string, string | number | null>
  shap_top5: ShapContribution[] | null   // null khi model fallback (baseline LogReg)
  review: Review | null
}
```

> `shap_top5` **có thể là `null`** — `model/src/fraud_model/score.py` trả
> `shap: None` khi đang chạy fallback `baseline_logreg`. Frontend phải render
> trạng thái "chưa có explainability" thay vì crash.

## Endpoints

### `GET /health`
```json
{ "status": "ok" }
```

### `GET /meta`
Metadata cho frontend hiển thị + tự sinh filter options.
```json
{
  "model_version": "lightgbm-2026-07-25",
  "model_name": "lightgbm",
  "explainability": true,
  "bands": [
    { "band": "low",      "min": 0,  "max": 19 },
    { "band": "guarded",  "min": 20, "max": 39 },
    { "band": "medium",   "min": 40, "max": 59 },
    { "band": "high",     "min": 60, "max": 79 },
    { "band": "critical", "min": 80, "max": 100 }
  ]
}
```

### `GET /transactions`
Query params (tất cả optional):

| param | kiểu | mặc định | ghi chú |
|---|---|---|---|
| `risk_band` | `RiskBand` | – | lọc theo 1 band |
| `decision` | `Decision` | – | |
| `review_status` | `ReviewStatus` | – | dùng cho màn rà soát: `pending` |
| `min_score` / `max_score` | int 0–100 | – | |
| `search` | string | – | khớp `transaction_id` |
| `sort` | `risk_score` \| `-risk_score` \| `scored_at` \| `-scored_at` | `-risk_score` | |
| `page` | int ≥ 1 | 1 | |
| `page_size` | int 1–100 | 20 | |

```json
{
  "items": [ /* Transaction[] */ ],
  "total": 348,
  "page": 1,
  "page_size": 20
}
```

### `GET /transactions/stats`
Số liệu tổng quan cho KPI row của dashboard. Khai báo **trước** route
`/{transaction_id}` để `stats` không bị hiểu là id.
```json
{
  "total": 348,
  "pending_review": 96,
  "by_band": [
    { "band": "low", "count": 171 },
    { "band": "guarded", "count": 74 },
    { "band": "medium", "count": 52 },
    { "band": "high", "count": 33 },
    { "band": "critical", "count": 18 }
  ],
  "avg_risk_score": 28.4,
  "high_risk_amount": 128450.75
}
```
- `by_band` luôn trả đủ 5 band, band không có giao dịch thì `count: 0`.
- `high_risk_amount` = tổng `amount` của band `high` + `critical`.

### `GET /transactions/{transaction_id}`
Trả `TransactionDetail`. `404` nếu không tồn tại.

### `POST /transactions/{transaction_id}/review`
Người rà soát duyệt/từ chối + gắn nhãn.
```json
// request
{ "action": "reject", "label": "fraud", "reviewer": "long", "note": "Thẻ lạ, IP khác quốc gia" }
```
- `action`: `"approve" | "reject"` (bắt buộc) → map sang `review.status`
  `approved`/`rejected`.
- `label`: `"fraud" | "legit"` (bắt buộc) — nhãn thủ công để đối chiếu model.
- `reviewer`, `note`: optional.

Response: `TransactionDetail` sau khi cập nhật (`200`). `404` nếu không tồn tại,
`422` nếu payload sai.

### `POST /score`
Chấm điểm ad-hoc, không ghi DB — dùng cho demo "nhập giao dịch mới".
```json
// request
{ "features": { "TransactionAmt": 4899.0, "ProductCD": "W", "card4": "visa", "...": null } }
```
```json
// response
{
  "fraud_probability": 0.8712,
  "risk_score": 87,
  "risk_band": "critical",
  "decision": "reject",
  "shap_top5": [ /* ShapContribution[] | null */ ],
  "model_version": "lightgbm-2026-07-25",
  "scored_at": "2026-07-26T09:12:33Z"
}
```
Feature thiếu được điền `-999` như `score.py` đang làm — không lỗi.

### `POST /transactions/import`
`multipart/form-data`, field `file` = CSV theo `DATA_DICTIONARY.md`. Mỗi dòng
được chấm điểm rồi ghi DB.
```json
{ "imported": 200, "failed": 2, "errors": [{ "row": 17, "error": "TransactionAmt không phải số" }] }
```

## Feature set (cho `POST /score` và cột `features` ở detail)

Theo `DATA_DICTIONARY.md`:

- **Amount**: `TransactionAmt`, `log_transaction_amount`, `amount_band`
- **Presence**: `has_identity`, `has_device_info`, `has_p_email`, `has_r_email`
- **Missingness**: `selected_missing_count`, `selected_missing_ratio`, `identity_missing_count`
- **Entity history**: `prior_card_transaction_count`, `prior_card_amount_sum`,
  `prior_email_transaction_count`, `prior_email_amount_sum`,
  `prior_device_transaction_count`, `prior_device_amount_sum`
- **Categorical** (giá trị string gốc, backend không encode — `score()` tự lo):
  `ProductCD`, `card4`, `card6`, `DeviceType`, `device_family`, `M4`, `amount_band`

## Thay đổi hợp đồng

Sửa file này trước, cập nhật `frontend/src/types/api.ts` và
`frontend/src/mocks/` cùng commit. Không đổi shape một phía.
