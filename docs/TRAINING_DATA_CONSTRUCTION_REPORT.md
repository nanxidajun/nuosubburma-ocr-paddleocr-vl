# 训练数据构建报告

本文档对应比赛评分中的“训练数据集构建科学性”。它只说明训练数据如何来、如何标注、如何质检，以及为什么最终训练包采用当前结构。评估集真实性和评估结果另见 [评估集说明](EVALUATION_DATASET.md) 与 [评估集质检报告](EVALUATION_QUALITY_REPORT.md)。

## 对齐评分项

| 官方子项 | 本项目对应材料 |
|---|---|
| 采集流程规范性 | 真实书页/行图、手写、页面照片和实拍照片分别记录来源；训练数据 manifest 保留构建脚本、包名、随机种子和清理记录 |
| 标注规范完整性 | 真实训练锚点使用人工整理或核对后的文本标签；合成与重渲染样本使用训练侧规则生成的可追溯标签 |
| 质量控制机制 | 图片路径、空标签、替换符、LaTeX-like 标签、反斜杠、训练/评估重叠等检查均有记录 |
| 数据统计分析 | 公开训练配置和 manifest 记录训练行数、真实/合成构成、重渲染比例、风险通道上限和主要类别分布 |

## 构建目标

规范彝文 OCR 是低资源文字场景。只依赖少量真实书页，很难覆盖 1165 个规范彝文字符、形近字、旧印刷噪声、彝汉混排、数字和页面边界；但合成样本使用过多或分布失衡，又容易让模型学到错误输出习惯。因此训练集采用三层结构：

```text
真实样本作为任务锚点
+ 受控合成样本补字符、形近字和视觉域覆盖
+ monitor/guard 样本限制输出空间漂移
```

这里的“受控”有两层含义：第一，合成样本只用于训练，不进入主评估集；第二，Latin、脚注、region-like 等容易引发漂移的通道设置上限，不能因为局部错误就无限加样本。

## 数据来源

训练数据来自两类入口：真实资料整理和规则化合成补覆盖。

| 来源类型 | 内容 | 在训练中的作用 |
|---|---|---|
| 真实旧书/扫描件裁切行 | 《勒俄特依》相关旧书、资料选译、语法书、工具书等 | 锚定真实字体、旧印刷、长行、彝汉混排和版式边界 |
| 真实短行与混排行 | 纯彝文、彝汉混排、标题/目录/短句 | 让模型先学会 OCR 输出格式和常见行图形态 |
| 手写与页面照片 | 人工采集手写样本、页面照片和实拍照片 | 提供真实用户输入路径的初步泛化信号 |
| 合成低频字覆盖 | 按字符频率和规范彝文字符集生成 | 补真实训练中缺失或极低频的字形 |
| 形近字与 tone pair guard | 面向易混字、x/base 声调家族和结构相近字 | 降低形近字互相吸附的问题 |
| 旧印刷与页面退化 | 低对比、轻微模糊、压缩、旧印刷缺损等 | 扩大视觉域，而不是只适应清晰行图 |
| 多行 region 与脚注 guard | 段落、换行、脚注和注音邻近样本 | 训练输出完整性，同时监控 LaTeX 化和长输出风险 |

所有真实资料样本和合成样本在构建逻辑上保持区分。公开仓库不直接发布训练图片包，但保留提交模型对应的训练配置和 manifest：

```text
configs/paddleocr-vl_lora_16k_nuosubburma_v5_16.yaml
configs/paddleocr-vl_lora_export_nuosubburma_v5_16.yaml
configs/train_data_manifest_v5_16.json
```

## 训练样本构建流程

训练集和评估集分开构建。评估集的“模型预标注 + 人工核对”流程见 [评估集质检报告](EVALUATION_QUALITY_REPORT.md)；本节只说明训练数据如何形成。

训练数据由三类样本组成：

| 类型 | 标签来源 | 进入训练的条件 |
|---|---|---|
| 真实训练锚点 | 人工整理或人工核对后的真实行图/区域图文本 | 只保留可判读、路径完整、标签非空的样本；不把最终评估集作为训练目标 |
| 合成/重渲染训练样本 | 渲染文本本身就是标签，同标签重渲染不改变文本内容 | 只用于补字符覆盖、形近字和视觉域；生成后检查空标签、替换符、LaTeX-like 标签和反斜杠 |
| monitor / guard 样本 | 按训练侧规则构造的边界样本 | 用来限制 Latin、脚注、region-like、多行和长输出风险；设置比例上限 |

真实训练锚点的处理方式：

```text
真实训练图片整理
-> 切成行图或区域图
-> 人工整理或核对文本标签
-> 删除坏图、不可判读样本或重复样本
-> 通过路径、空标签和格式检查
-> 写入训练包
```

合成与重渲染样本的处理方式：

