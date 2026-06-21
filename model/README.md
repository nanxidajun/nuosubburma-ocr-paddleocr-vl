# NuosuBburma OCR Model

本目录是 GitHub 仓库中的模型入口说明，不直接托管大模型权重。

完整模型权重与模型卡托管在 Hugging Face：

```text
https://huggingface.co/nanxidajun/NuosuBburma-OCR
```

## 模型信息

| 项目 | 内容 |
|---|---|
| 公开模型名 | `NuosuBburma OCR` |
| 基座模型 | `PaddleOCR-VL-1.6 (0.9B)` |
| 微调方式 | LoRA |
| 任务提示词 | `<image>OCR:` |
| 主要任务 | 规范彝文 OCR |
| 支持输入 | page / region / line 图像 |
| 模型权重 | Hugging Face Model 仓库托管 |

## 下载方式

```bash
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

## 评估口径

最终评估集：

```text
https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set
```

提交评估结果：

| 指标 | 结果 |
|---|---:|
| 样本数 | 603 |
| Avg NED | 0.036068 |
| Exact match | 67.99% |
| Yi-only Avg NED | 0.038309 |
| Yi-only exact | 74.96% |
| Han-only Avg NED | 0.022447 |
| Han-only exact | 93.99% |
| replacement / LaTeX / ASCII-letter / long_pred | 0 / 2 / 18 / 0 |

完整评估结果见：

```text
NuosuBburma_OCR_Evaluation_Set/
```

## 使用边界

- 本模型支持整页、区域和行图输入。
- 当前最稳定的使用方式通常是 line / region OCR。
- 复杂整页文档在版面较密、手写、多栏、脚注、注音块或图文混排较强时，建议配合版面分析、切图流程或人工复核。
- 手写样本已有一定泛化能力，但稳定性弱于印刷体。
- 本版本尚未进行专门的端侧/移动端优化。

## GitHub 存放原则

GitHub 只保留模型入口说明、训练配置、评估脚本和评估结果。大模型权重通过 Hugging Face Model 仓库发布，避免把大文件直接提交到 GitHub。
