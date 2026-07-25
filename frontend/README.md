# frontend/ — Long (Frontend)

Dashboard React + TypeScript: danh sách giao dịch có filter theo mức rủi ro,
chi tiết giao dịch (điểm số + SHAP top-5), và màn rà soát (duyệt/từ chối/gắn nhãn).

Hợp đồng API: [`../docs/API_CONTRACT.md`](../docs/API_CONTRACT.md).
Design system: [`../design-system/risk-scoring-engine/MASTER.md`](../design-system/risk-scoring-engine/MASTER.md).
Phân công & lịch: [`../docs/RISK_SCORING_PLAN.md`](../docs/RISK_SCORING_PLAN.md) mục 2 và 4.

## Yêu cầu

**Node ≥ 20.19** (Vite 8). Node 18 cài được deps nhưng `vite dev/build` sẽ lỗi
`styleText`. Dùng `nvm install 20 && nvm use 20`.

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

Backend cần chạy ở `http://localhost:8000` (xem `../backend/README.md`).

### Chạy không cần backend

```bash
VITE_USE_MOCKS=true npm run dev
```

Đọc mock JSON trong `src/mocks/` thay vì gọi API — dùng khi backend chưa lên
hoặc để demo offline.

### Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Địa chỉ backend |
| `VITE_USE_MOCKS` | `false` | `true` = đọc `src/mocks/` |

## Cấu trúc

```
src/
├── types/api.ts        # Kiểu dữ liệu API — khớp docs/API_CONTRACT.md
├── mocks/              # Mock JSON theo hợp đồng (có cả case shap_top5=null)
├── lib/api.ts          # Fetch client + ApiError (phân biệt offline vs lỗi server)
├── lib/format.ts       # Format tiền/ngày/SHAP có dấu
├── hooks/queries.ts    # react-query: useMeta / useTransactions / useSubmitReview
├── components/
│   ├── RiskBadge       # Pill mức rủi ro (luôn có text, không chỉ màu)
│   ├── ScoreBullet     # Bullet chart điểm 0–100 + vùng ngưỡng + marker
│   ├── ShapChart       # Diverging bar SHAP + bảng số fallback a11y
│   ├── ReviewPanel     # Form duyệt/từ chối/gắn nhãn
│   ├── StatusBadge     # DecisionBadge (máy) vs ReviewStatusBadge (người)
│   └── TransactionTable, Pagination, Feedback (skeleton/empty/error)
└── pages/
    ├── TransactionsPage       # Danh sách + KPI + filter (state trong URL)
    ├── TransactionDetailPage  # Điểm + SHAP + feature + rà soát
    ├── ReviewQueuePage        # Hàng chờ: điểm ≥ 40, chưa ai xử lý
    ├── ScorePage              # Chấm điểm thử 1 giao dịch (POST /score, không ghi DB)
    └── ImportPage             # Nhập CSV theo lô (POST /transactions/import)
```

Sidebar chia 2 nhóm: **Vận hành** (đọc dữ liệu đã chấm) và **Chấm điểm** (hai
màn gọi model để chấm mới).

## Trợ lý trong khung chat

Nút nổi góc phải dưới → `src/components/ChatDock.tsx` + `src/lib/chatAgent.ts`.

**Là rule-based, KHÔNG phải LLM** — nhận diện ý định bằng keyword + regex, nên
không cần API key, không tốn phí, và câu trả lời tiền định (demo không bao giờ
bịa). Nhãn trong UI ghi rõ "hiểu lệnh theo cú pháp, không phải AI".

Lệnh hiểu được:

| Câu | Việc |
|---|---|
| `chấm điểm 4899 visa credit mobile android` | `POST /score`, hiện band + SHAP top-5 |
| `nhập csv` + gắn file | `POST /transactions/import` |
| `giao dịch 2987055` | `GET /transactions/{id}` |
| `tổng quan` | `GET /transactions/stats` |
| `giúp` | liệt kê lệnh |

Có bỏ dấu tiếng Việt trước khi so khớp nên `cham diem` cũng chạy; số tiền chấp
nhận cả `4899`, `4.899,50`, `4,899.50`.

**Muốn thay bằng LLM thật**: chỉ cần đổi `parseIntent()` thành lời gọi API trả
về đúng shape `Intent` (dạng tool-calling). Phần thực thi `runIntent()` và toàn
bộ giao diện giữ nguyên.

> Ở `VITE_USE_MOCKS=true`, màn "Chấm điểm thử" trả **điểm giả** (hàm
> `fakeScore` trong `src/lib/api.ts`, `model_version` ghi rõ
> `mock-không-phải-model-thật`) và màn "Nhập CSV" báo cần backend thật. Muốn
> điểm thật thì phải chạy backend.

## Tuỳ chọn giao diện

Lưu trong `localStorage` (xem `src/lib/prefs.ts`), giữ nguyên giữa các lần mở:

| Key | Giá trị | Ý nghĩa |
|---|---|---|
| `rse.theme` | `system` \| `light` \| `dark` | Chọn ở segmented control góc phải topbar |
| `rse.sidebar.collapsed` | `true` \| `false` | Nút 3 sọc bên trái tiêu đề topbar |

Cách theme được áp:

- `[data-theme="light"\|"dark"]` trên `<html>` = người dùng chọn tay, thắng tất cả
- Không có attribute = theo `prefers-color-scheme` của hệ thống

> Khối token light trong `src/index.css` **xuất hiện 2 lần** (một cho
> `[data-theme="light"]`, một cho `@media (prefers-color-scheme: light)`) vì CSS
> không cho gộp media query vào selector list. Sửa màu thì phải sửa cả hai.

Sidebar có 3 trạng thái: đầy đủ 264px, **rail 76px** (chỉ icon, badge số ca chờ
chuyển thành huy hiệu góc), và **drawer** ở ≤ 1024px. Ở rail, nhãn được ẩn bằng
kỹ thuật `sr-only` chứ không `display: none` — screen reader vẫn đọc được tên mục.

Chỉ có **một** control cho sidebar: nút 3 sọc ở topbar. Trên desktop nó thu
gọn/mở rộng, ở ≤ 1024px nó đóng/mở drawer — `useIsDrawerLayout()` trong
`src/lib/prefs.ts` quyết định, breakpoint phải khớp `1024px` trong `App.css`.

## Quy ước

- **Không hardcode màu/spacing** trong component — chỉ dùng token `--color-*`,
  `--space-*` ở `src/index.css` (sinh từ skill ui-ux-pro-max, style
  "Data-Dense Dashboard", density 8/10, có cả light và dark).
- **`risk_band` do backend tính**, frontend chỉ hiển thị. Đừng tự suy từ
  `risk_score` — sẽ lệch khi bands đổi.
- **`shap_top5` có thể `null`** (model fallback không có SHAP) → render
  `<ShapUnavailable/>`, không crash. Mock `transaction-detail-no-shap.json`
  để test case này.
- **Filter/phân trang lưu trong URL query param** → chia sẻ link được.
- Màu không bao giờ là tín hiệu duy nhất: badge có text, SHAP có dấu `+`/`−`,
  chart kèm bảng số.

## Kiểm tra trước khi giao

```bash
npm run build     # tsc -b + vite build
npx oxlint
```

Checklist thủ công (từ skill ui-ux-pro-max): contrast ≥ 4.5:1 ở cả light/dark,
focus ring thấy rõ khi tab, touch target ≥ 44px, `prefers-reduced-motion`,
responsive ở 375 / 768 / 1024 / 1440px.
