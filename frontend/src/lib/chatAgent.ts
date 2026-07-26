/**
 * Trợ lý trong khung chat — nhận diện ý định bằng LUẬT (keyword + regex), KHÔNG
 * phải LLM. Không cần API key, không tốn phí, và trả lời tiền định nên demo
 * không bao giờ "nói sai".
 *
 * Muốn thay bằng LLM thật sau này: chỉ cần đổi `parseIntent()` thành một lời
 * gọi API trả về đúng shape `Intent` (một dạng tool-calling), phần thực thi
 * `runIntent()` và giao diện giữ nguyên.
 */
import { api } from './api'
import type {
  Dataset,
  ImportResponse,
  Job,
  LoadMode,
  RiskBand,
  ScoreResponse,
  Stats,
  Transaction,
  TransactionDetail,
} from '../types/api'

export type Intent =
  | { kind: 'score'; features: Record<string, string | number | null>; echo: string[] }
  | { kind: 'import' }
  | { kind: 'template' }
  | { kind: 'lookup'; transactionId: number }
  | { kind: 'stats' }
  | { kind: 'datasets' }
  | { kind: 'top'; count: number; band?: RiskBand }
  | { kind: 'load'; mode: LoadMode; limit: number; perBand: number }
  | {
      kind: 'review'
      transactionId: number
      action: 'approve' | 'reject'
      label: 'fraud' | 'legit'
    }
  | { kind: 'navigate'; to: string; label: string }
  | { kind: 'help' }
  | { kind: 'unknown' }

/** Từ khoá -> giá trị categorical theo DATA_DICTIONARY.md */
const CARD_BRANDS: Record<string, string> = {
  visa: 'visa',
  master: 'mastercard',
  mastercard: 'mastercard',
  amex: 'american express',
  'american express': 'american express',
  discover: 'discover',
}

const DEVICE_FAMILY: Record<string, string> = {
  android: 'android',
  ios: 'ios',
  iphone: 'ios',
  windows: 'windows',
  macos: 'macos',
  mac: 'macos',
}

const BAND_WORDS: { test: RegExp; band: RiskBand }[] = [
  { test: /nghiem trong|critical/, band: 'critical' },
  { test: /rui ro cao|muc cao|\bcao\b|high/, band: 'high' },
  { test: /trung binh|medium/, band: 'medium' },
  { test: /can luu y|guarded/, band: 'guarded' },
  { test: /muc thap|\bthap\b|low/, band: 'low' },
]

function normalize(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    // bỏ dấu tiếng Việt để "chấm điểm" và "cham diem" đều khớp
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
}

/** Số tiền: lấy số đầu tiên, cho phép 4.899,50 / 4,899.50 / 4899 */
function extractAmount(text: string): number | null {
  const match = text.match(/(\d[\d.,]*)/)
  if (!match) return null
  let raw = match[1]
  // Nếu có cả . và , thì ký tự sau cùng là dấu thập phân
  if (raw.includes('.') && raw.includes(',')) {
    const decimalSep = raw.lastIndexOf('.') > raw.lastIndexOf(',') ? '.' : ','
    const thousandSep = decimalSep === '.' ? ',' : '.'
    raw = raw.split(thousandSep).join('').replace(decimalSep, '.')
  } else if ((raw.match(/,/g) || []).length === 1 && /,\d{1,2}$/.test(raw)) {
    raw = raw.replace(',', '.')
  } else {
    raw = raw.replace(/[.,]/g, '')
  }
  const value = Number(raw)
  return Number.isFinite(value) ? value : null
}

/** Mã giao dịch IEEE-CIS là số ≥ 5 chữ số — dùng để phân biệt với "nạp 500". */
function extractTransactionId(text: string): number | null {
  const m = text.match(/\b(\d{5,})\b/)
  return m ? Number(m[1]) : null
}

function extractBand(text: string): RiskBand | undefined {
  for (const { test, band } of BAND_WORDS) if (test.test(text)) return band
  return undefined
}

