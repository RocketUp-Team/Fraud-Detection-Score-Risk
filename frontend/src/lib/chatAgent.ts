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
import type { ImportResponse, ScoreResponse, TransactionDetail } from '../types/api'

export type Intent =
  | { kind: 'score'; features: Record<string, string | number | null>; echo: string[] }
  | { kind: 'import' }
  | { kind: 'lookup'; transactionId: number }
  | { kind: 'stats' }
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

export function parseIntent(input: string): Intent {
  const text = normalize(input.trim())
  if (!text) return { kind: 'unknown' }

  if (/^(help|giup|huong dan|lam gi|\?)/.test(text)) return { kind: 'help' }

  if (/(csv|nhap file|import|upload|tai len)/.test(text)) return { kind: 'import' }

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
  | { type: 'await-file'; text: string }

export const HELP_TEXT = [
  'Tôi hiểu được mấy việc này:',
  '• `chấm điểm 4899 visa credit mobile android` — gọi model chấm ngay',
  '• `nhập csv` rồi gắn file — chấm điểm cả lô và lưu vào DB',
  '• `giao dịch 2987055` — xem điểm và SHAP của một giao dịch đã có',
  '• `tổng quan` — số liệu hiện tại của hệ thống',
].join('\n')

/** Thực thi ý định. Lỗi được trả về dạng text để hiện trong chat, không throw. */
export async function runIntent(intent: Intent): Promise<AgentResult> {
  try {
    switch (intent.kind) {
      case 'help':
        return { type: 'text', text: HELP_TEXT }

      case 'import':
        return {
          type: 'await-file',
          text: 'Gắn file .csv vào đây (nút kẹp giấy bên dưới). Mỗi dòng sẽ được model chấm điểm rồi lưu vào DB. File cần có cột `TransactionID`.',
        }

      case 'stats': {
        const stats = await api.stats()
        const bands = stats.by_band.map((b) => `${b.band} ${b.count}`).join(' · ')
        return {
          type: 'text',
          text: `Đang có ${stats.total} giao dịch đã chấm, ${stats.pending_review} ca chờ rà soát. Điểm trung bình ${stats.avg_risk_score}/100. Phân bố: ${bands}.`,
        }
      }

      case 'lookup': {
        const txn = await api.getTransaction(intent.transactionId)
        return {
          type: 'transaction',
          text: `Giao dịch ${txn.transaction_id}:`,
          result: txn,
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
        return {
          type: 'text',
          text: `Chưa hiểu câu đó. ${HELP_TEXT}`,
        }
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
    return {
      type: 'import',
      text: `Đã xử lý ${file.name}:`,
      result,
    }
  } catch (error) {
    return {
      type: 'text',
      text: `Nhập file thất bại: ${error instanceof Error ? error.message : 'lỗi không xác định'}`,
    }
  }
}
