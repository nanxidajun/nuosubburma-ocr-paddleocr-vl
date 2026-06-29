# PaddleOCR 全球衍生模型挑战赛提交说明

`NuosuBburma OCR` 是面向 **PaddleOCR 全球衍生模型挑战赛** 的规范彝文 OCR 衍生模型，基于 `PaddleOCR-VL-1.6 (0.9B)` + LoRA 构建。本项目任务是 **自然场景中的规范彝文 OCR**。

它要解决的问题很具体：许多规范彝文资料仍以书籍、扫描件和手写稿存在，难以搜索、复制、校对和进入语料建设。

本次提交提供真实评估集、训练配置、模型结果、页面切割流程和复现入口，方便评委按官方评分表核验。

## 0. 评委快速核验

本节直接对应赛事评审最关心的六件事：数据是否真实，场景是否稀缺，任务是否超过单行 OCR，训练数据是否有构建方法，模型选择是否有实验依据，以及开源复现是否方便。

| 核验问题 | 本项目回答 | 入口 |
|---|---|---|
| 评估集是否真实 | 是。主评估使用 `603` 条真实来源样本，含 `7` 张实拍/屏幕样本；合成样本不进入主评估。 | [EVALUATION_DATASET.md](EVALUATION_DATASET.md)，[EVALUATION_QUALITY_REPORT.md](EVALUATION_QUALITY_REPORT.md)，[Hugging Face 评估集](https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set) |
| 模型结果是否已经跑完 | 是。提交模型在 `603` 条主评估样本上 Avg NED `0.036068`，Yi-only Avg NED `0.038309`，Han-only Avg NED `0.022447`。 | [evaluation/summary.md](../evaluation/summary.md)，[evaluation/raw/submission_model_result.jsonl](../evaluation/raw/submission_model_result.jsonl) |
| 是否只是单行 OCR | 否。仓库能从整页、PDF、照片开始，使用 PP-DocLayout 做页面切割，记录阅读顺序，再识别 OCR 单元，最后合并页面文本并按需补注音；复杂整页仍建议人工复核。 | [页面切割流程](../page_processing/README.md)，[demo](../demo/README.md)，[后处理工具](../postprocess/README.md) |
| 训练数据是否科学 | 训练包 `v5_16_synth_capped_rerender_official` 共 `21504` 行；训练材料、合成样本和同标签重渲染分开记录；缺图、空标签、替换符、LaTeX-like 标签均为 `0`。 | [TRAINING_DATA_CONSTRUCTION_REPORT.md](TRAINING_DATA_CONSTRUCTION_REPORT.md)，[configs/train_data_manifest_v5_16.json](../configs/train_data_manifest_v5_16.json) |
| 模型选择是否有实验依据 | 有。v5.8、v5.15、v5.16、v5.17 等分支使用同一组开发诊断集比较；提交模型采用 v5.16，v5.17 因 LaTeX 和 long prediction 风险回升未采用。 | [MODEL_AND_TRAINING.md](MODEL_AND_TRAINING.md)，[evaluation](../evaluation/) |
| 是否可复现 | 提供 Hugging Face 模型、Hugging Face 评估集、Space 交互入口、本地 demo、训练配置、评估脚本和逐样本输出；GPU 不足时以本地 demo 与脚本为准。 | [model](../model/README.md)，[demo](../demo/README.md)，[scripts](../scripts/README.md) |

这张表只作为评审入口。详细证据见各专题文档。

## 1. 官方评分点映射

官方评分同时考察评估集、场景、任务、训练数据、微调策略和开源贡献。下表按六个维度列出证据和边界。

