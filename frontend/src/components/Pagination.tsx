type Props = {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, pageSize, total, onPageChange }: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, total)

  return (
    <nav className="pagination" aria-label="Phân trang">
      <p className="pagination__info">
        Hiển thị <span className="num">{from}</span>–<span className="num">{to}</span> trong{' '}
        <span className="num">{total}</span> giao dịch
      </p>
      <div className="pagination__controls">
        <button
          type="button"
          className="btn btn--secondary"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
        >
          ← Trước
        </button>
        <span className="pagination__page num">
          {page} / {totalPages}
        </span>
        <button
          type="button"
          className="btn btn--secondary"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
        >
          Sau →
        </button>
      </div>
    </nav>
  )
}
