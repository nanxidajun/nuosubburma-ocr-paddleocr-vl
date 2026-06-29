---
language:
  - ii
  - zh
  - en
license: other
library_name: paddlepaddle
pipeline_tag: image-to-text
base_model: PaddlePaddle/PaddleOCR-VL
datasets:
  - nanxidajun/NuosuBburma-OCR-Evaluation-Set
tags:
  - ocr
  - paddleocr-vl
  - paddlepaddle
  - paddleformers
  - nuosu
  - yi
  - low-resource-language
  - document-ocr
  - lora
model-index:
  - name: NuosuBburma OCR
    results:
      - task:
          type: image-to-text
          name: OCR
        dataset:
          type: nanxidajun/NuosuBburma-OCR-Evaluation-Set
          name: NuosuBburma OCR Evaluation Set historical 603-result split
        metrics:
          - type: avg_ned
            name: Avg NED
            value: 0.036068
          - type: yi_avg_ned
            name: Yi-only Avg NED
            value: 0.038309
          - type: han_avg_ned
            name: Han-only Avg NED
            value: 0.022447
---

# NuosuBburma OCR：规范彝文识别模型

`NuosuBburma OCR` 是面向规范彝文（ꆈꌠꁱꂷ / Nuosu Bburma）的文字识别模型，基于 `PaddleOCR-VL-1.6 (0.9B)` / `PaddlePaddle/PaddleOCR-VL` 进行 LoRA 微调。

模型用于把图片中的规范彝文、彝汉混排、数字、标点和可见拉丁注音转写为 Unicode 文本。

典型输入包括书籍扫描页、行图、文本区域、屏幕拍照、实拍标牌和手写拍照样本。

相关入口：

| 入口 | 链接 |
|---|---|
| Hugging Face 模型仓库 | <https://huggingface.co/nanxidajun/NuosuBburma-OCR> |
| GitHub 仓库 | <https://github.com/nanxidajun/nuosubburma-ocr-paddleocr-vl> |
| Hugging Face 评估集 | <https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set> |
| 线上演示 | <https://huggingface.co/spaces/nanxidajun/NuosuBburma-OCR-Demo> |

## 模型信息

| 项目 | 内容 |
|---|---|
| 公开名称 | `NuosuBburma OCR` / `规范彝文识别` |
| 基座模型 | `PaddleOCR-VL-1.6 (0.9B)` / `PaddlePaddle/PaddleOCR-VL` |
| 微调方式 | LoRA |
| 推理提示词 | `<image>OCR:` |
| 主任务 | 规范彝文文字识别 |
| 主要输出 | 图片中可见文本的 Unicode 转写 |
| 稳定输入 | 单行图、区域图 |
| 扩展输入 | 整页图、PDF 渲染页、手机拍照页、屏幕拍照、实拍标牌 |
| 推荐整页流程 | 先用 Paddle DocLayout 做页面切割，再识别、合并页面文本并导出结构化结果 |

## 当前评估口径

最新评估集为 `758` 条真实来源样本，含 `line 470` / `region 119` / `page 169`，空 GT、缺图、重复 ID 和合成样本标记均为 `0`。原始 `PaddleOCR-VL-1.6` baseline 已完成 `758` 条 aligned raw prediction，错误行 `0`；最终 LoRA 与原始模型的同口径 NED 表等待正式 rerun 后补充。

模型卡 metadata 中的 NED 指标来自历史 `603` 条 OCR 主指标，保留为已经完成的可复查结果，不代表最新 `758` 条最终分数。

## 快速使用

推荐从 GitHub 仓库运行本地演示脚本。模型推理建议使用 CUDA GPU 环境。

```bash
git clone https://github.com/nanxidajun/nuosubburma-ocr-paddleocr-vl.git
cd nuosubburma-ocr-paddleocr-vl

conda create -n paddleocr-vl python=3.11 -y
conda activate paddleocr-vl
python -m pip install -U pip setuptools wheel

python -m pip install paddlepaddle-gpu==3.3.0 \
  -i https://www.paddlepaddle.org.cn/packages/stable/cu118/

python -m pip install -r requirements.txt
```

下载模型：

```bash
hf download nanxidajun/NuosuBburma-OCR \
  --repo-type model \
  --local-dir models/NuosuBburma-OCR
```

国内网络较慢时，可先设置镜像：

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

运行单图识别：

```bash
python demo/infer_single_image.py \
  --model models/NuosuBburma-OCR \
  --image demo/sample_images/mixed_line.png \
  --max-image-side 2400 \
  --html-output outputs/demo/mixed_line.html
```

运行整页流程：

```bash
python demo/run_page_workflow.py \
  --input demo/sample_images/screen_page.jpg \
  --model models/NuosuBburma-OCR \
  --output-root outputs/demo_page_workflow \
  --max-image-side 2400 \
  --with-pronunciation
```

安装后也可以先跑健康检查：

```bash
scripts/smoke_check.sh
```

## 推理提示词

固定提示词：

```text
<image>OCR:
```

输入为包含规范彝文或彝汉混排文本的图片，输出为图片中可见文本。注音是后处理步骤，不会改写识别正文。

## 页面和复杂图像

模型可以直接输入整页图像，但复杂整页更推荐先做页面切割：

```text
整页图片 / PDF / 页面照片 / 屏幕拍照
-> Paddle DocLayout 页面切割
-> 切出文本区域后识别
-> 页面文本合并
-> 结构化页面输出
-> 异常检查
-> 可选注音
```

在总评估材料中的《雪族子史篇》65 页整页子集上，两种路径的对比如下。历史 OCR 指标、最新 `758` 条正式 rerun 和雪族 65 页整页切割对照分表报告，口径不同，不合并成一个平均分。

