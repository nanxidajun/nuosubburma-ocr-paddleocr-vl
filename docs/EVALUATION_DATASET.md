# 评估集说明

本文档对应主提交稿中的“真实评估集构建”。它重点说明评估集为什么可信、覆盖了哪些真实难点，以及评估结果如何复查。

## 设计原则

低资源 OCR 可以使用合成数据训练，但不能用合成数据证明真实能力。因此本项目把训练数据和评估数据严格区分：

| 原则 | 说明 |
|---|---|
| 真实来源 | 主评估集只使用真实来源样本，不使用合成样本证明真实能力 |
| 全量计入 | `603` 条样本全部纳入评估，没有空 GT 和占位符 GT |
| 覆盖多场景 | 覆盖新印刷、旧印刷、规范手写、页面照片、真实场景照片、line/region/page |
| 保留难样本 | 手写、多行区域、脚注、数字、彝汉混排不被简单过滤 |
| 可复查 | 保留 annotations、图片、逐样本结果和分组统计 |

这样设计是为了让评估结果尽量接近真实使用场景，同时保留可复查的样本、标注和统计结果。

## 数据托管

完整评估集托管在 Hugging Face Dataset：

```text
https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set
```

HF Dataset 当前只保留复跑评估所需的最小文件：

| 文件/目录 | 说明 |
|---|---|
| `README.md` | 数据集说明 |
| `annotations.jsonl` | 主评估标注，603 条样本 |
| `images/` | 全部被引用图片，603 张 |

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
| 总量 | `603` 条样本，引用图片 `603` 张，全部纳入评估 |
| 样本类型 | `line` 515，`region` 84，`page` 4 |
| 场景 | 新印刷 PDF 309，旧印刷/旧书扫描 235，规范手写 53，照片/真实场景 6 |
| 难度 | `easy` 172，`medium` 324，`hard` 107 |
| 文字混合 | `yi` 321，`yi_han` 265，`yi_han_latin` 17 |
| 数字样本 | 含数字 `81` 条，不含数字 `522` 条 |

这些分布不是为了追求样本数量最大，而是为了覆盖规范彝文 OCR 的真实难点：换书、换字体、换版式、换输入粒度、混排、手写和照片输入。

![Evaluation dataset composition](figures/dataset_composition.svg)

## 构建流程

评估集采用“模型预标注 + 人工核对”的方式制作。这样既能降低低资源文字标注成本，又避免把模型输出直接当作 GT。

```text
真实来源图片整理
-> 切图或区域裁剪
-> 中间模型做预标注
-> 人工逐条核对 GT
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
| 手写/照片 | 检查模型是否有基础真实泛化能力 |
| 照片/上传图 | 检查切图与识别链路是否暴露问题 |
| 单行/多行 | 检验区域识别能力，而不是只看单行样例 |

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
| ASCII-letter | 统计预测中出现 Latin 字母的样本数，需要与 GT 对照 |
| extra Latin | 检查 GT 无 Latin 但预测多出 Latin 的样本数 |
| long_pred | 检查是否出现异常长输出 |

## 最终评估结果

最终提交模型在 `603` 条真实样本上的重跑结果：

![Evaluation snapshot](figures/evaluation_snapshot.svg)

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
| page | Avg NED `0.060449`，样本数 4 | 可以处理整页输入，但复杂整页不应夸大 |
| new_print_pdf | Avg NED `0.029050` | 新印刷 PDF 效果稳定 |
| old_print_pdf | Avg NED `0.025771` | 旧印刷书籍在本评估集中表现稳定 |
| neat_handwriting | Avg NED `0.122708` | 手写仍是最弱场景，应单独解释 |

## 真实性边界

- 评估集不作为训练目标。
- 合成训练样本不进入主评估集。
- 模型预标注只作为人工核对草稿，不直接作为最终 GT。
- 手写、region 和 page 结果需要与 line OCR 分开解读。
- 评估集中的书籍样本来自扫描件裁剪，原始出版物版权归原出版社和权利人所有。