| 官方维度 | 本项目最强证据 | 当前边界 |
|---|---|---|
| 评估集质量 | 主评估 `603` 条真实样本，覆盖 `line 515 / region 84 / page 4`；场景覆盖新印刷 `309`、旧印刷 `235`、规范手写 `53`、实拍/屏幕 `6`；难度覆盖 easy `172`、medium `324`、hard `107`。 | 主评分集未到 1000+ 样本；复杂整页压力测试不混入 603 主结果夸大精度。 |
| 场景稀缺性 | 规范彝文公开 OCR 数据少；项目覆盖旧书、教材、工具书、彝汉混排、注音、手写和实拍资料。 | 应用目标限定在检索、校对、注音、语料建设和教学工作流。 |
| 任务复杂度 | 整页、PDF 和照片先经 PP-DocLayout 切割为 OCR 单元，再识别、恢复阅读顺序并合并页面文本；仓库提供整页 demo 和 Space 入口。 | 不声称已经稳定解决所有复杂整页；复杂 page 仍建议人工复核。 |
| 训练数据构建科学性 | `21504` 行训练包，训练材料、合成样本、同标签重渲染分开记录；Latin rerender `0`，footnote rerender `60`，region-like rerender `649`；缺图、空标签、替换符、LaTeX-like 标签均为 `0`。 | GitHub 保留配置、manifest、脚本和统计；权重与评估集分别放在 Hugging Face。 |
| 微调策略与创新 | 三阶段 LoRA 微调；训练侧用同标签重渲染补字体和旧印刷退化覆盖，并限制 Latin、脚注、region-like 多行等高风险通道。 | 不改 PaddleOCR-VL 结构，重点是训练数据构建、隔离检查和输出风险检查。 |
| 技术文档与开源贡献 | GitHub 提供 README、提交说明、评估集说明、质检报告、训练数据构建、模型训练、页面切割、后处理、Space、本地 demo、评估脚本和逐样本结果。 | Space 需要 GPU；本地 demo 和脚本是主要复现入口。 |

表中的“当前边界”说明哪些能力已经稳定，哪些仍需复核。

## 2. 提交物边界

