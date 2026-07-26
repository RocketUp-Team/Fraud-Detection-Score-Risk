import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { Icon } from '../components/Icon'
import { ScoreBullet } from '../components/ScoreBullet'
import { ShapChart, ShapUnavailable } from '../components/ShapChart'
import { DecisionBadge } from '../components/StatusBadge'
import { useMeta } from '../hooks/queries'
import { api } from '../lib/api'
import { formatProbability } from '../lib/format'
import type { ScoreResponse } from '../types/api'

/**
 * Chấm điểm 1 giao dịch nhập tay bằng `POST /score` — KHÔNG ghi DB.
 *
 * Đây là màn cho thấy model đang thật sự chạy: đổi số tiền / loại thẻ là điểm
 * và SHAP đổi theo ngay.
 *
 * Giá trị categorical lấy đúng theo `DATA_DICTIONARY.md`; `__MISSING__` là
 * category tường minh mà pipeline của An dùng cho ô trống, không phải null.
 */
const CATEGORICAL_OPTIONS = {
  ProductCD: ['W', 'C', 'R', 'H', 'S'],
  card4: ['visa', 'mastercard', 'american express', 'discover'],
  card6: ['debit', 'credit', '__MISSING__'],
  DeviceType: ['desktop', 'mobile', '__MISSING__'],
  device_family: ['windows', 'ios', 'android', 'macos', '__MISSING__'],
  M4: ['M0', 'M1', 'M2', '__MISSING__'],
} as const

const LABELS: Record<string, string> = {
  ProductCD: 'Loại sản phẩm (ProductCD)',
  card4: 'Nhà phát hành thẻ (card4)',
  card6: 'Loại thẻ (card6)',
  DeviceType: 'Loại thiết bị (DeviceType)',
  device_family: 'Hệ điều hành (device_family)',
  M4: 'Cờ khớp M4',
}

type CategoricalKey = keyof typeof CATEGORICAL_OPTIONS

const DEFAULTS: Record<CategoricalKey, string> = {
  ProductCD: 'W',
  card4: 'visa',
  card6: 'credit',
  DeviceType: 'mobile',
  device_family: 'android',
  M4: '__MISSING__',
}

