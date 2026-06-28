# 评估集质检报告

本文档对应比赛评分中的“评估集质量”，重点说明当前 `NuosuBburma OCR Evaluation Set` 为什么是真实、可复查、可稳定评估的。对本次 PaddleOCR 衍生模型挑战赛来说，评估集不是结果表的附件，而是判断衍生模型是否真正覆盖长尾 OCR 场景的基础证据。数据集的来源、分布和结果解读另见 [评估集说明](EVALUATION_DATASET.md)。

## 质检结论

最终主评估集全部使用真实来源样本，纳入主评分的样本不使用合成训练数据。这一点直接对齐赛事对评估集真实性和真实噪声覆盖的要求。

| 检查项 | 结果 |
|---|---:|
| score-included samples | 603 |
| referenced images | 603 |
| missing images | 0 |
| blank labels | 0 |
| replacement labels | 0 |
| all samples score included | true |
| removed or archived during build | 27 |
| official eval version | NuosuBburma OCR Evaluation Set |

这些检查来自构建摘要、逐样本输出和公开复查入口。GitHub 仓库保留可复查的最终材料，方便评委从 summary 追到分组统计和逐样本输出：

```text
NuosuBburma_OCR_Evaluation_Set/README.md
docs/EVALUATION_DATASET.md
evaluation/summary.md
evaluation/summary.json
evaluation/tables/
evaluation/charts/
evaluation/raw/submission_model_result.jsonl
```

完整图片数据托管在 Hugging Face 评估集仓库，GitHub 仓库只保留入口、脚本、统计和逐样本输出。

## 数据真实性

评估样本来自真实资料整理，不使用合成样本证明主结果。

| 来源类型 | 样本数 | 说明 |
|---|---:|---|
| 新印刷扫描 | 309 | 教材、现代出版物、工具书等清晰资料 |
| 旧书扫描 | 235 | 旧版资料选译、旧式排版、旧印刷噪声和旧书页面 |
| 手写拍照 | 53 | 作者采集或整理的规范彝文手写样本 |
| 真实场景拍摄/屏幕图 | 6 | 公共标牌、屏幕页面、页面图像或真实上传噪声 |

按来源书目和材料看，评估集包含：

| 来源 | 样本数 |
|---|---:|
| 勒俄玛牧导读教程 | 126 |
| 根与花 | 121 |
| 凉山彝文资料选译第2集 | 106 |
| 凉山彝文资料选译第3集 | 84 |
| 规范手写 | 53 |
| 《勒俄特依》译注 | 45 |
| 彝文检字本 | 32 |
| 凉山彝语语法 | 30 |
| 真实照片 / 实拍图 | 3 |
| 页面图像 / 屏幕图 | 3 |

书籍样本来自扫描件裁剪，原始出版物版权归原出版社和权利人所有；本项目仅使用裁剪图像进行规范彝文 OCR 评估和模型验证。

## 标注流程

评估集采用“模型预标注 + 人工核对”的方式构建。预标注用于降低人工录入成本，最终标准答案仍以人工核对为准。

```text
真实来源图片整理
-> 页面切割或区域裁剪
-> 中间模型生成预标注草稿
-> 人工逐条核对标准答案
-> 删除坏图、单字碎片或不可稳定判读样本
-> 统一 metadata 和 annotations.jsonl
-> 生成分布统计与复查页面
```

标注规则：

- 空标注和占位符标注不进入主评估。
- 规范手写、多行 region、页面图像、脚注、数字和彝汉混排不因难度高而简单删除。
- 多行样本保留换行，避免把 region/page 强行压成单行。
- Latin 注音只在人工标注可见时保留；人工标注无 Latin 的样本用于检查模型是否出现多余 Latin 输出。
- 评估样本不进入最终训练目标，训练侧只使用排除清单规避精确重合。

## 数据规模与粒度

最终数据集覆盖真实评估所需的主要输入粒度，但项目仍把 `line / region / page` 分开解读，避免把行图识别、区域换行和整页能力混为一个指标。

