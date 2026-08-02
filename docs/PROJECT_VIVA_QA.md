# Bộ câu hỏi và trả lời vấn đáp — Fraud Detection Risk Scoring

Tài liệu này tổng hợp các câu hỏi thường gặp khi trình bày project Fraud Detection, cùng câu trả lời mẫu.

## 1. Project giải quyết bài toán gì?

Project xây dựng hệ thống phát hiện giao dịch gian lận. Dữ liệu đầu vào là thông tin giao dịch và thông tin identity của khách hàng. Hệ thống xử lý dữ liệu, huấn luyện mô hình machine learning, chấm điểm rủi ro từ 0 đến 100 và hiển thị kết quả trên dashboard để nhân viên kiểm tra.

## 2. Project sử dụng dataset nào?

Project sử dụng bộ IEEE-CIS Fraud Detection của Vesta, gồm hai bảng chính là `train_transaction` và `train_identity`. Hai bảng được nối thông qua `TransactionID`. Dataset có khoảng 590 nghìn giao dịch và tỷ lệ gian lận khoảng 3,5%.

## 3. Vì sao phải join hai bảng transaction và identity?

Bảng transaction chứa thông tin giao dịch như số tiền, loại thẻ và sản phẩm. Bảng identity chứa thông tin thiết bị, trình duyệt, hệ điều hành và các đặc điểm nhận diện khác. Kết hợp hai bảng giúp mô hình có thêm tín hiệu để phát hiện fraud.

## 4. Vì sao dùng left join thay vì inner join?

Không phải giao dịch nào cũng có thông tin identity. Nếu dùng inner join, các giao dịch thiếu identity sẽ bị loại bỏ. Dùng left join giúp giữ toàn bộ giao dịch trong bảng transaction; các giá trị identity bị thiếu sẽ được xử lý ở bước missing-value handling.

## 5. Project xử lý missing data như thế nào?

- Biến số được thay missing bằng median tính trên tập train.
- Biến categorical được thay bằng category đặc biệt như `__MISSING__`.
- Tạo thêm các feature như `has_identity`, `selected_missing_count` và `selected_missing_ratio`.
- Median và mapping chỉ được fit trên training data rồi áp dụng cho validation và holdout để tránh leakage.

## 6. Data imbalance là gì trong project?

Fraud chỉ chiếm khoảng 3,5% tổng số giao dịch, trong khi legitimate chiếm phần lớn. Đây là hiện tượng mất cân bằng lớp. Nếu không xử lý, model có thể đoán hầu hết giao dịch là legitimate nhưng vẫn có accuracy cao và bỏ sót nhiều fraud.

## 7. Project xử lý imbalance data như thế nào?

Project sử dụng hai hướng:

1. Dùng `class_weight` hoặc `sample_weight` để tăng mức phạt cho fraud class.
2. Tạo thêm tập `train_balanced` bằng cách undersampling lớp legitimate để so sánh.

Luồng chính ưu tiên weighted training vì vẫn giữ được nhiều dữ liệu legitimate hơn. Project không dùng SMOTE trong pipeline chính vì dữ liệu có nhiều categorical feature, missing value và yếu tố thời gian. Việc tạo dữ liệu tổng hợp có thể làm sai phân phối giao dịch thực tế và gây leakage nếu làm không cẩn thận.

## 8. Vì sao không chỉ dùng accuracy?

Với dữ liệu mất cân bằng, model đoán tất cả là legitimate vẫn có thể đạt accuracy khoảng 96,5%, nhưng recall của fraud bằng 0. Vì vậy project sử dụng PR-AUC, ROC-AUC, precision, recall và confusion matrix.

## 9. Vì sao chọn PR-AUC làm metric quan trọng?

PR-AUC tập trung vào chất lượng nhận diện positive class là fraud, phản ánh mối quan hệ giữa precision và recall. Với dữ liệu mất cân bằng mạnh, PR-AUC thường phù hợp hơn accuracy và sát với mục tiêu nghiệp vụ hơn ROC-AUC.

