#!/usr/bin/env bash
# PySpark cần JAVA_HOME; tính động để không phụ thuộc kiến trúc CPU
# (đường dẫn openjdk khác nhau giữa amd64/arm64).
set -euo pipefail
export JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(which java)")")")"
exec "$@"
