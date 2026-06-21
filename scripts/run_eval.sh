#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

MODEL_PATH="${1:-outputs/nuosubburma_v5_16_synth_capped_rerender_lora/export}"
DATASET="${2:-datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl}"
OUTPUT_PATH="${3:-outputs/eval_yi_result.jsonl}"

mkdir -p outputs/eval_logs "$(dirname "${OUTPUT_PATH}")"

CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}" python -m paddle.distributed.launch   --log_dir outputs/eval_logs   scripts/eval_nuosubburma.py   --model_name_or_path "${MODEL_PATH}"   --data_path "${DATASET}"   --output_path "${OUTPUT_PATH}"
