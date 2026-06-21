# 模型与训练

本文档记录 `NuosuBburma OCR` 的模型路线、训练配置和模型选择依据。长篇实验复盘不放在这里，这里只保留提交和复现需要的核心信息。

## 基础方案

| 项目 | 内容 |
|---|---|
| 基座模型 | PaddleOCR-VL-1.6 (0.9B) |
| 微调方式 | LoRA |
| 任务提示词 | `<image>OCR:` |
| 主任务 | 规范彝文 OCR |
| 混排能力 | 支持彝汉混排 |
| 训练硬件 | NVIDIA RTX 4090D |
| 部署状态 | 暂未做端侧/移动端部署 |

## 关键训练参数

| 参数 | 值 |
|---|---:|
| max sequence length | 16384 |
| LoRA rank | 8 |
| per-device batch size | 4 |
| gradient accumulation | 16 |
| epochs | 2 |
| scheduler | cosine |
| learning rate | 5.0e-4 |
| minimum learning rate | 5.0e-5 |
| precision | bf16 |
| sharding | stage2 |

配置文件：

- `configs/paddleocr-vl_lora_16k_nuosubburma_v5_16.yaml`
- `configs/paddleocr-vl_lora_export_nuosubburma_v5_16.yaml`
- `configs/train_data_manifest_v5_16.json`

## 训练路线

训练不是一次性混入大量数据，而是从简单到复杂逐步扩展。

### 第一阶段：单书可行性

起点：

- 使用《勒俄特依》中的真实裁切行。
- 版式相对简单，主要是短句诗歌。
- 目标是确认 PaddleOCR-VL LoRA 微调能否学到彝文字形和基本输出格式。

判断：

- 模型可以学习基本彝文字形。
- 仅靠单书数据不足以覆盖字体、混排、老印刷噪声、多行区域和手写。

### 第二阶段：真实数据 + 合成覆盖 + 监控集

起点：

- 保留《勒俄特依》真实行。
- 增加低频字、形近字、标点边界、老印刷退化、彝汉混排和版式变化的合成数据。
- 使用监控集观察输出空间漂移、LaTeX 化、Latin/ASCII 干扰和超长输出。

判断：

- 合成数据有用，但必须同时控制视觉扩展和输出空间风险。
- 监控集只用于诊断，不作为主评分。

### 第三阶段：复核评估集与模型选择

起点：

- 使用人工复核后的 clean603 评估集。
- 选择模型时同时看 NED、彝文识别、汉字识别、输出漂移、超长输出和混排行为。

判断：

- 模型选择不能只按单一指标选择。
- 输出稳定性和错误类型必须进入选择标准。

## 提交模型配置

```text
NuosuBburma OCR (PaddleOCR-VL LoRA)
```

训练快照：

| 项目 | 值 |
|---|---:|
| 训练行数 | 21504 |
| epochs | 2 |
| train loss | 0.191 |
| train runtime | 1:08:53.89 |

clean603 评估：

| 指标 | 值 |
|---|---:|
| 样本数 | 603 |
| Avg NED | 0.036068 |
| Exact match | 67.99% |
| Yi-only NED | 0.038309 |
| Yi-only exact | 74.96% |
| Han-only NED | 0.022447 |
| Han-only exact | 93.99% |
| replacement collapse | 0 |
| long prediction failure | 0 |
| LaTeX-like outputs | 2 |

## 数据构建原则

- 真实数据和合成数据保持可区分。
- 不把评估集答案作为训练目标。
- 优先增加视觉多样性，而不是盲目增加文本标签多样性。
- 对 Latin、公式化输出、脚注和 region 类高风险样本设置比例上限。
- 彝文识别、汉字识别和混排行为分开观察。
- 手写和多行 region OCR 作为高难度泛化场景，不把它们当作已经完全解决的能力。

## 已知限制

- 真实手写仍是最弱场景。
- 多行 region/page OCR 应该和单行 OCR 分开解释。
- 端侧部署尚未实现。
- 脚注符号仍有少量 LaTeX 化残留。