export function parseIntent(input: string): Intent {
  const text = normalize(input.trim())
  if (!text) return { kind: 'unknown' }

  if (/^(help|giup|huong dan|lam gi|\?)/.test(text)) return { kind: 'help' }

  // ---- Điều hướng: phải xét TRƯỚC các lệnh hành động, vì "mở màn chấm điểm"
  // cũng khớp regex chấm điểm. Bắt buộc có động từ mở/vào/đi để không nhầm.
  if (/(mo|vao|di den|chuyen|xem) (man|trang|muc)?\s*/.test(text)) {
    if (/hang cho|ra soat/.test(text)) return { kind: 'navigate', to: '/review', label: 'Hàng chờ rà soát' }
    if (/cham diem thu|thu nghiem/.test(text))
      return { kind: 'navigate', to: '/score', label: 'Chấm điểm thử' }
    if (/nap du lieu|import|csv/.test(text))
      return { kind: 'navigate', to: '/import', label: 'Nạp dữ liệu' }
    if (/danh sach|giao dich/.test(text) && !extractTransactionId(text))
      return { kind: 'navigate', to: '/transactions', label: 'Danh sách giao dịch' }
  }

  // ---- File mẫu: xét trước `import` vì "tải file mẫu" cũng chứa "file"
  if (/(file mau|tai mau|template|mau csv)/.test(text)) return { kind: 'template' }

  // ---- Nạp dữ liệu theo lô
  if (/(nap|load)\b/.test(text) && !/mo |vao /.test(text)) {
    if (/du 5 muc|moi muc|day du muc|coverage/.test(text)) {
      // Bỏ cụm "5 mức" ra trước khi lấy số, nếu không "nạp đủ 5 mức 10" sẽ ăn
      // số 5 của chính cụm đó thay vì 10 mà người dùng muốn.
      const per = extractAmount(text.replace(/\b5\s*muc\b/g, ''))
      return { kind: 'load', mode: 'coverage', limit: 5000, perBand: per && per <= 500 ? per : 20 }
    }
    const n = extractAmount(text)
    if (n !== null) {
      // Mặc định mẫu ngẫu nhiên: đại diện hơn N dòng đầu (xem README backend).
      const mode: LoadMode = /dong dau|head|lien tiep/.test(text) ? 'head' : 'sample'
      return { kind: 'load', mode, limit: Math.min(Math.round(n), 100_000), perBand: 20 }
    }
    return { kind: 'load', mode: 'coverage', limit: 5000, perBand: 20 }
  }

  // ---- Duyệt / từ chối
  const reviewId = extractTransactionId(text)
  if (reviewId !== null && /(duyet|thong qua|chap nhan|tu choi|reject|approve)/.test(text)) {
    const reject = /(tu choi|reject|gian lan|fraud)/.test(text)
    return {
      kind: 'review',
      transactionId: reviewId,
      action: reject ? 'reject' : 'approve',
      label: reject ? 'fraud' : 'legit',
    }
  }

  if (/(csv|nhap file|import|upload|tai len)/.test(text)) return { kind: 'import' }

  if (/(bo du lieu|dataset|co nhung bo)/.test(text)) return { kind: 'datasets' }

  // ---- Top N ca rủi ro cao nhất
  // `nhat` là dấu hiệu chung của câu hỏi "cái nào ... nhất", bắt được cả
  // "cao nhất", "nghiêm trọng nhất", "nặng nhất", "nguy hiểm nhất".
  if (/\bnhat\b|^top\b|\btop \d/.test(text)) {
    const n = extractAmount(text)
    return { kind: 'top', count: n && n >= 1 && n <= 20 ? Math.round(n) : 5, band: extractBand(text) }
  }

  if (/(tong quan|thong ke|so lieu|bao nhieu ca|dashboard|stats)/.test(text)) {
    return { kind: 'stats' }
  }

  // Tra cứu: "giao dịch 2987055" / "xem 2987055" / "id 2987055"
  const lookup = text.match(/(?:giao dich|ma|id|xem|tra cuu|detail)\D{0,10}(\d{5,})/)
  if (lookup) return { kind: 'lookup', transactionId: Number(lookup[1]) }

  if (/(cham diem|score|danh gia|rui ro|tinh diem)/.test(text)) {
    const amount = extractAmount(text)
    if (amount === null) {
      return { kind: 'unknown' }
    }

    const features: Record<string, string | number | null> = {
      TransactionAmt: amount,
      log_transaction_amount: Math.log1p(amount),
    }
    const echo = [`số tiền ${amount}`]

    for (const [key, value] of Object.entries(CARD_BRANDS)) {
      if (text.includes(key)) {
        features.card4 = value
        echo.push(`thẻ ${value}`)
        break
      }
    }
    if (/(credit|tin dung)/.test(text)) {
      features.card6 = 'credit'
      echo.push('credit')
    } else if (/(debit|ghi no)/.test(text)) {
      features.card6 = 'debit'
      echo.push('debit')
    }
    if (/(mobile|dien thoai|mobi)/.test(text)) {
      features.DeviceType = 'mobile'
      echo.push('thiết bị mobile')
    } else if (/(desktop|may tinh|pc)/.test(text)) {
      features.DeviceType = 'desktop'
      echo.push('thiết bị desktop')
    }
    for (const [key, value] of Object.entries(DEVICE_FAMILY)) {
      if (text.includes(key)) {
        features.device_family = value
        echo.push(value)
        break
      }
    }
    const product = text.match(/productcd\s*([wcrhs])\b/)
    if (product) {
      features.ProductCD = product[1].toUpperCase()
      echo.push(`ProductCD ${features.ProductCD}`)
    }
    if (/(the moi|khong co lich su|lan dau)/.test(text)) {
      features.prior_card_transaction_count = 0
      echo.push('thẻ mới')
    }

    return { kind: 'score', features, echo }
  }

  return { kind: 'unknown' }
}

