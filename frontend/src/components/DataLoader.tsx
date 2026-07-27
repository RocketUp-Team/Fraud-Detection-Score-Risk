import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import {
  useActiveJob,
  useCancelJob,
  useDatasets,
  useJob,
  useStartLoad,
} from '../hooks/queries'
import { useStats } from '../hooks/queries'
import type { LoadMode } from '../types/api'
import { Icon } from './Icon'

/**
 * Nạp N giao dịch từ bộ IEEE-CIS đã tiền xử lý — người dùng tự nhập số.
 *
 * Chạy nền ở backend (`POST /data/load` trả 202 + job_id) rồi poll tiến độ, chứ
 * không chờ trong một request: 50.000 dòng mất vài phút, giữ request mở suốt
 * thời gian đó thì proxy cắt và người dùng không thấy gì đang chạy.
 */
const QUICK_PICKS = [500, 5_000, 50_000]
const PERCENT_PICKS = [1, 10, 20]
const PER_BAND_PICKS = [10, 20, 50]

/**
 * Ba plan nạp. `short` hiện trên thẻ chọn, `long` chỉ hiện cho plan ĐANG chọn —
 * ba đoạn mô tả dài xếp dọc làm card cao gấp rưỡi card bên cạnh.
 */
const PLANS: { mode: LoadMode; title: string; short: string; long: string }[] = [
  {
    mode: 'coverage',
    title: 'Đủ 5 mức',
    short: 'Thấp → Nghiêm trọng',
    long: 'Bộ nhỏ có đủ ca ở cả 5 mức để đi hết các trường hợp khi trình bày. Model chấm lần lượt và chỉ giữ ca thuộc mức còn thiếu.',
  },
  {
    mode: 'sample',
    title: 'Mẫu ngẫu nhiên',
    short: 'Sát thực tế nhất',
    long: 'Rải đều toàn bộ dữ liệu nên tỉ lệ gian lận sát thực tế. Có seed nên nạp lại ra đúng mẫu cũ.',
  },
  {
    mode: 'head',
    title: 'N dòng đầu',
    short: 'Nhanh, không đại diện',
    long: 'Nhanh nhất, nhưng là một khối liền trong 1–2 file part nên không đại diện cho cả bộ.',
  },
]

