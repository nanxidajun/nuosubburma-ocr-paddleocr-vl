# 模型与训练说明

本文档对应主提交稿中的“训练数据集构建”和“模型微调策略与实验验证”。它重点说明：训练数据如何构建、为什么选择 LoRA、如何控制输出漂移、为什么最终选择当前提交模型。

## 基础方案

| 项目 | 内容 |
|---|---|
| 公开模型名 | `规范彝文 OCR / NuosuBburma OCR` |
| 基座模型 | `PaddleOCR-VL-1.6 (0.9B)` |
| 微调方式 | LoRA |
| 任务提示词 | `<image>OCR:` |
| 主任务 | 规范彝文 OCR |
| 混排能力 | 支持纯彝文、彝汉混排，以及少量数字/符号场景 |
| 输入范围 | 支持 page / region / line 图像输入 |
| 训练硬件 | NVIDIA RTX 4090D |
| 部署状态 | 暂未做端侧/移动端部署 |

## 训练环境

| 项目 | 内容 |
|---|---|
| 操作环境 | Linux + CUDA GPU |
| Python | 3.11 |
| 深度学习框架 | PaddlePaddle |
| 训练/导出工具 | PaddleFormers 1.1.1 |
| CUDA runtime | 11.8 |
| cuDNN | 8.9 |
| 精度 | bf16 |
| GPU | NVIDIA RTX 4090D，单卡训练 |
| 默认 conda 环境名 | `paddleocr-vl` |

关键配置文件：

```text
configs/paddleocr-vl_lora_16k_nuosubburma_v5_16.yaml
configs/paddleocr-vl_lora_export_nuosubburma_v5_16.yaml
configs/train_data_manifest_v5_16.json
```

## 关键训练参数

| 参数 | 值 |
|---|---:|
| max sequence length | 16384 |
| LoRA rank | 8 |
| per-device batch size | 4 |
| gradient accumulation | 16 |
| epochs | 2 |
| scheduler | cosine |
| learning rate | 5.0e-4 |
| minimum learning rate | 5.0e-5 |
| precision | bf16 |
| sharding | stage2 |

训练快照：

| 项目 | 值 |
|---|---:|
| 训练行数 | 21504 |
| epochs | 2 |
| train loss | 0.191 |
| train runtime | 1:08:53.89 |

## 训练数据构建原则

训练集构建遵循“真实锚点 + 合成覆盖 + 冻结评估”的原则，避免把真实评估错题喂回模型。

低资源文字训练有一个现实矛盾：只用真实数据，覆盖不够；大量使用合成数据，又可能污染真实语言分布和视觉分布。本项目的处理方式是先让真实样本决定任务边界，再从具体场景设计合成数据补真实训练集中不足的部分。

| 数据类型 | 作用 |
|---|---|
| 真实书页/行图 | 锚定真实字体、旧印刷、混排和版式 |
| 合成低频字样本 | 补真实训练中缺失或极低频的规范彝文字形 |
| 形近字 pair guard | 平衡易混字的视觉边界，避免只把模型推向其中一个字 |
| 旧印刷退化样本 | 模拟低对比、模糊、压缩、油墨不均等视觉退化 |
| 多行 region 样本 | 训练换行、阅读顺序、段落和脚注/注音块 |
| 输出空间 guard | 防止 Latin、LaTeX、替换符、长尾续写等漂移 |
| monitor 数据 | 诊断特定错误是否回归，不参与最终评估 |

数据构建约束：

- 真实数据和合成数据保持可区分。
- 不把最终评估集答案作为训练目标。
- 优先增加视觉多样性，而不是盲目增加文本标签多样性。
- 对 Latin、公式化输出、脚注和 region 类高风险样本设置比例上限。
- 彝文识别、汉字识别、数字识别和混排行为分开观察。
- 手写、复杂多行 region 和复杂整页 OCR 作为高难度泛化场景，不和清晰印刷行图混为同一种能力。

## 三阶段训练路线

训练没有一开始就把所有数据混在一起。最早先用《勒俄特依》的真实裁切行确认模型能学会规范彝文字形，再加入合成覆盖、monitor 诊断和真实评估集横向比较。

| 阶段 | 目标 | 关键判断 |
|---|---|---|
| 第一阶段：单书可行性 | 使用《勒俄特依》真实裁切行，确认 PaddleOCR-VL LoRA 能否学习规范彝文字形和基本输出格式 | 可以学习基本彝文字形，但单书覆盖不足 |
| 第二阶段：真实数据 + 合成覆盖 + monitor | 增加低频字、形近字、标点边界、旧印刷退化、彝汉混排和版式变化；用 monitor 观察输出漂移 | 合成数据有用，但必须控制 Latin、LaTeX、ASCII 和长输出风险 |
| 第三阶段：reviewed 真实集横评 | 用人工复核后的真实集做横向检测，同时看 NED、彝文、汉字、数字和输出空间风险 | 真实集不作为训练目标；重点看模型是否反复出现漂移、公式化、漏行、长输出和混排不稳 |

