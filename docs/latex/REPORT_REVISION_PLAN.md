# Kế hoạch chỉnh report: ít chữ, nhiều hình, đúng trọng tâm

## Đã thực hiện

| Hạng mục | Điều chỉnh |
|---|---|
| Hình trùng nội dung | Giữ Overall System Architecture ở phần chính; Application Deployment chỉ giữ trong Appendix. |
| Historical V1/V2 chart | Chuyển xuống Appendix vì khác model family và preprocessing contract. |
| Model identity | Thêm bảng phân biệt Historical V2, serving default `v2`, và current CatBoost candidate. |
| Model evidence | Thêm bảng model-family comparison và chart selection-window PR-AUC. |
| Candidate evidence | Thêm validation-versus-holdout chart, holdout confusion matrix, và calibration Brier chart. |
| Policy ownership | Thêm bảng candidate policy versus backend runtime policy. |
| Split counts | Sửa validation legitimate thành 85,450 và holdout legitimate thành 85,993. |
| Captions | Giữ caption ngắn, nêu status/evidence và chỉ một kết luận chính. |

## Bộ hình chính sau chỉnh

### Architecture and methodology

1. Overall System Architecture
2. Layered Data Architecture
3. Data, Feature and Evaluation Contracts
4. Detailed Data Processing Pipeline
5. Leakage-Controlled Transformation
6. Model Development Lifecycle
7. Temporal Development Windows
8. Promotion State Machine

### Evidence and results

1. Class Distribution
2. Fraud Rate by ProductCD
3. Fraud Rate by Identity Presence
4. Fraud Rate by Transaction Hour
5. Model-Family Comparison
6. Current Candidate Validation vs Holdout
7. Holdout Confusion Matrix
8. Calibration Before vs After

## Nội dung không đưa vào phần chính

- Endpoint và route chi tiết: Appendix API Reference.
- Application deployment details: Appendix Deployment and Implementation Diagrams.
- Historical V1/V2 comparison: Appendix Historical Model Comparison.
- Reject-threshold holdout metrics tại 0.53: không suy đoán khi artifact chưa cung cấp prediction-level evidence.

## Nguyên tắc trình bày

- Mỗi hình chỉ có caption và một đoạn giải thích ngắn.
- Không lặp lại toàn bộ pipeline sau khi đã trình bày ở Chapter 4.
- Không lặp lại toàn bộ limitation ở từng chapter; tập trung ở Chapter 7 và Conclusion.
- Bảng giữ dạng LaTeX native để bảo toàn khả năng đọc và chất lượng in.
- Chart và diagram lấy số liệu từ official artifacts hoặc source PNG đã được kiểm tra.
- Không dùng “V2” đơn độc khi claim có thể trộn historical LightGBM với current CatBoost candidate.

## Kiểm tra trước khi nộp

- Build LaTeX thành công tối thiểu hai pass.
- Không còn `Figure ??`, `Table ??`, hoặc unresolved references.
- Kiểm tra lại List of Figures và List of Tables.
- Kiểm tra mọi số liệu split và candidate metrics với official-run artifacts.
- Kiểm tra chart ở mức zoom 100%.
- Không đưa claim production-ready vào report.