export function ScorePage() {
  const { data: meta } = useMeta()

  const [amount, setAmount] = useState('4899')
  const [cats, setCats] = useState<Record<CategoricalKey, string>>(DEFAULTS)
  const [hasIdentity, setHasIdentity] = useState(true)
  const [hasDeviceInfo, setHasDeviceInfo] = useState(true)
  const [priorCardCount, setPriorCardCount] = useState('1')

  const mutation = useMutation({
    mutationFn: (features: Record<string, string | number | null>) => api.score({ features }),
  })

  const expectedCount = meta?.n_features ?? 0

  const amountNum = Number(amount)
  const amountValid = amount !== '' && Number.isFinite(amountNum) && amountNum >= 0
  // Mã giao dịch IEEE-CIS là số 7 chữ số (2987xxx) nên rất dễ bị dán vào đây.
  // Không chặn — chỉ nhắc, vì biết đâu có giao dịch lớn thật.
  const amountSuspiciouslyLarge = amountValid && amountNum >= 100_000

  function buildFeatures(): Record<string, string | number | null> {
    return {
      TransactionAmt: amountNum,
      // log1p(amount) — đúng theo định nghĩa `log_transaction_amount` trong
      // DATA_DICTIONARY.md, tính được chắc chắn nên gửi luôn.
      log_transaction_amount: Math.log1p(amountNum),
      ...cats,
      has_identity: hasIdentity ? 1 : 0,
      has_device_info: hasDeviceInfo ? 1 : 0,
      prior_card_transaction_count: Number(priorCardCount) || 0,
    }
  }

  // Đếm từ chính payload, không đếm tay — sửa form là con số tự đúng theo.
  const providedCount = Object.keys(buildFeatures()).length

  function submit() {
    if (!amountValid) return
    mutation.mutate(buildFeatures())
  }

  const result: ScoreResponse | undefined = mutation.data

  return (
    <section>
      <header className="page-head">
        <div>
          <h1>Chấm điểm thử</h1>
          <p>
            Nhập một giao dịch, model sẽ chấm ngay qua <code>POST /score</code>. Kết quả{' '}
            <strong>không lưu vào cơ sở dữ liệu</strong> — dùng để thử phản ứng của model.
          </p>
        </div>
      </header>

      <div className="grid grid--detail">
        <section className="card">
          <h2>Thông tin giao dịch</h2>

          <div className="field">
            <label htmlFor="s-amount">Số tiền (TransactionAmt)</label>
            <input
              id="s-amount"
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              value={amount}
              aria-invalid={!amountValid}
              aria-describedby={amountValid ? undefined : 's-amount-err'}
              onChange={(e) => setAmount(e.target.value)}
            />
            {/* Lỗi hiện ngay cạnh field, không dồn lên đầu form */}
            {!amountValid && (
              <p className="field__error" id="s-amount-err">
                Nhập một số ≥ 0.
              </p>
            )}
            {amountSuspiciouslyLarge && (
              <p className="field__warn">
                Đây là <strong>số tiền</strong>, không phải mã giao dịch.{' '}
                <span className="num">{amountNum.toLocaleString('vi-VN')}</span> USD là lớn bất
                thường — nếu bạn đang muốn xem một giao dịch đã có, dùng ô tìm kiếm ở màn{' '}
                <Link to="/transactions">Giao dịch</Link> hoặc gõ{' '}
                <code>giao dịch {amount}</code> trong trợ lý.
              </p>
            )}
          </div>

          {(Object.keys(CATEGORICAL_OPTIONS) as CategoricalKey[]).map((key) => (
            <div className="field" key={key}>
              <label htmlFor={`s-${key}`}>{LABELS[key]}</label>
              <select
                id={`s-${key}`}
                value={cats[key]}
                onChange={(e) => setCats((prev) => ({ ...prev, [key]: e.target.value }))}
              >
                {CATEGORICAL_OPTIONS[key].map((opt) => (
                  <option key={opt} value={opt}>
                    {opt === '__MISSING__' ? 'thiếu dữ liệu' : opt}
                  </option>
                ))}
              </select>
            </div>
          ))}

          <div className="field">
            <label htmlFor="s-prior">Số giao dịch trước đó của thẻ</label>
            <input
              id="s-prior"
              type="number"
              min="0"
              step="1"
              value={priorCardCount}
              onChange={(e) => setPriorCardCount(e.target.value)}
            />
            <p className="field__hint">Thẻ mới (0–1) thường bị model đánh giá rủi ro hơn.</p>
          </div>

          <div className="checks">
            <label className="check">
              <input
                type="checkbox"
                checked={hasIdentity}
                onChange={(e) => setHasIdentity(e.target.checked)}
              />
              Có dữ liệu định danh (has_identity)
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={hasDeviceInfo}
                onChange={(e) => setHasDeviceInfo(e.target.checked)}
              />
              Có thông tin thiết bị (has_device_info)
            </label>
          </div>

          <button
            type="button"
            className="btn btn--primary"
            onClick={submit}
            disabled={!amountValid || mutation.isPending}
          >
            <Icon name="calculator" size={18} />
            {mutation.isPending ? 'Đang chấm điểm…' : 'Chấm điểm'}
          </button>

          <div className="callout callout--warn" style={{ marginTop: 'var(--space-4)' }}>
            <strong>
              Form này cung cấp <span className="num">{providedCount}</span>
              {expectedCount > 0 && (
                <>
                  /<span className="num">{expectedCount}</span>
                </>
              )}{' '}
              feature model cần.
            </strong>
            <p>
              Phần còn lại (các biến đếm C1–C14, D1–D15, lịch sử email/thiết bị, missingness)
              được điền giá trị mặc định. Hệ quả thực tế: với số tiền lớn, điểm hay bị{' '}
              <em>bão hoà</em> — 1.500 và 25.000 có thể ra cùng một điểm vì các nhánh cây tách
              trên số tiền đều ở ngưỡng thấp. Muốn điểm chuẩn thì chấm theo lô từ dữ liệu đầy
              đủ (màn <strong>Nhập CSV</strong>).
            </p>
          </div>
        </section>

        <section className="card">
          <h2>Kết quả</h2>

          {mutation.isError && (
            <p className="callout callout--error" role="alert">
              Không chấm được điểm: {(mutation.error as Error).message}
            </p>
          )}

          {!result && !mutation.isError && (
            <p className="muted">Nhập thông tin bên cạnh rồi bấm “Chấm điểm”.</p>
          )}

          {result && (
            <>
              <ScoreBullet
                score={result.risk_score}
                band={result.risk_band}
                bands={meta?.bands}
              />
              <dl className="kv">
                <div>
                  <dt>Xác suất gian lận</dt>
                  <dd className="num">{formatProbability(result.fraud_probability)}</dd>
                </div>
                <div>
                  <dt>Quyết định hệ thống</dt>
                  <dd>
                    <DecisionBadge decision={result.decision} />
                  </dd>
                </div>
                <div>
                  <dt>Model</dt>
                  <dd className="num" style={{ fontSize: '0.9375rem' }}>
                    {result.model_version}
                  </dd>
                </div>
              </dl>
            </>
          )}
        </section>

        {result && (
          <section className="card card--wide">
            <h2>Vì sao điểm này? — SHAP top 5</h2>
            {result.shap_top5 ? (
              <ShapChart items={result.shap_top5} />
            ) : (
              <ShapUnavailable modelVersion={result.model_version} />
            )}
          </section>
        )}
      </div>
    </section>
  )
}