export type AgentResult =
  | { type: 'text'; text: string }
  | { type: 'score'; text: string; result: ScoreResponse }
  | { type: 'import'; text: string; result: ImportResponse }
  | { type: 'transaction'; text: string; result: TransactionDetail }
  | { type: 'transactions'; text: string; result: Transaction[] }
  | { type: 'datasets'; text: string; result: Dataset[] }
  | { type: 'stats'; text: string; result: Stats }
  | { type: 'job'; text: string; result: Job }
  | { type: 'navigate'; text: string; to: string }
  | { type: 'download'; text: string; url: string }
  | { type: 'await-file'; text: string }

export const HELP_TEXT = [
  'Gõ được mấy việc này:',
  '• `chấm điểm 4899 visa credit mobile` — model chấm ngay',
  '• `nạp 5000` — nạp mẫu ngẫu nhiên · `nạp đủ 5 mức 20` — mỗi mức 20 ca',
  '• `nhập csv` rồi gắn file · `tải file mẫu`',
  '• `5 ca cao nhất` · `3 ca nghiêm trọng nhất`',
  '• `giao dịch 2987055` · `duyệt 2987055` · `từ chối 2987055`',
  '• `tổng quan` · `bộ dữ liệu` · `mở hàng chờ`',
].join('\n')

