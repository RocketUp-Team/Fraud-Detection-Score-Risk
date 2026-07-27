/**
 * Tuỳ chọn giao diện, lưu trong localStorage để giữ nguyên giữa các lần mở.
 *
 * Không dùng context/store: chỉ có 2 giá trị và cả hai đều đọc/ghi ở
 * component gốc (App), nên state cục bộ là đủ.
 */
import { useCallback, useEffect, useState } from 'react'

export type Theme = 'system' | 'light' | 'dark'

const THEME_KEY = 'rse.theme'
const SIDEBAR_KEY = 'rse.sidebar.collapsed'

function readStorage(key: string): string | null {
  // Chặn cả trường hợp SSR (không có window) và Safari private mode (throw).
  try {
    return typeof window === 'undefined' ? null : window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStorage(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    /* hết quota hoặc bị chặn — không đáng để làm app lỗi */
  }
}

function applyTheme(theme: Theme): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  if (theme === 'system') root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', theme)
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => {
    const saved = readStorage(THEME_KEY)
    return saved === 'light' || saved === 'dark' || saved === 'system' ? saved : 'system'
  })

  // Áp ngay khi mount (SSR không có DOM nên phải làm ở effect) và mỗi lần đổi.
  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next)
    writeStorage(THEME_KEY, next)
  }, [])

  return { theme, setTheme }
}

/**
 * Có đang ở breakpoint mà sidebar biến thành drawer hay không.
 *
 * Phải khớp đúng breakpoint 900px trong App.css — nút 3 sọc cần biết nó đang
 * đóng/mở drawer hay đang thu gọn/mở rộng rail để đặt nhãn cho đúng.
 */
export function useIsDrawerLayout(): boolean {
  const [isDrawer, setIsDrawer] = useState<boolean>(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false
    return window.matchMedia('(max-width: 900px)').matches
  })

  useEffect(() => {
    if (!window.matchMedia) return
    const mq = window.matchMedia('(max-width: 900px)')
    const onChange = (e: MediaQueryListEvent) => setIsDrawer(e.matches)
    setIsDrawer(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  return isDrawer
}

export function useSidebarCollapsed() {
  const [collapsed, setCollapsedState] = useState<boolean>(
    () => readStorage(SIDEBAR_KEY) === 'true',
  )

  const setCollapsed = useCallback((next: boolean) => {
    setCollapsedState(next)
    writeStorage(SIDEBAR_KEY, String(next))
  }, [])

  return { collapsed, setCollapsed }
}
