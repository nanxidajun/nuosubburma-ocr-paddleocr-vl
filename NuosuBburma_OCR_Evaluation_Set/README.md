# NuosuBburma OCR Evaluation Set

本目录是 `NuosuBburma OCR` 的评估集入口说明。

完整评估集不直接放在 GitHub，托管在 Hugging Face Dataset：

```text
https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set
```

## 数据内容

HF Dataset 当前包含复跑评估需要的最小文件：

| 文件/目录 | 说明 |
|---|---|
| `README.md` | 数据集说明 |
| `annotations.jsonl` | 主评估标注，603 条样本 |
| `images/` | 全部被引用图片，603 张 |

本仓库只保留评估集入口、评估脚本和提交模型重跑结果，不重复提交完整图片数据。

## 下载

复跑评估时，可以下载到本地 `datasets/` 目录：

```bash
hf download nanxidajun/NuosuBburma-OCR-Evaluation-Set \
  --repo-type dataset \
  --local-dir datasets/NuosuBburma_OCR_Evaluation_Set
```

`datasets/` 是本地下载目录，已在 `.gitignore` 中忽略，不作为 GitHub 仓库内容提交。

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
