# 最终评估结果

本目录作为公开评估结果入口。当前统一口径为最终 `758` 条真实来源样本，使用最新人工 GT；未微调基座和 LoRA 微调模型使用同一套标注、同一套图片和同一套评估脚本。

## 当前结果

归一化编辑距离（NED）越低越好。LoRA 微调后整体 Avg NED 为 `0.052310`，未微调基座为 `0.726733`。

| 指标 | 未微调基座 | LoRA 微调后 |
|---|---:|---:|
| 评估样本 | `758` | `758` |
| Avg NED | `0.726733` | `0.052310` |
| WS Avg NED | `0.719600` | `0.051771` |
| NFKC+WS Avg NED | `0.706794` | `0.051670` |
| Exact | `0 / 758` | `445 / 758 (58.7%)` |
| Yi-only Avg NED | `1.000000` | `0.054440` |
| Han-only Avg NED | `0.209245` | `0.037348` |
| Digit-only Avg NED | `0.369451` | `0.178630` |
| replacement / LaTeX-like / extra Latin / long prediction | `16 / 105 / 321 / 34` | `0 / 9 / 1 / 1` |

## 多角度统计

| 公开主维度 | 入口 |
|---|---|
| 难度 简单 / 复杂 / 困难 | `tables/by_difficulty.csv` |
| 输入粒度 line / region / page | `tables/by_sample_type.csv` |
| 真实场景 old_print / new_print / screen / handwriting / photo | `tables/by_scene.csv` |
| 风险输出样本 | `tables/risk_rows.csv` |
| 最差 50 条 | `tables/worst_50.csv` |

其他诊断和追溯表保留在 `tables/` 中，不作为公开主图展示。

## 核心拆分

### 按难度

| 分组 | rows | Avg NED | WS NED | Exact | Yi-only NED | Han-only NED | Digit-only NED | 风险 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| easy 简单 | 83 | 0.031944 | 0.030882 | 67/83 (80.7%) | 0.029882 |  | 0.200000 | 0/0/0/0 |
| medium 复杂 | 467 | 0.036846 | 0.035866 | 366/467 (78.4%) | 0.042100 | 0.019408 | 0.111111 | 0/1/0/0 |
| hard 困难 | 208 | 0.095156 | 0.095817 | 12/208 (5.8%) | 0.092128 | 0.069934 | 0.196136 | 0/8/1/1 |

### 按输入粒度

| 分组 | rows | Avg NED | WS NED | Exact | Yi-only NED | Han-only NED | Digit-only NED | 风险 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| line 单行图 | 470 | 0.025444 | 0.024531 | 386/470 (82.1%) | 0.029608 | 0.012273 | 0.151515 | 0/1/0/0 |
| region 区域图 | 119 | 0.082315 | 0.084714 | 57/119 (47.9%) | 0.077560 | 0.085192 | 0.200000 | 0/0/0/0 |
| page 整页图 | 169 | 0.105898 | 0.104330 | 2/169 (1.2%) | 0.107534 | 0.062188 | 0.189705 | 0/8/1/1 |

### 按真实场景

| 分组 | rows | Avg NED | WS NED | Exact | Yi-only NED | Han-only NED | Digit-only NED | 风险 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 旧印刷/扫描资料 | 507 | 0.034428 | 0.034182 | 356/507 (70.2%) | 0.039019 | 0.024413 | 0.275397 | 0/1/1/0 |
| 新印刷/PDF | 100 | 0.053475 | 0.049492 | 71/100 (71.0%) | 0.061976 | 0.023500 | 0.085106 | 0/0/0/0 |
| 屏幕拍照/页面上传图 | 87 | 0.117566 | 0.113988 | 1/87 (1.1%) | 0.084740 | 0.075399 | 0.126430 | 0/8/0/1 |
| 手写拍照 | 53 | 0.122555 | 0.130483 | 7/53 (13.2%) | 0.146028 | 1.000000 | 1.000000 | 0/0/0/0 |
| 真实场景照片 | 11 | 0.011364 | 0.011858 | 10/11 (90.9%) | 0.014354 | 0.000000 |  | 0/0/0/0 |

## 指标怎么读

| 指标 | 中文解释 |
|---|---|
| Avg NED | 平均归一化编辑距离。预测文本改成人工标注需要多少编辑量，再按文本长度归一 |
| WS Avg NED | 忽略空白差异后的 Avg NED |
| NFKC+WS Avg NED | 做 Unicode 兼容规范化并忽略空白差异后的 Avg NED |
| Yi-only / Han-only / Digit-only Avg NED | 分别只抽取彝文、汉字、数字后计算 NED |
| replacement / LaTeX-like / extra Latin / long prediction | 输出风险检查项 |

## 结果图表

### 总体 NED

![NED Overview](charts/ned_overview.svg)

### 不同难度

![Avg NED by Difficulty](charts/ned_by_difficulty.svg)

### 不同输入粒度

![Avg NED by Input Granularity](charts/ned_by_sample_type.svg)

### 不同真实场景

![Avg NED by Scene](charts/ned_by_scene.svg)

### 输出风险

![Safety Failure Counts](charts/safety_failures.svg)

## 文件结构

```text
summary.md
summary.json
raw/
  submission_model_result.jsonl
  submission_model_predictions.jsonl
tables/
  by_difficulty.csv
  by_sample_type.csv
  by_scene.csv
  by_script_mix.csv
  by_has_digit.csv
  by_text_length.csv
  by_gt_lines.csv
  all_scored_rows.csv
  worst_50.csv
  risk_rows.csv
charts/
  ned_overview.svg
  ned_by_difficulty.svg
  ned_by_sample_type.svg
  ned_by_scene.svg
  safety_failures.svg
```