第三阶段要单独说明。真实数据在这里承担的是检测作用，不是把评估答案喂回训练。低资源 OCR 里，单个字的错当然会记录，但选模型时更重要的是错误模式有没有反复出现：脚注附近被公式化、GT 外 Latin 尾巴、region 漏行、数字不稳、整页边界错、手写域落差。这些信号决定某个分支是否继续，不会直接把样本答案反向补进训练集。

## 分支选择摘要

内部实验很多，但最终文档不按流水账列几十次训练，而按“分支判断”说明为什么当前模型胜出。

![Training branch strategy](figures/training_branch.svg)

关键分支卡：

| 分支 | 数据构成/动作 | 结果与判断 |
|---|---|---|
| v5.8 Stable Balance | train `11218` 行，恢复稳定数据形状，补 region/multiline 与 pure-Yi anti-drift | total `0.0634`，yi `0.0512`，Han `0.0265`；replacement 和 long prediction 为 0，作为稳定回退 |
| v5.15 Layout Latin Rebalance | train `12436` 行，恢复字典注音、单行 Yi-Han 和纯彝文形近字平衡 | total `0.0505`，yi `0.0473`，Han `0.0261`；修复 v5.14 collapse，曾为最强 |
| v5.16 Synth Capped Rerender | train `21504` 行；同标签合成重渲染 `9069` 行；Latin 不放大，footnote 和 region-like 设上限 | 旧 611 口径 total `0.0342`，yi `0.0372`，Han `0.0225`；LaTeX 降到 2，最终胜出 |
| v5.17 Micro Format Tail | train `21854` 行；新增 `350` 行格式长尾 guard | total 回升到 `0.0429`，LaTeX 回到 10，出现 long_pred 1，因此不替代 v5.16 |

取舍结论：这几条分支最后给出的判断很明确：继续加数据不会自动变好，真正要盯的是数据分布。layout、脚注、safe-ending 类样本能修局部问题，也会把 Latin、LaTeX 和 long prediction 风险带回来。最终保留 v5.16，是因为它在旧 reviewed 口径下同时压低 total NED、yi NED、Han NED，输出风险也最低。

## 最终提交模型

最终公开模型命名为 **规范彝文 OCR / NuosuBburma OCR**。模型固定后，在 `NuosuBburma OCR Evaluation Set` 的 `603` 条 clean submission samples 上评估，作为本次提交包使用的结果。

| 指标 | 结果 |
|---|---:|
| 样本数 | 603 |
| Avg NED | 0.036068 |
| WS Avg NED | 0.034219 |
| NFKC+WS Avg NED | 0.033964 |
| Yi-only Avg NED | 0.038309 |
| Han-only Avg NED | 0.022447 |
| Digit-only Avg NED | 0.139918 |
| replacement / LaTeX / extra Latin / long_pred | 0 / 2 / 0 / 0 |
| ASCII-letter rows | 18 / 18，预测含 Latin 的 18 条 GT 本身也含 Latin 注音 |

结果文件：

```text
evaluation/README.md
evaluation/summary.md
evaluation/summary.json
evaluation/charts/
evaluation/tables/
evaluation/raw/submission_model_result.jsonl
```

## 评估集隔离与清理

为避免“评估集答案喂回训练”的风险，本项目保留了训练/评估隔离说明：

| 检查 | 结果 |
|---|---|
| eval image path 命中 | 0 |
| eval image basename 命中 | 0 |
| eval sample-id 命中 | 0 |
| `handwriting_small` 与 v5.16 rerender 标签完全重合 | 0 |
| v5.16 清理动作 | 删除 2 条 `handwriting_small` 标签完全重合行 |
| 剩余完全重合说明 | 7 条来自继承的 `train_yi` 旧行，不来自 v5.16 新增 rerender 或 handwriting_small |

这部分信息记录在 `configs/train_data_manifest_v5_16.json` 的 `post_clean_20260622` 字段中。

## 使用边界

- 本模型支持整页、区域和行图输入。
- 当前最稳定的使用方式通常是 line / region OCR。
- 复杂整页文档在版面较密、手写、多栏、脚注、注音块或图文混排较强时，建议配合版面分析、切图流程或人工复核。
- 手写样本已有一定泛化能力，但稳定性弱于印刷体。
- 脚注符号仍有少量 LaTeX 化残留。
- 本版本尚未进行专门的端侧/移动端优化。
