#!/usr/bin/env bash
# 安装后健康检查：验证依赖、样例图和本地模型是否能跑通单图 OCR。
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CALL_DIR="$(pwd)"
cd "${ROOT_DIR}"

resolve_path() {
  local input_path="$1"
  local base_dir="$2"
  if [[ "${input_path}" = /* ]]; then
    printf '%s\n' "${input_path}"
  else
    printf '%s\n' "${base_dir}/${input_path}"
  fi
}

if [[ -n "${MODEL_PATH:-}" ]]; then
  MODEL_PATH="$(resolve_path "${MODEL_PATH}" "${CALL_DIR}")"
else
  MODEL_PATH="$(resolve_path "models/NuosuBburma-OCR" "${ROOT_DIR}")"
fi

if [[ -n "${IMAGE_PATH:-}" ]]; then
  IMAGE_PATH="$(resolve_path "${IMAGE_PATH}" "${CALL_DIR}")"
else
  IMAGE_PATH="$(resolve_path "demo/sample_images/mixed_line.png" "${ROOT_DIR}")"
fi

DEVICE="${DEVICE:-gpu}"
MAX_NEW_TOKENS="${MAX_NEW_TOKENS:-128}"
PYTHON_BIN="${PYTHON:-}"
if [[ -n "${PYTHON_BIN}" && "${PYTHON_BIN}" == */* && "${PYTHON_BIN}" != /* ]]; then
  PYTHON_BIN="$(resolve_path "${PYTHON_BIN}" "${CALL_DIR}")"
fi
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK="${PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK:-True}"
export SMOKE_IMAGE_PATH="${IMAGE_PATH}"

if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "找不到 Python。请先创建并激活 Python 3.11 环境。" >&2
    exit 1
  fi
fi

if [[ "${PYTHON_BIN}" == */* ]]; then
  if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "找不到可执行 Python：${PYTHON_BIN}" >&2
    echo "请先激活环境，或用 PYTHON=/path/to/python 指定正确路径。" >&2
    exit 1
  fi
elif ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "找不到 Python 命令：${PYTHON_BIN}" >&2
  echo "请先激活环境，或用 PYTHON=/path/to/python 指定正确路径。" >&2
  exit 1
fi

echo "[1/3] 检查 Python 依赖"
echo "仓库目录：${ROOT_DIR}"
echo "样例图：${IMAGE_PATH}"
if [[ ! -f "${IMAGE_PATH}" ]]; then
  echo "找不到样例图：${IMAGE_PATH}" >&2
  exit 1
fi

"${PYTHON_BIN}" - <<'PY'
import importlib.metadata as metadata
import os
import sys
from pathlib import Path

packages = [
    "paddleocr",
    "paddleformers",
    "Pillow",
    "tqdm",
    "python-Levenshtein",
    "numpy",
    "huggingface_hub",
]

missing = []
versions = []
for dist_name in packages:
    try:
        versions.append((dist_name, metadata.version(dist_name)))
    except metadata.PackageNotFoundError:
        missing.append(dist_name)

if missing:
    print("已安装依赖：")
    for dist_name, version in versions:
        print(f"- {dist_name} {version}")
    print("\n缺少以下依赖：")
    for dist_name in missing:
        print(f"- {dist_name}")
    print("\n请先执行：")
    print("python -m pip install -r requirements.txt")
    sys.exit(1)

import paddle
from PIL import Image
import Levenshtein

print("已安装依赖：")
for dist_name, version in versions:
    print(f"- {dist_name} {version}")
print(f"- paddle {paddle.__version__}")
print(f"paddle_device {paddle.device.get_device()}")
print(f"levenshtein_check {Levenshtein.distance('abc', 'adc')}")

sample = Path(os.environ["SMOKE_IMAGE_PATH"])
with Image.open(sample) as image:
    print(f"sample_image {sample} size={image.size}")
PY

echo "[2/3] 检查模型目录"
echo "模型目录：${MODEL_PATH}"

if [[ ! -d "${MODEL_PATH}" ]]; then
  cat <<EOF
模型目录不存在：${MODEL_PATH}

依赖和样例图检查已通过。要继续跑单图 OCR，请先下载模型：

hf download nanxidajun/NuosuBburma-OCR \\
  --repo-type model \\
  --local-dir "${MODEL_PATH}"

如果国内网络较慢，可先设置：

export HF_ENDPOINT=https://hf-mirror.com
EOF
  exit 0
fi

if [[ ! -f "${MODEL_PATH}/config.json" ]]; then
  echo "模型目录存在，但缺少 config.json：${MODEL_PATH}" >&2
  exit 1
fi

echo "[3/3] 运行单图 OCR 自检"
"${PYTHON_BIN}" demo/infer_single_image.py \
  --model "${MODEL_PATH}" \
  --image "${IMAGE_PATH}" \
  --device "${DEVICE}" \
  --max-new-tokens "${MAX_NEW_TOKENS}"

echo "smoke check passed"