| 识别路径 | 平均归一化编辑距离（Avg NED） | 说明 |
|---|---:|---|
| 页面切割后识别 | `0.0504` | 阅读顺序更稳，彝汉配对更接近人工标注，非文字干扰更少 |
| 直接整页识别 | `0.5448` | 容易出现跨行、错行、彝汉配对拆散和图案误识别 |

对复杂书页，先做页面切割再识别，通常比整页直接识别更稳定。本次流程已跑通 `65` 页、`2501` 个 OCR 单元和 `65` 页拼合文本；替换符、空页和重复页均为 `0`。

## 评估结果

当前公开 NED 结果来自历史 `603` 条 OCR 主指标；最新 `758` 条整合评估集已经完成清理，等待最终同口径 rerun。合成样本不进入评估结果。归一化编辑距离（NED）越低越好。

| 指标 | PaddleOCR-VL-1.6 原始模型 | 当前 LoRA 模型 |
|---|---:|---:|
| 最新 `758` 条 raw prediction | 已完成，错误行 `0` | 等待正式 rerun |
| 最新 `758` 条 Avg NED | 待最终计算 | 待正式 rerun |
| 历史 `603` 条样本数 | 未公开同口径指标 | `603` |
| 历史 `603` 条平均归一化编辑距离（Avg NED，越低越好） | 未公开同口径指标 | `0.036068` |
| 历史 `603` 条忽略空白后的平均编辑距离 | 未公开同口径指标 | `0.034219` |
| 历史 `603` 条 NFKC+WS Avg NED | 未公开同口径指标 | `0.033964` |
| 历史 `603` 条 Yi-only Avg NED | 未公开同口径指标 | `0.038309` |
| 历史 `603` 条 Han-only Avg NED | 未公开同口径指标 | `0.022447` |
| 历史 `603` 条 Digit-only Avg NED | 未公开同口径指标 | `0.139918` |
| 历史 `603` 条 replacement / LaTeX / extra Latin / long_pred | 未公开同口径指标 | `0 / 2 / 0 / 0` |

指标解释：

| 指标 | 中文说明 |
|---|---|
| Avg NED | 平均归一化编辑距离，越低越接近人工标注 |
| WS Avg NED | 忽略空白差异后的平均归一化编辑距离 |
| NFKC+WS Avg NED | 做 Unicode 兼容规范化并忽略空白差异后的平均归一化编辑距离 |
| Yi-only Avg NED | 只抽取彝文字符后计算平均归一化编辑距离 |
| Han-only Avg NED | 只抽取汉字后计算平均归一化编辑距离 |
| Digit-only Avg NED | 只抽取数字后计算平均归一化编辑距离 |
| 替换符 / 公式化片段 / 多余拉丁字母 / 异常长输出 | 输出风险检查项；括号中的英文名保留在评估脚本和模型卡元数据中 |

原始模型和 LoRA 模型的同一 `758` 条评估设置对比会在正式 rerun 后补充。

## 训练策略摘要

训练策略：

| 原则 | 做法 |
|---|---|
| 真实训练材料打底 | 使用旧书、教材、工具书、混排、手写和页面照片等训练材料建立任务边界 |
| 合成样本补覆盖 | 合成样本补低频字符；文本不变、图像状态变化样本用于覆盖字体变化和旧印刷状态 |
| 隔离检查 | 训练包和评估集分开维护；重合检查保留在 GitHub 配置和训练数据报告中 |
| 输出风险控制 | 训练和开发诊断时观察替换符、公式化片段、多余拉丁字母、异常长输出等错误 |
| 开发诊断选模 | 用固定开发诊断集比较分支，最终模型以真实评估集结果报告 |

更多训练细节见 GitHub 文档：

- `docs/MODEL_AND_TRAINING.md`
- `docs/TRAINING_DATA_CONSTRUCTION_REPORT.md`
- `configs/train_data_manifest_v5_16.json`

## 适用场景

适合：

- 规范彝文印刷行图识别；
- 旧书、教材、工具书中的规范彝文识别；
- 彝汉混排文字识别；
- 屏幕拍照、页面照片和实拍标牌的文本识别；
- 后续人工校对、检字和注音整理。

需要谨慎：

- 严重倾斜、反光、遮挡、弯曲或低清页面；
- 复杂整页、多栏、脚注/注音密集区域；
- 手写拍照长段落；
- 数字、页码、编号和特殊脚注符号。

## 使用边界

- 清晰单行图和区域图输入是当前最稳定的使用方式。
- 直接整页识别可作为诊断入口，但复杂整页建议先做页面切割后识别。
- 模型输出是文字识别结果，不是自动校对结果；重要文本仍建议人工复核。
- 注音是识别后的处理步骤，不参与模型评分，也不会改写识别正文。
- 本版本尚未做端侧或移动端优化。
- 线上演示需要 GPU 才能稳定运行模型；没有 GPU 时，以本地演示与脚本为准。

## 许可与合规

本模型基于 `PaddlePaddle/PaddleOCR-VL` 微调发布。使用者需要同时遵守基座模型、PaddleOCR/PaddlePaddle 相关依赖、Hugging Face 托管条款以及数据来源的版权边界。

本模型主要面向比赛评审、研究和规范彝文资料数字化实验。商业使用前请确认基座模型、数据来源和部署环境的授权条件。

## 引用

如果这个模型对你的研究或项目有帮助，可引用本仓库：

```bibtex
@misc{nuosubburma_ocr_2026,
  title = {NuosuBburma OCR: OCR for Standard Nuosu Yi Text in Real-World Documents},
  author = {NanxiDajun},
  year = {2026},
  url = {https://github.com/nanxidajun/nuosubburma-ocr-paddleocr-vl}
}
```
