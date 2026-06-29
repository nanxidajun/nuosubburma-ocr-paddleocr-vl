# 模型与训练说明

本文档说明提交模型的基础设置、三阶段 LoRA 微调策略、训练包构成、分支选择和当前评估结果。

先给出边界：训练包、开发诊断集和最终评估集分开使用。

| 材料 | 用途 | 是否进入训练 |
|---|---|---|
| 训练包 | 给模型提供学习信号，包含真实训练材料、训练侧合成样本、同标签重渲染和少量约束样本 | 是 |
| 开发诊断集 | 比较不同训练分支的输出表现，观察 NED、LaTeX-like、extra Latin 和 long prediction 等风险 | 否 |
| 最终评估集 | 报告提交模型效果，支撑公开结果表 | 否 |

## 基础设置

| 项目 | 内容 |
|---|---|
| 公开模型名 | `规范彝文 OCR / NuosuBburma OCR` |
| 基座模型 | `PaddleOCR-VL-1.6 (0.9B)` |
| 微调方式 | LoRA |
| 任务提示词 | `<image>OCR:` |
| 主任务 | 规范彝文 OCR |
| 输入范围 | line / region / page 图像；稳定交付优先使用 line / region，复杂 page 建议先做页面切割 |
| 训练硬件 | NVIDIA RTX 4090D，单卡训练 |
| 部署状态 | 暂未做端侧或移动端部署 |

关键配置文件：

```text
configs/paddleocr-vl_lora_16k_nuosubburma_v5_16.yaml
configs/paddleocr-vl_lora_export_nuosubburma_v5_16.yaml
configs/train_data_manifest_v5_16.json
```

训练环境和核心参数：

| 项目 | 值 |
|---|---:|
| Python | 3.11 |
| PaddleFormers | 1.1.1 |
| CUDA runtime | 11.8 |
| cuDNN | 8.9 |
| max sequence length | 16384 |
| LoRA rank | 8 |
| per-device batch size | 4 |
| gradient accumulation | 16 |
| epochs | 2 |
| learning rate | 5.0e-4 |
| minimum learning rate | 5.0e-5 |
| precision | bf16 |
| train loss | 0.191 |
| train runtime | 1:08:53.89 |

## 训练包

提交模型对应的训练包为：

```text
v5_16_synth_capped_rerender_official
```

训练数据不是简单扩大规模，而是分成四类：真实训练材料确定任务边界，训练侧合成样本补字符和格式覆盖，同标签重渲染补字体与旧印刷视觉变化，少量训练侧约束样本用于控制高风险格式。

| 项目 | 数量或设置 |
|---|---:|
| train rows after clean | 21504 |
| base rows | 12435 |
| new rerender rows | 9069 |
| unchanged real rows | 1861 |
| original synthetic rows | 10574 |
| ordinary rerenders added | 8360 |
| footnote rerenders added | 60 |
| region-like rerenders added | 649 |
| Latin rerenders added | 0 |
| missing images / empty labels / replacement labels | 0 / 0 / 0 |
| rows with LaTeX-like labels / backslash | 0 / 0 |

训练包约束：

- 真实训练材料和合成样本分开记录。
- 同标签重渲染只改变字体、退化和页面视觉状态，不改变文本标签。
- Latin、脚注、region-like 多行等高风险通道设置上限。
- 评估集图片、sample id 和标准答案不进入训练包。
- 新样本来自训练侧字符规则、频率规则、版式规则或原始合成标签。

训练数据的详细来源、标签来源和质检见 [训练数据构建报告](TRAINING_DATA_CONSTRUCTION_REPORT.md)。

## 三阶段调优策略

三阶段调优要体现的是训练策略，不是三次堆数据。

| 阶段 | 解决的问题 | 数据动作 | 判断方式 |
|---|---|---|---|
| 第一阶段：单书可行性 | 验证 `PaddleOCR-VL-1.6` + LoRA 能否学习规范彝文 | 使用《勒俄特依》真实裁切行建立基本任务 | 看模型是否能学会规范彝文字形和基本输出格式 |
| 第二阶段：覆盖补充 | 解决低频字符、字体变化、旧印刷退化和彝汉混排覆盖不足 | 加入训练侧合成样本、字符覆盖样本和同标签重渲染 | 分开观察彝文、汉字、数字、混排和异常输出 |
| 第三阶段：分支检查 | 比较不同训练包分支是否真正更稳 | 使用固定开发诊断集读取模型输出，不改写训练包 | 同时看 NED、LaTeX-like、extra Latin、long prediction 和 region 漏行 |