```text
训练侧字符/版式规则
-> 生成文本标签
-> 渲染为图片
-> 同标签多视觉形态重渲染
-> 执行输出空间与路径检查
-> 按风险通道上限并入训练包
```

关键规则：

- 训练集不复用最终评估集作为训练目标。
- 合成样本只用于训练补覆盖，不进入主评估集。
- 真实训练锚点、合成样本、monitor/guard 样本在 manifest 中保持类别区分。
- 对彝文、汉字、数字、Latin 注音和标点分别观察，不把所有错误混成一个指标。
- 多行 region 用于训练换行和完整性，但设置上限，避免模型把单行也输出成多行。
- 脚注、括号、斜杠、Latin 注音等高风险格式不随意扩充，避免诱发 LaTeX-like 输出或 GT 外 Latin 尾巴。

## 当前训练包

最终公开模型对应的训练包为：

```text
v5_16_synth_capped_rerender_official
```

它从 `v5_15_layout_latin_rebalance_official` 继承稳定数据，再进行同标签合成重渲染。训练超参数保持不变，主要改变是数据分布与高风险通道上限。

| 项目 | 数量或设置 |
|---|---:|
| train rows after clean | 21504 |
| base rows | 12435 |
| new rerender rows | 9069 |
| unchanged real rows | 1861 |
| original synthetic rows | 10574 |
| added ordinary rerenders | 8360 |
| added footnote rerenders | 60 |
| added region-like rerenders | 649 |
| added Latin rerenders | 0 |
| epochs | 2 |
| learning rate | 5.0e-4 |
| min learning rate | 5.0e-5 |
| batch size / grad accumulation | 4 / 16 |

重渲染不是为了改变标签，而是让相同标签在更多字体、退化和页面视觉状态下出现。这样能扩大视觉覆盖，同时避免把真实评估错误直接写成训练目标。

## 高风险通道控制

低资源 OCR 的风险不只在 NED，还在输出空间是否稳定。本项目把若干容易导致漂移的通道单独限额。

| 通道 | 当前处理 |
|---|---|
| Latin 注音 | 不放大 Latin rerender；保留必要的字典/注音样本，但避免把 Latin 尾巴扩成默认输出习惯 |
| 脚注/符号 | 只保留少量 literal guard，避免增加 LaTeX-like 先验 |
| region-like 多行 | 保留多行完整性训练，但设置上限，避免模型把单行也输出成多行 |
| 形近字 | 使用 pair-balanced 和 frequency-rule 样本补边界，不直接照搬评估错题 |
| 旧印刷退化 | 用视觉重渲染补域，不改变 OCR 标签语义 |

manifest 中记录的上限和新增量：

| 项目 | 数量 |
|---|---:|
| ordinary rerenders added | 8360 |
| footnote rerenders added | 60 |
| region-like rerenders added | 649 |
| Latin rerenders added | 0 |
| footnote cap | 60 |
| region-like cap | 650 |
| Latin cap | 0 |

## 质量控制

当前训练包在公开 manifest 中保留以下检查结果：

| 检查项 | 结果 |
|---|---:|
| missing images | 0 |
| empty labels | 0 |
| replacement labels | 0 |
| rows with LaTeX-like labels | 0 |
| rows with backslash | 0 |
| eval image path hits after clean | 0 |
| eval image basename hits after clean | 0 |
| eval sample-id hits after clean | 0 |

训练/评估隔离还做了标签重合清理。2026-06-22 的清理记录显示，已删除 `2` 条 `handwriting_small` 与评估集完全重合的标签行。清理后仍有 `7` 条完全重合标签，但来源为继承的 `train_yi` 旧行，不来自 v5.16 新增重渲染，也不来自 `handwriting_small`；它们保留为历史真实训练锚点，同时在 manifest 中明示。

## 训练/评估隔离

为避免“把评估集喂回训练”的风险，本项目遵守以下规则：

- 主评估集冻结后，不按最终模型输出自动改写。
- 合成训练样本不进入主评估结果。
- 人工复核真实样本只用于检查模型分支的错误模式，不作为新样本生成清单。
- 形式化评估标签只作为 denylist 使用，避免生成样本与评估样本精确重合。
- 新增样本来自原始合成标签、训练侧频率规则、字符集规则或版式规则。

最终提交模型固定后，在 `603` 条真实样本上评估，结果见 [评估结果](../evaluation/)。

## 可复现入口

训练入口：

```bash
scripts/run_train_lora.sh
```

导出配置：

```text
configs/paddleocr-vl_lora_export_nuosubburma_v5_16.yaml
```

评估入口：

```bash
scripts/run_eval.sh \
  models/NuosuBburma-OCR \
  datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  outputs/NuosuBburma_OCR_Evaluation_Set/result.jsonl
```

环境、训练参数和模型选择逻辑详见 [模型与训练说明](MODEL_AND_TRAINING.md)。
