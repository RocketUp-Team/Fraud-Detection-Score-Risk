import { EmptyState, ErrorState, TableSkeleton } from '../components/Feedback'
import { Pagination } from '../components/Pagination'
import { TransactionTable } from '../components/TransactionTable'
import { useTransactions } from '../hooks/queries'
import { useSearchParams } from 'react-router-dom'

const PAGE_SIZE = 20
/** Chỉ những ca hệ thống yêu cầu người xem: từ mức Trung bình trở lên. */
const MIN_SCORE = 40

/**
 * Hàng chờ rà soát — điểm cao nhất lên đầu, chỉ lấy ca chưa ai xử lý.
 * Đây là màn làm việc chính của người rà soát, tách khỏi màn duyệt toàn bộ.
 */
export function ReviewQueuePage() {
  const [params, setParams] = useSearchParams()
  const page = Number(params.get('page') || 1)

  const { data, isPending, isError, error, refetch } = useTransactions({
    review_status: 'pending',
    min_score: MIN_SCORE,
    sort: '-risk_score',
    page,
    page_size: PAGE_SIZE,
  })

  return (
    <section>
      <header className="page-head">
        <div>
          <h1>Hàng chờ rà soát</h1>
          <p className="muted">
            Giao dịch từ mức <strong>Trung bình</strong> (điểm ≥ <span className="num">
              {MIN_SCORE}
            </span>
            ) chưa được rà soát, xếp theo điểm rủi ro giảm dần. Mở chi tiết để duyệt, từ chối
            và gắn nhãn.
          </p>
        </div>
        {data && (
          <p className="stat">
            <span className="stat__value num">{data.total}</span>
            <span className="stat__label">ca đang chờ</span>
          </p>
        )}
      </header>

      {isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : isPending ? (
        <TableSkeleton cols={8} />
      ) : data.items.length === 0 ? (
        <EmptyState
          title="Hết ca cần rà soát"
          hint="Không còn giao dịch rủi ro nào đang chờ. Xem toàn bộ ở màn Danh sách giao dịch."
        />
      ) : (
        <>
          <TransactionTable
            items={data.items}
            startIndex={(data.page - 1) * data.page_size}
          />
          <Pagination
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onPageChange={(p) => {
              const next = new URLSearchParams(params)
              next.set('page', String(p))
              setParams(next, { replace: true })
            }}
          />
        </>
      )}
    </section>
  )
}
