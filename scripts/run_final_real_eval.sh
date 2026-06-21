#!/usr/bin/env bash
set -euo pipefail
MODEL_DIR="${1:-outputs/nuosubburma_v5_16_synth_capped_rerender_lora/export}"
DATASET="${2:-data/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl}"
OUT_DIR="${3:-outputs/final_clean603_eval}"
mkdir -p "${OUT_DIR}"
scripts/run_eval.sh "${MODEL_DIR}" "${DATASET}" "${OUT_DIR}/eval_main_result.jsonl" 2>&1 | tee "${OUT_DIR}/eval_main.log"
