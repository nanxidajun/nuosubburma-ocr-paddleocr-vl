#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

CONDA_BASE="${CONDA_BASE:-/root/miniconda3}"
CONDA_ENV="${CONDA_ENV:-paddleocr-vl}"
HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
LOCAL_MODEL_SNAPSHOT="/root/.cache/huggingface/hub/models--PaddlePaddle--PaddleOCR-VL-1.6/snapshots/66317acc4c9fc17bd154591ce650735cd2855f3e"

if [ -f "${CONDA_BASE}/etc/profile.d/conda.sh" ]; then
  # AutoDL shells do not always start inside the training environment.
  source "${CONDA_BASE}/etc/profile.d/conda.sh"
  conda activate "${CONDA_ENV}"
fi

export HF_ENDPOINT
MODEL_NAME_OR_PATH="${MODEL_NAME_OR_PATH:-${LOCAL_MODEL_SNAPSHOT}}"

mkdir -p outputs

CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}" paddleformers-cli train   configs/paddleocr-vl_lora_16k_nuosubburma_v5_16.yaml   model_name_or_path="${MODEL_NAME_OR_PATH}"   train_dataset_path="${TRAIN_DATASET_PATH:-jsonl/train.jsonl}"   eval_dataset_path="${EVAL_DATASET_PATH:-jsonl/eval_yi.jsonl}"   output_dir="${OUTPUT_DIR:-outputs/nuosubburma_v5_16_synth_capped_rerender_lora}"   logging_dir="${LOGGING_DIR:-outputs/nuosubburma_v5_16_synth_capped_rerender_lora/visualdl_logs}"   pre_alloc_memory="${PRE_ALLOC_MEMORY:-18}"   "$@"
