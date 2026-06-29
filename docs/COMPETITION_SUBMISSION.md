# PaddleOCR 全球衍生模型挑战赛提交说明

`NuosuBburma OCR` 是面向 **PaddleOCR 全球衍生模型挑战赛** 的规范彝文识别模型，基于 `PaddleOCR-VL-1.6 (0.9B)` + LoRA 构建。本项目任务是 **真实场景中的规范彝文识别**。

它要解决的问题很具体：许多规范彝文资料仍以书籍、扫描件和手写稿存在，难以搜索、复制、校对和进入语料建设。

本次提交提供真实评估集、训练配置、模型结果、页面切割流程和复现入口，方便评委按官方评分表核验。

## 当前口径说明

本文档按 `2026-06-29` 最新整合评估集口径组织。最新数据集已经扩展并清理到 `758` 条真实样本；模型最终结果仍需在该口径上正式 rerun。历史 `603` 条 OCR 主指标结果保留为已经完成的可复查 LoRA 指标，不与最新数据集规模混写。

| 口径 | 状态 | 用途 |
|---|---|---|
| 最新整合评估集 | `758` 条真实样本，`line 470` / `region 119` / `page 169`，空 GT `0`，缺图 `0`，合成标记 `0` | 下一次正式评估与提交主口径 |
| 原始模型 baseline | `PaddleOCR-VL-1.6` 已完成 `758` 条 aligned raw prediction，错误行 `0` | 等最终 GT 冻结后计算 NED、exact 和输出风险指标 |
| 历史 LoRA 指标 | `603` 条 OCR 主指标，Avg NED `0.036068` | 已完成结果，用于说明当前模型能力和历史分支选择 |

## 0. 评委快速核验

本节直接对应赛事评审最关心的六件事：数据是否真实，场景是否稀缺，任务是否超过单行识别，训练数据是否有构建方法，模型选择是否有实验依据，以及开源复现是否方便。

| 核验问题 | 本项目回答 | 入口 |
|---|---|---|
| 评估集是否真实 | 是。最新整合评估集为 `758` 条真实来源样本，含 `169` 个 page 样本、`119` 个 region 样本、`98` 个真实照片/屏幕拍照样本；空 GT、缺图、重复 ID 和合成样本标记均为 `0`。 | [EVALUATION_DATASET.md](EVALUATION_DATASET.md)，[EVALUATION_QUALITY_REPORT.md](EVALUATION_QUALITY_REPORT.md)，[Hugging Face 评估集](https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set) |
| 模型结果是否已经跑完 | 历史 `603` 条 LoRA 指标已跑完：Avg NED `0.036068`，Yi-only Avg NED `0.038309`，Han-only Avg NED `0.022447`。最新 `758` 条口径已完成原始模型 raw prediction，最终同口径 NED 表等待正式 rerun。 | [evaluation/summary.md](../evaluation/summary.md)，[evaluation/raw/submission_model_result.jsonl](../evaluation/raw/submission_model_result.jsonl) |
| 是否只是单行识别 | 否。仓库能从整页、PDF、照片开始，使用 Paddle DocLayout 做页面切割，记录阅读顺序，再识别切出的文本区域，最后合并页面文本并导出结构化页面结果；复杂整页仍建议人工复核。 | [页面切割流程](../page_processing/README.md)，[演示](../demo/README.md)，[后处理工具](../postprocess/README.md) |
| 训练数据是否科学 | 是。训练包 `v5_16_synth_capped_rerender_official` 共 `21504` 行；真实材料、训练侧合成样本和视觉变化样本分开记录；缺图、空标签、替换符、反斜杠和公式化片段标签均为 `0`。 | [TRAINING_DATA_CONSTRUCTION_REPORT.md](TRAINING_DATA_CONSTRUCTION_REPORT.md)，[configs/train_data_manifest_v5_16.json](../configs/train_data_manifest_v5_16.json) |
| 模型选择是否有实验依据 | 有。多个训练分支使用同一组开发诊断集比较；对照实验显示，继续追加长尾格式样本会带来公式化片段和异常长输出风险回升；原始 `PaddleOCR-VL-1.6` baseline raw prediction 已完成。 | [MODEL_AND_TRAINING.md](MODEL_AND_TRAINING.md)，[evaluation](../evaluation/) |
| 是否可复现 | 提供 Hugging Face 模型、Hugging Face 评估集、线上演示入口、本地演示、训练配置、评估脚本和逐样本输出；GPU 不足时以本地演示和脚本为准。 | [model](../model/README.md)，[演示](../demo/README.md)，[scripts](../scripts/README.md) |

