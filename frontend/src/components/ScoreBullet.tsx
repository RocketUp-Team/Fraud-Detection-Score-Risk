import { RISK_BAND_LABEL, type BandRange, type RiskBand } from '../types/api'

/**
 * Bullet chart cho điểm rủi ro (skill ui-ux-pro-max: "Performance vs Target
 * (Compact)" — accessibility AAA, gọn hơn gauge).
 *
 * Quy tắc a11y đi kèm: giá trị số LUÔN hiện dạng text, không chỉ hover; các
 * vùng ngưỡng có nhãn text chứ không chỉ màu.
 */

const FALLBACK_BANDS: BandRange[] = [
  { band: 'low', min: 0, max: 19 },
  { band: 'guarded', min: 20, max: 39 },
  { band: 'medium', min: 40, max: 59 },
  { band: 'high', min: 60, max: 79 },
  { band: 'critical', min: 80, max: 100 },
]

type Props = {
  score: number
  band: RiskBand
  bands?: BandRange[]
  /** Ngưỡng nghiệp vụ cần đánh dấu (mặc định 60 = bắt đầu rủi ro cao). */
  threshold?: number
}

export function ScoreBullet({ score, band, bands = FALLBACK_BANDS, threshold = 60 }: Props) {
  const clamped = Math.max(0, Math.min(100, score))

  return (
    <div className="bullet">
      <div className="bullet__head">
        <span className="bullet__value num">{clamped}</span>
        <span className="bullet__scale">/ 100</span>
        <span className={`bullet__band bullet__band--${band}`}>{RISK_BAND_LABEL[band]}</span>
      </div>

      <div
        className="bullet__track"
        role="meter"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Điểm rủi ro ${clamped} trên 100, mức ${RISK_BAND_LABEL[band]}`}
      >
        {/* Vùng ngưỡng định tính */}
        {bands.map((b) => (
          <span
            key={b.band}
            className={`bullet__zone bullet__zone--${b.band}`}
            style={{ left: `${b.min}%`, width: `${b.max - b.min + 1}%` }}
          />
        ))}
        {/* Thanh giá trị */}
        <span className={`bullet__bar bullet__bar--${band}`} style={{ width: `${clamped}%` }} />
        {/* Marker ngưỡng */}
        <span
          className="bullet__threshold"
          style={{ left: `${threshold}%` }}
          aria-hidden="true"
        />
      </div>

      <div className="bullet__legend">
        {bands.map((b) => (
          <span key={b.band} className="bullet__legend-item">
            <span className={`bullet__swatch bullet__swatch--${b.band}`} aria-hidden="true" />
            {RISK_BAND_LABEL[b.band]} <span className="num">{b.min}–{b.max}</span>
          </span>
        ))}
      </div>
      <p className="bullet__note">
        Ngưỡng cần rà soát: <span className="num">{threshold}</span>
      </p>
    </div>
  )
}
