import {
  DECISION_LABEL,
  REVIEW_STATUS_LABEL,
  type Decision,
  type ReviewStatus,
} from '../types/api'

/** Quyết định tự động của hệ thống (theo band). */
export function DecisionBadge({ decision }: { decision: Decision }) {
  return <span className={`chip chip--${decision}`}>{DECISION_LABEL[decision]}</span>
}

/** Trạng thái rà soát của *người* — khác với DecisionBadge. */
export function ReviewStatusBadge({ status }: { status: ReviewStatus }) {
  return <span className={`chip chip--review-${status}`}>{REVIEW_STATUS_LABEL[status]}</span>
}
