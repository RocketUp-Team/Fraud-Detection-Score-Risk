import { useState } from 'react'

import { useSubmitReview } from '../hooks/queries'
import { formatDateTime } from '../lib/format'
import { REVIEW_STATUS_LABEL, type ReviewLabel, type TransactionDetail } from '../types/api'

/**
 * Màn rà soát: duyệt / từ chối + gắn nhãn thủ công.
 *
 * Form UX: label hiện rõ (không dùng placeholder làm label), lỗi hiện cạnh
 * form, nút disable + đổi text trong lúc gửi để có feedback tức thì.
 */
export function ReviewPanel({ txn }: { txn: TransactionDetail }) {
  const [label, setLabel] = useState<ReviewLabel>(
    txn.review?.label ?? (txn.risk_score >= 60 ? 'fraud' : 'legit'),
  )
  const [reviewer, setReviewer] = useState(txn.review?.reviewer ?? '')
  const [note, setNote] = useState(txn.review?.note ?? '')

  const mutation = useSubmitReview(txn.transaction_id)

  function submit(action: 'approve' | 'reject') {
    mutation.mutate({
      action,
      label,
      reviewer: reviewer.trim() || undefined,
      note: note.trim() || undefined,
    })
  }

  return (
    <section className="card">
      <h2>Rà soát thủ công</h2>

      {txn.review ? (
        <p className="review__current">
          Đã xử lý: <strong>{REVIEW_STATUS_LABEL[txn.review.status]}</strong>
          {txn.review.label && <> · nhãn: <strong>{txn.review.label}</strong></>}
          {txn.review.reviewer && <> · bởi {txn.review.reviewer}</>}
          <br />
          <span className="muted">Cập nhật {formatDateTime(txn.review.updated_at)}</span>
        </p>
      ) : (
        <p className="muted">Giao dịch này chưa được ai rà soát.</p>
      )}

      <div className="field">
        <label htmlFor="r-label">Nhãn thủ công</label>
        <select
          id="r-label"
          value={label}
          onChange={(e) => setLabel(e.target.value as ReviewLabel)}
        >
          <option value="fraud">Gian lận (fraud)</option>
          <option value="legit">Hợp lệ (legit)</option>
        </select>
        <p className="field__hint">Nhãn này dùng để đối chiếu với dự đoán của model.</p>
      </div>

      <div className="field">
        <label htmlFor="r-reviewer">Người rà soát</label>
        <input
          id="r-reviewer"
          type="text"
          value={reviewer}
          onChange={(e) => setReviewer(e.target.value)}
          maxLength={64}
        />
      </div>

      <div className="field">
        <label htmlFor="r-note">Ghi chú</label>
        <textarea
          id="r-note"
          rows={3}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={1000}
        />
        <p className="field__hint">Lý do quyết định — hữu ích khi trình bày ca demo.</p>
      </div>

      {mutation.isError && (
        <p className="callout callout--error" role="alert">
          Không lưu được: {(mutation.error as Error).message}
        </p>
      )}
      {mutation.isSuccess && (
        <p className="callout callout--ok" role="status">
          Đã lưu quyết định rà soát.
        </p>
      )}

      <div className="review__actions">
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => submit('approve')}
          disabled={mutation.isPending}
        >
          {mutation.isPending ? 'Đang lưu…' : 'Duyệt giao dịch'}
        </button>
        <button
          type="button"
          className="btn btn--danger"
          onClick={() => submit('reject')}
          disabled={mutation.isPending}
        >
          {mutation.isPending ? 'Đang lưu…' : 'Từ chối giao dịch'}
        </button>
      </div>
    </section>
  )
}
