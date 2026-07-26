import { useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { DataLoader } from '../components/DataLoader'
import { Icon } from '../components/Icon'
import { api } from '../lib/api'
import type { ImportResponse } from '../types/api'

/**
 * Nhập CSV theo lô: mỗi dòng được model chấm điểm rồi ghi vào DB
 * (`POST /transactions/import`).
 *
 * Dòng lỗi không làm dừng cả file — backend dùng savepoint từng dòng và trả về
 * danh sách lỗi, nên ở đây phải hiển thị cả phần thành công lẫn phần thất bại.
 */
export function ImportPage() {
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)

  const mutation = useMutation({
    mutationFn: (f: File) => api.importCsv(f),
    onSuccess: () => {
      // Dữ liệu mới đã vào DB -> danh sách và KPI phải làm mới.
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })

  function pick(next: File | null) {
    if (!next) return
    if (!next.name.toLowerCase().endsWith('.csv')) {
      // Chặn sớm ở client cho phản hồi tức thì; backend vẫn kiểm lại.
      mutation.reset()
      setFile(null)
      window.alert('Chỉ nhận file .csv')
      return
    }
    mutation.reset()
    setFile(next)
  }

  const result: ImportResponse | undefined = mutation.data

  return (
    <section>
      <header className="page-head">
        <div>
          <h1>Nạp dữ liệu</h1>
          <p>
            Mỗi dòng được model chấm điểm rồi lưu vào DB. Chọn một trong hai cách dưới đây.
          </p>
        </div>
      </header>

      <div className="grid grid--detail">
        <DataLoader />

        <section className="card card--csv">
          <h2>Tải lên CSV của bạn</h2>

          {/* Vùng kéo-thả: bấm hoặc kéo file vào đều được, không chỉ dựa vào drag */}
          <div
            className={`dropzone${dragging ? ' is-dragging' : ''}`}
            onDragOver={(e) => {
              e.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragging(false)
              pick(e.dataTransfer.files?.[0] ?? null)
            }}
          >
            <Icon name="upload" size={28} />
            <p className="dropzone__text">Kéo file .csv vào đây</p>
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => inputRef.current?.click()}
            >
              Chọn file từ máy
            </button>
            <input
              ref={inputRef}
              type="file"
              accept=".csv,text/csv"
              className="sr-only"
              aria-label="Chọn file CSV để nhập"
              onChange={(e) => pick(e.target.files?.[0] ?? null)}
            />
          </div>

          {file && (
            <p className="picked">
              <Icon name="file" size={16} />
              <span className="picked__name">{file.name}</span>
              <span className="muted num">{(file.size / 1024).toFixed(1)} KB</span>
            </p>
          )}

          <div className="review__actions">
            <button
              type="button"
              className="btn btn--primary"
              disabled={!file || mutation.isPending}
              onClick={() => file && mutation.mutate(file)}
            >
              <Icon name="upload" size={18} />
              {mutation.isPending ? 'Đang chấm điểm và ghi…' : 'Nhập và chấm điểm'}
            </button>
            {file && (
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => {
                  setFile(null)
                  mutation.reset()
                  if (inputRef.current) inputRef.current.value = ''
                }}
              >
                Bỏ chọn
              </button>
            )}
          </div>

          <p className="field__hint" style={{ marginTop: 'var(--space-3)' }}>
            Cần cột <code>TransactionID</code>. Tối đa 5.000 dòng mỗi lần.
          </p>
        </section>

        {(result || mutation.isError) && (
        <section className="card card--load-result">
          <h2>Kết quả nhập</h2>

          {mutation.isError && (
            <p className="callout callout--error" role="alert">
              Nhập thất bại: {(mutation.error as Error).message}
            </p>
          )}

          {result && (
            <>
              <div className="kpi__row">
                <article className="tile">
                  <p className="tile__label">Đã nhập</p>
                  <p className="tile__value num">{result.imported}</p>
                </article>
                <article className="tile">
                  <p className="tile__label">Dòng lỗi</p>
                  <p className="tile__value num">{result.failed}</p>
                </article>
              </div>

              {result.imported > 0 && (
                <div className="callout callout--ok done-actions" role="status">
                  <strong>
                    Đã chấm điểm và lưu {result.imported.toLocaleString('vi-VN')} giao dịch.
                  </strong>
                  <div className="done-actions__row">
                    <Link className="btn btn--primary" to="/transactions">
                      <Icon name="transactions" size={18} />
                      Xem danh sách giao dịch
                    </Link>
                    <Link className="btn btn--secondary" to="/review">
                      <Icon name="review" size={18} />
                      Vào hàng chờ rà soát
                    </Link>
                  </div>
                </div>
              )}

              {result.errors.length > 0 && (
                <>
                  <h3 className="subhead">Chi tiết dòng lỗi</h3>
                  <div className="table-wrap">
                    <table className="table table--compact">
                      <thead>
                        <tr>
                          <th scope="col">Dòng</th>
                          <th scope="col">Lý do</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.errors.map((err) => (
                          <tr key={`${err.row}-${err.error}`}>
                            <td className="num">{err.row}</td>
                            <td>{err.error}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {result.failed > result.errors.length && (
                    <p className="field__hint">
                      Hiển thị {result.errors.length} lỗi đầu tiên trên tổng {result.failed}.
                    </p>
                  )}
                </>
              )}
            </>
          )}
        </section>
        )}
      </div>
    </section>
  )
}
