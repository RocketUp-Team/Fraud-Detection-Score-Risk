/**
 * Icon SVG inline, style outline (theo `--domain icons`: Phosphor outline).
 *
 * Không dùng emoji làm icon (pre-delivery checklist) và không thêm dependency
 * icon library cho 8 icon — stroke="currentColor" nên tự ăn theo màu chữ.
 */
type IconName =
  | 'dashboard'
  | 'transactions'
  | 'review'
  | 'shield'
  | 'search'
  | 'alert'
  | 'check'
  | 'close'
  | 'chevron-left'
  | 'menu'
  | 'spark'
  | 'sun'
  | 'moon'
  | 'monitor'
  | 'panel-collapse'
  | 'panel-expand'
  | 'calculator'
  | 'upload'
  | 'file'

const PATHS: Record<IconName, React.ReactNode> = {
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </>
  ),
  transactions: (
    <>
      <path d="M3 6h18M3 12h18M3 18h12" />
    </>
  ),
  review: (
    <>
      <path d="M9 11l3 3 7-7" />
      <path d="M21 12v6a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3h9" />
    </>
  ),
  shield: (
    <>
      <path d="M12 3l7 3v6c0 4.5-3 7.7-7 9-4-1.3-7-4.5-7-9V6l7-3z" />
      <path d="M9.5 12l1.8 1.8L15 10" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="6" />
      <path d="M20 20l-4.2-4.2" />
    </>
  ),
  alert: (
    <>
      <path d="M12 4l9 15.5H3L12 4z" />
      <path d="M12 10v4M12 17h.01" />
    </>
  ),
  check: <path d="M5 12.5l4.5 4.5L19 7" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  'chevron-left': <path d="M14.5 5L8 12l6.5 7" />,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  spark: (
    <>
      <path d="M3 17l5-6 4 3 4-6 5 4" />
      <path d="M3 21h18" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19" />
    </>
  ),
  moon: <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z" />,
  monitor: (
    <>
      <rect x="3" y="4" width="18" height="12" rx="2" />
      <path d="M8 20h8M12 16v4" />
    </>
  ),
  'panel-collapse': (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M10 4v16M16.5 9.5L14 12l2.5 2.5" />
    </>
  ),
  'panel-expand': (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M10 4v16M13.5 9.5L16 12l-2.5 2.5" />
    </>
  ),
  calculator: (
    <>
      <rect x="4" y="3" width="16" height="18" rx="2" />
      <path d="M8 7h8M8 12h.01M12 12h.01M16 12h.01M8 16h.01M12 16h.01M16 16h.01" />
    </>
  ),
  upload: (
    <>
      <path d="M12 16V4M8 8l4-4 4 4" />
      <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
    </>
  ),
  file: (
    <>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5z" />
      <path d="M14 3v5h5" />
    </>
  ),
}

export function Icon({
  name,
  size = 20,
  className,
}: {
  name: IconName
  size?: number
  className?: string
}) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      // Icon luôn đi kèm nhãn text -> ẩn với screen reader, không lặp thông tin
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  )
}
