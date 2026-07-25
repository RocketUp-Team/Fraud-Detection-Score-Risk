import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { HELP_TEXT, parseIntent, runImport, runIntent, type AgentResult } from '../lib/chatAgent'
import { formatProbability, formatSigned } from '../lib/format'
import { RISK_BAND_LABEL } from '../types/api'
import { Icon } from './Icon'
import { RiskBadge } from './RiskBadge'

/**
 * Khung chat nổi: chấm điểm thử và nhập CSV ngay trong hội thoại.
 *
 * Trợ lý là rule-based (xem lib/chatAgent.ts), KHÔNG phải LLM — nên nhãn ghi
 * "Trợ lý" chứ không phải "AI", tránh tạo kỳ vọng sai.
 */
type Message = {
  id: number
  from: 'user' | 'bot'
  text: string
  result?: AgentResult
}

let messageId = 0

const SUGGESTIONS = ['chấm điểm 4899 visa credit mobile', 'tổng quan', 'nhập csv']

function ResultCard({ result }: { result: AgentResult }) {
  if (result.type === 'score') {
    const r = result.result
    return (
      <div className="chat__card">
        <div className="chat__card-head">
          <RiskBadge band={r.risk_band} score={r.risk_score} />
          <span className="num muted">{formatProbability(r.fraud_probability)}</span>
        </div>
        {r.shap_top5 ? (
          <ul className="chat__shap">
            {r.shap_top5.slice(0, 5).map((s) => (
              <li key={s.feature}>
                <span className="chat__shap-name">{s.feature}</span>
                <span
                  className={`num chat__shap-val chat__shap-val--${
                    s.shap_value >= 0 ? 'pos' : 'neg'
                  }`}
                >
                  {formatSigned(s.shap_value)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Model đang chạy bản dự phòng, không có SHAP.</p>
        )}
        <p className="chat__card-foot num">{r.model_version}</p>
      </div>
    )
  }

  if (result.type === 'import') {
    const r = result.result
    return (
      <div className="chat__card">
        <p>
          Đã nhập <strong className="num">{r.imported}</strong> dòng
          {r.failed > 0 && (
            <>
              , lỗi <strong className="num">{r.failed}</strong>
            </>
          )}
          .
        </p>
        {r.errors.slice(0, 3).map((e) => (
          <p key={`${e.row}-${e.error}`} className="chat__err">
            Dòng <span className="num">{e.row}</span>: {e.error}
          </p>
        ))}
        {r.imported > 0 && <Link to="/transactions">Xem trong danh sách</Link>}
      </div>
    )
  }

  if (result.type === 'transaction') {
    const t = result.result
    return (
      <div className="chat__card">
        <div className="chat__card-head">
          <RiskBadge band={t.risk_band} score={t.risk_score} />
          <span className="muted">{RISK_BAND_LABEL[t.risk_band]}</span>
        </div>
        <Link to={`/transactions/${t.transaction_id}`}>Mở chi tiết</Link>
      </div>
    )
  }

  return null
}

export function ChatDock() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([
    { id: messageId++, from: 'bot', text: HELP_TEXT },
  ])
  const fileRef = useRef<HTMLInputElement>(null)
  const logRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Tin mới thì cuộn xuống cuối
  useEffect(() => {
    if (open && logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [messages, open])

  // Mở là focus vào ô nhập; Esc để đóng
  useEffect(() => {
    if (!open) return
    inputRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  function push(msg: Omit<Message, 'id'>) {
    setMessages((prev) => [...prev, { ...msg, id: messageId++ }])
  }

  async function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || busy) return
    push({ from: 'user', text: trimmed })
    setInput('')
    setBusy(true)

    const intent = parseIntent(trimmed)
    if (intent.kind === 'import') {
      // Mở hộp thoại chọn file luôn, đỡ một bước bấm
      fileRef.current?.click()
    }
    const result = await runIntent(intent)
    push({ from: 'bot', text: result.text, result })
    setBusy(false)
  }

  async function onFile(file: File | null) {
    if (!file || busy) return
    if (!file.name.toLowerCase().endsWith('.csv')) {
      push({ from: 'bot', text: 'Chỉ nhận file .csv.' })
      return
    }
    push({ from: 'user', text: `Đã gắn file ${file.name}` })
    setBusy(true)
    const result = await runImport(file)
    push({ from: 'bot', text: result.text, result })
    // Dữ liệu mới vào DB -> làm mới danh sách và KPI
    queryClient.invalidateQueries({ queryKey: ['transactions'] })
    queryClient.invalidateQueries({ queryKey: ['stats'] })
    setBusy(false)
    if (fileRef.current) fileRef.current.value = ''
  }

  return (
    <>
      <button
        type="button"
        className="chat-fab"
        aria-expanded={open}
        aria-controls="chat-panel"
        onClick={() => setOpen((v) => !v)}
      >
        <Icon name={open ? 'close' : 'spark'} size={20} />
        <span>{open ? 'Đóng trợ lý' : 'Trợ lý'}</span>
      </button>

      {open && (
        <section className="chat" id="chat-panel" aria-label="Trợ lý chấm điểm">
          <header className="chat__head">
            <div>
              <strong>Trợ lý chấm điểm</strong>
              {/* Nói rõ không phải AI để không tạo kỳ vọng sai */}
              <span className="chat__sub">hiểu lệnh theo cú pháp, không phải AI</span>
            </div>
            <button
              type="button"
              className="icon-btn icon-btn--sm"
              aria-label="Đóng trợ lý"
              onClick={() => setOpen(false)}
            >
              <Icon name="close" size={16} />
            </button>
          </header>

          <div className="chat__log" ref={logRef} role="log" aria-live="polite">
            {messages.map((msg) => (
              <div key={msg.id} className={`chat__msg chat__msg--${msg.from}`}>
                <p className="chat__text">{msg.text}</p>
                {msg.result && <ResultCard result={msg.result} />}
              </div>
            ))}
            {busy && (
              <p className="chat__typing" aria-hidden="true">
                đang xử lý…
              </p>
            )}
          </div>

          <div className="chat__suggest">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                className="chat__chip"
                disabled={busy}
                onClick={() => send(s)}
              >
                {s}
              </button>
            ))}
          </div>

          <form
            className="chat__form"
            onSubmit={(e) => {
              e.preventDefault()
              send(input)
            }}
          >
            <button
              type="button"
              className="icon-btn icon-btn--sm"
              aria-label="Gắn file CSV"
              title="Gắn file CSV"
              onClick={() => fileRef.current?.click()}
            >
              <Icon name="file" size={16} />
            </button>
            <label className="sr-only" htmlFor="chat-input">
              Nhập yêu cầu cho trợ lý
            </label>
            <input
              id="chat-input"
              ref={inputRef}
              type="text"
              value={input}
              placeholder="vd: chấm điểm 4899 visa mobile"
              disabled={busy}
              onChange={(e) => setInput(e.target.value)}
            />
            <button type="submit" className="btn btn--primary btn--sm" disabled={busy || !input.trim()}>
              Gửi
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,text/csv"
              className="sr-only"
              aria-label="Chọn file CSV"
              onChange={(e) => onFile(e.target.files?.[0] ?? null)}
            />
          </form>
        </section>
      )}
    </>
  )
}
