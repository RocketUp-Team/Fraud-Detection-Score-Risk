import { RISK_BAND_LABEL, type RiskBand } from '../types/api'

/**
 * Pill hiển thị mức rủi ro. Luôn có text nhãn — màu chỉ là tín hiệu phụ
 * (rule a11y: không truyền nghĩa chỉ bằng màu).
 */
export function RiskBadge({ band, score }: { band: RiskBand; score?: number }) {
  return (
    <span className={`badge badge--${band}`}>
      {RISK_BAND_LABEL[band]}
      {score !== undefined && <span className="num badge__score">{score}</span>}
    </span>
  )
}
