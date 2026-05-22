#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
OUT_ARG="${1:-backend_clean.zip}"

if [[ "${OUT_ARG}" = /* ]]; then
  OUT_PATH="${OUT_ARG}"
else
  OUT_PATH="${ROOT_DIR}/${OUT_ARG}"
fi

mkdir -p "$(dirname "${OUT_PATH}")"
rm -f "${OUT_PATH}"

cd "${BACKEND_DIR}"
zip -r "${OUT_PATH}" . \
  -x "__MACOSX/*" \
  -x "*/__MACOSX/*" \
  -x "__pycache__/" \
  -x "*.DS_Store" \
  -x "*/.DS_Store" \
  -x "._*" \
  -x "*/._*" \
  -x "*/__pycache__/" \
  -x "*/__pycache__/*" \
  -x "*.pyc" \
  -x "*.pyo" \
  -x ".pytest_cache/*" \
  -x ".mypy_cache/*" \
  -x ".ruff_cache/*" \
  -x ".git/*" \
  -x ".venv/*" \
  -x "venv/*" \
  -x "env/*" \
  -x "node_modules/*"

echo "Created package: ${OUT_PATH}"