| sample type | 样本数 |
|---|---:|
| line | 515 |
| region | 84 |
| page | 4 |

这组分布的定位是主评估集：行图用于观察文字识别稳定性，region/page 用于暴露漏行、版面边界、阅读顺序和非标注换行问题。复杂整页资料建议配合页面切割流程和人工复核；压力测试材料与主评估集分开维护。

## 多样性

评估集从场景、文字混合和数字三个维度记录分布。

| script mix | 样本数 |
|---|---:|
| 彝文 | 321 |
| 彝汉混排 | 265 |
| 带拉丁字母的彝汉混排 | 17 |

| digit presence | 样本数 |
|---|---:|
| has digit | 81 |
| no digit | 522 |

数字、页码和编号在结果中单独报告，因为这类字符在 OCR 输出里容易受格式、换行和标点影响。

## 难度合理性

难度分布如下：

| difficulty | 样本数 |
|---|---:|
| easy | 172 |
| medium | 324 |
| hard | 107 |

难度不是按模型预测结果倒推，而是结合来源、视觉质量、输入粒度和文本混合情况标注。主集保留了规范手写、region、页面图像、旧印刷、数字、脚注和彝汉混排样本，因此不会只评估清晰 PDF 行图。

## 删除与归档记录

构建过程中有 `27` 条临时整理样本被删除、替换或归档，原因包括：

- 行切分版本与完整原图重复，保留完整原图或更稳定版本。
- 单字切片信息量太低，不作为主评估样本。
- 用户补充的更清晰副本替换旧版本。
- 页面图像使用人工整理后的完整标准答案。

这些删除不用于“刷高指标”，而是为了避免重复、不可稳定判读和低信息量样本影响评估集质量。保留样本全部计入主评分，不再拆成“展示样本”和“评分样本”两套。

## 评估复查入口

公开仓库保留以下复查材料：

```text
NuosuBburma_OCR_Evaluation_Set/README.md
docs/EVALUATION_DATASET.md
evaluation/summary.md
evaluation/summary.json
evaluation/tables/
evaluation/charts/
evaluation/raw/submission_model_result.jsonl
scripts/eval_nuosubburma.py
scripts/analyze_submission_eval.py
```

Hugging Face 评估集保留：

```text
annotations.jsonl
images/
README.md
samples.csv
dataset_summary.json
```

评估脚本会输出整体 NED、空白处理后的 NED、Unicode 规范化后的 NED、Yi-only / Han-only / Digit-only NED，以及 replacement、LaTeX-like、extra Latin 和 long prediction 等输出风险指标。首页不把 exact match 作为唯一判断依据，因为逐字全等对空白、换行和标点过于敏感，不适合作为低资源 OCR 的主展示指标。

## 当前结果摘要

当前提交模型已使用同一评估集、同一脚本、同一指标统计。Base、第一阶段、第二阶段和最终模型结果将在最终评估集冻结后按同一脚本补充，当前模型列是本次主结果：

| 指标 | PaddleOCR-VL Base | 当前提交模型 |
|---|---:|---:|
| 样本数 | 最终评估后补充 | 603 |
| Avg NED | 最终评估后补充 | 0.036068 |
| WS Avg NED | 最终评估后补充 | 0.034219 |
| NFKC+WS Avg NED | 最终评估后补充 | 0.033964 |
| Yi-only Avg NED | 最终评估后补充 | 0.038309 |
| Han-only Avg NED | 最终评估后补充 | 0.022447 |
| Digit-only Avg NED | 最终评估后补充 | 0.139918 |
| replacement / LaTeX / extra Latin / long_pred | 最终评估后补充 | 0 / 2 / 0 / 0 |

结果可由 `scripts/run_eval.sh` 和 `scripts/analyze_submission_eval.py` 复跑；逐条输出保存在 `evaluation/raw/submission_model_result.jsonl`，用于解释分支选择和错误风险。
