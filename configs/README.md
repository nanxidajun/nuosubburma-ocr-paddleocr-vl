# 配置

本目录保存本次提交使用的训练/导出配置快照，以及训练数据 manifest。

```text
paddleocr-vl_lora_16k_nuosubburma_v5_16.yaml
paddleocr-vl_lora_export_nuosubburma_v5_16.yaml
train_data_manifest_v5_16.json
```

复现环境摘要：

- Linux + CUDA GPU 环境。
- Python 3.11。
- PaddlePaddle / PaddleFormers 训练栈。
- PaddleFormers 版本：1.1.1。
- 训练 GPU：NVIDIA RTX 4090D，单卡训练。
- CUDA runtime：11.8；cuDNN：8.9。
- 训练脚本默认使用 conda 环境名：`paddleocr-vl`。
- 主要 Python 依赖：`paddle`、`paddleformers`、`Pillow`、`tqdm`、`python-Levenshtein`。

主要训练参数：

- max sequence length: 16384
- LoRA rank: 8
- epochs: 2
- learning rate: 5e-4
- minimum learning rate: 5e-5
- batch size: 4
- gradient accumulation: 16
- precision: bf16
