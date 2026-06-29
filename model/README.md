# 规范彝文 OCR 模型 / NuosuBburma OCR Model

本目录是 GitHub 仓库中的模型入口说明，不直接托管大模型权重。

完整模型权重与模型卡托管在 Hugging Face 模型仓库：

```text
https://huggingface.co/nanxidajun/NuosuBburma-OCR
```

本目录中的 [`HUGGINGFACE_MODEL_CARD.md`](HUGGINGFACE_MODEL_CARD.md) 是给该 Hugging Face 模型仓库准备的上传版模型卡。上传到 Hugging Face 时，将它的内容作为模型仓库根目录的 `README.md` 使用。

## 模型信息

| 项目 | 内容 |
|---|---|
| 公开模型名 | `规范彝文 OCR / NuosuBburma OCR` |
| 基座模型 | `PaddleOCR-VL-1.6 (0.9B)` |
| 微调方式 | LoRA |
| 任务提示词 | `<image>OCR:` |
| 主要任务 | 规范彝文 OCR |
| 支持输入 | page / region / line 图像；稳定交付优先使用 line / region |
| 模型权重 | Hugging Face 模型仓库托管 |

## 下载方式

```bash
# 国内网络较慢时，取消下一行注释使用 Hugging Face 镜像：
# export HF_ENDPOINT=https://hf-mirror.com

hf download nanxidajun/NuosuBburma-OCR \
  --repo-type model \
  --local-dir models/NuosuBburma-OCR
```

下载后的模型目录应包含：

```text
config.json
model-00001-of-00001.safetensors
model.safetensors.index.json
preprocessor_config.json
tokenizer.json
tokenizer.model
tokenizer_config.json
special_tokens_map.json
chat_template.jinja
merge_config.json
flex-ckpt.auto_generated.metadata
```

## 推理提示词

```text
<image>OCR:
```

输入为包含规范彝文或彝汉混排文本的图片，输出为图片中可见文本的 Unicode 转写。

## 评估设置

最终评估集：

```text
https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set
```

最终评估集为 `758` 条真实来源样本。下表保留历史 `603` 条 OCR 主指标结果，作为已完成、可核验的模型指标；`758` 条真实样本作为最终评估口径。

![Evaluation snapshot](../docs/figures/evaluation_snapshot.svg)

| 指标 | 当前 LoRA 模型 |
|---|---:|
| 历史 `603` 条样本数 | 603 |
| 历史 `603` 条 Avg NED | 0.036068 |
| 历史 `603` 条 WS Avg NED | 0.034219 |
| 历史 `603` 条 NFKC+WS Avg NED | 0.033964 |
| 历史 `603` 条 Yi-only Avg NED | 0.038309 |
| 历史 `603` 条 Han-only Avg NED | 0.022447 |
| 历史 `603` 条 Digit-only Avg NED | 0.139918 |
| 历史 `603` 条 replacement / LaTeX / extra Latin / long_pred | 0 / 2 / 0 / 0 |

完整评估结果见：

```text
evaluation/
```

## 使用边界

- 本模型可以输入整页、区域和行图。
- 当前最稳定的使用方式通常是 line / region OCR。
- 直接 page OCR 更适合作为诊断入口；复杂整页可能出现与人工标注不一致的换行、阅读顺序偏差或段落边界误判。
- 复杂整页文档在版面较密、手写拍照、多栏、脚注、注音块或图文混排较强时，建议先走 [页面处理说明](../docs/PAGE_PROCESSING.md)，再做 line/region OCR 和人工核验。
- 手写拍照样本已纳入独立观察，结果与印刷体分开解读。
- 本版本尚未进行专门的端侧/移动端优化。

## GitHub 存放原则

GitHub 只保留模型入口说明、训练配置、评估脚本和评估结果。大模型权重通过 Hugging Face 模型仓库发布，避免把大文件直接提交到 GitHub。
