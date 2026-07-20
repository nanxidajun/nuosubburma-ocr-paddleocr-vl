# NuosuBburma OCR：真实场景中的规范彝文识别

<p align="center">
  <a href="https://huggingface.co/nanxidajun/NuosuBburma-OCR"><img alt="HF 模型" src="https://img.shields.io/badge/HuggingFace-%E6%A8%A1%E5%9E%8B-f7c948"></a>
  <a href="https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set"><img alt="HF 评估集" src="https://img.shields.io/badge/HuggingFace-%E8%AF%84%E4%BC%B0%E9%9B%86-4c9f70"></a>
  <a href="https://huggingface.co/spaces/nanxidajun/NuosuBburma-OCR-Demo"><img alt="在线演示" src="https://img.shields.io/badge/Space-%E5%9C%A8%E7%BA%BF%E6%BC%94%E7%A4%BA-0f766e"></a>
  <img alt="基座" src="https://img.shields.io/badge/Base-PaddleOCR--VL--1.6_0.9B-3465d9">
  <img alt="微调" src="https://img.shields.io/badge/Fine__tuning-LoRA-8a5cf6">
</p>

输入一张图片，**端到端**输出其中规范彝文（ꆈꌠꁱꂷ / Nuosu Bburma）、汉字、拉丁字母、数字和标点的 Unicode 文本——单模型一次推理，不做文字分类、双模型路由或检测识别切割。输出的可搜索、可校对文本可直接进入语料库，支撑规范彝文的检索、校对与低资源 NLP。

[模型](https://huggingface.co/nanxidajun/NuosuBburma-OCR) · [评估集](https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set) · [评估集可视化](https://huggingface.co/spaces/nanxidajun/NuosuBburma-OCR-Evaluation-Set) · [在线演示](https://huggingface.co/spaces/nanxidajun/NuosuBburma-OCR-Demo) · [模型与训练](docs/MODEL_AND_TRAINING.md) · [训练数据构建](docs/TRAINING_DATA_CONSTRUCTION_REPORT.md)

## 背景与目标

规范彝文是一门**仍在使用、仍在创作的活语言文字**，北部彝语（诺苏语）使用者约 300 万。教材、诗歌、民族文献和日常资料大量存在，却仍停留在图片、扫描件和纸质书稿里——旧书资料不可检索、教学考试缺可复制文本、母语新创作难进入数字流程，而主流 OCR 尚不能稳定识别规范彝文。OCR 是这条链路的第一步：先把图片转成可核验的 Unicode 文本，才能继续检索、语料建设和低资源模型训练。

围绕真实使用，模型的目标定为三条：

1. **整页输入与输出**——整页图片直接进入，按视觉阅读顺序输出整页文字，保留必要行结构，不切行、不切块、不做多模型路由。
2. **混排识别**——彝文、汉字、拉丁字母、数字和标点在同一次识别中一起输出。
3. **满足多种场景**——不止清晰文档，还有旧书扫描、屏幕拍照、手写和更多现实材料。

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
| 推理 | 单模型端到端，整幅图片直接输入，无需加载 adapter |
| 评估集 | 1,030 张真实扫描 / 拍摄图片（519 页 + 511 区域），不含合成数据 |
| 数据托管 | 权重在 Hugging Face 模型库，评估集在 Hugging Face 评估集，本仓库保留代码、配置与文档 |

## 评估结果

指标为逐页平均文本误差 **NED**（越低越好），计算前统一 Unicode 规范化并忽略空白与换行差异。评估集为 [Hugging Face 评估集](https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set) 的 1,030 张真实图片。

| 指标 | 数值 | 说明 |
|---|---:|---|
| Raw Avg NED | **0.0474** | 主口径，按模型原始输出计算 |
| 去空白 Avg NED | 0.0399 | 诊断用，剔除空白差异 |
| 规范化后 Avg NED | 0.0346 | 诊断用，剔除 Unicode 表示差异 |
| 整页完全一致率 | 32.3% | 1,030 页中 333 页与标准答案逐字一致 |

分组 NED（去空白口径，按采集场景与难度统计整样本 NED）：

| 采集场景 | 样本 | NED | | 难度 | 样本 | NED |
|---|--:|--:|---|---|--:|--:|
| 书籍扫描 | 787 | 0.0259 | | 低 | 271 | 0.0163 |
| 屏幕拍照 | 164 | 0.0393 | | 中 | 501 | 0.0239 |
| 手写拍照 | 70 | 0.2000 | | 高 | 258 | 0.0957 |
| 实景拍照 | 9 | 0.0247 | | | | |

书籍扫描是当前最可靠的适用范围；手写拍照是最明显的短板。少数带装饰图案、部首检字表或屏幕摩尔纹的页面会触发异常生成、抬高总体误差。完整逐类分析与异常页清单见 [评估结果分析](docs/EVALUATION_RESULT_ANALYSIS.md)，评估集与标注质量见 [评估集说明](docs/EVALUATION_DATASET.md)。

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

整页图片同样直接输入（提示词 `<image>OCR:`），由单一模型一次读出，无需切行或切块。

## 复现评估

端到端直评流程（下载模型与评估集 → 逐图推理 → 打分与分组统计）见 [scripts/README.md](scripts/README.md)。

## 项目结构

```text
README.md            项目说明（背景、目标、评估结果、使用）
LICENSE              Apache-2.0
requirements.txt     运行依赖
configs/             训练与导出配置、数据清单
demo/                本地单图 OCR 演示 + 样例图
docs/                评估集、结果分析、模型与训练、数据构建
model/               模型下载说明（权重托管在 Hugging Face）
scripts/             端到端评估与训练脚本
```

## 使用边界

- 输出是 OCR 初稿，不是自动校对或翻译结果。
- 书籍扫描与清晰印刷最稳定；复杂整页、屏幕照片、实景照片和长手写段落误差更高，建议人工复核。
- 形近字专项微调降低了总体错误，但未解决全部形近字，个别高频单向混淆仍存在。
- 约 0.9B 参数的高精度参考模型，尚未针对移动端优化。

## 许可

本仓库以 Apache-2.0 发布（见 [LICENSE](LICENSE)）。模型基于 PaddleOCR-VL-1.6 微调，上游在固定版本 `66317acc4c9fc17bd154591ce650735cd2855f3e` 处核验为 Apache-2.0。评估集许可见 [Hugging Face 评估集](https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set)。使用时需同时遵守上游项目与数据来源的相关许可。
