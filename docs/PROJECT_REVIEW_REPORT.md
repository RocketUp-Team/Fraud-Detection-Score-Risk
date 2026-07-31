# Whole-Project Review Report

**Review date:** 30 July 2026

**Prepared by:** Group 1 — Dương Bình An, Lê Quang Tuyến, Phạm Đức Long,
Đỗ Quốc Trung, Dương Hồng Quân, and Nguyễn Lê Hồng Nhi

**Supervisor:** TAN Le Duy

**Decision:** the repository is a coherent end-to-end academic/demo system, but
it needs reproducibility, serving-policy, security, and operational controls
before it can support a production-readiness claim.

## 1. Technical summary

The implementation covers all major layers promised by the project plan:
large-data preparation, model development, real-time scoring, persistence,
review workflow, dashboard, and container orchestration. The interfaces between
the four documented subsystem workstreams are visible and mostly consistent:

- the Spark pipeline exports an explicit model-ready contract;
- the model consumes the canonical feature order and exports a Python scoring
  interface;
- the backend calls that interface and publishes typed HTTP responses;
- the frontend models the same response shapes and presents the scoring/review
  flow.

The best-evidenced result is the processed-data contract. V2 remains the saved
offline champion by holdout PR-AUC and the current serving default. A later
`0.0.2` XGBoost candidate adds five completed MLflow stage runs, isotonic
calibration, selected review/reject thresholds, and holdout operating metrics,
but its holdout PR-AUC (`0.4318`) is below V2 (`0.4582`) and it has not been
promoted. The application layer is feature-complete for a demonstration but
deliberately omits production controls.

## 2. Scope and method

### 2.1 Inspected areas

- all tracked source/configuration/documentation files;
- ignored processed-data and model artifact inventories available locally;
- current Git changes;
- data manifest and generated reports;
- model comparison/training metadata;
- backend routes, schemas, persistence, scoring, and tests;
- frontend pages, API layer, types, components, and documented manual QA;
- Compose topology, Dockerfiles, scripts, and CI configuration;
- the supplied FPT MSE thesis template.

The repository contains 48 tracked Python files, 28 TypeScript/TSX files, and
more than 5,000 tracked Python source lines plus more than 3,500 tracked
TypeScript/TSX source lines. The local `data/` tree is approximately 5.6 GB and
contains the raw and processed evidence used by the project.

### 2.2 Evidence rules

1. Running code and configuration override prose documentation.
2. Machine-readable artifacts override manually copied metrics.
3. A source implementation proves capability, not successful execution.
4. A dated validation report is “previously validated” unless rerun now.
5. Missing dependencies, services, credentials, or artifacts are recorded as
   blockers, not silently replaced with a passing claim.

### 2.3 Reviewed update context

The review includes commit `c6cc994`, which constrains pandas below 3 and
PyArrow below 22 for MLflow compatibility, changes the local MLflow backend to
SQLite, and records the current thesis/report updates. Ignored local artifacts
were inspected as execution evidence but are not committed as source files.

## 3. Completion matrix

| Capability | Status | Evidence |
|---|---|---|
| Raw IEEE-CIS validation | Complete | Source inventory with sizes/checksums |
| Typed Spark ingestion and joins | Complete | Pipeline source and join audit |
| EDA and data-quality reporting | Complete | Generated CSV/JSON/PNG reports |
| Chronological leakage-controlled split | Complete | Split artifacts and verifier |
| Model-ready contracts | Complete | Schema, feature order, medians, policies |
| Data handover verification | Complete | 82 passed, 0 failed |
| Baseline and multi-model comparison | Complete | Scripts and V1/V2 comparison JSON |
| V2 final artifact | Present | Joblib plus training metadata |
| V2 independent reproduction | Partial | Metrics saved; local model load initially blocked |
| `0.0.2` candidate artifact | Present | XGBoost, calibration, thresholds, holdout metrics |
| MLflow implementation | Verified locally | SQLite backend and five finished stage runs |
| MLflow run history | Partial | Local/ignored history exists; no registry or promotion record |
| Probability calibration | Candidate-only | Isotonic calibration saved for `0.0.2`, not V2 |
| Business threshold policy | Not complete | Candidate thresholds are not enforced by backend |
| SHAP local explanations | Implemented | TreeSHAP scoring and UI |
| FastAPI scoring/review API | Complete for demo | Routes, schemas, tests |
| PostgreSQL/SQLite persistence | Complete for demo | SQLAlchemy models and Compose |
| CSV import and background loading | Complete for demo | Routes, jobs, loader |
| React investigation UI | Complete for demo | Five routes and components |
| Frontend automated testing | Not complete | Build/lint/manual checks only |
| Docker application topology | Complete for demo | Compose and Dockerfiles |
| Production security/operations | Not complete | No auth, durable queue, migrations, SLOs |

## 4. Key findings

### F1. The processed-data handoff is the strongest part of the system

**Severity:** informational
**Confidence:** high

The pipeline exports explicit schemas, feature order, medians, categorical
policy, imbalance configuration, split thresholds, data-quality reports, and
model-ready Parquet datasets. The verifier checks row counts, uniqueness,
schema hashes, split overlap, chronological order, required columns, and
artifact presence.

