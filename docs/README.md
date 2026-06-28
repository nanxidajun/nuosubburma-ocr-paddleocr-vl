# 文档入口

文档按 PaddleOCR 全球衍生模型挑战赛的评分项组织。评审若只看一份文件，建议先看 [COMPETITION_SUBMISSION.md](COMPETITION_SUBMISSION.md)；若要复查证据，再按官方六个维度进入专题文档。

| 评分/核验问题 | 文档 | 内容 |
|---|---|---|
| 总体提交与评分映射 | [COMPETITION_SUBMISSION.md](COMPETITION_SUBMISSION.md) | 评委快速核验、官方评分点映射、结果统计、复现入口和边界说明 |
| 评估集质量 | [EVALUATION_DATASET.md](EVALUATION_DATASET.md) | `603` 条真实主评估集的来源、分布、指标和结果解读 |
| 标注与质检 | [EVALUATION_QUALITY_REPORT.md](EVALUATION_QUALITY_REPORT.md) | 标注流程、质检、去重、删除归档和训练/评估隔离 |
| 训练数据科学性 | [TRAINING_DATA_CONSTRUCTION_REPORT.md](TRAINING_DATA_CONSTRUCTION_REPORT.md) | 训练数据来源、真实/合成边界、受控重渲染、质量控制和 manifest |
| 微调策略与创新 | [MODEL_AND_TRAINING.md](MODEL_AND_TRAINING.md) | 模型设置、训练参数、v5.8-v5.17 分支选择和提交模型结果 |
| 场景稀缺性 | [PROJECT_BACKGROUND.md](PROJECT_BACKGROUND.md) | 规范彝文 OCR 的低资源场景、应用价值和任务边界 |
| 任务复杂度 | [页面切割流程说明](PAGE_PROCESSING.md) | 整页、PDF、页面照片的页面切割、阅读顺序和 OCR 单元识别链路 |

补充复查入口：

| 材料 | 入口 |
|---|---|
| 模型下载与使用边界 | [../model/README.md](../model/README.md) |
| 本地 demo | [../demo/README.md](../demo/README.md) |
| 评估脚本 | [../scripts/README.md](../scripts/README.md) |
| 提交模型评估结果 | [../evaluation/README.md](../evaluation/README.md) |
