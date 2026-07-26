# frontend/ — Dashboard chấm điểm rủi ro

React 19 + TypeScript + Vite. 5 màn: danh sách giao dịch, chi tiết + SHAP, hàng
chờ rà soát, chấm điểm thử, nạp dữ liệu. Không dùng UI framework — chỉ CSS
thuần với design token.

- Hợp đồng API: [`../docs/API_CONTRACT.md`](../docs/API_CONTRACT.md)
- Design system: [`../design-system/risk-scoring-engine/MASTER.md`](../design-system/risk-scoring-engine/MASTER.md)

---

## 1. Cài đặt

**Node ≥ 20.19** (Vite 8 yêu cầu). Node 18 cài được dependency nhưng
`vite dev/build` sẽ lỗi `The requested module 'node:util' does not provide an
export named 'styleText'`.

```bash
nvm install 20 && nvm use 20
cd frontend
npm install
npm run dev            # http://localhost:5173
```

Backend cần chạy ở `http://localhost:8000` — xem [`../backend/README.md`](../backend/README.md).

### Chạy khi chưa có backend

```bash
VITE_USE_MOCKS=true npm run dev
```

Đọc mock JSON trong `src/mocks/`. Lưu ý chế độ này:
- Màn **Chấm điểm thử** trả **điểm giả** (hàm `fakeScore`), `model_version` ghi rõ
  `mock-không-phải-model-thật`
- **Nạp dữ liệu** và **nhập CSV** báo cần backend thật
- Filter và phân trang **không đổi kết quả** vì mock là một danh sách cố định —
  logic đó nằm ở backend

### Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | địa chỉ backend |
| `VITE_USE_MOCKS` | `false` | `true` = đọc `src/mocks/` |

Vite thay `import.meta.env` lúc **build**, không đọc lúc chạy. Nên trong Docker,
`VITE_API_URL` phải truyền dạng **build arg**, không phải `environment:`.

---

## 2. Các màn

| Đường dẫn | Nội dung |
|---|---|
| `/transactions` | KPI + phân bố band, 5 filter, phân trang, cột STT chạy liên tục qua trang |
| `/transactions/:id` | bullet chart điểm, SHAP top-5, 53 feature có giải nghĩa, form rà soát |
| `/review` | hàng chờ: điểm ≥ 40 và chưa ai xử lý, xếp điểm cao trước |
| `/score` | chấm 1 giao dịch nhập tay (`POST /score`), không ghi DB |
| `/import` | nạp N dòng từ bộ IEEE-CIS (có tiến độ) hoặc tải lên CSV |

Sidebar chia 2 nhóm: **Vận hành** (đọc dữ liệu đã chấm) và **Chấm điểm** (gọi
model để chấm mới).

### Chi tiết đáng lưu ý

**Danh sách** mặc định sắp xếp **mới nhất trước**, không phải điểm cao nhất. Sắp
theo điểm thì cả trang đầu chỉ có ca 100 điểm và người xem tưởng mọi giao dịch
đều gian lận.

**Nạp dữ liệu** có 3 plan (đủ 5 mức / mẫu ngẫu nhiên / N dòng đầu) — giải thích
đầy đủ trong README backend. Chạy nền, poll `GET /jobs/{id}`, F5 giữa chừng vẫn
thấy tiến độ, dừng được và giữ phần đã chấm.

**Nhập CSV** cảnh báo trước rằng file phải là dữ liệu đã tiền xử lý: CSV thô của
Kaggle chỉ khớp **28/53** cột. Có nút tải file mẫu đúng header, và sau khi nhập
hiện số cột khớp + danh sách cột thiếu.

**Chấm điểm thử** nói rõ form chỉ cung cấp 11/53 feature, phần còn lại dùng giá
trị mặc định nên điểm bão hoà với số tiền lớn. Nhập số ≥ 100.000 thì nhắc rằng
đây là ô số tiền chứ không phải mã giao dịch.

---

## 3. Tuỳ chọn giao diện

Lưu trong `localStorage` (`src/lib/prefs.ts`), giữ nguyên giữa các lần mở:

| Key | Giá trị | Điều khiển ở |
|---|---|---|
| `rse.theme` | `system` \| `light` \| `dark` | segmented control góc phải topbar |
| `rse.sidebar.collapsed` | `true` \| `false` | nút 3 sọc bên trái tiêu đề |

**Theme**: `[data-theme]` trên `<html>` thắng `prefers-color-scheme`; không có
attribute thì theo hệ thống. Khối token light trong `src/index.css` **xuất hiện 2
lần** (một cho `[data-theme="light"]`, một cho media query) vì CSS không cho gộp
media query vào selector list — sửa màu phải sửa cả hai.

**Sidebar** có 3 trạng thái: đầy đủ 232px, **rail 64px** (chỉ icon, badge số ca
chờ thành huy hiệu góc, logo team thay chữ), và **drawer** ở ≤ 900px. Chỉ có một
control: nút 3 sọc — desktop thì thu gọn/mở rộng, ≤900px thì đóng/mở drawer
(`useIsDrawerLayout()`, breakpoint phải khớp `900px` trong `App.css`).

---

## 4. Trợ lý trong khung chat

