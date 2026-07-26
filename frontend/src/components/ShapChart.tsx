import { describeFeature } from '../lib/featureDocs'
import { formatSigned } from '../lib/format'
import type { ShapContribution } from '../types/api'

/**
 * Diverging bar ngang cho SHAP top-5.
 *
 * - Dương (đỏ) = đẩy về phía gian lận; âm (xanh) = kéo về phía hợp lệ.
 * - Mỗi dòng đều in giá trị có dấu +/− dạng text → không phụ thuộc màu.
 * - Bảng dữ liệu thô là fallback a11y bắt buộc cho chart (rule "Charts & Data").
 */
export function ShapChart({ items }: { items: ShapContribution[] }) {
  if (items.length === 0) {
    return <p className="muted">Model không trả về đóng góp feature nào.</p>
  }

  const maxAbs = Math.max(...items.map((i) => Math.abs(i.shap_value))) || 1

  return (
    <div className="shap">
      <div className="shap__axis-labels" aria-hidden="true">
        <span>← hợp lệ</span>
        <span>gian lận →</span>
      </div>

      <ul className="shap__list">
        {items.map((item) => {
          const positive = item.shap_value >= 0
          // Nửa trái/phải mỗi bên 50% chiều rộng; bar dài theo |value| / maxAbs.
          const width = (Math.abs(item.shap_value) / maxAbs) * 50
          return (
            <li key={item.feature} className="shap__row">
              <span className="shap__feature-cell">
                <span className="shap__feature">{item.feature}</span>
                {describeFeature(item.feature).label && (
                  <span className="shap__feature-note">
                    {describeFeature(item.feature).label}
                  </span>
                )}
              </span>
              <span className="shap__track">
                <span className="shap__zero" aria-hidden="true" />
                <span
                  className={`shap__bar shap__bar--${positive ? 'positive' : 'negative'}`}
                  style={
                    positive
                      ? { left: '50%', width: `${width}%` }
                      : { right: '50%', width: `${width}%` }
                  }
                />
              </span>
              <span className="shap__value num">{formatSigned(item.shap_value)}</span>
            </li>
          )
        })}
      </ul>

      <details className="shap__data">
        <summary>Xem dạng bảng số</summary>
        {/* Bọc overflow: bảng 3 cột từng bị cắt mất cột "Hướng tác động" */}
        <div className="table-wrap">
          <table className="table table--compact">
            <thead>
              <tr>
                <th scope="col">Feature</th>
                <th scope="col">Ý nghĩa</th>
                <th scope="col" className="ta-right">
                  SHAP
                </th>
                <th scope="col">Hướng tác động</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.feature}>
                  <td className="shap__cell-name">{item.feature}</td>
                  <td className="feature-note">{describeFeature(item.feature).label || '—'}</td>
                  <td className="num ta-right">{formatSigned(item.shap_value)}</td>
                  <td>{item.shap_value >= 0 ? 'Tăng rủi ro' : 'Giảm rủi ro'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}

/** Trạng thái khi backend trả `shap_top5: null` (model fallback không có SHAP). */
export function ShapUnavailable({ modelVersion }: { modelVersion: string }) {
  return (
    <div className="callout callout--warn">
      <strong>Chưa có giải thích SHAP cho giao dịch này.</strong>
      <p>
        Model đang phục vụ (<span className="num">{modelVersion}</span>) là bản dự phòng
        Logistic Regression, không sinh SHAP. Điểm rủi ro vẫn hợp lệ. Khi model cây
        (LightGBM/XGBoost/CatBoost) được nạp, phần này sẽ tự hiển thị.
      </p>
    </div>
  )
}
