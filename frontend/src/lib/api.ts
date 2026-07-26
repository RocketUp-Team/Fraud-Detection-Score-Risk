/**
 * API client — shape theo `docs/API_CONTRACT.md`.
 *
 * Bật `VITE_USE_MOCKS=true` để chạy trên mock JSON khi backend chưa lên
 * (hữu ích lúc demo/offline). Mặc định gọi API thật ở VITE_API_URL.
 */
import type {
  Dataset,
  ImportResponse,
  Job,
  LoadRequest,
  Meta,
  Paginated,
  ReviewRequest,
  ScoreRequest,
  ScoreResponse,
  Stats,
  Transaction,
  TransactionDetail,
  TransactionListParams,
} from '../types/api'

import mockDetail from '../mocks/transaction-detail.json'
import mockMeta from '../mocks/meta.json'
import mockStats from '../mocks/stats.json'
import mockList from '../mocks/transactions.json'

const BASE_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'

export class ApiError extends Error {
  // Khai báo field tường minh: `erasableSyntaxOnly` không cho parameter property.
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
        ...init?.headers,
      },
    })
  } catch {
    // Phân biệt rõ "không nối được backend" với "backend trả lỗi" — hai
    // trạng thái này cần hai thông báo khác nhau cho người dùng.
    throw new ApiError(0, `Không kết nối được backend tại ${BASE_URL}. Backend đã chạy chưa?`)
  }

  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = (await res.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      /* body không phải JSON — giữ statusText */
    }
    throw new ApiError(res.status, detail)
  }

  return res.json() as Promise<T>
}

function toQuery(params: TransactionListParams): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

/**
 * Điểm giả cho chế độ mock — KHÔNG phải output của model.
 * Bám theo số tiền để việc đổi input có phản hồi thấy được, và dùng đúng
 * ngưỡng band trong `RISK_SCORE_DATA_CONTRACT.md` để phần hiển thị vẫn đúng.
 */
function fakeScore(payload: ScoreRequest): ScoreResponse {
  const amount = Number(payload.features.TransactionAmt) || 0
  const proba = Math.min(0.99, Math.max(0.01, 1 / (1 + Math.exp(-(Math.log1p(amount) - 6) / 1.2))))
  const risk_score = Math.round(proba * 100)
  const band: Stats['by_band'][number]['band'] =
    risk_score >= 80
      ? 'critical'
      : risk_score >= 60
        ? 'high'
        : risk_score >= 40
          ? 'medium'
          : risk_score >= 20
            ? 'guarded'
            : 'low'
  return {
    fraud_probability: proba,
    risk_score,
    risk_band: band,
    decision: band === 'critical' ? 'reject' : risk_score >= 40 ? 'review' : 'approve',
    shap_top5: [
      { feature: 'log_transaction_amount', shap_value: (proba - 0.5) * 3 },
      { feature: 'prior_card_transaction_count', shap_value: (0.5 - proba) * 2 },
      { feature: 'ProductCD', shap_value: 0.42 },
      { feature: 'has_identity', shap_value: -0.31 },
      { feature: 'device_family', shap_value: 0.18 },
    ],
    model_version: 'mock-không-phải-model-thật',
    scored_at: new Date().toISOString(),
  }
}

export const api = {
  meta(): Promise<Meta> {
    // `as unknown as` vì TS suy JSON ra `string` chứ không phải union literal.
    if (USE_MOCKS) return Promise.resolve(mockMeta as unknown as Meta)
    return request<Meta>('/meta')
  },

  listDatasets(): Promise<Dataset[]> {
    if (USE_MOCKS) {
      return Promise.resolve([
        {
          name: 'holdout',
          rows: 89092,
          recommended: true,
          note: 'Chế độ mock — cần backend thật để nạp.',
          fraud_rate: 0.0349,
          has_labels: true,
          model_trained_on: false,
        },
      ])
    }
    return request<Dataset[]>('/datasets')
  },

  startLoad(payload: LoadRequest): Promise<Job> {
    if (USE_MOCKS) {
      return Promise.reject(
        new ApiError(0, 'Đang chạy chế độ mock — cần backend thật để nạp dữ liệu.'),
      )
    }
    return request<Job>('/data/load', { method: 'POST', body: JSON.stringify(payload) })
  },

  getJob(jobId: string): Promise<Job> {
    return request<Job>(`/jobs/${jobId}`)
  },

  /** Job đang chạy (nếu có) — để nối lại thanh tiến độ sau khi F5. */
  getActiveJob(): Promise<Job | null> {
    if (USE_MOCKS) return Promise.resolve(null)
    return request<Job | null>('/jobs/active/current')
  },

  cancelJob(jobId: string): Promise<Job> {
    return request<Job>(`/jobs/${jobId}/cancel`, { method: 'POST' })
  },

  stats(): Promise<Stats> {
    if (USE_MOCKS) return Promise.resolve(mockStats as unknown as Stats)
    return request<Stats>('/transactions/stats')
  },

  listTransactions(params: TransactionListParams = {}): Promise<Paginated<Transaction>> {
    if (USE_MOCKS) return Promise.resolve(mockList as unknown as Paginated<Transaction>)
    return request<Paginated<Transaction>>(`/transactions${toQuery(params)}`)
  },

  getTransaction(id: number): Promise<TransactionDetail> {
    if (USE_MOCKS) return Promise.resolve(mockDetail as unknown as TransactionDetail)
    return request<TransactionDetail>(`/transactions/${id}`)
  },

  submitReview(id: number, payload: ReviewRequest): Promise<TransactionDetail> {
    return request<TransactionDetail>(`/transactions/${id}/review`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  score(payload: ScoreRequest): Promise<ScoreResponse> {
    // Ở chế độ mock KHÔNG có model: trả về số giả để màn "Chấm điểm thử" còn
    // bấm được khi demo offline. Số này không phải của model — muốn điểm thật
    // thì phải chạy backend.
    if (USE_MOCKS) return Promise.resolve(fakeScore(payload))
    return request<ScoreResponse>('/score', { method: 'POST', body: JSON.stringify(payload) })
  },

  importCsv(file: File): Promise<ImportResponse> {
    if (USE_MOCKS) {
      return Promise.resolve({
        imported: 0,
        failed: 1,
        errors: [
          {
            row: 0,
            error: 'Đang chạy chế độ mock (VITE_USE_MOCKS=true) — cần backend thật để nhập CSV.',
          },
        ],
      })
    }
    const form = new FormData()
    form.append('file', file)
    return request<ImportResponse>('/transactions/import', { method: 'POST', body: form })
  },
}