export function DataLoader() {
  const queryClient = useQueryClient()
  const { data: datasets, isPending: datasetsPending } = useDatasets()
  const { data: activeJob } = useActiveJob()
  const { data: stats } = useStats()

  const [dataset, setDataset] = useState('holdout')
  const [mode, setMode] = useState<LoadMode>('coverage')
  const [limit, setLimit] = useState('5000')
  const [perBand, setPerBand] = useState('20')
  const [seed, setSeed] = useState('42')
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
  const perBandNum = Number(perBand)
  const limitValid = Number.isInteger(limitNum) && limitNum >= 1 && limitNum <= 100_000
  const perBandValid = Number.isInteger(perBandNum) && perBandNum >= 1 && perBandNum <= 500
  const inputValid = mode === 'coverage' ? perBandValid : limitValid
  const running = job?.status === 'running'
  // Xin nhiều hơn số dòng có thật thì backend tự cắt — nói trước cho người dùng biết.
  const willBeCapped = Boolean(
    mode === 'head' && selected && limitValid && limitNum > selected.rows,
  )

  return (
    <section className="card card--load">
      <h2>Nạp dữ liệu từ bộ IEEE-CIS</h2>
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
              {d.recommended ? '★ ' : ''}
              {d.name} — {d.rows.toLocaleString('vi-VN')} dòng
              {d.fraud_rate !== null ? `, ${(d.fraud_rate * 100).toFixed(2)}% gian lận` : ''}
            </option>
          ))}
        </select>
        {selected && (
          <p className={selected.recommended ? 'field__hint' : 'field__warn'}>{selected.note}</p>
        )}
      </div>

      <fieldset className="plans">
        <legend className="field__legend">Plan nạp</legend>
        <div className="plans__row">
          {PLANS.map((plan) => (
            <label key={plan.mode} className={`plan${mode === plan.mode ? ' is-active' : ''}`}>
              <input
                type="radio"
                name="load-mode"
                value={plan.mode}
                checked={mode === plan.mode}
                disabled={running}
                onChange={() => setMode(plan.mode)}
              />
              <span className="plan__text">
                <strong>{plan.title}</strong>
                <span className="plan__desc">{plan.short}</span>
              </span>
            </label>
          ))}
        </div>
        <p className="plans__note">{PLANS.find((p) => p.mode === mode)?.long}</p>
      </fieldset>

      {mode === 'coverage' ? (
        <div className="field">
          <label htmlFor="dl-perband">Số ca mỗi mức</label>
          <input
            id="dl-perband"
            type="number"
            min={1}
            max={500}
            value={perBand}
            disabled={running}
            aria-invalid={!perBandValid}
            onChange={(e) => setPerBand(e.target.value)}
          />
          {!perBandValid && <p className="field__error">Nhập số từ 1 đến 500.</p>}
          {perBandValid && (
            <p className="field__hint">
              Tổng <span className="num">{perBandNum * 5}</span> giao dịch (5 mức ×{' '}
              <span className="num">{perBandNum}</span>)
            </p>
          )}
          <div className="quick-picks">
            {PER_BAND_PICKS.map((n) => (
              <button
                key={n}
                type="button"
                className={`chat__chip${perBandNum === n ? ' is-active' : ''}`}
                disabled={running}
                onClick={() => setPerBand(String(n))}
              >
                {n}/mức
              </button>
            ))}
          </div>
        </div>
      ) : (
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
                className={`chat__chip${limitNum === n ? ' is-active' : ''}`}
                disabled={running}
                onClick={() => setLimit(String(n))}
              >
                {n.toLocaleString('vi-VN')}
              </button>
            ))}
            {selected &&
              PERCENT_PICKS.map((pct) => {
                const n = Math.min(100_000, Math.round((selected.rows * pct) / 100))
                return (
                  <button
                    key={`pct-${pct}`}
                    type="button"
                    className={`chat__chip${limitNum === n ? ' is-active' : ''}`}
                    disabled={running}
                    title={`${pct}% của ${selected.rows.toLocaleString('vi-VN')} dòng = ${n.toLocaleString('vi-VN')}`}
                    onClick={() => setLimit(String(n))}
                  >
                    {pct}%
                  </button>
                )
              })}
          </div>

          {mode === 'sample' && (
            <p className="field__hint">
              Seed <span className="num">{seed}</span> — cùng seed thì nạp lại ra đúng mẫu cũ.{' '}
              <button
                type="button"
                className="btn btn--link"
                disabled={running}
                onClick={() => setSeed(String(Math.floor(Math.random() * 10000)))}
              >
                Đổi mẫu
              </button>
            </p>
          )}
        </div>
      )}

      <label className="check">
        <input
          type="checkbox"
          checked={reset}
          disabled={running}
          onChange={(e) => setReset(e.target.checked)}
        />
        Xoá{' '}
        {stats && stats.total > 0 ? (
          <>
            toàn bộ <span className="num">{stats.total.toLocaleString('vi-VN')}</span> giao dịch
            hiện có
          </>
        ) : (
          'dữ liệu cũ'
        )}{' '}
        trước khi nạp
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

      {/* Nạp xong thì phải có đường đi tiếp — không thì người dùng đứng lại ở
          đây không biết dữ liệu vừa nạp nằm đâu. */}
      {job && job.status !== 'running' && job.processed > 0 && (
        <div className="callout callout--ok done-actions" role="status">
          <strong>
            Đã chấm điểm và lưu {job.processed.toLocaleString('vi-VN')} giao dịch.
          </strong>
          <div className="done-actions__row">
            <Link className="btn btn--primary" to="/transactions">
              <Icon name="transactions" size={18} />
              Xem danh sách giao dịch
            </Link>
            <Link className="btn btn--secondary" to="/review">
              <Icon name="review" size={18} />
              Vào hàng chờ rà soát
            </Link>
          </div>
        </div>
      )}

      <div className="review__actions">
        <button
          type="button"
          className="btn btn--primary"
          disabled={!inputValid || running || start.isPending}
          onClick={() =>
            start.mutate(
              {
                dataset,
                limit: limitNum,
                reset,
                mode,
                per_band: perBandNum,
                seed: Number(seed) || 42,
              },
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

      <p className="field__hint card__foot-note">
        ~125 giao dịch/giây · chạy nền, rời trang vẫn giữ tiến độ
      </p>
    </section>
  )
}
