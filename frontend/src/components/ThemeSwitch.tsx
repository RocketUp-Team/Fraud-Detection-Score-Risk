import { Icon } from './Icon'
import type { Theme } from '../lib/prefs'

/**
 * Chọn giao diện Sáng / Tối / Theo hệ thống.
 *
 * Dùng radiogroup thay vì nút toggle 2 trạng thái vì "theo hệ thống" là một
 * lựa chọn thật, không phải trạng thái trung gian. Icon-only nên mỗi nút bắt
 * buộc có `aria-label` + `title` (rule a11y: không icon-only mà thiếu nhãn).
 */
const OPTIONS: { value: Theme; label: string; icon: 'sun' | 'moon' | 'monitor' }[] = [
  { value: 'light', label: 'Giao diện sáng', icon: 'sun' },
  { value: 'dark', label: 'Giao diện tối', icon: 'moon' },
  { value: 'system', label: 'Theo hệ thống', icon: 'monitor' },
]

export function ThemeSwitch({
  theme,
  onChange,
}: {
  theme: Theme
  onChange: (theme: Theme) => void
}) {
  return (
    <div className="segmented" role="radiogroup" aria-label="Chế độ giao diện">
      {OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          role="radio"
          aria-checked={theme === opt.value}
          aria-label={opt.label}
          title={opt.label}
          className={`segmented__btn${theme === opt.value ? ' is-active' : ''}`}
          onClick={() => onChange(opt.value)}
        >
          <Icon name={opt.icon} size={16} />
        </button>
      ))}
    </div>
  )
}