## 10. Vì sao chia dữ liệu theo thời gian?

Giao dịch trong thực tế xảy ra theo thời gian. Nếu chia ngẫu nhiên, dữ liệu tương lai có thể lọt vào training và làm kết quả đánh giá quá tốt. Project dùng `TransactionDT` để chia dữ liệu theo thứ tự thời gian, mô phỏng việc dùng dữ liệu quá khứ để dự đoán giao dịch tương lai.

## 11. Data leakage là gì? Project phòng tránh như thế nào?

Data leakage là việc thông tin từ validation, holdout hoặc tương lai vô tình được dùng trong quá trình train. Project phòng tránh bằng cách:

- Chia dữ liệu theo thời gian trước.
- Chỉ fit median trên train.
- Chỉ fit categorical mapping trên train.
- Tạo aggregate history từ dữ liệu quá khứ.
- Không dùng holdout để tuning.
- Chỉ đánh giá holdout một lần sau khi model và policy đã được cố định.

## 12. Project có những feature engineering nào?

Các nhóm feature chính gồm:

- Feature về số tiền: `TransactionAmt`, log amount và amount band.
- Feature về thời gian: day, week và hour.
- Feature về missingness.
- Feature về card history, email history và device history.
- Feature về identity và device presence.
- Feature categorical như `ProductCD`, `card4`, `card6` và `DeviceType`.

## 13. Vì sao dùng Spark?

Dataset lớn và có nhiều bước join, aggregation, profiling và feature engineering. Spark phù hợp để xử lý dữ liệu quy mô lớn và tạo model-ready dataset. Sau đó dữ liệu được chuyển sang pandas ở bước cuối để train LightGBM, XGBoost và CatBoost.

## 14. Vì sao không train trực tiếp bằng Spark?

Các model được dùng trong project có API Python/scikit-learn thuận tiện hơn và cần dữ liệu dạng in-memory. Vì vậy Spark xử lý phần preprocessing quy mô lớn, còn pandas được dùng ở ranh giới cuối để huấn luyện model.

## 15. Project đã thử những model nào?

Project có baseline Logistic Regression và so sánh với LightGBM, XGBoost và CatBoost. Sau đó model tốt nhất được tuning và tạo SHAP explanation.

## 16. Vì sao chọn LightGBM?

LightGBM phù hợp với dữ liệu dạng bảng, nhiều feature và quan hệ phi tuyến. Model có tốc độ train tốt, hiệu quả cao trên tabular data và hỗ trợ giải thích bằng TreeSHAP.

## 17. Kết quả model hiện tại như thế nào?

Theo kết quả V2 trong project:

- Validation ROC-AUC: khoảng 0,8941.
- Validation PR-AUC: khoảng 0,4925.
- Holdout ROC-AUC: khoảng 0,8796.
- Holdout PR-AUC: khoảng 0,4582.

Holdout được giữ riêng và chỉ đánh giá sau khi model đã được chọn, tuning và đóng băng.

## 18. SHAP dùng để làm gì?

SHAP giải thích vì sao model đưa ra một điểm rủi ro cụ thể. Với mỗi giao dịch, SHAP cho biết feature nào làm điểm fraud tăng hoặc giảm. Dashboard hiển thị top 5 feature quan trọng nhất để analyst hiểu lý do giao dịch bị đánh dấu.

## 19. Điểm risk từ 0 đến 100 được tính như thế nào?

Model tạo ra xác suất fraud từ 0 đến 1. Xác suất này được chuyển thành risk score từ 0 đến 100 để dễ hiển thị trên dashboard. Trong demo, score được chia thành các nhóm:

- Dưới 40: approve.
- Từ 40 đến dưới 80: review.
- Từ 80 trở lên: reject.

