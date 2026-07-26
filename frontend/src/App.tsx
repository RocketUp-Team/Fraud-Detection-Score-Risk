import { useEffect, useState } from 'react'
import { NavLink, Route, Routes, useLocation } from 'react-router-dom'

import rocketLogo from './assets/rocket.jpeg'
import { ChatDock } from './components/ChatDock'
import { Icon } from './components/Icon'
import { ThemeSwitch } from './components/ThemeSwitch'
import { useMeta, useStats } from './hooks/queries'
import { useIsDrawerLayout, useSidebarCollapsed, useTheme } from './lib/prefs'
import { ImportPage } from './pages/ImportPage'
import { ReviewQueuePage } from './pages/ReviewQueuePage'
import { ScorePage } from './pages/ScorePage'
import { TransactionDetailPage } from './pages/TransactionDetailPage'
import { TransactionsPage } from './pages/TransactionsPage'
import './App.css'

const NAV_MAIN = [
  { to: '/transactions', label: 'Giao dịch', icon: 'transactions' as const },
  { to: '/review', label: 'Hàng chờ', icon: 'review' as const },
]

// Tách nhóm: 2 mục dưới đây là nơi model thật sự được gọi để chấm điểm.
const NAV_MODEL = [
  { to: '/score', label: 'Chấm điểm thử', icon: 'calculator' as const },
  { to: '/import', label: 'Nạp dữ liệu', icon: 'upload' as const },
]

function Sidebar({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean
  onNavigate: () => void
}) {
  const { data: stats } = useStats()
  const { data: meta } = useMeta()

  return (
    <>
      <div className="sidebar__brand">
        <span className="sidebar__mark" aria-hidden="true">
          <Icon name="shield" size={22} />
        </span>
        <span className="sidebar__brand-text">
          <strong>Risk Scoring</strong>
          <span>Engine</span>
        </span>
      </div>

      <nav className="sidebar__nav" aria-label="Điều hướng chính">
        <p className="sidebar__section">Vận hành</p>
        {NAV_MAIN.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            // Khi thu gọn, nhãn bị ẩn khỏi mắt nên nút cần tên có thể đọc được
            title={collapsed ? item.label : undefined}
          >
            <Icon name={item.icon} size={18} />
            <span className="sidebar__label">{item.label}</span>
            {item.to === '/review' && stats && stats.pending_review > 0 && (
              <span className="sidebar__count num">{stats.pending_review}</span>
            )}
          </NavLink>
        ))}

        <p className="sidebar__section sidebar__section--gap">Chấm điểm</p>
        {NAV_MODEL.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            title={collapsed ? item.label : undefined}
          >
            <Icon name={item.icon} size={18} />
            <span className="sidebar__label">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar__foot">
        <div className="sidebar__model-box">
          <p className="sidebar__section">Model đang phục vụ</p>
          <p className="sidebar__model num">{meta?.model_version ?? '—'}</p>
          <p className="sidebar__model-note">
            <Icon name={meta?.explainability ? 'spark' : 'alert'} size={14} />
            {meta ? (meta.explainability ? 'có giải thích SHAP' : 'không có SHAP') : 'đang tải…'}
          </p>
        </div>

        <p className="credit">
          {/* alt rỗng: logo chỉ nhắc lại tên đã có ở dòng chữ bên cạnh, để alt
              thì screen reader đọc tên team hai lần. width/height đặt sẵn để
              không gây layout shift lúc ảnh tải. */}
          <img
            className="credit__logo"
            src={rocketLogo}
            alt=""
            width={36}
            height={36}
            loading="lazy"
          />
          <span className="credit__text">
            <span className="credit__label">Created by</span>
            <span className="credit__name">Rocket Team</span>
          </span>
        </p>
      </div>
    </>
  )
}

export default function App() {
  const { data: meta } = useMeta()
  const { theme, setTheme } = useTheme()
  const { collapsed, setCollapsed } = useSidebarCollapsed()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const isDrawerLayout = useIsDrawerLayout()
  const location = useLocation()

  // Một nút 3 sọc duy nhất cho cả hai layout: ≤1024px thì đóng/mở drawer,
  // desktop thì thu gọn/mở rộng sidebar. Hai nút cho cùng một việc chỉ làm
  // người dùng phải đoán.
  const menuOpen = isDrawerLayout ? drawerOpen : !collapsed
  const menuLabel = isDrawerLayout
    ? drawerOpen
      ? 'Đóng menu điều hướng'
      : 'Mở menu điều hướng'
    : collapsed
      ? 'Mở rộng menu'
      : 'Thu gọn menu'

  function toggleMenu() {
    if (isDrawerLayout) setDrawerOpen((v) => !v)
    else setCollapsed(!collapsed)
  }

  // Đổi route thì đóng drawer (mobile) — nếu không, drawer che nội dung mới.
  useEffect(() => setDrawerOpen(false), [location.pathname])

  // Esc đóng drawer: hành vi mong đợi của mọi overlay.
  useEffect(() => {
    if (!drawerOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setDrawerOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [drawerOpen])

  const shellClass = [
    'shell',
    collapsed ? 'shell--rail' : '',
    drawerOpen ? 'shell--drawer-open' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={shellClass}>
      <a className="skip-link" href="#main">
        Bỏ qua điều hướng
      </a>

      <aside className="sidebar" id="sidebar">
        <Sidebar collapsed={collapsed} onNavigate={() => setDrawerOpen(false)} />
      </aside>

      {/* Lớp phủ chỉ tồn tại khi drawer mở, click ra ngoài để đóng */}
      {drawerOpen && (
        <button
          type="button"
          className="scrim"
          aria-label="Đóng menu"
          onClick={() => setDrawerOpen(false)}
        />
      )}

      <div className="main">
        <header className="topbar">
          <button
            type="button"
            className="icon-btn topbar__burger"
            aria-label={menuLabel}
            title={menuLabel}
            aria-expanded={menuOpen}
            aria-controls="sidebar"
            onClick={toggleMenu}
          >
            <Icon name={isDrawerLayout && drawerOpen ? 'close' : 'menu'} />
          </button>

          <p className="topbar__title">Chấm điểm rủi ro giao dịch · IEEE-CIS</p>

          {meta?.warning && (
            <p className="topbar__warn" role="alert">
              <Icon name="alert" size={16} />
              <span>Model thật chưa nạp được</span>
            </p>
          )}

          <div className="topbar__actions">
            <ThemeSwitch theme={theme} onChange={setTheme} />
          </div>
        </header>

        {meta?.warning && (
          <div className="banner banner--warn" role="alert">
            {meta.warning}
          </div>
        )}

        <main className="content" id="main">
          <Routes>
            <Route path="/" element={<TransactionsPage />} />
            <Route path="/transactions" element={<TransactionsPage />} />
            <Route path="/transactions/:id" element={<TransactionDetailPage />} />
            <Route path="/review" element={<ReviewQueuePage />} />
            <Route path="/score" element={<ScorePage />} />
            <Route path="/import" element={<ImportPage />} />
            <Route
              path="*"
              element={
                <div className="callout callout--warn">
                  <strong>Không có trang này.</strong>
                  <p>
                    <NavLink to="/transactions">Về danh sách giao dịch</NavLink>
                  </p>
                </div>
              }
            />
          </Routes>
        </main>
      </div>

      <ChatDock />
    </div>
  )
}