这张表只作为评审入口。详细证据见各专题文档。

## 1. 官方评分点映射

官方评分同时考察评估集、场景、任务、训练数据、微调策略和开源贡献。下表按六个维度列出证据和边界。

| 官方维度 | 本项目最强证据 | 当前边界 |
|---|---|---|
| 评估集质量 | 最新整合评估集 `758` 条真实样本；`line 470` / `region 119` / `page 169`；旧印刷 `507`、新印刷 `100`、手写 `53`、真实照片 `11`、屏幕拍照 `87`；`easy 83` / `medium 467` / `hard 208`；空 GT、缺图、合成标记均为 `0`。 | 最新 `758` 条最终模型指标等待正式 rerun；历史 `603` 条结果保留为已跑模型指标。 |
| 场景稀缺性 | 规范彝文公开文字识别数据少；项目覆盖旧书、教材、工具书、彝汉混排、拉丁注音、手写、实拍照片和屏幕拍照资料。 | 应用目标限定在检索、校对、注音和语料整理。 |
| 任务复杂度 | 整页、PDF 和照片先经 Paddle DocLayout 切成文本区域，再识别、恢复阅读顺序、合并页面文本，并导出标题、正文、页码、块位置和彝汉对照行；《雪族子史篇》65 页切割后 OCR Avg NED `0.0504`，直接整页 OCR `0.5448`。 | 不声称已经稳定解决所有复杂整页；复杂整页仍建议人工复核。 |
| 训练数据构建科学性 | `21504` 行训练包；真实材料、训练侧合成样本和视觉变化样本分开记录；拉丁注音、脚注和多行区域设上限；缺图、空标签、替换符、反斜杠和公式化片段标签均为 `0`。 | GitHub 保留配置、训练包清单、脚本和统计；权重与评估集分别放在 Hugging Face。 |
| 微调策略与创新 | 三阶段 LoRA 微调；先证明单书真实行图可学，再补低频字符和旧印刷视觉变化，最后用固定开发诊断集比较分支，不把诊断集写回训练；原始模型 baseline raw prediction 已完成。 | 不改 PaddleOCR-VL 结构，重点是训练数据构建、隔离检查和输出风险检查。 |
| 技术文档与开源贡献 | GitHub 提供 README、提交说明、评估集说明、质检报告、训练数据构建、模型训练、页面切割、后处理、线上演示、本地演示、评估脚本和逐样本结果。 | 线上演示需要 GPU；本地演示和脚本是主要复现入口。 |

表中的“当前边界”说明哪些能力已经稳定，哪些仍需复核。

## 2. 提交物边界

