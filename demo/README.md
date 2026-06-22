# Demo

本目录提供 `NuosuBburma OCR` 的本地单图推理 Demo 原型。

当前不提供线上 Space。PaddleOCR-VL 推理环境较重，模型权重约 1.8GB，并依赖 PaddleFormers / PaddlePaddle / GPU 环境；免费 CPU Space 难以稳定承载。线上演示可在后续具备 GPU 环境时补充。

## 本地运行

示例：

```bash
python demo/infer_single_image.py \
  --model /path/to/NuosuBburma-OCR-export \
  --image demo/sample_images/mixed_line.png
```

固定提示词：

```text
<image>OCR:
```

样例图：

- `sample_images/mixed_line.png`
- `sample_images/screen_page.jpg`
- `sample_images/handwriting_region.jpg`

整页扫描件不建议直接当作普通单行 demo 输入。可以先运行切图流程，再从 `04_successful_crop_summary/01_line_ocr_ready/` 中选择行图进入本地推理。说明见 [`../docs/CROP_PIPELINE.md`](../docs/CROP_PIPELINE.md)。

模型权重：

- Hugging Face: `https://huggingface.co/nanxidajun/NuosuBburma-OCR`

说明：

- `--model` 需要指向已经下载到本地的 merged export 模型目录。
- `--device` 默认使用 `gpu`；如需 CPU 仅可做环境连通性测试，实际推理速度和可用性不保证。
- Demo 面向单图 OCR 链路展示，不声明完整线上 OCR 服务能力。
