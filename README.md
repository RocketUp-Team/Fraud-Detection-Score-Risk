<h1 align="center">
  🛡️ Fraud Detection & Risk Scoring System
</h1>

<p align="center">
  <b>BDA501 — Big Data Analytics Capstone Project</b><br>
  FPT University · 2026 · Group <b>RocketUpTeam</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Apache_Spark-E25A1C?style=for-the-badge&logo=apachespark&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/CatBoost-FFCC00?style=for-the-badge&logo=catboost&logoColor=black" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
</p>

---

## 📋 Overview

An end-to-end fraud detection platform that processes **590K+ transactions** through a distributed **Apache Spark** pipeline, trains and evaluates **CatBoost** gradient boosting models with **68 engineered features**, and serves real-time risk scores via a **FastAPI** backend and **React** analyst dashboard with **TreeSHAP** explainability.

---

## 🏗️ System Architecture

<p align="center">
  <img src="docs/diagrams/final/overall-system-architecture.png" width="90%" alt="Overall System Architecture" />
</p>

| Subsystem | Stack | Purpose |
|---|---|---|
| 🔄 **Data Pipeline** | Apache Spark, PySpark | Distributed ETL, feature engineering, temporal splitting |
| 🧠 **Model Training** | CatBoost, LightGBM, XGBoost, Scikit-learn | Model comparison, isotonic calibration, promotion gates |
| ⚡ **Backend API** | FastAPI, PostgreSQL, Docker | Real-time scoring, SHAP explanations, transaction management |
| 🖥️ **Frontend** | React, TypeScript, Vite | Risk dashboard, score visualization, analyst review workflow |

---

## 📊 Key Metrics

<table>
  <tr>
    <th>Metric</th>
    <th>Validation</th>
    <th>Holdout</th>
  </tr>
  <tr>
    <td><b>🎯 PR-AUC</b></td>
    <td><code>0.5806</code></td>
    <td><code>0.4266</code></td>
  </tr>
  <tr>
    <td><b>📈 ROC-AUC</b></td>
    <td><code>0.9081</code></td>
    <td><code>0.8781</code></td>
  </tr>
  <tr>
    <td><b>🔍 Precision</b></td>
    <td><code>0.3970</code></td>
    <td><code>0.3820</code></td>
  </tr>
  <tr>
    <td><b>📡 Recall</b></td>
    <td><code>0.6220</code></td>
    <td><code>0.5182</code></td>
  </tr>
  <tr>
    <td><b>📐 Brier Score</b></td>
    <td>—</td>
    <td><code>0.0248</code></td>
  </tr>
</table>

> 🏆 **Best model**: CatBoost Balanced · 68 features · Isotonic calibration
> ⚠️ **Status**: `not_promoted` — holdout PR-AUC below promotion threshold

---

## 🖥️ Application Screenshots

### 📋 Transaction Monitoring Queue
<p align="center">
  <img src="screenshots/demo/transactions.png" width="90%" alt="Transaction Queue" />
</p>

### 🎯 Risk Score & SHAP Feature Importance
<p align="center">
  <img src="screenshots/demo/score-result.png" width="90%" alt="Score Result" />
</p>

### 🔎 Transaction Detail Panel
<p align="center">
  <img src="screenshots/demo/detail.png" width="90%" alt="Detail Panel" />
</p>

### ✅ Analyst Fraud Review Workflow
<p align="center">
  <img src="screenshots/demo/review.png" width="90%" alt="Review Workflow" />
</p>

### 📖 API Documentation (Swagger)
<p align="center">
  <img src="screenshots/demo/api-docs.png" width="90%" alt="API Docs" />
</p>

---

## 🔄 Data Pipeline

<p align="center">
  <img src="docs/diagrams/final/detailed-data-processing-pipeline.png" width="90%" alt="Detailed Data Processing Pipeline" />
</p>

- **📥 Input**: IEEE-CIS Fraud Detection — 590K transactions, 434 raw columns
- **📤 Output**: 6 model-ready Parquet partitions, **68 engineered features** (61 numeric, 7 categorical)

