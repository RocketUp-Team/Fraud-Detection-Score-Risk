import { Link } from 'react-router-dom'

import { formatAmount } from '../lib/format'
import { RISK_BAND_LABEL, type Stats } from '../types/api'

/**
 * KPI row + phân bố theo mức rủi ro.
 *
 * Mỗi tile có nhãn text và số hiện rõ (không phải hover mới thấy). Thanh phân
 * bố kèm số đếm + % dạng text để không phụ thuộc màu.
 */
export function StatTiles({ stats }: { stats: Stats }) {
  const maxCount = Math.max(...stats.by_band.map((b) => b.count), 1)

  return (
    <div className="kpi">
      <div className="kpi__row">
        <article className="tile">
          <p className="tile__label">Tổng giao dịch đã chấm</p>
          <p className="tile__value num">{stats.total.toLocaleString('vi-VN')}</p>
        </article>

        <article className="tile tile--accent">
          <p className="tile__label">Đang chờ rà soát</p>
          <p className="tile__value num">{stats.pending_review.toLocaleString('vi-VN')}</p>
          <Link className="tile__link" to="/review">
            Mở hàng chờ
          </Link>
        </article>

        <article className="tile">
          <p className="tile__label">Điểm rủi ro trung bình</p>
          <p className="tile__value num">
            {stats.avg_risk_score}
            <span className="tile__unit">/100</span>
          </p>
        </article>

        <article className="tile">
          <p className="tile__label">Giá trị rủi ro cao</p>
          <p className="tile__value tile__value--sm num">
            {formatAmount(stats.high_risk_amount)}
          </p>
          <p className="tile__hint">Tổng tiền các giao dịch mức Cao + Nghiêm trọng</p>
        </article>
      </div>

      <article className="tile tile--wide">
        <p className="tile__label">Phân bố theo mức rủi ro</p>
        <ul className="dist">
          {stats.by_band.map((b) => {
            const pct = stats.total ? (b.count / stats.total) * 100 : 0
            return (
              <li key={b.band} className="dist__row">
                <Link className="dist__name" to={`/transactions?risk_band=${b.band}`}>
                  {RISK_BAND_LABEL[b.band]}
                </Link>
                <span className="dist__track">
                  <span
                    className={`dist__bar dist__bar--${b.band}`}
                    style={{ width: `${(b.count / maxCount) * 100}%` }}
                  />
                </span>
                <span className="dist__count num">{b.count}</span>
                <span className="dist__pct num">{pct.toFixed(1)}%</span>
              </li>
            )
          })}
        </ul>
      </article>
    </div>
  )
}
