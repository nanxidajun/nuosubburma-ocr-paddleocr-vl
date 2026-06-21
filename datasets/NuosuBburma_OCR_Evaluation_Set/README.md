# NuosuBburma OCR 评估集

这是 `NuosuBburma OCR` 的提交评估集包。

本评估集为真实数据提交评估集，全部样本计入主评分。样本来自真实书籍扫描件裁剪、规范手写、屏幕页面和真实照片。合成训练样本不进入本评估集。样本数见 `dataset_summary.json`。

书籍样本来源于扫描件。项目从扫描件中裁取文字区域，用于规范彝文 OCR 评估与模型验证。原始出版物版权归原出版社和权利人所有。

## 文件

| 文件/目录 | 说明 |
|---|---|
| `annotations.jsonl` | 主评估标注，样本数见 `dataset_summary.json` |
| `images/` | 全部被引用图片，文件名与样本 ID 对齐 |
| `samples.csv` | 行级索引，便于人工检查和统计 |
| `source_summary.csv` | 来源书目/来源类型统计 |
| `dataset_summary.json` | 机器可读的数据分布摘要 |
| `digit_summary.csv` | 含数字样本统计 |
| `review.html` | 静态可视化复核页 |
| `excluded_samples.csv` | 从提交评估集中排除的样本记录 |

## 命名规则

样本 ID 使用：

```text
{source_code}_{line|region|page}_{000001}
```

示例：

```text
gen_yu_hua_line_000001
le_e_ma_mu_guide_line_000122
luoe_teyi_region_000277
screen_page_000597
```

## 来源

来源名称、出版社、年份、来源材料和样本数见 `source_summary.csv`。

## 任务

输入：包含规范彝文可见文本的图片。

输出：图片中可见的 Unicode 文本。

提示词：

```text
<image>OCR:
```
