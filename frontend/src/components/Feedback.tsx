import type { ReactNode } from 'react'
import { ApiError } from '../lib/api'

/** Skeleton giữ đúng chỗ của bảng để không bị layout shift (CLS < 0.1). */
export function TableSkeleton({ rows = 8, cols = 6 }: { rows?: number; cols?: number }) {
  return (
    <div className="skeleton-table" aria-busy="true" aria-live="polite">
      <span className="sr-only">Đang tải dữ liệu…</span>
      {Array.from({ length: rows }).map((_, r) => (
        <div className="skeleton-row" key={r}>
          {Array.from({ length: cols }).map((_, c) => (
            <span className="skeleton-cell" key={c} />
          ))}
        </div>
      ))}
    </div>
  )
}

/** Empty state luôn kèm hành động gợi ý, không để trắng trang. */
export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string
  hint?: string
  action?: ReactNode
}) {
  return (
    <div className="empty">
      <p className="empty__title">{title}</p>
      {hint && <p className="empty__hint">{hint}</p>}
      {action}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const isOffline = error instanceof ApiError && error.status === 0
  const message = error instanceof Error ? error.message : 'Lỗi không xác định'

  return (
    <div className="callout callout--error" role="alert">
      <strong>{isOffline ? 'Không kết nối được backend' : 'Không tải được dữ liệu'}</strong>
      <p>{message}</p>
      {isOffline && (
        <p className="muted">
          Khởi động backend: <code>docker compose up backend</code> hoặc{' '}
          <code>cd backend &amp;&amp; uv run uvicorn fraud_backend.main:app --reload</code>
        </p>
      )}
      {onRetry && (
        <button type="button" className="btn btn--secondary" onClick={onRetry}>
          Thử lại
        </button>
      )}
    </div>
  )
}