| 上传位置 | 内容 | 说明 |
|---|---|---|
| GitHub 仓库 | README、文档、配置、脚本、demo、页面切割、后处理、评估摘要和逐样本输出 | 作为赛事评审入口和复现入口，不重复上传完整大图数据和模型权重 |
| Hugging Face 模型 | `NuosuBburma-OCR` 模型权重和模型卡 | [Hugging Face 模型](https://huggingface.co/nanxidajun/NuosuBburma-OCR) |
| Hugging Face 评估集 | `NuosuBburma-OCR-Evaluation-Set` 图片、标注和统计 | [Hugging Face 评估集](https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set) |

## 3. 结果统计

最终提交模型来自内部 v5.16 分支。该分支在开发诊断集上同时降低整体 NED、彝文 NED 和汉字 NED，并保持 replacement 和 long prediction 为 `0`。

当前提交模型已在 `603` 条主评估样本上重新评估；Base 结果保留脚本入口，可后续补齐。

| 指标 | PaddleOCR-VL Base | 当前提交模型 |
|---|---:|---:|
| 样本数 | 最终评估后补充 | 603 |
| Avg NED | 最终评估后补充 | 0.036068 |
| Exact match | 最终评估后补充 | 67.99% |
| WS Avg NED | 最终评估后补充 | 0.034219 |
| NFKC+WS Avg NED | 最终评估后补充 | 0.033964 |
| Yi-only Avg NED | 最终评估后补充 | 0.038309 |
| Yi-only exact | 最终评估后补充 | 74.96% |
| Han-only Avg NED | 最终评估后补充 | 0.022447 |
| Han-only exact | 最终评估后补充 | 93.99% |
| Digit-only Avg NED | 最终评估后补充 | 0.139918 |
| Digit-only exact | 最终评估后补充 | 85.19% |
| replacement / LaTeX / extra Latin / long_pred | 最终评估后补充 | 0 / 2 / 0 / 0 |

line 输入最稳定。region/page 用来暴露漏行、阅读顺序和换行边界问题。规范手写单独报告，不和印刷体混成一个结论。

## 4. 真实评估集

主评估为 `603` 条真实来源样本，全部计入结果表，不拆成展示样本和评分样本两套。

| 维度 | 分布 |
|---|---|
| 输入粒度 | `line 515`，`region 84`，`page 4` |
| 真实场景 | 新印刷扫描 `309`，旧书扫描 `235`，规范手写 `53`，实拍/屏幕 `6` |
| 文字混合 | `yi 321`，`yi_han 265`，`yi_han_latin 17` |
| 数字样本 | 含数字 `81`，不含数字 `522` |
| 难度 | `easy 172`，`medium 324`，`hard 107` |

主要来源如下：

| 来源 | 样本数 | 作用 |
|---|---:|---|
| 勒俄玛牧导读教程 | 126 | 教程类资料，覆盖教学文本和彝汉混排 |
| 根与花 | 121 | 新印刷正文，提供清晰行图基准 |
| 凉山彝文资料选译第2集 | 106 | 旧印刷资料，覆盖旧书噪声 |
| 凉山彝文资料选译第3集 | 84 | 换书、换排版的旧印刷评估 |
| 真实手写 | 53 | 规范手写泛化分组 |
| 《勒俄特依》译注 | 45 | 译注资料，覆盖注释边界和混排 |
| 彝文检字本 | 32 | 工具书结构、检字和字形边界 |
| 凉山彝语语法 | 30 | 语法资料，覆盖汉字、数字和编号 |
| 真实照片 / 屏幕页面 | 6 | 实拍、屏幕、页面上传噪声 |

复杂整页切割对比与主评估集分开维护。主评估集只统计 OCR 指标；页面切割 demo 只证明整页流程能跑通。

## 5. 任务复杂度：自然场景中的规范彝文 OCR

规范彝文 OCR 不能只看单行识别。旧书或页面照片要变成可用文本，还需要页面切割、阅读顺序、混排识别、页面文本合并和人工校对。

```text
整页 / PDF / 手机照片 / 屏幕图
-> PP-DocLayout 页面切割
-> 阅读顺序索引
-> OCR 单元识别
-> 彝文、汉字、数字、标点、可见 Latin 注音保真输出
-> replacement / LaTeX-like / extra Latin / long_pred 等输出风险审计
-> 页面文本合并
-> 按需注音、校对和语料化输出
```

这条链路对应多个子任务：

| 子任务 | 仓库实现 | 评分意义 |
|---|---|---|
| 页面/PDF/照片输入 | [页面切割入口脚本](../page_processing/run.py) | 让任务覆盖真实文献和用户上传图，而不是只测裁好的单行 |
| 页面切割 | [页面切割流程](../page_processing/README.md) | 使用 PP-DocLayout 生成 OCR 单元，降低复杂整页直接 OCR 的漏行、错行和边界风险 |
| 阅读顺序恢复 | `page_id`、`crop_id`、`reading_order`、`bbox`、页面元数据 | 把 OCR 单元结果合并为可校对页面文本 |
| 彝文/彝汉混排 OCR | 固定提示词 `<image>OCR:` | 检查低资源文字和常见汉字解释、数字、标点的混排稳定性 |
| 输出风险审计 | [analyze_submission_eval.py](../scripts/analyze_submission_eval.py)、整页 audit | 报告 replacement、LaTeX-like、extra Latin、long_pred、空页和重复页等风险；审计信号不自动改写正文 |
| 页面文本合并 | [assemble_pages.py](../page_processing/assemble_pages.py) | 使用 visual-line 拼合支撑书页、教材和旧文献的文本化，生成 `submission_pages.*` 与 `official_submission.*` |
| 注音 | [add_nuosu_pronunciation.py](../postprocess/add_nuosu_pronunciation.py) | 在页面文本完成后按需添加读音字段，供教学、检字和校对使用 |
| 整页 demo | [run_page_workflow.py](../demo/run_page_workflow.py) | 证明普通页面样例能按页面切割、OCR 单元识别、页面文本合并、异常审计和可选注音顺序跑通 |

在评估集《雪族子史篇》65 页整页样本上，`PP-DocLayout` 页面切割后识别的 Avg NED 为 `0.0654`，直接整页 OCR 为 `0.5540`。该对比说明页面切割能降低复杂整页中的阅读顺序错位、彝汉混排拆散和非文字花纹误识别。

当前边界：复杂整页、手写段落、多栏、脚注/注音密集区域仍建议人工复核。模型可以输入 page，但稳定交付优先使用可检查的 OCR 单元。

## 6. 训练数据构建

训练集遵循“真实训练材料打底、合成样本补覆盖、同标签重渲染补视觉变化”的原则。

低资源文字训练不能只靠真实数据，因为规范彝文字符、字体变化、旧印刷状态和混排格式覆盖不足；也不能靠大量无约束合成，因为模型容易学出多余 Latin、公式化片段、替换符和异常长输出。

训练数据不是越多越好。每类新增数据都有用途和上限，训练包记录样本来源、重渲染数量、高风险通道上限和训练包质检结果。

最终训练包为 `v5_16_synth_capped_rerender_official`：

| 项目 | 数量或设置 |
|---|---:|
| train rows after clean | 21504 |
| base rows | 12435 |
| new same-label rerender rows | 9069 |
| unchanged real rows | 1861 |
| original synthetic rows | 10574 |
| ordinary rerenders added | 8360 |
| footnote rerenders added | 60 |
| region-like rerenders added | 649 |
| Latin rerenders added | 0 |
| missing images / empty labels / replacement labels | 0 / 0 / 0 |
| rows with LaTeX-like labels / backslash | 0 / 0 |

v5.16 使用同标签受控重渲染：文本标签不变，只改变字体、退化和页面视觉状态。Latin、脚注、region-like 多行样本设置上限，避免某类格式被模型学成默认输出习惯。

隔离检查单独列出，不作为训练包质量指标：

| 检查项 | 结果 |
|---|---:|
| eval image path hits after clean | 0 |
| eval image basename hits after clean | 0 |
| eval sample-id hits after clean | 0 |
| 删除的完全重合标签行 | 2 |
| 保留的完全重合标签行 | 7 |

## 7. 模型策略与分支实验

基础设置保持稳定：PaddleOCR-VL-1.6 0.9B、LoRA rank `8`、2 epoch、learning rate `5.0e-4`、单卡 4090D。分支比较主要改变数据分布，不把模型结构和数据策略混在一起。

| 分支 | 训练数据动作 | 开发诊断集结果 | 判断 |
|---|---|---|---|
| v5.8 Stable Balance | 稳定数据形状，补 region/multiline 与纯彝文稳定样本 | total `0.0634`，yi `0.0512`，Han `0.0265`，long `0` | 早期稳定基线 |
| v5.15 Layout Latin Rebalance | 恢复字典注音、单行 Yi-Han、纯彝文字符覆盖 | total `0.0505`，yi `0.0473`，Han `0.0261`，long `0` | 总分继续下降，但脚注风险仍高 |
| v5.16 Synth Capped Rerender | 同标签重渲染 `9069` 行，Latin 不放大，footnote/region 设上限 | total `0.0342`，yi `0.0372`，Han `0.0225`，LaTeX `2`，long `0` | 最终提交模型 |
| v5.17 Micro Format Tail | 追加 `350` 行格式长尾约束样本 | total `0.0429`，LaTeX 回到 `10`，long `1` | 未作为提交模型 |

实验结论：继续加数据不一定变好，关键是控制数据分布。提交模型采用 v5.16，因为它在开发诊断集上同时降低 total NED、yi NED、Han NED，并把 replacement 和 long prediction 保持为 `0`。

## 8. 开源与复现

核心入口：

| 任务 | 入口 |
|---|---|
| 项目概览 | [README.md](../README.md) |
| 下载模型 | [model/README.md](../model/README.md)，[Hugging Face 模型](https://huggingface.co/nanxidajun/NuosuBburma-OCR) |
| 下载评估集 | [NuosuBburma_OCR_Evaluation_Set/README.md](../NuosuBburma_OCR_Evaluation_Set/README.md)，[Hugging Face 评估集](https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set) |
| 单图 / 整页 demo | [demo/README.md](../demo/README.md) |
| 运行评估 | [scripts/README.md](../scripts/README.md) |
| 页面切割 | [页面切割流程](../page_processing/README.md) |
| OCR 后处理 | [postprocess/README.md](../postprocess/README.md) |
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

运行单图 demo：

```bash
python demo/infer_single_image.py \
  --model models/NuosuBburma-OCR \
  --image demo/sample_images/mixed_line.png
```

运行整页 demo：

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
| 主评估集是否使用合成样本 | 否。合成数据只用于训练覆盖，不用于证明主结果 |
| 标注是否直接使用模型输出 | 否。模型输出只作为预标注草稿，最终需要人工核对 |
| 评估集是否作为训练数据 | 否。训练侧保留隔离检查；路径、basename、sample-id 命中均为 `0` |
| 整页 OCR 是否已经稳定 | 否。项目提供页面切割、阅读顺序和整页诊断，但复杂整页仍建议人工复核 |
| 手写 OCR 是否已经稳定 | 否。规范手写已有泛化信号，但明显弱于印刷体，单独报告 |
| 是否提供线上 Space | 是，提供 Hugging Face Space 作为交互入口；模型推理需要 GPU，未配置 GPU 时以本地单图 demo、整页 demo 与脚本为主入口 |

## 10. 提交总结

本项目的重点是把规范彝文 OCR 放到真实资料中评估和复现。

可核验内容有四项：`603` 条真实主评估集、`21504` 行训练包、v5.8-v5.17 分支实验，以及整页/PDF/照片到 OCR 单元识别、页面文本合并、审计和按需注音的流程。

后续可以继续扩大真实整页和手写样本，并补充更稳定的在线体验。
