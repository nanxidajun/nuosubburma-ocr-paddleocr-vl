# 最终评估结果

本目录作为公开评估结果入口。当前统一口径为最终 `758` 条真实来源样本，对比对象为：

| 模型 | 状态 | 说明 |
|---|---|---|
| `PaddleOCR-VL-1.6` 未微调基座 | 已完成 | 使用最终 `758` 条评估集，作为未微调对照 |
| NuosuBburma OCR LoRA 微调模型 | 结果未出 | 将使用同一评估集、同一评估脚本和同一指标回填 |

## 当前结果

归一化编辑距离（NED）越低越好。

| 指标 | 未微调基座 | LoRA 微调后 |
|---|---:|---:|
| 评估样本 | `758` | 待回填 |
| Avg NED | `0.726733` | 待回填 |
| WS Avg NED | `0.7196` | 待回填 |
| NFKC+WS Avg NED | `0.706794` | 待回填 |
| Yi-only Avg NED | `1.000000` | 待回填 |
| Han-only Avg NED | `0.209245` | 待回填 |
| Digit-only Avg NED | `0.369451` | 待回填 |
| replacement / LaTeX-like / extra Latin / long prediction | `16 / 105 / 321 / 34` | 待回填 |

## 指标怎么读

| 指标 | 中文解释 |
|---|---|
| Avg NED | 平均归一化编辑距离。预测文本改成人工标注需要多少编辑量，再按文本长度归一 |
| WS Avg NED | 忽略空白差异后的 Avg NED |
| NFKC+WS Avg NED | 做 Unicode 兼容规范化并忽略空白差异后的 Avg NED |
| Yi-only Avg NED | 只抽取彝文字符后计算 NED |
| Han-only Avg NED | 只抽取汉字后计算 NED |
| Digit-only Avg NED | 只抽取数字后计算 NED |
| replacement | 预测中出现替换符 |
| LaTeX-like | 脚注、圈号或符号被模型输出成公式样文本 |
| extra Latin | 人工标注无拉丁字母但预测多出拉丁字母 |
| long prediction | 预测明显长于标注，属于异常长输出风险 |

## 结果图表

### 总体 NED

![NED Overview](charts/ned_overview.svg)

### 不同输入粒度

![Avg NED by Input Granularity](charts/ned_by_sample_type.svg)

### 不同真实场景

![Avg NED by Scene](charts/ned_by_scene.svg)

### 不同来源

![Avg NED by Source](charts/ned_by_source.svg)

### 输出风险

![Safety Failure Counts](charts/safety_failures.svg)

## 文件结构

```text
summary.md
summary.json
charts/
  ned_overview.svg
  ned_by_sample_type.svg
  ned_by_source.svg
  ned_by_scene.svg
  safety_failures.svg
```

LoRA 微调模型在最终评估集上的逐条输出和分组表将在结果完成后回填。