/** Thực thi ý định. Lỗi được trả về dạng text để hiện trong chat, không throw. */
export async function runIntent(intent: Intent): Promise<AgentResult> {
  try {
    switch (intent.kind) {
      case 'help':
        return { type: 'text', text: HELP_TEXT }

      case 'navigate':
        return { type: 'navigate', text: `Mở ${intent.label}.`, to: intent.to }

      case 'template':
        return {
          type: 'download',
          text: 'File mẫu có đúng 53 cột model cần + 20 dòng thật. Sửa lại rồi nhập vào.',
          url: api.importTemplateUrl(20),
        }

      case 'import':
        return {
          type: 'await-file',
          text: 'Gắn file .csv vào đây (nút kẹp giấy bên dưới). Cần cột `TransactionID`, và phải là dữ liệu ĐÃ tiền xử lý — CSV thô Kaggle chỉ khớp 28/53 cột.',
        }

      case 'stats': {
        const stats = await api.stats()
        return {
          type: 'stats',
          text: `${stats.total.toLocaleString('vi-VN')} giao dịch đã chấm, ${stats.pending_review.toLocaleString('vi-VN')} ca chờ rà soát, điểm trung bình ${stats.avg_risk_score}/100.`,
          result: stats,
        }
      }

      case 'datasets': {
        const datasets = await api.listDatasets()
        return {
          type: 'datasets',
          text: `Có ${datasets.length} bộ trong model_ready. Bộ có dấu ★ là nên dùng.`,
          result: datasets,
        }
      }

      case 'top': {
        const page = await api.listTransactions({
          sort: '-risk_score',
          page_size: intent.count,
          risk_band: intent.band,
        })
        if (page.items.length === 0) {
          return { type: 'text', text: 'Không có giao dịch nào khớp — DB đã có dữ liệu chưa?' }
        }
        return {
          type: 'transactions',
          text: `${page.items.length} ca điểm cao nhất${intent.band ? ` ở mức ${intent.band}` : ''}:`,
          result: page.items,
        }
      }

      case 'lookup': {
        const txn = await api.getTransaction(intent.transactionId)
        return { type: 'transaction', text: `Giao dịch ${txn.transaction_id}:`, result: txn }
      }

      case 'review': {
        const txn = await api.submitReview(intent.transactionId, {
          action: intent.action,
          label: intent.label,
          reviewer: 'trợ lý',
        })
        return {
          type: 'transaction',
          text: `Đã ${intent.action === 'approve' ? 'duyệt' : 'từ chối'} giao dịch ${
            txn.transaction_id
          }, gắn nhãn ${intent.label}.`,
          result: txn,
        }
      }

      case 'load': {
        const job = await api.startLoad({
          dataset: 'holdout',
          limit: intent.limit,
          reset: false,
          mode: intent.mode,
          per_band: intent.perBand,
          seed: 42,
        })
        const what =
          intent.mode === 'coverage'
            ? `${intent.perBand} ca mỗi mức (${intent.perBand * 5} giao dịch)`
            : `${intent.limit.toLocaleString('vi-VN')} dòng ${
                intent.mode === 'sample' ? 'mẫu ngẫu nhiên' : 'đầu tiên'
              }`
        return {
          type: 'job',
          // `reset: false` -> ghi thêm, không xoá. Xoá dữ liệu là việc nguy hiểm,
          // không để một câu chat làm được.
          text: `Đang nạp ${what} từ holdout, ghi thêm vào dữ liệu hiện có.`,
          result: job,
        }
      }

      case 'score': {
        const result = await api.score({ features: intent.features })
        return {
          type: 'score',
          text: `Đã chấm với ${intent.echo.join(', ')}. Các feature khác dùng giá trị mặc định nên điểm mang tính tham khảo.`,
          result,
        }
      }

      default:
        return { type: 'text', text: `Chưa hiểu câu đó. ${HELP_TEXT}` }
    }
  } catch (error) {
    return {
      type: 'text',
      text: `Không thực hiện được: ${error instanceof Error ? error.message : 'lỗi không xác định'}`,
    }
  }
}

export async function runImport(file: File): Promise<AgentResult> {
  try {
    const result = await api.importCsv(file)
    return { type: 'import', text: `Đã xử lý ${file.name}:`, result }
  } catch (error) {
    return {
      type: 'text',
      text: `Nhập file thất bại: ${error instanceof Error ? error.message : 'lỗi không xác định'}`,
    }
  }
}
