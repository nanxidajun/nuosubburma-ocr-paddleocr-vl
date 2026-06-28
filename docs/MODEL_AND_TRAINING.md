# 模型与训练说明

本文档对应主提交稿中的“训练数据集构建”和“模型微调策略与实验验证”。它重点说明：作为 PaddleOCR-VL 衍生模型，本项目如何构建训练数据、为什么选择 LoRA、如何控制输出漂移、为什么最终选择当前提交模型。

这份说明的重点是说明每一次取舍都有依据，而不只是证明训练过程复杂。对规范彝文这样的低资源 OCR，模型能力往往由数据分布、评估设置和输出风险共同决定，不能只看单个参数。它对应赛事中的“模型微调策略与创新”维度：创新不一定是改模型结构，也可以是把长尾文字训练做成可解释、可复查、可复现的闭环。

## 基础方案

| 项目 | 内容 |
|---|---|
| 公开模型名 | `规范彝文 OCR / NuosuBburma OCR` |
| 基座模型 | `PaddleOCR-VL-1.6 (0.9B)` |
| 微调方式 | LoRA |
| 任务提示词 | `<image>OCR:` |
| 主任务 | 规范彝文 OCR |
| 混排能力 | 支持纯彝文、彝汉混排、数字和符号场景 |
| 输入范围 | 可输入 page / region / line 图像；稳定交付优先使用 line / region |
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

训练集构建遵循“真实锚点 + 合成覆盖 + 冻结评估”的原则，避免把真实评估错题喂回模型。这一原则服务于比赛的两个评分面：既要证明训练数据构建科学，也要保证评估结果能独立说明模型能力。

低资源文字训练有一个现实矛盾：只用真实数据，覆盖不够；大量使用合成数据，又可能污染真实语言分布和视觉分布。本项目的处理方式是先让真实样本决定任务边界，再从具体场景设计合成数据补真实训练集中不足的部分。也就是说，真实数据负责“像不像真实任务”，合成数据负责“够不够覆盖”，诊断样本负责“有没有跑偏”。

| 数据类型 | 作用 |
|---|---|
| 真实书页/行图 | 锚定真实字体、旧印刷、混排和版式 |
| 合成低频字样本 | 补真实训练中缺失或极低频的规范彝文字形 |
| 形近字防混淆样本 | 平衡易混字的视觉边界，避免只把模型推向其中一个字 |
| 旧印刷退化样本 | 模拟低对比、模糊、压缩、油墨不均等视觉退化 |
| 多行 region 样本 | 训练换行、阅读顺序、段落和脚注/注音块 |
| 输出约束样本 | 防止 Latin、LaTeX、替换符、长尾续写等漂移 |
| 诊断样本 | 诊断特定错误是否回归，不参与最终评估 |

数据构建约束：

- 真实数据和合成数据保持可区分。
- 不把最终评估集答案作为训练目标。
- 优先增加视觉多样性，而不是盲目增加文本标签多样性。
- 对 Latin、公式化输出、脚注和 region 类高风险样本设置比例上限。
- 彝文识别、汉字识别、数字识别和混排行为分开观察。
- 规范手写、复杂多行 region 和复杂整页 OCR 作为高难度泛化场景，不和清晰印刷行图混为同一种能力。

## 三阶段训练路线

训练没有一开始就把所有数据混在一起。最早先用《勒俄特依》的真实裁切行确认模型能学会规范彝文字形，再加入合成覆盖、诊断样本和人工复核真实样本错误检查。

| 阶段 | 目标 | 关键判断 |
|---|---|---|
| 第一阶段：单书可行性 | 使用《勒俄特依》真实裁切行，确认 PaddleOCR-VL LoRA 能否学习规范彝文字形和基本输出格式 | 可以学习基本彝文字形，但单书覆盖不足 |
| 第二阶段：真实数据 + 合成覆盖 + 诊断样本 | 增加低频字、形近字、标点边界、旧印刷退化、彝汉混排和版式变化；用诊断样本观察输出漂移 | 合成数据有用，但必须控制 Latin、LaTeX、ASCII 和长输出风险 |
| 第三阶段：真实样本错误检查 | 用人工复核后的真实样本比较模型分支，同时看 NED、彝文、汉字、数字和输出空间风险 | 这些真实样本不作为训练目标；重点看模型是否反复出现漂移、公式化、漏行、长输出和混排不稳 |

第三阶段要单独说明。真实数据在这里承担的是检测作用，不是把评估答案喂回训练。低资源 OCR 里，单个字的错当然会记录，但选模型时更重要的是错误模式有没有反复出现：脚注附近被公式化、人工标注外多出 Latin、region 漏行、数字不稳、整页边界错、规范手写域差异。这些信号决定某个分支是否继续，不会直接把样本答案反向补进训练集。这种做法牺牲了一点“快速修分”的诱惑，换来的是模型选择的可信度。

