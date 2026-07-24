# 配置

本目录保存两阶段 LoRA 微调使用的训练 / 导出配置。

```text
paddleocr-vl_lora_16k_nuosubburma.yaml     LoRA 训练配置（rank-16，固定基座快照）
paddleocr-vl_lora_export_nuosubburma.yaml  合并 / 导出配置
```

## 环境

- Linux + CUDA GPU；Python 3.11；PaddlePaddle / PaddleFormers 训练栈（PaddleFormers 1.1.1）。
- 训练 GPU：单卡 NVIDIA RTX 4090D；CUDA runtime 11.8，cuDNN 8.9。
- 训练脚本默认 conda 环境名：`paddleocr-vl`。
- 主要依赖：`paddle`、`paddleformers`、`Pillow`、`tqdm`、`python-Levenshtein`。

## 基座

固定基座为 `PaddlePaddle/PaddleOCR-VL-1.6`，锁定 revision `66317acc4c9fc17bd154591ce650735cd2855f3e`（不使用浮动别名）。训练 YAML 已写入该快照路径，`run_train_lora.sh` 也可用 `MODEL_NAME_OR_PATH` 覆盖为本地缓存路径。

## 两阶段训练参数

两阶段共用：LoRA rank 16、bf16、每卡 batch size 4、梯度累积 16（有效 batch size 64）、max sequence length 16384、cosine 调度、seed 23。各阶段差异：

| 项目 | 第一阶段（通用混合文字适配） | 第二阶段（形近字专项继续微调） |
|---|---|---|
| 训练起点 | 固定基座快照 | 第一阶段合并导出模型 |
| Train / Dev | 18,800 / 960 | 23,124 / 960 |
| Epoch | 2 | 1 |
| Optimizer steps | 588 | 362 |
| 学习率 / 最低 | `5e-4` / `5e-5` | `1e-4` / `1e-5` |
| warmup ratio | 0.01 | 0.03 |

本目录 YAML 对应第一阶段基础配置；第二阶段以第一阶段合并导出模型为起点，按上表覆盖 epoch、学习率与 warmup。第二阶段辅助损失与更新范围（视觉侧 + 视觉到文本投影、语言层冻结）见 [模型与训练策略](../docs/MODEL_AND_TRAINING.md)。

训练数据的合成、配额与审计见 [训练数据构建报告](../docs/TRAINING_DATA_CONSTRUCTION_REPORT.md)。
