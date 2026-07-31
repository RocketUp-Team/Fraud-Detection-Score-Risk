# Architecture Gaps and Actions

| ID | Area | Current State | Risk | Recommendation | Priority |
|---|---|---|---|---|---|
| G-01 | Offline–online feature parity | Historical card/email/device features được tạo batch; API chưa có online feature service | Full-feature request-time scoring không tái tạo được | Giữ partial-demo là demo-only; target online feature store/service | Critical |
| G-02 | Policy ownership | Backend fixed risk bands; bundle có threshold config | Hai decision authority | Tách model bundle/policy bundle và version hóa policy | High |
| G-03 | As-built/target mixing | Diagram/report cũ mô tả registry, calibrated serving, human approval như active | Thesis overstates implementation | Dùng final diagrams với solid/dashed legend | Critical |
| G-04 | Spark → Pandas | `.toPandas()` trước Python ML | Driver-memory bottleneck | Giới hạn data hoặc chọn distributed-compatible training khi scale | High |
| G-05 | Serving coupling | Backend import model in-process | Dependency/image/scaling coupling | Giữ modular monolith cho demo; target model service nếu cần | Medium |
| G-06 | Partial scoring | Missing feature default và `partial_demo` | Không tương đương full-feature score | Expose warning/label rõ; không claim production parity | High |
| G-07 | MLflow | Local SQLite/file tracking | Chưa là registry/promotion authority | Ghi đúng là experiment tracking/lineage; target registry | Medium |
| G-08 | Promotion | Gate ghi decision, automatic promotion false | Human approval/serving update chưa enforce end-to-end | Thêm release state rõ trong target | High |
| G-09 | Historical aggregates | Sơ đồ cũ có thể hiểu aggregate trước split | Leakage misunderstanding | Dùng PIT previous-row diagram và train-only lookup | Critical |
| G-10 | Fixed risk bands | Backend là runtime authority | Candidate thresholds không điều khiển decision | Version hóa policy, test boundary values | High |
| G-11 | Joblib | `joblib.load()` artifact | Untrusted artifact có thể execute code | Chỉ load trusted/checksummed bundle | High |
| G-12 | Fallback | Heuristic fallback giữ API chạy | Fail-open/degraded score bị hiểu là model | Strict readiness hoặc explicit degraded mode | High |
| G-13 | V1 legacy | Root artifact metadata yếu hơn versioned contract | Rollback lineage không chắc chắn | Repackage/verify V1 trước khi gọi rollback champion | Medium |
| G-14 | Holdout reuse | Rule nằm trong code/docs, không có external lock | Silent tuning sau holdout | Candidate state + immutable holdout evidence | High |
| G-15 | Evidence snapshot | Manifest/verification có thể khác run | Metrics/facts không reproducible | Bundle cùng timestamp, versions, hashes và run IDs | Critical |

## Submission blockers

Trước final thesis, cần một evidence bundle nhất quán gồm manifest, verification report, output schema, model metadata, metrics và checksum từ cùng một run. Nếu không có versioned V2 artifact trong bundle, chỉ gọi V2 là software/configuration default hoặc historical claim, không gọi là runtime-verified artifact.
