# NuosuBburma OCR：真实场景中的规范彝文识别

<p align="center">
  <a href="https://huggingface.co/nanxidajun/NuosuBburma-OCR"><img alt="HF 模型" src="https://img.shields.io/badge/HuggingFace-%E6%A8%A1%E5%9E%8B-f7c948"></a>
  <a href="https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set"><img alt="HF 评估集" src="https://img.shields.io/badge/HuggingFace-%E8%AF%84%E4%BC%B0%E9%9B%86-4c9f70"></a>
  <a href="https://huggingface.co/spaces/nanxidajun/NuosuBburma-OCR-Demo"><img alt="在线演示" src="https://img.shields.io/badge/Space-%E5%9C%A8%E7%BA%BF%E6%BC%94%E7%A4%BA-0f766e"></a>
  <img alt="基座" src="https://img.shields.io/badge/Base-PaddleOCR--VL--1.6_0.9B-3465d9">
  <img alt="微调" src="https://img.shields.io/badge/Fine__tuning-LoRA-8a5cf6">
</p>

输入一张图片，输出其中规范彝文（ꆈꌠꁱꂷ / Nuosu Bburma）、汉字、拉丁字母、数字和标点的 Unicode 文本。输出的可搜索、可校对文本可直接进入语料库，支撑规范彝文的检索、校对与低资源 NLP。

