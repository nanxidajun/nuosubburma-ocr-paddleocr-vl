#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

CONDA_BASE="${CONDA_BASE:-/root/miniconda3}"
CONDA_ENV="${CONDA_ENV:-paddleocr-vl}"
HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
BASE_MODEL="${BASE_MODEL:-/root/.cache/huggingface/hub/models--PaddlePaddle--PaddleOCR-VL-1.6/snapshots/66317acc4c9fc17bd154591ce650735cd2855f3e}"
RUN_DIR="${RUN_DIR:-outputs/nuosubburma_v5_16_synth_capped_rerender_lora}"
EXPORT_CONFIG="${EXPORT_CONFIG:-configs/paddleocr-vl_lora_export_nuosubburma_v5_16.yaml}"
EXPORT_DIR="${RUN_DIR}/export"
REAL_EVAL_DATASET="${REAL_EVAL_DATASET:-data/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl}"
REAL_EVAL_OUT_DIR="${REAL_EVAL_OUT_DIR:-outputs/final_clean603_eval}"

if [ -f "${CONDA_BASE}/etc/profile.d/conda.sh" ]; then
  source "${CONDA_BASE}/etc/profile.d/conda.sh"
  conda activate "${CONDA_ENV}"
fi

export HF_ENDPOINT

if [ ! -f "${EXPORT_DIR}/model.safetensors.index.json" ]; then
  echo "[1/2] Exporting LoRA: ${RUN_DIR} -> ${EXPORT_DIR}"
  paddleformers-cli export "${EXPORT_CONFIG}"     model_name_or_path="${BASE_MODEL}"     output_dir="${RUN_DIR}"
else
  echo "[1/2] Export already exists: ${EXPORT_DIR}"
fi

echo "[2/2] Run frozen real main eval only: ${REAL_EVAL_DATASET}"
scripts/run_final_real_eval.sh "${EXPORT_DIR}" "${REAL_EVAL_DATASET}" "${REAL_EVAL_OUT_DIR}"