This provides an auditable boundary between data engineering and model training.
The remaining defect is lifecycle consistency: the top-level manifest still
states `verification_pending` although the later verification report states
`ready_for_downstream_training`.

### F2. V2 is the offline champion, not a fully governed production model

**Severity:** high
**Confidence:** high

Saved metadata reports that V2 LightGBM improves holdout PR-AUC from `0.4298` to
`0.4582`, a relative increase of approximately `6.59%`. However:

- V1 and V2 use different feature contracts (53 versus 68 features);
- the review initially could not load V2 without installing LightGBM;
- V2 metadata omits operating-point precision/recall/confusion counts;
- V2 has no calibration or threshold artifact;
- model checksums and registry records are absent;
- the later `0.0.2` XGBoost candidate has fuller evaluation evidence but a lower
  holdout PR-AUC (`0.4318`) than V2 (`0.4582`) and is not the serving default.

The correct statement is therefore: **V2 is the artifact-reported offline
champion and current code default; production effectiveness is not established.**

### F3. Legacy model-promotion wording has been reconciled

**Severity:** informational
**Confidence:** high

`model/src/fraud_model/config.py` defaults to V2. Before this follow-up review,
the scoring module docstring still said V1 was the current default; it has now
been corrected. The V1/V2 comparison report also previously mixed “do not
promote yet” recommendations with “V2 has been promoted” conclusions; those
statements now consistently distinguish the V2 software default from an
unrecorded production promotion.

Operational source truth is V2-by-default with an environment rollback to V1.
The documentation should continue to separate that software default from a
business-approved production promotion.

### F4. Decision policy is fixed in the backend

**Severity:** high
**Confidence:** high

The model interface can expose threshold metadata, but the backend derives
decisions from fixed score bands:

- below 40: approve;
- 40–79: review;
- 80–100: reject.

This policy is not connected to model validation costs or review capacity.
Future threshold work must either replace the fixed policy or define how model
thresholds and risk bands interact. Returning unused threshold metadata would
otherwise create a false impression that the policy is model-driven.

### F5. Heuristic fallback favors demo continuity over fail-closed safety

**Severity:** high
**Confidence:** high

When the model package or artifact cannot load, the backend can use a heuristic
scorer and expose a warning. This is useful during a short demonstration, but a
production service should fail readiness or require explicit demo-mode opt-in.
Otherwise syntactically valid scores may be mistaken for model predictions.

### F6. MLflow run history exists, but controlled promotion does not

**Severity:** high
**Confidence:** high

The local SQLite tracking database contains five finished `0.0.2` stage runs:
baseline, candidate comparison, validation/tuning, threshold/calibration, and
final holdout. Parameters and metrics are queryable, and the candidate artifact
directory contains the corresponding evaluation files.

The evidence remains local and Git-ignored. Artifact URIs reference the
container-local `/app/artifacts/mlflow-artifacts` path, and the database has no
registered models, model versions, promotion aliases, immutable model checksum,
or approval/rollback record. MLflow therefore supports local experiment audit,
but not yet a portable model-registry or controlled-promotion claim.

### F7. Backend and frontend are complete for the intended demonstration

**Severity:** informational
**Confidence:** high

The application supports health/metadata, scoring, transaction exploration,
statistics, review, import, dataset discovery, background loading, job progress,
and cancellation. The UI supports transaction list/detail, review queue,
ad-hoc scoring, import/data loading, SHAP, theming, and a rule-based assistant.

The major caveat is that backend API documentation had fallen behind the newer
dataset/job and metadata shapes. The frontend TypeScript declarations also omit
some current backend fields (`processing_version`, `feature_schema_version`,
feature requirement lists, and `scoring_mode`). Runtime calls tolerate extra JSON
properties, but generated types or a manual synchronization change is still
needed. `docs/API_CONTRACT.md` is updated as part of this documentation delivery.

### F8. Automated assurance is uneven across subsystems

**Severity:** medium
**Confidence:** high

Model and backend unit/API tests exist. The only GitHub Actions workflow covers
the model. The frontend has type checking, linting, a static UI checker, and a
manual accessibility checklist, but no automated component or browser tests.

The minimum CI expansion should run:

- processed-contract smoke checks;
- model lint/tests;
- backend lint/tests;
- frontend lint/build;
- an application contract smoke using the real OpenAPI schema.

### F9. Application operations are intentionally non-durable

**Severity:** medium
**Confidence:** high

Background jobs are stored in memory, only one loader can run, database tables
are created without migrations, CSV import is synchronous, and there is no
re-score workflow. These are acceptable demo tradeoffs but must not be presented
as scalable production architecture.

### F10. Security controls are below a deployable baseline

**Severity:** critical for external deployment
**Confidence:** high

There is no authentication, authorization, rate limiting, audit event history,
secret-management integration, or production credential policy. Development
database credentials and permissive local CORS settings are visible in Compose.
The system should remain local/private until these controls are designed.

## 5. Interface reconciliation

### 5.1 Data-to-model

