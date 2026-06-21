# 配置

本目录保存最终 v5.16 的训练/导出配置快照，以及训练数据 manifest。

```text
paddleocr-vl_lora_16k_nuosubburma_v5_16.yaml
paddleocr-vl_lora_export_nuosubburma_v5_16.yaml
train_data_manifest_v5_16.json
```

主要训练参数：

- max sequence length: 16384
- LoRA rank: 8
- epochs: 2
- learning rate: 5e-4
- minimum learning rate: 5e-5
- batch size: 4
- gradient accumulation: 16
- precision: bf16