Trong production, các ngưỡng cần được calibrate theo chi phí false positive, false negative và năng lực xử lý của đội review.

## 20. False positive và false negative nào nghiêm trọng hơn?

False negative thường nghiêm trọng vì hệ thống bỏ sót giao dịch gian lận. Tuy nhiên nếu giảm threshold quá thấp thì false positive tăng, khiến nhiều giao dịch legitimate bị review. Threshold cần cân bằng giữa chi phí bỏ sót fraud, chi phí kiểm tra thủ công và trải nghiệm khách hàng.

## 21. Backend giao tiếp với model như thế nào?

Backend FastAPI gọi trực tiếp module `fraud_model.score()`, không gọi model qua một network service riêng. Model được load khi backend khởi động. Backend nhận feature, thực hiện scoring và trả về probability, risk score, risk band và SHAP explanation.

## 22. Database lưu những gì?

PostgreSQL lưu transaction ID, transaction amount, feature JSON, probability, risk score, risk band, decision, review status, review label, reviewer và note.

## 23. Nếu model không load được thì hệ thống xử lý thế nào?

Trong bản demo, backend có heuristic fallback để hệ thống vẫn khởi động. Backend trả warning rõ ràng trong `/meta` và dashboard hiển thị cảnh báo rằng điểm không đến từ model thật. Trong production nên fail-closed hoặc yêu cầu bật demo mode rõ ràng.

## 24. Hạn chế của project là gì?

- Chưa có authentication và authorization.
- Threshold còn cố định trong backend.
- Chưa có model registry production.
- Chưa có monitoring drift tự động.
- Chưa có durable queue cho các job lớn.
- Frontend chưa có đầy đủ automated browser testing.
- Fallback heuristic phù hợp cho demo nhưng chưa phù hợp để đưa thẳng lên production.

## 25. Nếu được phát triển tiếp, bạn sẽ cải thiện gì?

Em sẽ ưu tiên thêm authentication và role-based access control, đưa threshold policy ra configuration hoặc policy service, xây dựng model registry và quy trình promotion/rollback, thêm monitoring data drift và model performance, dùng queue bền vững cho batch scoring và bổ sung automated frontend/browser tests.

## Câu trả lời ngắn cho câu hỏi “Hãy mô tả toàn bộ pipeline”

Đầu tiên, project đọc hai bảng transaction và identity của IEEE-CIS, sau đó left join theo `TransactionID`. Tiếp theo, dữ liệu được kiểm tra missing, xử lý categorical và numeric feature, đồng thời tạo thêm feature về thời gian, missingness, card, email và device history. Dữ liệu được chia theo `TransactionDT` để tránh leakage. Vì fraud chỉ chiếm khoảng 3,5%, project xử lý imbalance bằng class weight và thêm một tập undersampling để so sánh. Spark xuất ra model-ready Parquet, sau đó pandas nhận dữ liệu ở bước train để so sánh Logistic Regression, LightGBM, XGBoost và CatBoost. LightGBM được chọn, tuning và giải thích bằng SHAP. Cuối cùng model được đóng gói vào FastAPI, lưu kết quả vào PostgreSQL và hiển thị trên React dashboard.

## Điểm cần thống nhất trước khi bảo vệ

Trong tài liệu hiện có sự khác nhau về số lượng feature: một số tài liệu ghi pipeline có **68 features**, trong khi backend/model serving có tài liệu ghi **53 features**. Khi trình bày cần xác nhận đúng artifact đang chạy và trả lời nhất quán:

> Feature count phụ thuộc vào version của feature contract. Pipeline preprocessing và model serving phải dùng cùng một canonical feature order. Khi trình bày, em sẽ dùng số feature đúng với artifact V2 đang được deploy và chứng minh bằng `feature_order.json` hoặc endpoint `/meta`.

Đây là điểm cần kiểm tra trước buổi bảo vệ vì feature contract phải thống nhất giữa data pipeline, model và backend.