| Dataset | Rows | Purpose |
|---|---:|---|
| `train_original` | 412,956 | Natural distribution training |
| `train_weighted` | 412,956 | Class-weighted training |
| `train_balanced` | 58,394 | Undersampled balanced training |
| `validation` | 88,486 | Model selection / calibration / policy |
| `holdout` | 89,098 | Final single-use evaluation |
| `kaggle_test` | 506,691 | Unlabeled scoring |

### 📜 Data & Feature Contracts
<p align="center">
  <img src="docs/diagrams/final/data-feature-evaluation-contracts.png" width="85%" alt="Data, Feature, and Evaluation Contracts" />
</p>

---

## 🧠 Model Training

<p align="center">
  <img src="docs/diagrams/final/End-to-End-Model-Training-Lifecycle.png" width="90%" alt="Model Training Lifecycle" />
</p>

### 🏅 Model Family Comparison (Validation PR-AUC)

| # | Model | Dataset | PR-AUC | ROC-AUC |
|--:|---|---|---:|---:|
| 🥇 | **CatBoost** | **Balanced** | **0.5703** | 0.9070 |
| 🥈 | XGBoost | Balanced | 0.5696 | 0.9086 |
| 🥉 | LightGBM | Weighted | 0.5682 | 0.9116 |
| 4 | LightGBM | Balanced | 0.5677 | 0.9078 |
| 5 | XGBoost | Weighted | 0.5529 | 0.8879 |
| 6 | CatBoost | Weighted | 0.5245 | 0.8757 |
| 7 | LogReg | Balanced | 0.3201 | 0.8185 |
| 8 | LogReg | Weighted | 0.3090 | 0.8219 |

### 🚦 Promotion Gate

<p align="center">
  <img src="docs/diagrams/final/promotion-state-machine.png" width="80%" alt="Promotion State Machine" />
</p>

9 automated gates evaluate each candidate:

| Gate | Result |
|---|---|
| Holdout PR-AUC ≥ 0.4582 | ❌ Fail (`0.4266`) |
| Holdout ROC-AUC ≥ 0.8746 | ✅ Pass (`0.8781`) |
| Review precision ≥ 0.30 | ✅ Pass (`0.3820`) |
| Calibration non-regression | ✅ Pass |
| Artifact checksum (SHA-256) | ✅ Pass |
| Artifact-load smoke test | ✅ Pass |
| Data contract verification | ✅ Pass |
| Version match | ✅ Pass |
| Git clean | ❌ Fail |

---

## 📁 Repository Structure

```
📦 Fraud-Detection-Score-Risk
├── 🔧 backend/                    → FastAPI scoring service + PostgreSQL
│   ├── src/fraud_backend/         → API routers, scoring, risk policy
│   └── tests/                     → API and risk unit tests
├── 🖥️ frontend/                   → React + TypeScript analyst dashboard
│   └── src/                       → Components, hooks, mock data
├── 🧠 model/                      → ML training, evaluation, serving
│   ├── src/fraud_model/           → Training scripts, score module, SHAP
│   └── artifacts/                 → Trained models, metrics, checksums
│       ├── v2/                    → Current CatBoost candidate artifacts
│       └── 0.0.3/                 → Versioned candidate run
├── 🔄 pipeline/                   → Data contract utilities & verification
├── 📊 data/
│   └── ieee_cis/pipeline/         → Spark preprocessing & feature engineering
├── 📚 docs/
│   ├── diagrams/final/            → Architecture & pipeline diagrams
│   ├── figures/final_report/      → EDA charts & evaluation plots
│   └── latex/                     → LaTeX thesis report source
├── 🛠️ scripts/                    → Automation (official run, training)
├── 🐳 docker-compose.yml          → Full application stack
└── 🐳 docker-compose.preprocessing.yml → Spark preprocessing pipeline
```

---

## 🚀 Quick Start