[模型](https://huggingface.co/nanxidajun/NuosuBburma-OCR) · [评估集](https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set) · [评估集可视化](https://huggingface.co/spaces/nanxidajun/NuosuBburma-OCR-Evaluation-Set) · [在线演示](https://huggingface.co/spaces/nanxidajun/NuosuBburma-OCR-Demo) · [模型与训练](docs/MODEL_AND_TRAINING.md) · [训练数据构建](docs/TRAINING_DATA_CONSTRUCTION_REPORT.md)

## 背景与任务

本项目面向记录彝语的规范彝文（ꆈꌠꁱꂷ）及其与汉字、拉丁字母、数字和标点的混排识别。教材、诗歌、民族文献和日常资料多以图片、扫描件和纸质书稿形式存在，难以检索、复制和整理，而通用 OCR 尚不能稳定识别。本项目按视觉阅读顺序输出图片中的文字，覆盖书籍扫描、屏幕拍照、手写和实景等真实场景。

任务复杂度来自真实资料本身：

| 复杂度 | 具体表现 |
|---|---|
| 字符 | 1,165 个规范彝文音节，差异常集中在细小笔画、方向、开口和局部结构 |
| 视觉域 | 新印刷 PDF、旧书扫描、页面照片、手机照片、手写拍照的噪声各不相同 |
| 结构 | 整页、区域、单行、短诗式排布、脚注块、注音块和段落图并存 |
| 混排 | 彝文、汉字、数字、脚注符号、拉丁字母和标点同时出现 |

## 概览

| 项目 | 内容 |
|---|---|
| 基座模型 | PaddleOCR-VL-1.6（0.9B） |
| 微调方式 | 两阶段 LoRA，权重已合并为单一模型 |
| 支持文字 | 规范彝文、汉字、拉丁字母、数字、标点 |
| 推理 | 最终权重已合并，无需加载 adapter |
| 评估集 | 1,030 张真实扫描 / 拍摄图片（519 页 + 511 区域），不含合成数据 |
| 数据托管 | 权重在 Hugging Face 模型库，评估集在 Hugging Face 评估集，本仓库保留代码、配置与文档 |

## 最终模型评估

这里只报告 Hugging Face 最终发布权重在完整 1,030 张真实图片上的固定结果，不混入训练中间模型或挑选后的子集。主指标为语料级字符错误率 **CER**（越低越好）：所有预测和 GT 先做 NFC 规范化并删除 Unicode 空白，再用总编辑距离除以 GT 总字符数。

![最终发布模型的完整评估结果](docs/figures/evaluation-final-model-overview.svg)

CER 回答“全部字符总体有多少错误”，平均 NED 回答“每张图片等权时平均有多难”，完全一致率给出最严格的整样本结果。三者口径不同，因此分别报告，不互相替代。

![各场景与难度对总编辑错误的贡献](docs/figures/evaluation-error-contribution.svg)

结果不是由大表堆出来的：高难度样本占 30.4% 的 GT 字符，却贡献 64.6% 的编辑错误；屏幕拍摄占 28.4% 的字符、贡献 40.3% 的错误；手写拍照组内 CER 为 20.65%，是最明显的场景短板。另有 27 张 NED 高于 25% 的长尾样本，仅占 2.6%，却贡献 55.7% 的编辑错误。实景拍照只有 9 张，只作小规模参考。

模型权重、最终标注和固定预测的 SHA-256 已写入图中；完整公式、长尾分布和复算说明见 [最终模型评估分析](docs/EVALUATION_RESULT_ANALYSIS.md)，机器可读汇总见 [evaluation_metrics.json](docs/evaluation_metrics.json)，评估集质检见 [评估集说明](docs/EVALUATION_DATASET.md)。

### 微调前后对比

以《雪族》（凉山彝文资料，64 页真实扫描）为例，在同一审定 GT、同一口径下，未微调基座 PaddleOCR-VL-1.6 的平均 NED / CER 为 `50.82% / 59.89%`，最终微调模型为 `2.59% / 2.06%`。

未微调基座基本只能读出汉字，几乎整行漏掉规范彝文；微调后彝汉混排逐行读对。以《雪族》扉页为例（截取前几行）：

- **GT**：`ꆃꎭꆈꌠꄯꒉꌋꌊꁏꄉꌠ / 凉山彝文资料选译 / ꇖꋐꀕꌠ / 第四集 / ꃰꎝ / 雪族`
- **未微调基座**：`凉山彝文资料选译 / 第四集 / 雪族`　—— 规范彝文行全部缺失
- **最终微调模型**：`ꆃꎭꆈꌠꄯꒉꌋꌊꁏꄉꌠ / 凉山彝文资料选译 / ꇖꋐꀕꈞ / 第四集 / ꃰꎝ / 雪族`

## 训练方法

两阶段连续 LoRA 微调，最终合并为单一模型；两阶段训练数据均独立合成：

1. **通用混合文字适配** —— 用合成的规范彝文、汉字与混排图片建立端到端识别能力，覆盖多字体、多版式与不同图像清晰度。
2. **形近字专项继续微调** —— 从第一阶段导出的模型继续训练，加入多字体、清晰与旧化条件下的彝文形近字 A/B 对照图片，并保留第一阶段通用样本 replay。

训练全程不使用评估图片、评估标准答案、模型在评估集上的输出或评估统计来制作或挑选训练数据。完整训练策略、消融边界与数据构建见 [模型与训练](docs/MODEL_AND_TRAINING.md) 与 [训练数据构建报告](docs/TRAINING_DATA_CONSTRUCTION_REPORT.md)。

## 安装

```bash
conda create -n paddleocr-vl python=3.11 -y
conda activate paddleocr-vl
python -m pip install -U pip
python -m pip install paddlepaddle-gpu==3.3.0 \
  -i https://www.paddlepaddle.org.cn/packages/stable/cu118/
python -m pip install -r requirements.txt
```

## 使用

下载模型后，单张图片 OCR：

```bash
hf download nanxidajun/NuosuBburma-OCR --repo-type model \
  --local-dir models/NuosuBburma-OCR

python demo/infer_single_image.py \
  --model models/NuosuBburma-OCR \
  --image demo/sample_images/mixed_line.png
```

支持整页图片输入，提示词为 `<image>OCR:`。

## 复现评估

端到端直评流程（下载模型与评估集 → 逐图推理 → 打分与分组统计）见 [scripts/README.md](scripts/README.md)。

## 项目结构

```text
README.md            项目说明（背景、目标、评估结果、使用）
LICENSE              Apache-2.0
requirements.txt     运行依赖
configs/             训练与导出配置、数据清单
data_generation/     合成训练数据生成器（含 SHA 锁定的核心脚本）
demo/                本地单图 OCR 演示 + 样例图
docs/                评估集、结果分析、模型与训练、数据构建
model/               模型下载说明（权重托管在 Hugging Face）
scripts/             端到端评估与训练脚本
```

## 使用边界

- 输出是 OCR 初稿，不是自动校对或翻译结果。
- 书籍扫描与清晰印刷最稳定；复杂整页、屏幕照片、实景照片和长手写段落误差更高。
- 形近字专项微调降低了总体错误，但未解决全部形近字，个别高频单向混淆仍存在。
- 约 0.9B 参数的高精度参考模型，尚未针对移动端优化。

## 许可

本仓库以 Apache-2.0 发布（见 [LICENSE](LICENSE)）。模型基于 PaddleOCR-VL-1.6 微调，上游在固定版本 `66317acc4c9fc17bd154591ce650735cd2855f3e` 处核验为 Apache-2.0。评估集许可见 [Hugging Face 评估集](https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set)。使用时需同时遵守上游项目与数据来源的相关许可。
