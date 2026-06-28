# 评估集说明

本文档对应主提交稿中的“真实评估集构建”，也是赛事评分中“评估集质量”的核心证据。它重点说明评估集为什么可信、覆盖了哪些真实难点，以及评估结果如何复查。

对低资源 OCR 来说，评估集决定了项目能否成立。本次比赛特别看重评估数据是否真实、是否覆盖复杂场景、是否能支撑公平复查；如果评估集只由干净样例组成，模型很容易看起来“已经可用”。只有来源真实、难度分层清楚、逐样本可复查，结果才有资格说明真实能力。

## 设计原则

低资源 OCR 可以使用合成数据训练，但不能用合成数据证明真实能力。赛事评分对评估集真实性非常敏感，因此本项目把训练数据和评估数据严格区分：

| 原则 | 说明 |
|---|---|
| 真实来源 | 主评估集只使用真实来源样本，合成样本不进入主结果 |
| 全量计入 | 主评估 `603` 条样本全部计入结果；没有“只展示不计分”的样本 |
| 覆盖多场景 | 覆盖新印刷、旧印刷、规范手写、页面照片、实拍/屏幕图、line/region/page |
| 保留难样本 | 规范手写、多行 region、脚注、数字、彝汉混排不因难度高而过滤 |
| 可复查 | 保留 annotations、图片、逐样本结果和分组统计 |

评估集尽量贴近真实使用，样本、标注和统计结果都保留下来，方便复查。这里刻意保留手写、多行、旧书和混排样本，是为了对齐赛事对复杂视觉场景和真实噪声的要求；这些样本会拉高难度，但能避免提交结果只对干净行图成立。

## 数据托管

完整评估集通过 Hugging Face 评估集仓库发布：

```text
https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set
```

正式评估集保留复跑评估所需的最小文件：

| 文件/目录 | 说明 |
|---|---|
| `README.md` | 数据集说明 |
| `annotations.jsonl` | 主评估标注，`603` 条 |
| `images/` | 全部被引用图片，`603` 张 |
| `samples.csv` | 每条样本的来源、场景、粒度、难度和文字构成 |
| `dataset_summary.json` | 汇总统计 |

GitHub 仓库不重复上传完整图片数据，只保留评估集入口说明、评估脚本和提交评估结果：

```text
NuosuBburma_OCR_Evaluation_Set/README.md
docs/EVALUATION_DATASET.md
scripts/eval_nuosubburma.py
scripts/analyze_submission_eval.py
evaluation/
```

## 数据分布

| 维度 | 分布 |
|---|---|
| 总量 | `603` 条主评估样本 |
| 样本类型 | `line 515`，`region 84`，`page 4` |
| 场景 | 新印刷扫描 `309`，旧书扫描 `235`，规范手写 `53`，实拍/屏幕 `6` |
| 难度 | `easy 172`，`medium 324`，`hard 107` |
| 文字混合 | `yi 321`，`yi_han 265`，`yi_han_latin 17` |
| 数字样本 | 含数字 `81`，不含数字 `522` |

这组分布主要覆盖规范彝文 OCR 在真实资料里会遇到的难点：换书、换字体、换版式、换输入粒度、旧书整页、混排、规范手写资料和照片输入。评估集真正要回答的，是模型能否跨来源、跨版式、跨输入形态保持基本稳定，而不只是读同一本书的相似行图。

![Evaluation dataset composition](figures/dataset_composition.svg)

## 来源构成

| 来源 | 样本数 | 评估意义 |
|---|---:|---|
| 勒俄玛牧导读教程 | 126 | 教程类资料，覆盖教学文本和彝汉混排 |
| 根与花 | 121 | 新印刷正文，提供清晰行图基准 |
| 凉山彝文资料选译第2集 | 106 | 旧印刷资料，覆盖旧书噪声和版式变化 |
| 凉山彝文资料选译第3集 | 84 | 换书、换排版的旧印刷评估样本 |
| 真实手写 | 53 | 规范手写资料，作为独立真实泛化分组 |
| 《勒俄特依》译注 | 45 | 译注资料，覆盖注释边界和彝汉混排 |
| 彝文检字本 | 32 | 工具书结构、检字和字形边界 |
| 凉山彝语语法 | 30 | 语法资料，覆盖汉字、数字和编号 |
| 真实照片 | 3 | 真实场景图像、背景干扰和可见文本 |
| 屏幕页面 | 3 | 屏幕页面、页面图像和上传噪声 |

## 构建流程

评估集采用“模型预标注 + 人工核对”的方式制作。预标注先给人工校对一份草稿，降低低资源文字标注成本；最终标准答案仍以人工核对为准。这样既利用了模型减少重复录入，也避免把模型自己的错误当成真值固化下来。

