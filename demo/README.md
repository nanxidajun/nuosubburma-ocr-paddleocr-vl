# Demo

本目录包含一个单图推理脚本和少量评估集样例图。

示例：

```bash
python demo/infer_single_image.py \
  --model /path/to/NuosuBburma-OCR-export \
  --image demo/sample_images/footnote_line.png
```

固定提示词：

```text
<image>OCR:
```

样例图：

- `sample_images/footnote_line.png`
- `sample_images/screen_page.jpg`
- `sample_images/handwriting_region.jpg`
