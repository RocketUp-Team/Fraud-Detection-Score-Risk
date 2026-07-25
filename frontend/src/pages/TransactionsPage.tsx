import { useSearchParams } from 'react-router-dom'

import { EmptyState, ErrorState, TableSkeleton } from '../components/Feedback'
import { Icon } from '../components/Icon'
import { Pagination } from '../components/Pagination'
import { StatTiles } from '../components/StatTiles'
import { TransactionTable } from '../components/TransactionTable'
import { useMeta, useStats, useTransactions } from '../hooks/queries'
import {
  DECISION_LABEL,
  REVIEW_STATUS_LABEL,
  RISK_BAND_LABEL,
  type Decision,
  type ReviewStatus,
  type RiskBand,
  type TransactionListParams,
} from '../types/api'

const PAGE_SIZE = 20

/** Filter/phân trang lưu trong URL query param -> chia sẻ link được (deep linking). */
export function TransactionsPage() {
  const [params, setParams] = useSearchParams()
  const { data: meta } = useMeta()
  const { data: stats } = useStats()

  const query: TransactionListParams = {
    risk_band: (params.get('risk_band') as RiskBand) || undefined,
    decision: (params.get('decision') as Decision) || undefined,
    review_status: (params.get('review_status') as ReviewStatus) || undefined,
    search: params.get('search') || undefined,
    sort: (params.get('sort') as TransactionListParams['sort']) || '-risk_score',
    page: Number(params.get('page') || 1),
    page_size: PAGE_SIZE,
  }

  const { data, isPending, isError, error, refetch } = useTransactions(query)

  function update(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    // Đổi filter thì luôn về trang 1, tránh rơi vào trang trống.
    if (key !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }

  const hasFilter = ['risk_band', 'decision', 'review_status', 'search'].some((k) =>
    params.get(k),
  )

  return (
    <section>
      <header className="page-head">
        <div>
          <h1>Danh sách giao dịch</h1>
          <p className="muted">
            Điểm rủi ro 0–100 do model chấm. Lọc theo mức rủi ro để khoanh vùng ca cần xử lý.
            {meta && (
              <>
                {' '}
                Model: <span className="num">{meta.model_version}</span>
              </>
            )}
          </p>
        </div>
      </header>

      {stats && <StatTiles stats={stats} />}

      <form className="filters" role="search" onSubmit={(e) => e.preventDefault()}>
        <div className="field field--search">
          <label htmlFor="f-search">Mã giao dịch</label>
          <span className="input-icon">
            <Icon name="search" size={16} />
            <input
              id="f-search"
              type="search"
              inputMode="numeric"
              placeholder="vd 2987055"
              defaultValue={params.get('search') ?? ''}
              onChange={(e) => update('search', e.target.value.trim())}
            />
          </span>
        </div>

        <div className="field">
          <label htmlFor="f-band">Mức rủi ro</label>
          <select
            id="f-band"
            value={params.get('risk_band') ?? ''}
            onChange={(e) => update('risk_band', e.target.value)}
          >
            <option value="">Tất cả</option>
            {(meta?.bands ?? []).map((b) => (
              <option key={b.band} value={b.band}>
                {RISK_BAND_LABEL[b.band]} ({b.min}–{b.max})
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="f-decision">Quyết định hệ thống</label>
          <select
            id="f-decision"
            value={params.get('decision') ?? ''}
            onChange={(e) => update('decision', e.target.value)}
          >
            <option value="">Tất cả</option>
            {Object.entries(DECISION_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="f-review">Trạng thái rà soát</label>
          <select
            id="f-review"
            value={params.get('review_status') ?? ''}
            onChange={(e) => update('review_status', e.target.value)}
          >
            <option value="">Tất cả</option>
            {Object.entries(REVIEW_STATUS_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="f-sort">Sắp xếp</label>
          <select
            id="f-sort"
            value={params.get('sort') ?? '-risk_score'}
            onChange={(e) => update('sort', e.target.value)}
          >
            <option value="-risk_score">Điểm rủi ro cao → thấp</option>
            <option value="risk_score">Điểm rủi ro thấp → cao</option>
            <option value="-scored_at">Chấm mới nhất</option>
            <option value="scored_at">Chấm cũ nhất</option>
          </select>
        </div>

        {hasFilter && (
          <button
            type="button"
            className="btn btn--secondary"
            onClick={() => setParams(new URLSearchParams(), { replace: true })}
          >
            Xoá filter
          </button>
        )}
      </form>

      {isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : isPending ? (
        <TableSkeleton cols={8} />
      ) : data.items.length === 0 ? (
        <EmptyState
          title="Không có giao dịch nào khớp filter"
          hint={
            hasFilter
              ? 'Thử bỏ bớt điều kiện lọc.'
              : 'DB chưa có dữ liệu — chạy `uv run python -m fraud_backend.seed` ở backend/.'
          }
        />
      ) : (
        <>
          <TransactionTable items={data.items} />
          <Pagination
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onPageChange={(p) => update('page', String(p))}
          />
        </>
      )}
    </section>
  )
}