The model correctly prioritizes canonical `feature_order.json`, rejects missing
canonical columns, and excludes metadata. Categorical mappings are fitted on
training and reused for later windows and serving. This fixes an earlier
`split_name` leakage/type-conversion defect.

### 5.2 Model-to-backend

The backend expects:

- model and schema version metadata;
- feature requirements;
- probability and optional SHAP;
- scoring mode;
- optional threshold metadata.

Risk policy remains backend-owned. Version and fallback state must be visible to
operators.

### 5.3 Backend-to-frontend

Pydantic and TypeScript shapes are manually synchronized. The current frontend
already consumes newer fields such as dataset descriptions, job progress, import
coverage, and `scoring_mode`; the previous Markdown contract did not document
all of them.

OpenAPI-generated types would reduce this three-source synchronization risk.

## 6. Validation matrix

| Check | Current assessment | Limitation |
|---|---|---|
| Python source compilation | Previously passed for key modules | Not equivalent to dependency/runtime test |
| YAML/JSON parsing | Previously passed | Generated reports may change independently |
| Compose syntax | Previously passed with Docker config warning | Docker engine access unavailable during initial review |
| Data verifier | Saved 82/82 pass | Manifest status is stale |
| Model unit tests | Test suite exists | Requires model environment |
| Model artifact smoke | Blocked initially by missing LightGBM | Must run in frozen container/environment |
| Backend tests | Test suite documents 23 tests | Real-model path is mocked/fallback-safe |
| Frontend build/lint | Scripts exist | No dependencies installed initially |
| Browser accessibility | Manual checklist | No automated axe/end-to-end evidence |
| Full-stack smoke | Previously reported | Not rerun until Docker access is available |

## 7. Severity matrix

| ID | Finding | Severity | Recommended owner |
|---|---|---|---|
| R1 | No auth/authorization/audit controls | Critical | Backend/platform |
| R2 | Missing fail-closed model readiness | High | Model/backend |
| R3 | Threshold policy not connected to validation | High | Model/product/backend |
| R4 | Local MLflow runs exist, but registry/promotion/checksum evidence is absent | High | ML engineering |
| R5 | Candidate calibration/thresholds are not the served backend policy | High | ML engineering/product/backend |
| R6 | Manifest/verifier lifecycle status mismatch | Medium | Data engineering |
| R7 | No durable jobs or schema migrations | Medium | Backend/platform |
| R8 | No automated frontend/browser tests | Medium | Frontend |
| R9 | Manual API type synchronization | Medium | Backend/frontend |
| R10 | Driver-memory pandas training boundary | Medium | ML/data engineering |
| R11 | No bulk re-score/version-isolated analytics | Medium | Backend/product |

## 8. Recommended remediation sequence

### Gate 1 — Reproducible model serving

1. Resolve and freeze model dependencies.
2. Build the model/backend container with `uv sync --frozen`.
3. Load V2 and score a full-feature holdout example without heuristic fallback.
4. Record SHA-256, model/schema/processing versions, and inference environment.

### Gate 2 — Evidence-based policy

1. Reproduce calibration and threshold tables on windows not reused for model
   selection.
2. Define review capacity and error costs.
3. Approve or revise the `0.0.2` review/reject thresholds against explicit
   targets and compare them with V2.
4. Connect the approved contract to backend decisions and test exact boundaries
   in model and API layers.

### Gate 3 — Operational assurance

1. Add readiness, structured logs, metrics, and drift/score monitoring.
2. Add migrations and durable jobs.
3. Add authentication, authorization, secret handling, and audit history.
4. Add CI for backend, frontend, contract, and full-stack smoke tests.

### Gate 4 — Controlled promotion

1. Run shadow scoring against the incumbent.
2. Compare paired predictions and operating metrics.
3. Approve a documented promotion with rollback evidence.
4. Re-score or isolate historical transactions by model version.

## 9. Final assessment

The project successfully demonstrates how a big-data pipeline, a tabular fraud
model, an explainable scoring API, and a human-review dashboard can be connected
within one repository. The data engineering handoff is unusually explicit for a
short academic project, and the application provides a credible end-to-end
demonstration.

The next engineering value comes from evidence and controls, not from adding
more model families or UI screens. A reproducible served artifact, an approved
operating policy, auditable runs, fail-closed readiness, and baseline security
would materially change the system from a demonstration into a deployable
candidate.

## 10. Source inventory

- current repository source, package manifests, lock files, tests, and Compose;
- `data/processed/ieee_cis_fraud_risk/manifest.json`;
- generated split, join, imbalance, schema, EDA, and verification reports;
- `model/artifacts/model_comparison.json`;
- `model/artifacts/v2/model_comparison_v2.json`;
- `model/artifacts/v2/training_metadata_v2.json`;
- ignored local `model/artifacts/0.0.2/` calibration, threshold, validation, and
  holdout evidence;
- ignored local `model/artifacts/mlflow.db` run/metric/parameter records;
- `reports/static_validation_report.md`;
- `reports/runtime_validation_report.md`;
- `reports/MODEL_TRAINING_REVIEW_REPORT.md`.
