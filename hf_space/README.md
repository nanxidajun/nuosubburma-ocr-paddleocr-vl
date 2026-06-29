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

# NuosuBburma OCR Demo

这个 Space 是规范彝文 OCR 的线上交互入口。上传规范彝文图片，选择识别方式后得到 OCR 文本；需要注音时勾选“生成注音”。

当前 Space 需要 GPU 才能稳定运行模型；如果没有配置 GPU，推理、页面切割和批量评估以 GitHub 仓库中的本地 demo 与脚本为准。

支持两种轻量交互方式：

- 直接识别：适合行图、区域图、标牌和简单整页。
- 页面切割后识别：适合整页、页面照片、拍屏和复杂混排页面。

本 Space 会从 Hugging Face 模型仓库加载 `nanxidajun/NuosuBburma-OCR`。PaddleOCR-VL 推理依赖 PaddlePaddle、PaddleFormers、PaddleOCR 和 GPU 环境。

推荐使用 GPU Space。

处理方式说明：行图、区域图和标牌可直接识别；整页和复杂混排页面建议使用“页面切割后识别”，页面切割使用 Paddle DocLayout。注音是 OCR 后处理，不改写 OCR 正文。

Space 只返回 OCR 文本、注音和异常提示，适合作为线上体验入口；完整的页面文本拼合、结构化页面导出、审计文件和批量评估以 GitHub 本地脚本为准。

大图处理：Space 默认把长边超过 `2400` 的输入图片等比例压缩后再识别；原图不会被修改。可通过环境变量 `MAX_IMAGE_SIDE` 调整这个限制。

本地入口见 GitHub 仓库的 `demo/` 和 `scripts/` 目录。