这条路线的关键是分工清楚：

- 第一阶段证明路线可行。
- 第二阶段补训练覆盖，但控制高风险通道比例。
- 第三阶段只做分支比较，不把开发诊断集或最终评估集写回训练包。

## 分支选择

分支比较主要改变数据分布，不改变模型结构。

![Training branch strategy](figures/training_branch.svg)

| 分支 | 训练数据动作 | 开发诊断集结果 | 判断 |
|---|---|---|---|
| v5.8 Stable Balance | 稳定数据形状，补 region/multiline 与纯彝文稳定样本 | total `0.0634`，yi `0.0512`，Han `0.0265`，long `0` | 早期稳定基线 |
| v5.15 Layout Latin Rebalance | 恢复字典注音、单行 Yi-Han 和纯彝文字符覆盖 | total `0.0505`，yi `0.0473`，Han `0.0261`，long `0` | 总分继续下降，但脚注风险仍高 |
| v5.16 Synth Capped Rerender | 同标签重渲染 `9069` 行，Latin 不放大，footnote/region 设上限 | total `0.0342`，yi `0.0372`，Han `0.0225`，LaTeX `2`，long `0` | 当前提交模型 |
| v5.17 Micro Format Tail | 追加 `350` 行格式长尾约束样本 | total `0.0429`，LaTeX 回到 `10`，long `1` | 风险回升，保留为对照 |

结论：继续加数据不一定变好。提交模型采用 v5.16，因为它在开发诊断集上同时降低 total NED、yi NED、Han NED，并保持较低输出风险。

## 当前评估结果

当前提交模型已经在 `603` 条主评估样本上完成评估。NED 为归一化编辑距离，越低越好。

| 指标 | 当前提交模型 |
|---|---:|
| 样本数 | 603 |
| Avg NED | 0.036068 |
| Exact match | 67.99% |
| WS Avg NED | 0.034219 |
| NFKC+WS Avg NED | 0.033964 |
| Yi-only Avg NED | 0.038309 |
| Yi-only exact | 74.96% |
| Han-only Avg NED | 0.022447 |
| Han-only exact | 93.99% |
| Digit-only Avg NED | 0.139918 |
| Digit-only exact | 85.19% |
| replacement / LaTeX / extra Latin / long_pred | 0 / 2 / 0 / 0 |

Base 模型、第一阶段模型、第二阶段模型和提交模型的同一最终评估集对比，待按同一脚本复跑后补充。当前不在公开文档中编造缺失结果。

结果文件：

```text
evaluation/README.md
evaluation/summary.md
evaluation/summary.json
evaluation/charts/
evaluation/tables/
evaluation/raw/submission_model_result.jsonl
```

## 隔离检查

训练包和评估集分开维护。当前 manifest 中保留以下检查：

| 检查 | 结果 |
|---|---:|
| eval image path 命中 | 0 |
| eval image basename 命中 | 0 |
| eval sample-id 命中 | 0 |
| `handwriting_small` 与当前重渲染标签完全重合 | 0 |
| 删除的完全重合标签行 | 2 |
| 保留的完全重合标签行 | 7 |

说明：保留的 `7` 条完全重合标签来自继承的 `train_yi` 旧行，不来自 v5.16 新增重渲染或 `handwriting_small`。这部分记录在 `configs/train_data_manifest_v5_16.json` 的 `post_clean_20260622` 字段中。

## 使用边界

- 本模型可以输入整页、区域和行图。
- 当前最稳定的使用方式通常是 line / region OCR。
- 复杂整页直接 page OCR 时，容易在长段落和复杂混排处产生非标注换行、阅读顺序偏差或段落边界误判。
- 复杂整页、规范手写长段落、多栏或脚注/注音密集页面，建议先走页面切割流程，再做 OCR 单元识别、页面文本合并和人工复核。
- 规范手写样本已纳入独立观察，结果与印刷体分开解读。
- 脚注符号有 `2` 条 LaTeX-like 输出需要单独复查。
- 本版本尚未进行专门的端侧或移动端优化。
