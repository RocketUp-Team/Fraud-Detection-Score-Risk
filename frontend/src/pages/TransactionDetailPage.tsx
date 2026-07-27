import { Link, useParams } from 'react-router-dom'

import { ErrorState, TableSkeleton } from '../components/Feedback'
import { Icon } from '../components/Icon'
import { ReviewPanel } from '../components/ReviewPanel'
import { RiskBadge } from '../components/RiskBadge'
import { ScoreBullet } from '../components/ScoreBullet'
import { ShapChart, ShapUnavailable } from '../components/ShapChart'
import { DecisionBadge } from '../components/StatusBadge'
import { useMeta, useTransaction } from '../hooks/queries'
import { GROUP_LABEL, groupFeatures } from '../lib/featureDocs'
import { formatAmount, formatDateTime, formatFeatureValue, formatProbability } from '../lib/format'

export function TransactionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const txnId = id && /^\d+$/.test(id) ? Number(id) : null
  const { data: meta } = useMeta()
  const { data: txn, isPending, isError, error, refetch } = useTransaction(txnId)

  if (txnId === null) {
    return <ErrorState error={new Error(`Mã giao dịch không hợp lệ: ${id}`)} />
  }
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />
  if (isPending) return <TableSkeleton rows={6} cols={4} />

  const featureGroups = groupFeatures(Object.entries(txn.features))
  const featureCount = Object.keys(txn.features).length

  return (
    <section>
      <nav className="breadcrumb">
        <Link to="/transactions">
          <Icon name="chevron-left" size={16} />
          Danh sách giao dịch
        </Link>
      </nav>

      <header className="page-head">
        <div>
          <h1>
            Giao dịch <span className="num">{txn.transaction_id}</span>
          </h1>
          <p className="muted">
            Chấm lúc {formatDateTime(txn.scored_at)} · model{' '}
            <span className="num">{txn.model_version}</span>
          </p>
        </div>
        <div className="page-head__badges">
          <RiskBadge band={txn.risk_band} score={txn.risk_score} />
          <DecisionBadge decision={txn.decision} />
        </div>
      </header>

      <div className="grid grid--detail">
        <section className="card card--score">
          <h2>Điểm rủi ro</h2>
          <ScoreBullet score={txn.risk_score} band={txn.risk_band} bands={meta?.bands} />
          <dl className="kv">
            <div>
              <dt>Số tiền</dt>
              <dd className="num">{formatAmount(txn.amount)}</dd>
            </div>
            <div>
              <dt>Xác suất gian lận</dt>
              <dd className="num">{formatProbability(txn.fraud_probability)}</dd>
            </div>
            <div>
              <dt>Quyết định hệ thống</dt>
              <dd>
                <DecisionBadge decision={txn.decision} />
              </dd>
            </div>
          </dl>
        </section>

        <section className="card card--shap">
          <h2>Vì sao điểm này? — SHAP top 5</h2>
          {txn.shap_top5 ? (
            <ShapChart items={txn.shap_top5} />
          ) : (
            <ShapUnavailable modelVersion={txn.model_version} />
          )}
        </section>

        <ReviewPanel txn={txn} />

        <section className="card card--features">
          <h2>
            Feature đã dùng để chấm điểm <span className="muted">({featureCount} cột)</span>
          </h2>
          <p className="card__lead muted">
            Gom theo nhóm và giải nghĩa để đọc được khi trình bày. Nhóm ẩn danh chỉ có nghĩa ở
            mức nhóm — Vesta không công bố nghĩa từng cột.
          </p>
          {/* 53 dòng: giới hạn chiều cao và cuộn trong khung, nếu không card này
              dài gấp 4 lần card rà soát bên cạnh và để lại một khoảng trống lớn. */}
          <div className="table-wrap table-wrap--scroll">
            <table className="table table--compact table--features">
              <thead>
                <tr>
                  <th scope="col">Feature</th>
                  <th scope="col">Ý nghĩa</th>
                  <th scope="col" className="ta-right">
                    Giá trị
                  </th>
                </tr>
              </thead>
              {featureGroups.map(({ group, items }) => (
                <tbody key={group}>
                  <tr className="row-group">
                    {/* Tiêu đề nhóm: th trong tbody + scope="rowgroup" để screen
                        reader hiểu đây là nhãn cho cả nhóm dòng bên dưới. */}
                    <th scope="rowgroup" colSpan={3}>
                      {GROUP_LABEL[group]} <span className="muted">({items.length})</span>
                    </th>
                  </tr>
                  {items.map(({ name, value, label }) => (
                    <tr key={name}>
                      <td className="num feature-name">{name}</td>
                      <td className="feature-note">{label || '—'}</td>
                      <td className="num ta-right">{formatFeatureValue(value)}</td>
                    </tr>
                  ))}
                </tbody>
              ))}
            </table>
          </div>
        </section>
      </div>
    </section>
  )
}
