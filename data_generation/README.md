# 合成训练数据生成器

本目录是训练数据的程序合成生成器，对应 [训练数据构建报告](../docs/TRAINING_DATA_CONSTRUCTION_REPORT.md) 中按 SHA-256 锁定的脚本。合成数据由字符表与版式规则生成，模型学习字符与版式规律，而非记忆具体句子。

## 脚本

| 脚本 | 作用 |
|---|---|
| `build_synth_layout_post_v3.py` | 主合成器：文本与版式采样、锁定字体渲染、图像/标签配对（核心） |
| `build_post_v3_addons.py` | 附加通道：Latin 补充、残墨与真字退化成对样本等 |
| `post_v3_degradation_policy.py` | 视觉退化策略：护栏、操作预算、过重 profile 的强度回调 |
| `assemble_post_v3_dataset.py` | 组装为正式训练包（JSONL `messages/images`），并做去重与一致性检查 |
| `build_shape_context_contrast_v1.py` | 第二阶段形近字 A/B 成对页面构建 |
| `build_shape_pairs_v3.py`、`build_shape_pairs.py` | 形近字对集合（多字体字形相似度聚类 + 彝文语言规律） |
| `confusable_injection.py` | 把形近字按规则注入到目标位置及可控上下文 |

前 5 个是构建报告中按哈希锁定的正式生成器；后 3 个是它们导入的依赖模块。

## 输入

生成器以下列内容为输入，这些不随本目录发布：

- **规范彝文 Unicode 字表**与常用汉字表；
- **锁定字体文件**（四款规范彝文字体及固定 CJK/Latin 字体，字体各自遵循其许可）。

## 复现要点

- 每次正式构建使用独立随机种子；相同种子逐样本复现，并产生一致的图像哈希与清单。
- 退化策略、操作顺序与强度由 `post_v3_degradation_policy.py` 约束，不做无限叠加。
- 详细配额、审计门与统计结果见 [训练数据构建报告](../docs/TRAINING_DATA_CONSTRUCTION_REPORT.md)。

依赖：`numpy`、`Pillow`、`fontTools`。
