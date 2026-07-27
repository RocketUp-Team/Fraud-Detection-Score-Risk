/**
 * Giải nghĩa tên feature sang tiếng Việt, để bảng feature và biểu đồ SHAP đọc
 * được mà không phải tra tài liệu.
 *
 * Nguồn: `DATA_DICTIONARY.md` (feature do pipeline của An sinh ra) và mô tả
 * nhóm mà Vesta công bố trong cuộc thi IEEE-CIS (nhóm C/D/M/dist).
 *
 * QUY TẮC: với nhóm ẩn danh, chỉ nói ĐÚNG những gì Vesta công bố — đó là nghĩa
 * của cả nhóm. Không suy diễn nghĩa cho từng cột, vì Vesta không công bố.
 */

export type FeatureGroup =
  | 'amount'
  | 'time'
  | 'missing'
  | 'presence'
  | 'history'
  | 'category'
  | 'anonymous'
  | 'other'

export const GROUP_LABEL: Record<FeatureGroup, string> = {
  amount: 'Số tiền',
  time: 'Thời gian',
  presence: 'Có/không có dữ liệu',
  missing: 'Mức độ thiếu dữ liệu',
  history: 'Lịch sử của thẻ / email / thiết bị',
  category: 'Phân loại',
  anonymous: 'Biến ẩn danh của Vesta',
  other: 'Khác',
}

type Doc = { label: string; group: FeatureGroup }

const EXACT: Record<string, Doc> = {
  TransactionAmt: { label: 'Số tiền giao dịch (USD)', group: 'amount' },
  log_transaction_amount: {
    label: 'log(1 + số tiền) — nén khoảng giá trị để model học dễ hơn',
    group: 'amount',
  },
  amount_decimal: { label: 'Phần thập phân của số tiền', group: 'amount' },
  amount_band: { label: 'Khoảng tiền đã chia nhóm', group: 'amount' },
  high_amount_flag: { label: 'Cờ: số tiền thuộc nhóm cao', group: 'amount' },

  transaction_day: { label: 'Ngày thứ mấy kể từ mốc gốc của bộ dữ liệu', group: 'time' },
  transaction_week: { label: 'Tuần thứ mấy kể từ mốc gốc', group: 'time' },
  transaction_hour: { label: 'Giờ trong ngày (0–23)', group: 'time' },

  has_identity: { label: 'Có dữ liệu định danh người mua hay không', group: 'presence' },
  has_device_info: { label: 'Có thông tin thiết bị hay không', group: 'presence' },
  has_p_email: { label: 'Có email người thanh toán hay không', group: 'presence' },
  has_r_email: { label: 'Có email người nhận hay không', group: 'presence' },
  same_email_domain: { label: 'Email người thanh toán và người nhận cùng tên miền', group: 'presence' },

  selected_missing_count: { label: 'Số cột bị thiếu trong nhóm cột đang xét', group: 'missing' },
  selected_missing_ratio: { label: 'Tỉ lệ cột bị thiếu trong nhóm cột đang xét', group: 'missing' },
  identity_missing_count: { label: 'Số cột định danh bị thiếu', group: 'missing' },

  prior_card_transaction_count: {
    label: 'Số giao dịch trước đó của cùng thẻ',
    group: 'history',
  },
  prior_card_amount_sum: { label: 'Tổng tiền các giao dịch trước của thẻ', group: 'history' },
  prior_card_avg_amount: { label: 'Số tiền trung bình các giao dịch trước của thẻ', group: 'history' },
  time_since_previous_card_transaction: {
    label: 'Khoảng thời gian từ giao dịch trước của thẻ',
    group: 'history',
  },
  prior_email_transaction_count: { label: 'Số giao dịch trước của cùng email', group: 'history' },
  prior_email_amount_sum: { label: 'Tổng tiền các giao dịch trước của email', group: 'history' },
  prior_device_transaction_count: {
    label: 'Số giao dịch trước của cùng thiết bị',
    group: 'history',
  },
  prior_device_amount_sum: { label: 'Tổng tiền các giao dịch trước của thiết bị', group: 'history' },

  ProductCD: { label: 'Mã loại sản phẩm', group: 'category' },
  card4: { label: 'Nhà phát hành thẻ (visa, mastercard…)', group: 'category' },
  card6: { label: 'Loại thẻ (debit / credit)', group: 'category' },
  DeviceType: { label: 'Loại thiết bị (desktop / mobile)', group: 'category' },
  device_family: { label: 'Hệ điều hành / dòng thiết bị', group: 'category' },
  M4: { label: 'Cờ khớp thông tin M4 (M0/M1/M2)', group: 'category' },
}

/** Nhóm ẩn danh: nghĩa chỉ có ở mức nhóm, Vesta không công bố từng cột. */
const ANONYMOUS_PATTERNS: { test: RegExp; label: string }[] = [
  {
    test: /^C\d+$/,
    label: 'Biến ĐẾM ẩn danh — đếm số thực thể gắn với giao dịch (địa chỉ, email, thiết bị trên cùng thẻ). Vesta không công bố cột này đếm gì',
  },
  {
    test: /^D\d+$/,
    label: 'Biến KHOẢNG THỜI GIAN ẩn danh — số ngày giữa hai mốc. Vesta không công bố mốc nào',
  },
  {
    test: /^dist\d+$/,
    label: 'Biến KHOẢNG CÁCH ẩn danh — khoảng cách giữa hai thực thể (vd địa chỉ thanh toán và vị trí IP). Vesta không công bố đơn vị',
  },
  {
    test: /^V\d+$/,
    label: 'Biến kỹ thuật ẩn danh do Vesta sinh ra. Không có mô tả công khai',
  },
]

export function describeFeature(name: string): { label: string; group: FeatureGroup } {
  const exact = EXACT[name]
  if (exact) return exact

  for (const { test, label } of ANONYMOUS_PATTERNS) {
    if (test.test(name)) return { label, group: 'anonymous' }
  }

  return { label: '', group: 'other' }
}

/** Thứ tự nhóm khi hiển thị: cái người ta hiểu ngay lên trước. */
export const GROUP_ORDER: FeatureGroup[] = [
  'amount',
  'time',
  'category',
  'history',
  'presence',
  'missing',
  'anonymous',
  'other',
]

/** Gom feature theo nhóm, giữ đúng thứ tự trên. */
export function groupFeatures<T>(
  entries: [string, T][],
): { group: FeatureGroup; items: { name: string; value: T; label: string }[] }[] {
  const buckets = new Map<FeatureGroup, { name: string; value: T; label: string }[]>()
  for (const [name, value] of entries) {
    const { label, group } = describeFeature(name)
    if (!buckets.has(group)) buckets.set(group, [])
    buckets.get(group)!.push({ name, value, label })
  }
  return GROUP_ORDER.filter((g) => buckets.has(g)).map((group) => ({
    group,
    items: buckets.get(group)!,
  }))
}
