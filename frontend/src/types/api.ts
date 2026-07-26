/**
 * Kiểu dữ liệu API — sinh tay theo `docs/API_CONTRACT.md`.
 * Sửa hợp đồng thì sửa file này + `src/mocks/` cùng commit.
 */

export type RiskBand = 'low' | 'guarded' | 'medium' | 'high' | 'critical'
export type Decision = 'approve' | 'review' | 'reject'
export type ReviewStatus = 'pending' | 'approved' | 'rejected'
export type ReviewLabel = 'fraud' | 'legit'

export type Transaction = {
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

export type ShapContribution = {
  feature: string
  /** > 0 đẩy về fraud, < 0 kéo về legit */
  shap_value: number
}

export type Review = {
  status: ReviewStatus
  label: ReviewLabel | null
  reviewer: string | null
  note: string | null
  updated_at: string
}

export type TransactionDetail = Transaction & {
  features: Record<string, string | number | null>
  /** null khi backend đang chạy model fallback (baseline LogReg, không có SHAP) */
  shap_top5: ShapContribution[] | null
  review: Review | null
}

export type Paginated<T> = {
  items: T[]
  total: number
  page: number
  page_size: number
}

export type BandRange = { band: RiskBand; min: number; max: number }

export type Meta = {
  model_version: string
  model_name: string
  explainability: boolean
  /** Số feature model mong đợi — dùng để nói rõ "đã cung cấp 9/53". */
  n_features: number
  bands: BandRange[]
  /** Chỉ có khi backend chưa dùng được model thật (fallback heuristic). */
  warning?: string | null
}

export type BandCount = { band: RiskBand; count: number }

export type Stats = {
  total: number
  pending_review: number
  by_band: BandCount[]
  avg_risk_score: number
  high_risk_amount: number
}

/** Bộ dữ liệu trong `model_ready/` mà backend có thể nạp. */
export type Dataset = {
  name: string
  rows: number
  /** false = model đã học trên bộ này, hoặc phân bố bị méo */
  recommended: boolean
  note: string
}

export type LoadRequest = {
  dataset: string
  limit: number
  reset: boolean
}

export type JobStatus = 'running' | 'done' | 'error' | 'cancelled'

export type Job = {
  id: string
  status: JobStatus
  processed: number
  total: number
  percent: number
  error: string | null
  started_at: string
  finished_at: string | null
}

export type TransactionListParams = {
  risk_band?: RiskBand
  decision?: Decision
  review_status?: ReviewStatus
  min_score?: number
  max_score?: number
  search?: string
  sort?: 'risk_score' | '-risk_score' | 'scored_at' | '-scored_at'
  page?: number
  page_size?: number
}

export type ReviewRequest = {
  action: 'approve' | 'reject'
  label: ReviewLabel
  reviewer?: string
  note?: string
}

export type ScoreRequest = {
  features: Record<string, string | number | null>
}

export type ScoreResponse = {
  fraud_probability: number
  risk_score: number
  risk_band: RiskBand
  decision: Decision
  shap_top5: ShapContribution[] | null
  model_version: string
  scored_at: string
}

export type ImportResponse = {
  imported: number
  failed: number
  errors: { row: number; error: string }[]
}

/** Nhãn tiếng Việt + màu semantic token cho từng band (dùng ở RiskBadge). */
export const RISK_BAND_LABEL: Record<RiskBand, string> = {
  low: 'Thấp',
  guarded: 'Cần lưu ý',
  medium: 'Trung bình',
  high: 'Cao',
  critical: 'Nghiêm trọng',
}

export const DECISION_LABEL: Record<Decision, string> = {
  approve: 'Duyệt',
  review: 'Cần rà soát',
  reject: 'Từ chối',
}

export const REVIEW_STATUS_LABEL: Record<ReviewStatus, string> = {
  pending: 'Chờ rà soát',
  approved: 'Đã duyệt',
  rejected: 'Đã từ chối',
}