## 分支选择摘要

内部实验很多，但最终文档不按流水账列几十次训练，而按“分支判断”说明为什么当前模型胜出。

![Training branch strategy](figures/training_branch.svg)

关键分支卡：

| 分支 | 数据构成/动作 | 结果与判断 |
|---|---|---|
| Stable Balance | train `11218` 行，恢复稳定数据形状，补 region/multiline 与纯彝文防漂移样本 | total `0.0634`，yi `0.0512`，Han `0.0265`；replacement 和 long prediction 为 0，作为早期稳定基线 |
| Layout Latin Rebalance | train `12436` 行，恢复字典注音、单行 Yi-Han 和纯彝文形近字平衡 | total `0.0505`，yi `0.0473`，Han `0.0261`；修复前序 collapse，曾为最强 |
| Synth Capped Rerender | train `21504` 行；同标签合成重渲染 `9069` 行；Latin 不放大，footnote 和 region-like 设上限 | 内部诊断口径 total `0.0342`，yi `0.0372`，Han `0.0225`；LaTeX 降到 2，最终胜出 |
| Micro Format Tail | train `21854` 行；新增 `350` 行格式长尾约束样本 | total 回升到 `0.0429`，LaTeX 回到 10，出现 long_pred 1，因此不替代当前提交分支 |

取舍结论：这几条分支最后给出的判断很明确：继续加数据不会自动变好，真正要盯的是数据分布。页面结构、脚注和结尾安全类样本能修局部问题，也可能把 Latin、LaTeX 和 long prediction 风险带回来。当前提交分支在开发诊断下同时压低 total NED、yi NED、Han NED，输出风险也最低。最终没有选择 v5.17，是因为本项目按真实评估和风险指标选模型，而不是按训练轮次或版本号选模型；这也是给赛事评委看的模型选择依据。

## 最终提交模型

最终公开模型命名为 **规范彝文 OCR / NuosuBburma OCR**。最终提交采用 `NuosuBburma OCR Evaluation Set` 统一口径；当前提交模型已经在 `603` 条主评估样本上完成评估。Base、第一阶段、第二阶段和最终模型结果将在最终评估集冻结后按同一脚本补充；当前提交模型列是本次主结果。

| 指标 | PaddleOCR-VL Base | 当前提交模型 |
|---|---:|---:|
| 样本数 | 最终评估后补充 | 603 |
| Avg NED | 最终评估后补充 | 0.036068 |
| Exact match | 最终评估后补充 | 67.99% |
| WS Avg NED | 最终评估后补充 | 0.034219 |
| NFKC+WS Avg NED | 最终评估后补充 | 0.033964 |
| Yi-only Avg NED | 最终评估后补充 | 0.038309 |
| Yi-only exact | 最终评估后补充 | 74.96% |
| Han-only Avg NED | 最终评估后补充 | 0.022447 |
| Han-only exact | 最终评估后补充 | 93.99% |
| Digit-only Avg NED | 最终评估后补充 | 0.139918 |
| Digit-only exact | 最终评估后补充 | 85.19% |
| replacement / LaTeX / extra Latin / long_pred | 最终评估后补充 | 0 / 2 / 0 / 0 |

开发诊断结果和分组结果保留在 `evaluation/`，用于解释分支选择、错误类型和输出风险控制。逐样本输出保存在 `evaluation/raw/submission_model_result.jsonl`，不是只提供汇总表。这样评审可以从总分追到分组，再追到具体样本，看到模型强在哪里、弱在哪里。

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
| `handwriting_small` 与当前重渲染标签完全重合 | 0 |
| 清理动作 | 删除 2 条 `handwriting_small` 标签完全重合行 |
| 剩余完全重合说明 | 7 条来自继承的 `train_yi` 旧行，不来自当前新增重渲染或 handwriting_small |

这部分信息记录在 `configs/train_data_manifest_v5_16.json` 的 `post_clean_20260622` 字段中。

## 使用边界

- 本模型可以输入整页、区域和行图。
- 当前最稳定的使用方式通常是 line / region OCR。
- 复杂整页输入直接 page OCR 时，容易在长段落和复杂混排处产生非标注换行、阅读顺序偏差或段落边界误判。
- 复杂整页文档在版面较密、规范手写、多栏、脚注、注音块或图文混排较强时，建议先走页面切割流程，再做 OCR 单元识别、页面文本合并和人工复核。
- 规范手写样本已纳入独立观察，结果与印刷体分开解读。
- 脚注符号有 `2` 条 LaTeX-like 输出需要单独复查。
- 本版本尚未进行专门的端侧/移动端优化。
