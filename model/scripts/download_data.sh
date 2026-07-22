#!/usr/bin/env bash
# Tải bộ IEEE-CIS Fraud Detection từ Kaggle vào model/data/raw/
#
# Yêu cầu trước:
#   1. Tài khoản Kaggle + tham gia competition "ieee-fraud-detection"
#      (https://www.kaggle.com/c/ieee-fraud-detection/rules)
#   2. Kaggle API token: Kaggle > Settings > Create New Token, tải kaggle.json
#      đặt tại ~/.kaggle/kaggle.json (chmod 600) hoặc export KAGGLE_USERNAME/KAGGLE_KEY
#   3. Cài kaggle CLI: uv run --with kaggle kaggle --version  (hoặc pip install kaggle)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAW_DIR="${SCRIPT_DIR}/../data/raw"

mkdir -p "${RAW_DIR}"

echo "Downloading ieee-fraud-detection into ${RAW_DIR} ..."
kaggle competitions download -c ieee-fraud-detection -p "${RAW_DIR}"

echo "Unzipping ..."
unzip -o "${RAW_DIR}/ieee-fraud-detection.zip" -d "${RAW_DIR}"

echo "Done. Expected files:"
ls "${RAW_DIR}"/*.csv