Nút nổi góc phải dưới. **Rule-based, KHÔNG phải LLM** — keyword + regex
(`src/lib/chatAgent.ts`), không cần API key, không tốn phí, không bịa số. Nhãn
trong UI ghi rõ "hiểu lệnh theo cú pháp, không phải AI".

| Gõ | Việc |
|---|---|
| `chấm điểm 4899 visa credit mobile android` | `POST /score`, hiện band + SHAP |
| `nhập csv` + gắn file | `POST /transactions/import` |
| `giao dịch 2987055` | tra cứu |
| `tổng quan` | `GET /transactions/stats` |
| `giúp` | liệt kê lệnh |

Có bỏ dấu trước khi so khớp nên `cham diem` cũng chạy; số tiền nhận cả `4899`,
`4.899,50`, `4,899.50`.

**Muốn thay bằng LLM thật**: đổi `parseIntent()` thành lời gọi API trả về đúng
shape `Intent` (dạng tool-calling). `runIntent()` và toàn bộ UI giữ nguyên.

---

## 5. Cấu trúc

```
src/
├── types/api.ts        # kiểu dữ liệu API — khớp docs/API_CONTRACT.md
├── mocks/              # mock JSON (có cả case shap_top5 = null)
├── lib/
│   ├── api.ts          # fetch client + ApiError (phân biệt offline vs lỗi server)
│   ├── format.ts       # tiền/ngày/SHAP có dấu
│   ├── prefs.ts        # theme + sidebar + breakpoint
│   ├── featureDocs.ts  # giải nghĩa 53 feature sang tiếng Việt
│   └── chatAgent.ts    # parse lệnh chat (rule-based)
├── hooks/queries.ts    # react-query
├── components/
│   ├── ScoreBullet     # bullet chart 0–100 + vùng ngưỡng
│   ├── ShapChart       # diverging bar + bảng số fallback
│   ├── DataLoader      # chọn plan, nhập số, theo dõi tiến độ
│   ├── ChatDock, ReviewPanel, StatTiles, TransactionTable
│   ├── RiskBadge, StatusBadge, Pagination, Feedback, Icon, ThemeSwitch
└── pages/              # 5 màn ở mục 2
```

---

## 6. Quy ước

- **Không hardcode màu/spacing/cỡ chữ** — chỉ dùng token `--color-*`, `--space-*`,
  `--text-*` trong `src/index.css`
- **`risk_band` do backend tính**, frontend chỉ hiển thị. Tự suy từ `risk_score`
  là sẽ lệch khi bands đổi
- **`shap_top5` có thể `null`** (model fallback) → render `<ShapUnavailable/>`.
  Mock `transaction-detail-no-shap.json` để test case này
- **Filter/phân trang lưu trong URL** → chia sẻ link được
- **Màu không bao giờ là tín hiệu duy nhất**: badge có text, SHAP có dấu `+`/`−`,
  chart kèm bảng số
- **Icon là SVG inline** (`Icon.tsx`), không emoji, không thêm thư viện icon

---

## 7. Kiểm tra trước khi giao

```bash
npx tsc -b             # typecheck
npx oxlint             # lint
npm run build          # production build
```

Ba lệnh trên **không bắt được lỗi bố cục**. Mọi lỗi giao diện của dự án này đều
do người nhìn màn hình phát hiện, cho tới khi thêm bước dưới đây.

### Kiểm bằng browser thật

```bash
uv venv --python 3.11 pw-env
uv pip install --python pw-env/bin/python playwright
./pw-env/bin/playwright install chromium
./pw-env/bin/python scripts/check-ui.py ./shots
```

Mở cả 5 màn ở 1440 / 1100 / 390px, kiểm: tràn ngang (`scrollWidth` >
`clientWidth`), lỗi console, nội dung mong đợi có xuất hiện, mở được chi tiết và
khung chat — rồi chụp ảnh để **xem bằng mắt**. Chính bước xem ảnh mới tìm ra 3
lỗi mà mọi assertion đều bỏ sót.

### Checklist thủ công

Contrast ≥ 4.5:1 ở cả light/dark · focus ring thấy rõ khi tab · touch target
≥ 44px ở ≤900px (desktop cố ý dùng 38px cho gọn) · `prefers-reduced-motion` ·
responsive 375 / 768 / 1024 / 1440.

---

## 8. Design system

Sinh từ skill `ui-ux-pro-max`: style **Modern Dark (Cinema Mobile)** + palette
**Luxury/Premium**, typography **Inter Tight / Inter / JetBrains Mono**, motion
4/10 (expo.out).

Những chỗ code **cố ý lệch** khỏi output của skill và lý do đều ghi ở cuối
[MASTER.md](../design-system/risk-scoring-engine/MASTER.md) — đáng chú ý nhất:
gold đổi mã ở cả hai theme để đạt contrast 4.5:1, và touch target 38px trên
desktop.

---

## 9. Hạn chế đã biết

| | |
|---|---|
| Bundle 335KB (gzip 103KB) | chưa code-split theo route; với 5 màn thì chưa đáng |
| Không có test tự động | chỉ có typecheck + lint + kiểm bằng browser thủ công |
| Trợ lý không hiểu ngôn ngữ tự nhiên | rule-based, xem mục 4 |
| Chưa có i18n | chuỗi tiếng Việt viết thẳng trong component |