| 上传位置 | 内容 | 说明 |
|---|---|---|
| GitHub 仓库 | README、文档、配置、脚本、演示、页面切割、后处理、评估摘要和逐样本输出 | 作为赛事评审入口和复现入口，不重复上传完整大图数据和模型权重 |
| Hugging Face 模型 | `NuosuBburma-OCR` 模型权重和模型卡 | [Hugging Face 模型](https://huggingface.co/nanxidajun/NuosuBburma-OCR) |
| Hugging Face 评估集 | `NuosuBburma-OCR-Evaluation-Set` 图片、标注和统计 | [Hugging Face 评估集](https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set) |

## 3. 结果统计

最终提交模型来自第三阶段调优中的一个稳定分支。该分支在开发诊断集上同时降低整体编辑距离、彝文编辑距离和汉字编辑距离，并保持替换符和异常长输出为 `0`。

当前提交模型已在历史 `603` 条 OCR 主指标样本上完成评估；原始 `PaddleOCR-VL-1.6` 已在最新 `758` 条整合评估集上完成 aligned raw prediction。下一步是在最终 GT 口径上同时计算原始模型和 LoRA 模型指标。

| 指标 | PaddleOCR-VL-1.6 原始模型 | 当前 LoRA 模型 |
|---|---:|---:|
| 最新 `758` 条 raw prediction | 已完成，错误行 `0` | 等待正式 rerun |
| 最新 `758` 条 Avg NED | 待最终计算 | 待正式 rerun |
| 历史 `603` 条样本数 | 未公开同口径指标 | 603 |
| 历史 `603` 条 Avg NED | 未公开同口径指标 | 0.036068 |
| 历史 `603` 条完全匹配率 | 未公开同口径指标 | 67.99% |
| 历史 `603` 条 NFKC+WS Avg NED | 未公开同口径指标 | 0.033964 |
| 历史 `603` 条 Yi-only Avg NED | 未公开同口径指标 | 0.038309 |
| 历史 `603` 条 Han-only Avg NED | 未公开同口径指标 | 0.022447 |
| 历史 `603` 条 Digit-only Avg NED | 未公开同口径指标 | 0.139918 |
| 历史 `603` 条 replacement / LaTeX / extra Latin / long_pred | 未公开同口径指标 | 0 / 2 / 0 / 0 |

单行图输入最稳定。区域图和整页图用于暴露漏行、阅读顺序和换行边界问题。手写拍照单独报告，不和印刷体混成一个结论。

## 4. 真实评估集

最新整合评估集为 `758` 条真实来源样本，全部计入评估集口径，不拆成展示样本和评分样本两套。历史 `603` 条 OCR 主指标结果保留为已完成模型结果；最新 `758` 条等待最终同口径 rerun。

| 维度 | 分布 |
|---|---|
| 输入粒度 | 单行图 `470`，区域图 `119`，整页图 `169` |
| 真实场景 | 新印刷 `100`，旧印刷 `507`，手写拍照 `53`，真实照片 `11`，屏幕拍照 `87` |
| 文字混合 | 纯彝文 `275`，彝汉混排 `443`，彝汉拉丁注音 `24`，纯汉字 `14`，其他 `2` |
| 数字样本 | 含数字 `179`，不含数字 `579` |
| 难度 | 简单 `83`，中等 `467`，困难 `208` |
| 质量检查 | 空 GT `0`，缺图 `0`，重复 ID `0`，合成样本标记 `0` |

主要来源如下：

| 来源 | 样本数 | 作用 |
|---|---:|---|
| 凉山彝文资料选译第3集 | 234 | 旧印刷资料和新增候选，覆盖旧书噪声、line、region 和 page |
| 越西彝族民间歌谣 彝文版 | 82 | 新增真实旧印刷行图，增加来源多样性 |
| 凉山彝文资料选译第2集 | 76 | 换书、换排版的旧印刷评估 |
| 勒俄玛牧导读教程 | 66 | 导读类资料和屏幕拍照页，覆盖彝汉混排与页面上传噪声 |
| 雪族 子史篇 | 65 | 整页切割、OCR、拼合、结构化输出和审计链路 |
| 手写拍照 | 53 | 手写拍照泛化分组 |
| 《勒俄特依》译注 | 46 | 译注资料，覆盖注释边界和混排 |
| 根与花 | 43 | 新印刷正文，提供清晰行图基准 |
| 彝文检字本 / 凉山彝语语法 | 62 | 工具书结构、检字、语法资料、汉字、数字和编号 |
| 真实照片 / 标牌 / 屏幕文本 | 22 | 实拍、屏幕、页面上传和真实场景噪声 |

雪族 `65` 页已计入最新 `758` 条总评估集，用于证明整页切割、OCR、拼合、结构化输出和审计链路能跑通。页面切割对照与 OCR 指标分表报告，口径不同，不合并成一个平均分。

## 5. 任务复杂度：真实场景中的规范彝文识别

规范彝文识别不能只看单行识别。旧书或页面照片要变成可用文本，还需要页面切割、阅读顺序、混排识别、页面文本合并和人工校对。

```text
整页 / PDF / 手机照片 / 屏幕图
-> Paddle DocLayout 页面切割
-> 阅读顺序索引
-> 切出文本区域后识别
-> 彝文、汉字、数字、标点、可见拉丁注音保真输出
-> 页面文本合并
-> 结构化页面输出
-> 替换符、公式化片段、多余拉丁字母、异常长输出、空页和重复页检查
-> 按需注音和人工校对
```

这条链路对应多个子任务：

| 子任务 | 仓库实现 | 评分意义 |
|---|---|---|
| 页面/PDF/照片输入 | [页面切割入口脚本](../page_processing/run.py) | 让任务覆盖真实文献和用户上传图，而不是只测裁好的单行 |
| 页面切割 | [页面切割流程](../page_processing/README.md) | 使用 Paddle DocLayout 生成文本区域，降低复杂整页直接识别的漏行、错行和边界风险 |
| 阅读顺序恢复 | 页面编号、裁切编号、阅读顺序、位置框和页面元数据 | 把识别结果合并为可校对页面文本 |
| 彝文/彝汉混排识别 | 固定提示词 `<image>OCR:` | 检查低资源文字和常见汉字解释、数字、标点的混排稳定性 |
| 页面文本合并 | [assemble_pages.py](../page_processing/assemble_pages.py) | 按视觉行合并书页、教材和旧文献文本，生成可校对页面文本 |
| 结构化页面输出 | [structure_pages.py](../page_processing/structure_pages.py) | 导出标题、正文、页码、块角色、位置框、彝文原文行和彝汉对照行，方便复核 |
| 输出风险检查 | [analyze_submission_eval.py](../scripts/analyze_submission_eval.py)、整页检查 | 报告替换符、公式化片段、多余拉丁字母、异常长输出、空页和重复页等风险；检查信号不自动改写正文 |
| 注音 | [add_nuosu_pronunciation.py](../postprocess/add_nuosu_pronunciation.py) | 在页面文本完成后按需添加读音字段，供检字和人工校对使用 |
| 整页演示 | [run_page_workflow.py](../demo/run_page_workflow.py) | 证明普通页面样例能按页面切割、识别、页面文本合并、结构化输出、异常检查和可选注音顺序跑通 |

在《雪族子史篇》65 页整页样本上，页面切割后识别的平均归一化编辑距离为 `0.0504`，直接整页识别为 `0.5448`。该对比说明页面切割能降低复杂整页中的阅读顺序错位、彝汉混排拆散和非文字图案误识别。

这组整页评估已经端到端跑通：`529` 个 DocLayout 版面块，`2501` 个 OCR 单元，`2501` 条 OCR 结果全部正常，拼合得到 `65` 页页面文本；替换符、空页和重复页均为 `0`。结构化输出得到 `65` 个页面结构，包含 `1123` 行彝文原文和 `1060` 组彝汉对照行。

当前边界：复杂整页、手写段落、多栏、脚注/注音密集区域仍建议人工复核。模型可以输入整页图，但稳定交付优先使用可检查的文本区域。

## 6. 训练数据构建

训练集遵循“真实材料定边界、合成样本补长尾、视觉变化样本补图像状态”的原则。

低资源文字训练不能只靠真实数据，因为规范彝文字符、字体变化、旧印刷状态和混排格式覆盖不足；也不能靠大量无约束合成，因为模型容易学出多余拉丁字母、公式化片段、替换符和异常长输出。

训练数据不是越多越好。每类新增数据都有用途和上限，训练包记录样本来源、外观增强数量、高风险通道上限和训练包质检结果。

最终训练包为 `v5_16_synth_capped_rerender_official`：

| 项目 | 数量或设置 |
|---|---:|
| train rows after clean | 21504 |
| base rows | 12435 |
| 新增外观增强样本 | 9069 |
| 保持不变的真实样本 | 1861 |
| 原始合成样本 | 10574 |
| 普通外观增强样本 | 8360 |
| 脚注外观增强样本 | 60 |
| 多行区域外观增强样本 | 649 |
| 拉丁注音外观增强样本 | 0 |
| 缺图 / 空标签 / 替换符标签 | 0 / 0 / 0 |
| 公式化片段标签 / 反斜杠标签 | 0 / 0 |

最终训练包保留一批文本不变、图像状态变化的样本：文字标签不变，只改变字体、清晰度和旧印刷状态。拉丁注音、脚注、多行区域样本设置上限，避免某类格式被模型学成默认输出习惯。

隔离检查单独列出，不作为训练包质量指标：

| 检查项 | 结果 |
|---|---:|
| 评估图片路径命中训练包 | 0 |
| 评估图片文件名命中训练包 | 0 |
| 评估样本编号命中训练包 | 0 |
| 删除的完全重合标签行 | 2 |
| 保留的完全重合标签行 | 7 |

## 7. 模型策略与分支实验

基础设置保持稳定：PaddleOCR-VL-1.6 0.9B、LoRA 秩 `8`、训练 `2` 轮、学习率 `5.0e-4`、单卡 4090D。分支比较主要改变数据分布，不把模型结构和数据策略混在一起。

三阶段调优策略如下：第一阶段验证 PaddleOCR-VL + LoRA 能否学习规范彝文；第二阶段用合成样本补低频字符和混排覆盖，并补充字体、清晰度和旧印刷状态的视觉变化；第三阶段只用固定开发诊断集比较分支输出，不把开发诊断集或最终评估集写回训练包。

| 分支 | 训练数据动作 | 开发诊断集结果 | 判断 |
|---|---|---|---|
| 早期稳定分支 | 稳定数据形状，补多行区域与纯彝文稳定样本 | 整体 `0.0634`，彝文 `0.0512`，汉字 `0.0265`，异常长输出 `0` | 早期稳定基线 |
| 版式与注音再平衡分支 | 恢复字典注音、单行彝汉混排、纯彝文字符覆盖 | 整体 `0.0505`，彝文 `0.0473`，汉字 `0.0261`，异常长输出 `0` | 总分继续下降，但脚注风险仍高 |
| 最终提交分支 | 文本不变、图像状态变化样本 `9069` 行，拉丁注音不放大，脚注/多行区域设上限 | 整体 `0.0342`，彝文 `0.0372`，汉字 `0.0225`，公式化片段 `2`，异常长输出 `0` | 最终提交模型 |
| 长尾格式对照分支 | 追加 `350` 行格式长尾约束样本 | 整体 `0.0429`，公式化片段回到 `10`，异常长输出 `1` | 风险回升，保留为对照 |

实验结论：继续加数据不一定变好，关键是控制数据分布。提交模型在开发诊断集上同时降低整体、彝文、汉字三组编辑距离，并把替换符和异常长输出保持为 `0`。

## 8. 开源与复现

核心入口：

| 任务 | 入口 |
|---|---|
| 项目概览 | [README.md](../README.md) |
| 下载模型 | [model/README.md](../model/README.md)，[Hugging Face 模型](https://huggingface.co/nanxidajun/NuosuBburma-OCR) |
| 下载评估集 | [NuosuBburma_OCR_Evaluation_Set/README.md](../NuosuBburma_OCR_Evaluation_Set/README.md)，[Hugging Face 评估集](https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set) |
| 单图 / 整页演示 | [demo/README.md](../demo/README.md) |
| 运行评估 | [scripts/README.md](../scripts/README.md) |
| 页面切割 | [页面切割流程](../page_processing/README.md) |
| 识别后处理 | [postprocess/README.md](../postprocess/README.md) |
| 评估结果 | [evaluation/README.md](../evaluation/README.md) |

下载模型：

```bash
hf download nanxidajun/NuosuBburma-OCR \
  --repo-type model \
  --local-dir models/NuosuBburma-OCR
```

下载评估集：

```bash
hf download nanxidajun/NuosuBburma-OCR-Evaluation-Set \
  --repo-type dataset \
  --local-dir datasets/NuosuBburma_OCR_Evaluation_Set
```

运行单图演示：

```bash
python demo/infer_single_image.py \
  --model models/NuosuBburma-OCR \
  --image demo/sample_images/mixed_line.png
```

运行整页演示：

```bash
python demo/run_page_workflow.py \
  --input demo/sample_images/screen_page.jpg \
  --model models/NuosuBburma-OCR \
  --output-root outputs/demo_page_workflow \
  --with-pronunciation
```

运行评估：

```bash
scripts/run_eval.sh \
  models/NuosuBburma-OCR \
  datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  outputs/NuosuBburma_OCR_Evaluation_Set/result.jsonl

python scripts/analyze_submission_eval.py \
  --annotations datasets/NuosuBburma_OCR_Evaluation_Set/annotations.jsonl \
  --result outputs/NuosuBburma_OCR_Evaluation_Set/result.jsonl \
  --out-dir outputs/NuosuBburma_OCR_Evaluation_Set/analysis
```

## 9. 真实性边界

| 问题 | 说明 |
|---|---|
| 评估集是否使用合成样本 | 否。合成数据只用于训练覆盖，不用于证明评估结果 |
| 标注是否直接使用模型输出 | 否。模型输出只作为预标注草稿，最终需要人工核对 |
| 评估集是否作为训练数据 | 否。训练侧保留隔离检查；路径、文件名、样本编号命中均为 `0` |
| 整页识别是否已经稳定 | 否。项目提供页面切割、阅读顺序和整页诊断，但复杂整页仍建议人工复核 |
| 手写识别是否已经稳定 | 否。手写拍照已有泛化信号，但明显弱于印刷体，单独报告 |
| 是否提供线上演示 | 是，提供 Hugging Face Space 作为交互入口；模型推理需要 GPU，未配置 GPU 时以本地单图演示、整页演示与脚本为主入口 |

## 10. 提交总结

本项目的重点是把规范彝文识别放到真实资料中评估和复现。

可核验内容有四项：`758` 条真实最新评估集、`21504` 行训练包、多组训练分支实验，以及整页/PDF/照片到文本区域识别、页面文本合并、结构化输出、异常检查和按需注音的流程。

后续可以继续扩大真实整页和手写样本，并补充更稳定的在线体验。
