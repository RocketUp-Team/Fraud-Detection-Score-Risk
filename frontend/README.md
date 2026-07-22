# frontend/ — Long (Frontend)

Phụ trách: scaffold FE (React + TypeScript), wireframe, layout; danh sách giao dịch + filter theo mức rủi ro; chi tiết giao dịch (điểm số, quyết định, biểu đồ SHAP top-5); màn rà soát (duyệt/từ chối/gắn nhãn), nối API thật của Trung.

Xem chi tiết phân công & lịch: [`../docs/RISK_SCORING_PLAN.md`](../docs/RISK_SCORING_PLAN.md) mục 2 và 4.

**Ngày 1–4:** dùng mock JSON theo hợp đồng API đã chốt với Trung, chưa cần chờ backend thật.
**Ngày 5:** nối API thật.

## Scaffold

Vite + React + TypeScript (`npm create vite@latest -- --template react-ts`).

```bash
cd frontend
npm install
npm run dev
```

`Dockerfile` build production bundle và serve qua `vite preview` (chỉ dùng cho
`docker compose up` demo local, xem `../docker-compose.yml`).

> Layout/component/logic thật (danh sách giao dịch, chi tiết, rà soát) do Long tự xây dựng theo phân công.
