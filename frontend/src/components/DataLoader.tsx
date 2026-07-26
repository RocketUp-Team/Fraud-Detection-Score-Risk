import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import {
  useActiveJob,
  useCancelJob,
  useDatasets,
  useJob,
  useStartLoad,
} from '../hooks/queries'
import { Icon } from './Icon'

/**
 * Nạp N giao dịch từ bộ IEEE-CIS đã tiền xử lý — người dùng tự nhập số.
 *
 * Chạy nền ở backend (`POST /data/load` trả 202 + job_id) rồi poll tiến độ, chứ
 * không chờ trong một request: 50.000 dòng mất vài phút, giữ request mở suốt
 * thời gian đó thì proxy cắt và người dùng không thấy gì đang chạy.
 */
const QUICK_PICKS = [500, 5_000, 50_000]

export function DataLoader() {
  const queryClient = useQueryClient()
  const { data: datasets, isPending: datasetsPending } = useDatasets()
  const { data: activeJob } = useActiveJob()

  const [dataset, setDataset] = useState('holdout')
  const [limit, setLimit] = useState('5000')
  const [reset, setReset] = useState(true)
  const [jobId, setJobId] = useState<string | null>(null)

  const start = useStartLoad()
  const cancel = useCancelJob()
  const { data: job } = useJob(jobId)

  // Nếu có job đang chạy lúc mở trang (vd vừa F5 giữa lúc nạp) thì nối lại.
  useEffect(() => {
    if (activeJob && activeJob.status === 'running' && !jobId) setJobId(activeJob.id)
  }, [activeJob, jobId])

  // Job xong -> làm mới danh sách và KPI để số trên dashboard khớp DB ngay.
  useEffect(() => {
    if (job && job.status !== 'running') {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    }
  }, [job?.status, job, queryClient])

  const selected = datasets?.find((d) => d.name === dataset)
  const limitNum = Number(limit)
  const limitValid = Number.isInteger(limitNum) && limitNum >= 1 && limitNum <= 100_000
  const running = job?.status === 'running'
  // Xin nhiều hơn số dòng có thật thì backend tự cắt — nói trước cho người dùng biết.
  const willBeCapped = Boolean(selected && limitValid && limitNum > selected.rows)

  return (
    <section className="card card--load">
      <h2>Nạp dữ liệu từ bộ IEEE-CIS</h2>
      <p className="muted" style={{ marginTop: 0 }}>
        Chọn số giao dịch cần nạp. Mỗi dòng được model chấm điểm rồi lưu vào DB, chạy nền nên
        bạn có thể rời trang.
      </p>

      <div className="field">
        <label htmlFor="dl-dataset">Bộ dữ liệu</label>
        <select
          id="dl-dataset"
          value={dataset}
          disabled={running || datasetsPending}
          onChange={(e) => setDataset(e.target.value)}
        >
          {(datasets ?? []).map((d) => (
            <option key={d.name} value={d.name}>
              {d.name} — {d.rows.toLocaleString('vi-VN')} dòng
              {d.recommended ? ' (nên dùng)' : ''}
            </option>
          ))}
        </select>
        {selected && (
          <p className={selected.recommended ? 'field__hint' : 'field__warn'}>{selected.note}</p>
        )}
      </div>

      <div className="field">
        <label htmlFor="dl-limit">Số giao dịch</label>
        <input
          id="dl-limit"
          type="number"
          min={1}
          max={100000}
          step={100}
          value={limit}
          disabled={running}
          aria-invalid={!limitValid}
          onChange={(e) => setLimit(e.target.value)}
        />
        {!limitValid && <p className="field__error">Nhập số từ 1 đến 100.000.</p>}
        {willBeCapped && selected && (
          <p className="field__warn">
            Bộ này chỉ có {selected.rows.toLocaleString('vi-VN')} dòng — sẽ nạp tối đa bằng đó.
          </p>
        )}
        <div className="quick-picks">
          {QUICK_PICKS.map((n) => (
            <button
              key={n}
              type="button"
              className={`chat__chip${Number(limit) === n ? ' is-active' : ''}`}
              disabled={running}
              onClick={() => setLimit(String(n))}
            >
              {n.toLocaleString('vi-VN')}
            </button>
          ))}
          {selected && (
            <button
              type="button"
              className="chat__chip"
              disabled={running}
              onClick={() => setLimit(String(Math.min(selected.rows, 100_000)))}
            >
              tối đa
            </button>
          )}
        </div>
      </div>

      <label className="check">
        <input
          type="checkbox"
          checked={reset}
          disabled={running}
          onChange={(e) => setReset(e.target.checked)}
        />
        Xoá dữ liệu cũ trước khi nạp
      </label>

      {start.isError && (
        <p className="callout callout--error" role="alert">
          {(start.error as Error).message}
        </p>
      )}

      {job && (
        <div className={`progress progress--${job.status}`} role="status" aria-live="polite">
          <div className="progress__head">
            <span>
              {job.status === 'running' && 'Đang chấm điểm…'}
              {job.status === 'done' && 'Đã nạp xong'}
              {job.status === 'cancelled' && 'Đã dừng — phần đã chấm vẫn được giữ'}
              {job.status === 'error' && 'Lỗi'}
            </span>
            <span className="num">
              {job.processed.toLocaleString('vi-VN')} / {job.total.toLocaleString('vi-VN')}
            </span>
          </div>
          <div
            className="progress__track"
            role="progressbar"
            aria-valuenow={job.percent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Tiến độ nạp dữ liệu"
          >
            <span className="progress__bar" style={{ width: `${job.percent}%` }} />
          </div>
          {job.error && <p className="field__error">{job.error}</p>}
        </div>
      )}

      <div className="review__actions">
        <button
          type="button"
          className="btn btn--primary"
          disabled={!limitValid || running || start.isPending}
          onClick={() =>
            start.mutate(
              { dataset, limit: limitNum, reset },
              { onSuccess: (j) => setJobId(j.id) },
            )
          }
        >
          <Icon name="upload" size={18} />
          {running ? 'Đang nạp…' : start.isPending ? 'Đang bắt đầu…' : 'Nạp dữ liệu'}
        </button>
        {running && jobId && (
          <button
            type="button"
            className="btn btn--secondary"
            disabled={cancel.isPending}
            onClick={() => cancel.mutate(jobId)}
          >
            Dừng
          </button>
        )}
      </div>

      <p className="field__hint" style={{ marginTop: 'var(--space-3)' }}>
        Tốc độ chấm khoảng 225 giao dịch/giây — 5.000 dòng mất ~25 giây, 50.000 dòng ~4 phút.
      </p>
    </section>
  )
}