```text
真实来源图片整理
-> 页面切割或区域裁剪
-> 中间模型做预标注
-> 人工逐条核对标准答案
-> 删除坏样本
-> 统一基本格式
-> 生成 annotations.jsonl
```

标注格式使用 PaddleOCR-VL messages JSONL：

```json
{
  "id": "gen_yu_hua_line_000001",
  "images": ["images/gen_yu_hua_line_000001.png"],
  "messages": [
    {"role": "user", "content": "<image>OCR:"},
    {"role": "assistant", "content": "ground truth text"}
  ],
  "meta": {
    "source_name": "根与花",
    "source_code": "gen_yu_hua",
    "sample_type": "line",
    "script_mix": "yi",
    "difficulty": "easy"
  }
}
```

## 评估集检查目标

| 检查项 | 目的 |
|---|---|
| 换一本书 | 判断模型是否只适应单一排版书籍 |
| 换一种版式 | 判断旧印刷、工具书、语法书、混排资料是否稳定 |
| 彝汉混排 | 检查汉语、符号、脚注和注音附近是否漂移 |
| 规范手写/照片 | 检查模型是否有基础真实泛化能力 |
| 页面照片/上传图 | 检查页面切割和识别过程中哪里容易出错 |
| 单行/多行/整页 | 检验区域识别、阅读顺序和换行边界，而不是只看单行样例 |

## 评价指标

主指标：

| 指标 | 含义 |
|---|---|
| NED | 归一化编辑距离，越低越好 |
| WS Avg NED | 空白处理后的 NED |
| NFKC+WS Avg NED | Unicode 规范化和空白处理后的 NED |

辅助诊断指标：

| 指标 | 目的 |
|---|---|
| Yi-only NED | 单独观察彝文识别能力 |
| Han-only NED | 单独观察汉字混排识别能力 |
| Digit-only NED | 单独观察数字识别和格式稳定性 |
| replacement | 检查是否出现替换符 collapse |
| LaTeX-like outputs | 检查脚注/符号是否被错误公式化 |
| ASCII-letter | 统计预测中出现 Latin 字母的样本数，需要与人工标注对照 |
| extra Latin | 检查人工标注无 Latin 但预测多出 Latin 的样本数 |
| long_pred | 检查是否出现异常长输出 |

## 最终评估结果

最终提交模型已在 `603` 条主评估样本上完成评估。Base、第一阶段、第二阶段和最终模型结果将在最终评估集冻结后按同一脚本补充；当前提交模型列是本次主结果。结果表同时给出空白处理、Unicode 规范化、彝文、汉字、数字和输出风险指标，是为了避免只用一个总分遮住错误类型。

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

![Evaluation snapshot](figures/evaluation_snapshot.svg)

分组结果保留在以下文件中：

```text
evaluation/README.md
evaluation/charts/
evaluation/tables/by_sample_type.csv
evaluation/tables/by_scene.csv
evaluation/tables/by_difficulty.csv
evaluation/tables/by_script_mix.csv
evaluation/tables/by_source.csv
```

## 结果解读

| 分组 | 结果摘要 | 说明 |
|---|---|---|
| line | Avg NED `0.028758` | 清晰行图是当前最稳定输入 |
| region | Avg NED `0.079725` | 多行区域更容易出现漏行和边界错误 |
| page | Avg NED `0.060449`，仅 `4` 条 | 作为复杂整页诊断，不夸大为完整整页 OCR 能力 |
| new_print_pdf | Avg NED `0.029050` | 新印刷 PDF 效果稳定 |
| old_print_pdf | Avg NED `0.025771` | 旧印刷书籍在本评估集中表现稳定 |
| neat_handwriting | Avg NED `0.122708` | 规范手写资料与印刷体分开解读，当前作为独立泛化分组观察 |

这份分组结果说明当前能力边界很清楚：印刷体行图已经较稳，多行区域和规范手写仍是后续提升重点。项目没有把困难样本删掉来换取更漂亮的平均分，而是把它们留下来，作为赛事评审可见的真实难点和后续改进方向。

## 真实性边界

- 评估集不作为训练目标。
- 合成训练样本不进入主评估集。
- 模型预标注只作为人工核对草稿，不直接作为最终标准答案。
- 规范手写、region 和 page 结果需要与 line OCR 分开解读。
- 复杂整页压力测试材料与主评估集分开维护，不混入 `603` 条主结果。
- 评估集中的书籍样本来自扫描件裁剪，原始出版物版权归原出版社和权利人所有。
