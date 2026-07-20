# Demo

本地单图 OCR 演示。Hugging Face Space 是线上入口；没有 Space GPU 时，以本地脚本为准。

本地 Demo 支持行图、区域图和整页图片，使用统一提示词 `<image>OCR:` 输出对应文字。

## 安装依赖

在仓库根目录执行：

```bash
python -m pip install -r requirements.txt
```

`requirements.txt` 顶部写有推荐环境和 PaddlePaddle 安装命令，推理建议使用 CUDA GPU。

## 下载模型

```bash
hf download nanxidajun/NuosuBburma-OCR \
  --repo-type model \
  --local-dir models/NuosuBburma-OCR
# 国内网络较慢时：export HF_ENDPOINT=https://hf-mirror.com
```

## 健康检查

```bash
scripts/smoke_check.sh
# 模型不在默认目录时：MODEL_PATH=/path/to/NuosuBburma-OCR scripts/smoke_check.sh
```

## 单图 OCR

```bash
python demo/infer_single_image.py \
  --model models/NuosuBburma-OCR \
  --image demo/sample_images/mixed_line.png
```

常用参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--model` | `models/NuosuBburma-OCR` | 已下载的模型目录 |
| `--image` | `demo/sample_images/mixed_line.png` | 输入图片（行图、区域图或整页均可） |
| `--prompt` | `<image>OCR:` | 推理提示词 |
| `--max-new-tokens` | `1024` | 最大输出 token 数；整页文本较长时可调大 |
| `--max-image-side` | `2400` | 输入长边压缩上限；设为 `0` 保留原图 |
| `--device` | `gpu` | 推理设备 |
| `--output` | 无 | 可选：把识别文本写入指定 txt |
| `--html-output` | 无 | 可选：生成带图片与识别文本的 HTML 预览 |

## 样例图

下面四张样例图均来自公开评估集的当前图片快照；样例只用于复现输入形态，正式指标以评估集报告为准。

| 图片 | 用途 |
|---|---|
| `sample_images/mixed_line.png` | 彝汉混排区域；评估样本 `liangshan_selection_2_p040_region_01` |
| `sample_images/handwriting_region.jpg` | 手写区域；评估样本 `liangshan_selection_2_p022_handwriting_01` |
| `sample_images/screen_page.jpg` | 屏幕拍摄页面；评估样本 `real_screen_photo_page_001_part1` |
| `sample_images/sign_photo.jpg` | 实景拍摄；评估样本 `real_photo_001` |

批量评估见 [scripts](../scripts/)。