### Prerequisites
- 🐳 Docker & Docker Compose
- 📦 Raw data: [IEEE-CIS Fraud Detection](https://drive.google.com/file/d/1n-PNthwE5DCWEqYuZjsl__OXCJqyX3mI/view?usp=sharing) → `data/data/ieee-fraud-detection/`

### 1️⃣ Preprocessing (Spark)

```bash
docker compose -f docker-compose.preprocessing.yml build
docker compose -f docker-compose.preprocessing.yml run --rm preprocess
docker compose -f docker-compose.preprocessing.yml run --rm verify-processed
```

### 2️⃣ Model Training (Official Pipeline)

```bash
bash scripts/run_official_full.sh
```

### 3️⃣ Run Application Stack

```bash
docker compose up --build
```

| Port | Service | URL |
|---:|---|---|
| 🖥️ 5173 | React Dashboard | http://localhost:5173 |
| ⚡ 8000 | FastAPI + Swagger | http://localhost:8000/docs |
| 🗃️ 5432 | PostgreSQL | `user/pass/db = fraud` |
| 🔧 8081 | Adminer (optional) | `docker compose --profile tools up -d adminer` |

### 4️⃣ Run Without Docker

```bash
# Terminal 1 — Backend (Python ≥ 3.11 + uv)
cd backend && uv sync
uv run python -m fraud_backend.seed --limit 300
uv run uvicorn fraud_backend.main:app --reload

# Terminal 2 — Frontend (Node ≥ 20)
cd frontend && npm install && npm run dev
```

---

## 👥 Team

| Name | Role |
|---|---|
| 👨‍💼 **TUYEN Le Quang** | Project Leader — System ideation & project management |
| 🔧 **AN Duong Binh** | Big Data & Pipeline Engineer — Spark ingestion, feature engineering, data contracts |
| 🧠 **LONG Pham Duc** | Machine Learning Engineer — Model training, tuning, calibration & evaluation |
| ⚙️ **TRUNG Do Quoc** | Backend & API Engineer — FastAPI, database persistence, REST contracts |
| 🖥️ **QUAN Duong Hong** | Frontend & UI Engineer — React dashboard, risk visualizations, analyst workflow |
| 📝 **NHI Nguyen Le Hong** | Content & Presentation Coordinator — Documentation, slides, presentation strategy |

**🎓 Supervisor**: TAN Le Duy

---

## 🔌 API Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | 💚 Service health check |
| `GET` | `/meta` | 📋 Model & schema metadata |
| `POST` | `/score` | 🎯 Score transaction → probability, risk band, SHAP |
| `GET` | `/transactions` | 📊 Paginated transaction queue |
| `GET` | `/transactions/{id}` | 🔍 Transaction detail |
| `POST` | `/transactions/{id}/review` | ✅ Submit analyst review decision |
| `POST` | `/transactions/import` | 📥 Bulk CSV import |
| `POST` | `/data/load` | 🔄 Background data loading job |

📖 Full API contract: [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md)

---

## 📚 Documentation

| Document | Description |
|---|---|
| 📊 [Data Pipeline Architecture](docs/AN_DATA_PIPELINE_ARCHITECTURE_SUMMARY.md) | Spark preprocessing overview |
| 🏗️ [System Architecture Report](docs/AN_FINAL_DATA_AND_MODEL_ARCHITECTURE_REPORT.md) | Complete architecture documentation |
| 🔄 [Model V1/V2 Comparison](docs/AN_MODEL_V1_V2_COMPARISON_REPORT.md) | Champion–challenger analysis |
| 🔌 [API Contract](docs/API_CONTRACT.md) | REST endpoint specifications |
| 📖 [Data Dictionary](DATA_DICTIONARY.md) | Feature definitions & descriptions |
| 📜 [Data Contract](MODEL_READY_DATA_CONTRACT.md) | Model-ready data specification |
| 📄 [LaTeX Report (PDF)](docs/latex/report.pdf) | Final thesis report |

---

## 📄 License

This project is developed as part of the **BDA501** capstone at **FPT University**.
All rights reserved by **RocketUpTeam** © 2026.
