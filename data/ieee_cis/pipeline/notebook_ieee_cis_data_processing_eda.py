from __future__ import annotations

import importlib.util
import json
import os
import re
import runpy
from pathlib import Path

PROJECT_ROOT = Path.cwd().resolve()
if not (PROJECT_ROOT / 'data' / 'ieee_cis').is_dir():
    PROJECT_ROOT = Path(r'D:\\MSE\\16. Big Data\\Fraud-Detection-Score-Risk')
OUTPUT_DIR = PROJECT_ROOT / 'data' / 'processed' / 'ieee_cis_spark'
PIPELINE_DIR = PROJECT_ROOT / 'data' / 'ieee_cis' / 'pipeline'
os.environ.setdefault('PROJECT_ROOT', str(PROJECT_ROOT))
os.environ.setdefault('IEEE_CIS_OUTPUT_DIR', str(OUTPUT_DIR))
os.environ.setdefault('PIPELINE_SEED', '42')
print('PROJECT_ROOT =', PROJECT_ROOT)
print('OUTPUT_DIR  =', OUTPUT_DIR)


required_packages = ['pyspark', 'pandas', 'numpy']
missing_packages = [name for name in required_packages if importlib.util.find_spec(name) is None]
if missing_packages:
    raise RuntimeError(f'Missing packages: {missing_packages}. Install docker/requirements.preprocessing.txt or run Docker.')

RUN_MODEL_DEMO = os.getenv('RUN_MODEL_DEMO', 'true').lower() in {'1', 'true', 'yes'}
WRITE_WIDE_FEATURE_STORE = os.getenv('WRITE_WIDE_FEATURE_STORE', 'true').lower() in {'1', 'true', 'yes'}
print({'RUN_MODEL_DEMO': RUN_MODEL_DEMO, 'WRITE_WIDE_FEATURE_STORE': WRITE_WIDE_FEATURE_STORE})


REQUIRED_FILES = ['train_transaction.csv', 'train_identity.csv', 'test_transaction.csv', 'test_identity.csv']
candidate_dirs = [
    PROJECT_ROOT / 'data' / 'ieee-cis-fraud-detection',
    PROJECT_ROOT / 'data' / 'data' / 'ieee-fraud-detection',
    PROJECT_ROOT / 'data' / 'data' / 'ieee-cis-fraud-detection',
    PROJECT_ROOT / 'data' / 'raw',
    Path('/app/data/raw'),
    Path('/data/raw'),
]
source_dir = next((p for p in candidate_dirs if all((p / name).is_file() for name in REQUIRED_FILES)), None)
if source_dir is None:
    checked = '\n'.join(f' - {p}' for p in candidate_dirs)
    raise FileNotFoundError(f'IEEE-CIS files not found. Checked:\n{checked}')

inventory = []
for path in sorted(source_dir.iterdir()):
    if path.is_file() and (path.suffix == '.csv'):
        inventory.append({'filename': path.name, 'path': str(path), 'size_mb': round(path.stat().st_size / 1024**2, 2)})
inventory_total_mb = sum(row['size_mb'] for row in inventory if row['filename'] in REQUIRED_FILES)
print(json.dumps({'source_dir': str(source_dir), 'required_size_mb': inventory_total_mb, 'files': inventory}, indent=2))
assert inventory_total_mb >= 500, 'The required IEEE-CIS files must exceed 500 MB.'


spark_config = {
    'SPARK_MASTER': os.getenv('SPARK_MASTER', 'local[*]'),
    'SPARK_DRIVER_MEMORY': os.getenv('SPARK_DRIVER_MEMORY', '6g'),
    'SPARK_SHUFFLE_PARTITIONS': os.getenv('SPARK_SHUFFLE_PARTITIONS', '32'),
    'SPARK_DEFAULT_PARALLELISM': os.getenv('SPARK_DEFAULT_PARALLELISM', '16'),
    'SPARK_SESSION_TIMEZONE': 'UTC',
    'PARQUET_COMPRESSION': 'snappy',
}
print(json.dumps(spark_config, indent=2))


pipeline_entrypoint = PIPELINE_DIR / 'data_processing_eda.py'
if not pipeline_entrypoint.is_file():
    raise FileNotFoundError(f'Pipeline entrypoint not found: {pipeline_entrypoint}')

# Keep execution settings visible and deterministic. Docker overrides these as needed.
os.environ.setdefault('RUN_FULL_PROFILE', 'true')
os.environ.setdefault('RUN_MODEL_DEMO', 'true')
os.environ.setdefault('WRITE_WIDE_FEATURE_STORE', 'true')
runpy.run_path(str(pipeline_entrypoint), run_name='__main__')


