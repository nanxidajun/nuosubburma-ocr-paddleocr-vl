# 模型与训练说明

本文档说明训练数据、LoRA 设置、输出风险控制和最终模型选择。

本文档先说明三阶段 LoRA 微调和训练包构成，再说明如何用固定评估设置比较模型。训练数据、开发诊断集和最终评估集分开使用。

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

训练数据由真实训练材料、训练侧合成样本、同标签重渲染和少量约束样本组成。

真实训练材料负责确定任务边界，合成数据和同标签重渲染负责补覆盖，约束样本用于限制容易过量输出的格式。评估集只出现在结果报告和隔离检查中。

| 数据类型 | 作用 |
|---|---|
| 真实训练书页/行图 | 锚定真实字体、旧印刷、混排和版式 |
| 合成低频字样本 | 补真实训练中缺失或极低频的规范彝文字形 |
| 字符覆盖样本 | 补充低频字符、字体变化和视觉边界，降低低资源字符覆盖不足带来的不稳定 |
| 旧印刷退化样本 | 模拟低对比、模糊、压缩、油墨不均等视觉退化 |
| 多行 region 样本 | 训练换行、阅读顺序、段落和脚注/注音块 |
| 训练侧约束样本 | 控制 Latin、LaTeX-like 片段、替换符和异常长输出风险 |

数据构建约束：

- 真实训练材料和合成数据保持可区分。
- 评估集图片、sample id 和标准答案不进入训练包。
- 优先增加视觉多样性，而不是盲目增加文本标签多样性。
- 对 Latin、公式化输出、脚注和 region 类高风险样本设置比例上限。
- 彝文识别、汉字识别、数字识别和混排行为分开观察。
- 规范手写、复杂多行 region 和复杂整页 OCR 作为高难度泛化场景，不和清晰印刷行图混为同一种能力。

## 三阶段训练路线

三阶段只说明训练推进方式；评估集不进入训练包。

| 阶段 | 目标 | 数据动作 | 判断方式 |
|---|---|---|---|
| 第一阶段：单书可行性 | 验证 PaddleOCR-VL + LoRA 能否学习规范彝文 | 使用《勒俄特依》真实裁切行建立基本任务 | 看模型是否能学会规范彝文字形和基本输出格式 |
| 第二阶段：覆盖补充 | 补低频字符、字体变化、旧印刷退化和彝汉混排 | 加入训练侧合成样本和同标签重渲染 | 看彝文、汉字、数字和混排行为是否更稳 |
| 第三阶段：分支检查 | 比较不同训练包分支的输出风险 | 使用固定开发诊断集读取模型输出，不改写训练包 | 同时观察 NED、LaTeX-like、extra Latin 和 long prediction |

这条路线的重点是分清三件事：训练包负责提供学习信号，开发诊断集负责比较分支，最终评估集负责报告提交结果。

## 分支选择摘要

下表只保留影响最终选择的分支。

![Training branch strategy](figures/training_branch.svg)

关键分支卡：

| 分支 | 数据构成/动作 | 结果与判断 |
|---|---|---|
| Stable Balance | train `11218` 行，恢复稳定数据形状，补 region/multiline 与纯彝文稳定样本 | 开发诊断集 total `0.0634`，yi `0.0512`，Han `0.0265`；replacement 和 long prediction 为 0，作为早期稳定基线 |
| Layout Latin Rebalance | train `12436` 行，恢复字典注音、单行 Yi-Han 和纯彝文字符覆盖 | 开发诊断集 total `0.0505`，yi `0.0473`，Han `0.0261`；总分继续下降，但脚注风险仍高 |
| Synth Capped Rerender | train `21504` 行；同标签合成重渲染 `9069` 行；Latin 不放大，footnote 和 region-like 设上限 | 开发诊断集 total `0.0342`，yi `0.0372`，Han `0.0225`；LaTeX 降到 2，作为当前提交分支 |
| Micro Format Tail | train `21854` 行；新增 `350` 行格式长尾约束样本 | 开发诊断集 total `0.0429`，LaTeX 回到 10，出现 long_pred 1，因此未采用 |

结论：继续加数据不一定变好，关键是控制数据分布。当前提交分支在开发诊断集上同时降低 total NED、yi NED、Han NED，并保持较低输出风险。

## 最终提交模型

最终公开模型命名为 **规范彝文 OCR / NuosuBburma OCR**。当前提交模型已经在 `603` 条主评估样本上完成评估。

Base、第一阶段、第二阶段和最终模型结果将在最终评估集冻结后按同一脚本补充；当前提交模型列是本次主结果。

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

开发诊断结果、分组结果和逐样本输出保留在 `evaluation/`。评审可以从总分追到分组和具体样本。

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

为避免训练包和评估集混用，本项目保留了以下检查：

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
- 复杂整页、规范手写长段落、多栏或脚注/注音密集页面，建议先走页面切割流程，再做 OCR 单元识别、页面文本合并和人工复核。
- 规范手写样本已纳入独立观察，结果与印刷体分开解读。
- 脚注符号有 `2` 条 LaTeX-like 输出需要单独复查。
- 本版本尚未进行专门的端侧/移动端优化。
