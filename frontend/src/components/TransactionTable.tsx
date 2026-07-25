import { Link } from 'react-router-dom'

import { formatAmount, formatDateTime, formatProbability } from '../lib/format'
import type { Transaction } from '../types/api'
import { RiskBadge } from './RiskBadge'
import { DecisionBadge, ReviewStatusBadge } from './StatusBadge'

/**
 * Bảng giao dịch, dùng chung cho màn danh sách và màn rà soát.
 * Bọc trong overflow-x: auto để không làm vỡ layout trên mobile.
 */
export function TransactionTable({ items }: { items: Transaction[] }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <caption className="sr-only">
          Danh sách giao dịch kèm điểm rủi ro, quyết định của hệ thống và trạng thái rà soát
        </caption>
        <thead>
          <tr>
            <th scope="col">Mã giao dịch</th>
            <th scope="col" className="ta-right">
              Số tiền
            </th>
            <th scope="col" className="ta-right">
              Xác suất
            </th>
            <th scope="col">Mức rủi ro</th>
            <th scope="col">Hệ thống</th>
            <th scope="col">Rà soát</th>
            <th scope="col">Thời điểm chấm</th>
            <th scope="col">
              <span className="sr-only">Hành động</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((txn) => (
            <tr key={txn.transaction_id}>
              <td className="num">{txn.transaction_id}</td>
              <td className="num ta-right">{formatAmount(txn.amount)}</td>
              <td className="num ta-right">{formatProbability(txn.fraud_probability)}</td>
              <td>
                <RiskBadge band={txn.risk_band} score={txn.risk_score} />
              </td>
              <td>
                <DecisionBadge decision={txn.decision} />
              </td>
              <td>
                <ReviewStatusBadge status={txn.review_status} />
              </td>
              <td className="muted">{formatDateTime(txn.scored_at)}</td>
              <td>
                <Link className="btn btn--link" to={`/transactions/${txn.transaction_id}`}>
                  Chi tiết
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
