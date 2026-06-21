# NuosuBburma OCR Evaluation Set

本目录是 GitHub 仓库中的评估集入口说明，不直接托管完整图片数据。

完整评估集托管在 Hugging Face Dataset：

```text
https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set
```

## 数据集内容

HF Dataset 当前只保留复跑评估所需的最小文件：

| 文件/目录 | 说明 |
|---|---|
| `README.md` | 数据集说明 |
| `annotations.jsonl` | 主评估标注，603 条样本 |
| `images/` | 全部被引用图片，603 张 |

GitHub 不重复上传完整数据集，也不在本目录设置额外子集。复跑评估时，直接从 HF Dataset 下载完整数据到本目录即可。

## 下载方式

```bash
hf download nanxidajun/NuosuBburma-OCR-Evaluation-Set \
  --repo-type dataset \
  --local-dir datasets/NuosuBburma_OCR_Evaluation_Set
```

## 任务定义

输入：包含规范彝文或规范彝文混排内容的图像。

输出：图片中可见文本的 Unicode 转写，尽量保留混排关系和基本标点。

推荐提示词：

```text
<image>OCR:
```

## 数据边界

- 本数据集用于评估，不是训练集。
- 样本来自真实材料，不使用合成样本作为主评分材料。
- 书籍样本来源于扫描件裁剪，原始出版物版权归原出版社和权利人所有。
- 使用时请同时尊重原始材料版权与本项目的数据说明。
