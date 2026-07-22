# data/ — An (Data Processing & EDA)

Phụ trách: khảo sát, làm sạch, phân tích bộ IEEE-CIS (`transaction` + `identity`), xử lý mất cân bằng lớp/missing values, chia train/val theo thời gian (`TransactionDT`), feature engineering (aggregation theo card/email/device), và chuẩn bị bộ ca demo.

Xem chi tiết phân công & lịch: [`../docs/RISK_SCORING_PLAN.md`](../docs/RISK_SCORING_PLAN.md) mục 2 và 4.

**Bàn giao cho Quân (Ngày 3 — 24/07):** feature engineering script, đặt tại đây để `model/` import trực tiếp.

> Thư mục này chưa được scaffold chi tiết — để An tự thiết lập cấu trúc phù hợp (notebooks/, scripts/, v.v.) khi bắt đầu phần việc của mình.
