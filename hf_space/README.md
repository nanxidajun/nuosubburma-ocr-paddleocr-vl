---
title: NuosuBburma OCR Demo
emoji: 📄
colorFrom: yellow
colorTo: red
sdk: gradio
sdk_version: 5.49.1
python_version: 3.11
app_file: app.py
suggested_hardware: l4x1
models:
  - nanxidajun/NuosuBburma-OCR
tags:
  - ocr
  - paddleocr
  - gradio
  - nuosu
  - yi
---

# NuosuBburma OCR GPU Space

这是 NuosuBburma OCR 的可复制 GPU Space 模板。它使用单一端到端模型识别规范彝文、汉字、拉丁字母、数字和标点，不调用额外的分类、检测或 OCR 路由模型。

## 运行条件

- Hugging Face Space 硬件：L4、A10G 或其他 CUDA GPU。
- Python：3.11。
- PaddlePaddle：`paddlepaddle-gpu==3.3.0`，CUDA 11.8 wheel。
- 模型提交：`12352adb52a26a3bcab0b5c38e42252009a3c12d`。

`suggested_hardware: l4x1` 只是页面提示，不会自动开通 GPU。复制该目录为新 Space 后，需在 Space 设置中选择 GPU 硬件。

## 复制到 Hugging Face Space

1. 新建 Gradio Space，Python 选择 3.11。
2. 把本目录中的 `README.md`、`app.py` 和 `requirements.txt` 放到 Space 根目录。
3. 在 Space 硬件设置中选择 GPU。

默认远程模型和提交已锁定。如果通过 `MODEL_ID` 换用其他模型，必须同时设置固定的 `MODEL_REVISION`。

## 本地 GPU 运行

需要 Linux、NVIDIA GPU 和兼容的 CUDA 驱动：

```bash
python -m pip install -r requirements.txt
PADDLE_DEVICE=gpu python app.py
```

本模板不承诺 CPU、macOS 或无 NVIDIA GPU 环境下的完整推理。
