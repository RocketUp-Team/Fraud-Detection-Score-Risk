# High-Resolution PNG Exports

Thư mục này chứa từng sơ đồ kiến trúc dưới dạng PNG riêng để chèn vào Word,
PowerPoint hoặc các công cụ không hỗ trợ SVG ổn định.

Export profile:

```text
source: ../../ARCHITECTURE_DIAGRAMS.md
renderer: @mermaid-js/mermaid-cli 11.16.0
theme: neutral
background: white
viewport width: 2400
scale: 2
```

| File | Nội dung |
| --- | --- |
| `01-system-overview.png` | Kiến trúc tổng thể offline/online |
| `02-data-pipeline.png` | Pipeline xử lý dữ liệu chi tiết |
| `03-temporal-windows.png` | Temporal split và validation windows |
| `04-data-contract.png` | Data contract và handover |
| `05-model-training-lifecycle.png` | Model training lifecycle |
| `06-training-sequence.png` | Runtime sequence của training run |
| `07-spark-deployment.png` | Spark local/standalone deployment |
| `08-promotion-state-machine.png` | Candidate promotion state machine |

PNG là generated fallback. Mermaid source và SVG tương ứng ở thư mục cha vẫn
là nguồn chuẩn để chỉnh sửa và in vector.
