# 文档目录

本目录存放项目提交需要的中文说明文档。建议按以下顺序阅读：

| 顺序 | 文档 | 作用 |
|---:|---|---|
| 1 | [提交材料总览](COMPETITION_SUBMISSION.md) | 快速查看提交材料、复现入口和核验说明 |
| 2 | [项目背景与任务定义](PROJECT_BACKGROUND.md) | 说明为什么选择规范彝文 OCR、任务稀缺性和任务复杂度 |
| 3 | [评估集说明](EVALUATION_DATASET.md) | 说明真实评估集的来源、分布、构建流程、指标和结果解读 |
| 4 | [评估集质检报告](EVALUATION_QUALITY_REPORT.md) | 对齐评分表说明评估集真实性、标注检查、多样性和难度分布 |
| 5 | [训练数据构建报告](TRAINING_DATA_CONSTRUCTION_REPORT.md) | 对齐评分表说明训练数据来源、标注、质控和统计 |
| 6 | [模型与训练说明](MODEL_AND_TRAINING.md) | 说明 LoRA 微调策略、分支选择和最终模型结果 |
| 7 | [书页切图流程](CROP_PIPELINE.md) | 说明整页扫描件如何切成可复核、可进入 OCR 的行图或区域图 |

相关入口：

- 模型入口：[`../model/README.md`](../model/README.md)
- 评估集入口：[`../NuosuBburma_OCR_Evaluation_Set/README.md`](../NuosuBburma_OCR_Evaluation_Set/README.md)
- 评估集说明：[`EVALUATION_DATASET.md`](EVALUATION_DATASET.md)
- 评估集质检报告：[`EVALUATION_QUALITY_REPORT.md`](EVALUATION_QUALITY_REPORT.md)
- 训练数据构建报告：[`TRAINING_DATA_CONSTRUCTION_REPORT.md`](TRAINING_DATA_CONSTRUCTION_REPORT.md)
- 评估结果：[`../evaluation/`](../evaluation/)
- 切图 Pipeline：[`../crop_pipeline/README.md`](../crop_pipeline/README.md)
- 切图详细说明：[`CROP_PIPELINE.md`](CROP_PIPELINE.md)
- 本地 Demo：[`../demo/README.md`](../demo/README.md)
