# Architecture Diagram Exports

## Final architecture exports

Bộ sơ đồ hiện hành được sinh từ [`../AN_FINAL_ARCHITECTURE_DIAGRAMS.md`](../AN_FINAL_ARCHITECTURE_DIAGRAMS.md).
Mermaid source là source of truth; các file trong thư mục `final/` là bản
render đã kiểm tra cú pháp và được đặt tên theo nội dung sơ đồ.

| File | Nội dung |
| --- | --- |
| `final/overall-system-architecture.svg` / `.png` | Overall system architecture |
| `final/layered-data-architecture.svg` / `.png` | Layered data architecture |
| `final/detailed-data-processing-pipeline.svg` / `.png` | Detailed data processing pipeline |
| `final/leakage-controlled-transformation-flow.svg` / `.png` | Leakage-controlled transformation flow |
| `final/data-feature-evaluation-contracts.svg` / `.png` | Data, feature and evaluation contracts |
| `final/model-training-lifecycle.svg` / `.png` | Model training lifecycle |
| `final/temporal-development-windows.svg` / `.png` | Temporal development windows |
| `final/promotion-state-machine.svg` / `.png` | Promotion state machine |

Bộ export cũ bên dưới được giữ lại để bảo toàn lịch sử và không đại diện cho
kiến trúc cuối.

Các file SVG trong thư mục này được sinh từ chín Mermaid blocks tại
[`../ARCHITECTURE_DIAGRAMS.md`](../ARCHITECTURE_DIAGRAMS.md).

Renderer chuẩn:

```text
@mermaid-js/mermaid-cli 11.16.0
theme: neutral
background: transparent
width: 1600
```

Ngoài SVG, từng sơ đồ có bản
[`PNG độ phân giải cao`](png/README.md) để dùng trong Word/PowerPoint.
Xem toàn bộ ảnh theo thứ tự đọc tại [`IMAGE_GALLERY.md`](IMAGE_GALLERY.md).

| File | View |
| --- | --- |
| `01-system-overview.svg` | Bản đồ kiến trúc tổng thể |
| `02-data-pipeline.svg` | Data Pipeline chi tiết |
| `03-temporal-windows.svg` | Timeline và validation windows |
| `04-data-contract.svg` | Data contract và handover |
| `05-model-training-lifecycle.svg` | Model Training lifecycle |
| `06-training-sequence.svg` | Runtime sequence |
| `07-spark-deployment.svg` | Local/cluster deployment |
| `08-promotion-state-machine.svg` | Candidate promotion states |
| `09-best-model-v2-serving.svg` | Best model V2 serving architecture |

Mermaid source là source of truth. Không chỉnh sửa SVG bằng tay; khi source
đổi, render lại tám final exports và review layout trước khi commit.