import pandas as pd

REPORTS_DIR = OUTPUT_DIR / 'reports'
DEMO_DIR = OUTPUT_DIR / 'demo'

def report_path(stem: str) -> Path | None:
    candidates = [REPORTS_DIR / stem, REPORTS_DIR / f'{stem}.csv', REPORTS_DIR / f'{stem}_csv']
    for candidate in candidates:
        if candidate.is_file():
            return candidate
        if candidate.is_dir():
            parts = sorted(candidate.glob('part-*.csv'))
            if parts:
                return parts[0]
    return None

def read_report(stem: str, rows: int = 20) -> pd.DataFrame:
    path = report_path(stem)
    if path is None:
        return pd.DataFrame()
    return pd.read_csv(path).head(rows)

def show_report(stem: str, rows: int = 20) -> None:
    frame = read_report(stem, rows)
    print(f'--- {stem} ---')
    display(frame) if 'display' in globals() else print(frame.to_string(index=False))


show_report('source_inventory', 20)
show_report('key_audit', 10)
show_report('join_audit', 10)


show_report('data_profile_csv', 30)
show_report('class_distribution_csv', 10)
print('Imbalance summary:')
imbalance_path = REPORTS_DIR / 'imbalance_summary.json'
if imbalance_path.is_file():
    print(json.dumps(json.loads(imbalance_path.read_text(encoding='utf-8')), indent=2))
show_report('class_balance_report_csv', 10)


sql_report_names = [
    'fraud_overview_csv', 'fraud_by_product_csv', 'fraud_by_card4_csv',
    'fraud_by_card6_csv', 'fraud_by_amount_band_csv', 'fraud_by_device_csv',
    'fraud_by_email_csv', 'fraud_by_hour_csv', 'fraud_by_week_csv',
]
for name in sql_report_names:
    show_report(name, 15)


show_report('chronological_split_csv', 10)
manifest_path = OUTPUT_DIR / 'manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.is_file() else {}
print(json.dumps({
    'split_boundaries': manifest.get('split_boundaries'),
    'numeric_features': manifest.get('numeric_features', []),
    'categorical_features': manifest.get('categorical_features', []),
}, indent=2))


feature_store_dirs = sorted((OUTPUT_DIR / 'feature_store').glob('*')) if (OUTPUT_DIR / 'feature_store').exists() else []
print('Feature-store outputs:')
for path in feature_store_dirs:
    print(' -', path.relative_to(OUTPUT_DIR))


metrics = read_report('decision_tree_metrics_csv', 100)
if metrics.empty:
    metrics_json = REPORTS_DIR / 'decision_tree_metrics.json'
    if metrics_json.is_file():
        metrics = pd.DataFrame(json.loads(metrics_json.read_text(encoding='utf-8')).get('metrics', []))
if metrics.empty:
    print('Decision Tree metrics are unavailable. Set RUN_MODEL_DEMO=true and rerun.')
else:
    display(metrics) if 'display' in globals() else print(metrics.to_string(index=False))


demo_names = ['demo_cases_csv', 'real_fraud_cases_csv', 'real_legitimate_cases_csv', 'true_positive_cases_csv', 'true_negative_cases_csv', 'false_positive_cases_csv', 'false_negative_cases_csv', 'kaggle_test_predictions_csv']
for name in demo_names:
    path = None
    for candidate in [DEMO_DIR / name, DEMO_DIR / f'{name}.csv']:
        if candidate.is_file():
            path = candidate
            break
        if candidate.is_dir():
            parts = sorted(candidate.glob('part-*.csv'))
            if parts:
                path = parts[0]
                break
    if path:
        print(f'--- {name} ---')
        display(pd.read_csv(path).head(10)) if 'display' in globals() else print(pd.read_csv(path).head(10).to_string(index=False))


required_outputs = [
    OUTPUT_DIR / 'manifest.json',
    OUTPUT_DIR / 'HANDOVER_TO_QUAN.md',
    REPORTS_DIR,
]
missing_outputs = [str(path) for path in required_outputs if not path.exists()]
if missing_outputs:
    raise FileNotFoundError(f'Missing required preprocessing outputs: {missing_outputs}')

print('Manifest:', manifest_path)
print('Handover:', OUTPUT_DIR / 'HANDOVER_TO_QUAN.md')
print('Reports:', REPORTS_DIR)
print('Notebook validation: PASS')

