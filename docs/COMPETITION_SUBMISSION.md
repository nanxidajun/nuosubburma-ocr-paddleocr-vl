# PaddleOCR 全球衍生模型挑战赛提交说明

`NuosuBburma OCR` 是面向 **PaddleOCR 全球衍生模型挑战赛** 的规范彝文 OCR 衍生模型，基于 `PaddleOCR-VL-1.6 (0.9B)` + LoRA 构建。赛事要求开发者围绕 PaddleOCR-VL 拓展真实 OCR 场景，并从评估集、任务复杂度、训练数据、微调策略和开源贡献等维度证明项目价值；本项目对应的任务是 **自然场景中的规范彝文 OCR**。

它要解决的问题很具体：许多规范彝文资料已经以书籍、扫描件、教材、工具书和手写稿存在，却仍然难以搜索、复制、校对和进入语料建设。

本次提交把真实数据、训练取舍、模型结果、文档处理流程和复现入口都摆出来，方便评委按官方评分表逐项核验。换句话说，这个项目的核心价值不止是“模型能识别几张图”，更在于给 PaddleOCR-VL 衍生模型赛道补上一套低资源民族文字的真实评估、谨慎训练和开源复现样板。

## 0. 评委快速核验

本节直接对应赛事评审最关心的六件事：数据是否真实，场景是否稀缺，任务是否超过单行 OCR，训练数据是否有构建方法，模型选择是否有实验依据，以及开源复现是否方便。

| 核验问题 | 本项目回答 | 入口 |
|---|---|---|
| 评估集是否真实 | 是。主评估使用 `603` 条真实来源样本，含 `7` 张实拍/屏幕样本；合成样本不进入主评估。 | [EVALUATION_DATASET.md](EVALUATION_DATASET.md)，[EVALUATION_QUALITY_REPORT.md](EVALUATION_QUALITY_REPORT.md)，[Hugging Face 评估集](https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set) |
| 模型结果是否已经跑完 | 是。提交模型在 `603` 条主评估样本上 Avg NED `0.036068`，Yi-only Avg NED `0.038309`，Han-only Avg NED `0.022447`。 | [evaluation/summary.md](../evaluation/summary.md)，[evaluation/raw/submission_model_result.jsonl](../evaluation/raw/submission_model_result.jsonl) |
| 是否只是单行 OCR | 否。仓库能从整页、PDF、照片开始，使用 PP-DocLayout 做页面切割，记录阅读顺序，再识别 OCR 单元，最后合并页面文本并按需补注音；复杂整页仍建议人工复核。 | [页面切割流程](../page_processing/README.md)，[demo](../demo/README.md)，[后处理工具](../postprocess/README.md) |
| 训练数据是否科学 | 训练包 `v5_16_synth_capped_rerender_official` 共 `21504` 行，真实样本打底，合成样本补覆盖，并记录形近字防混淆和输出约束；缺图、空标签、替换符、LaTeX-like 标签均为 `0`。 | [TRAINING_DATA_CONSTRUCTION_REPORT.md](TRAINING_DATA_CONSTRUCTION_REPORT.md)，[configs/train_data_manifest_v5_16.json](../configs/train_data_manifest_v5_16.json) |
| 模型选择是否有实验依据 | 有。v5.8、v5.15、v5.16、v5.17 等分支按同一真实评估设置比较，最终选择 v5.16，不选择 v5.17 是因为 LaTeX 和 long prediction 风险回升。 | [MODEL_AND_TRAINING.md](MODEL_AND_TRAINING.md)，[evaluation](../evaluation/) |
| 是否可复现 | 提供 Hugging Face 模型、Hugging Face 评估集、Hugging Face Space 交互入口、本地单图 demo、整页 demo、训练配置、评估脚本和逐样本输出；完整推理和批量复现以本地 demo 与脚本为准。 | [model](../model/README.md)，[demo](../demo/README.md)，[scripts](../scripts/README.md) |

这张表只作为评审入口。更完整的判断逻辑是：评估集先保证真实，训练集再解释为什么这样构建，模型分支用同一评估设置比较，最后把能力边界写清楚。对本次衍生模型挑战赛来说，诚实边界本身就是可复查性和开源贡献的一部分。

## 1. 官方评分点映射

官方评分不是只看最终模型指标，而是同时考察评估集、场景、任务、训练数据、微调策略和开源贡献。本项目的写法按这六个维度展开，避免把所有材料混成一份普通 README。

| 官方维度 | 本项目最强证据 | 当前边界 |
|---|---|---|
| 评估集质量 | 主评估 `603` 条真实样本，覆盖 `line 515 / region 84 / page 4`；场景覆盖新印刷 `309`、旧印刷 `235`、规范手写 `53`、实拍/屏幕 `6`；难度覆盖 easy `172`、medium `324`、hard `107`。 | 主评分集未到 1000+ 样本；复杂整页压力测试不混入 603 主结果夸大精度。 |
| 场景稀缺性 | 规范彝文公开 OCR 数据和可复现评估集稀缺，属于赛事鼓励覆盖的长尾 OCR 场景；项目面向旧书、教材、工具书、彝汉混排、注音、手写和实拍资料数字化。 | 不把民族文字价值写成泛泛“文化保护”，而是落到检索、校对、注音、语料建设和教学工作流。 |
| 任务复杂度 | 从整页、PDF、照片输入，到页面切割、阅读顺序、OCR 单元识别、页面文本合并、输出风险审计和注音附加输出；仓库提供整页 demo 和 Space 交互入口。 | 不声称已经解决任意复杂整页 OCR；复杂 page 仍建议结合切割结果和人工复核。 |
| 训练数据构建科学性 | `21504` 行训练包，`9069` 行同标签受控重渲染；Latin rerender `0`，footnote rerender `60`，region-like rerender `649`；训练/评估路径、样本 id 命中均为 `0`。 | 训练图片不直接塞进 GitHub；公开仓库保留配置、manifest、脚本和统计，完整权重放在 Hugging Face 模型，完整评估集放在 Hugging Face 评估集。 |
| 微调策略与创新 | PaddleOCR-VL LoRA + 低资源文字数据策略：固定真实评估集，同一标签换字体和退化方式重渲染，并专门检查形近字、多余 Latin、公式化片段和异常长输出。 | 模型结构创新不是重点，创新主要在数据闭环、输出风险控制和自然场景 OCR 工程。 |
| 技术文档与开源贡献 | GitHub 仓库、Hugging Face 模型、Hugging Face 评估集、README、提交说明、评估集说明、质检报告、训练数据构建、模型训练、页面切割、后处理、Hugging Face Space、本地单图 demo、整页 demo、评估脚本、逐样本结果齐全。 | Space 需要 GPU 才能稳定运行完整模型；本地 demo 和可复现脚本是完整复现入口。 |

这份提交选择把“边界”放进评分映射里，是为了避免把低资源任务写成过度承诺。能稳定做的部分明确给出结果，仍在探索的整页、手写和复杂混排也保留材料和诊断入口。这样评委看到的不只是一个分数，而是一个可复查、可复跑、可继续扩展的 PaddleOCR-VL 衍生模型基线。

## 2. 提交物边界

| 上传位置 | 内容 | 说明 |
|---|---|---|
| GitHub 仓库 | README、文档、配置、脚本、demo、页面切割、后处理、评估摘要和逐样本输出 | 作为赛事评审入口和复现入口，不重复上传完整大图数据和模型权重 |
| Hugging Face 模型 | `NuosuBburma-OCR` 模型权重和模型卡 | [Hugging Face 模型](https://huggingface.co/nanxidajun/NuosuBburma-OCR) |
| Hugging Face 评估集 | `NuosuBburma-OCR-Evaluation-Set` 图片、标注和统计 | [Hugging Face 评估集](https://huggingface.co/datasets/nanxidajun/NuosuBburma-OCR-Evaluation-Set) |

## 3. 结果统计

最终提交模型固定为内部 v5.16 分支导出的 `NuosuBburma OCR`。这个选择来自多个分支的同口径比较，而不是简单沿用“最后一次训练”：v5.16 在真实 reviewed 数据下同时压低整体 NED、彝文 NED 和汉字 NED，也没有重新打开替换符和超长输出风险。v5.16 随后在本次公开提交的 `603` 条主评估样本上重新评估。下表的当前提交模型列已经跑完；Base 同口径结果保留脚本入口，可由评审或后续复跑补齐。

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

这组结果的解读不是“所有场景都稳定解决”。line 输入最稳定，region/page 更能暴露漏行、阅读顺序和换行边界问题。规范手写作为独立真实泛化分组观察，不和清晰印刷体混成一个结论。这样的拆分会让指标看起来不如单一清晰行图漂亮，但它更接近真实资料进入 OCR 流程时会遇到的问题。

## 4. 真实评估集

主评估为 `603` 条真实来源样本，全部计入结果表，不拆成展示样本和评分样本两套。这个选择很重要：低资源 OCR 容易被少量漂亮样例误导，只有把难样本也放进同一评估设置，结果才有参考价值。

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

复杂整页切割/版面对比材料与这套主评估集分开维护。主评估集只回答模型在冻结真实样本上的 OCR 指标；页面切割 demo 回答页面检测、OCR 单元识别、页面文本合并和异常审计是否能按真实执行顺序跑通。两者不混算，避免用页面结构实验影响 `603` 条主评分。

## 5. 任务复杂度：自然场景中的规范彝文 OCR

规范彝文 OCR 的难点在于真实资料进入可检索文本时的连续链路。一本旧书或一张页面照片要变成可用文本，中间会经过页面切割、阅读顺序、混排识别、页面文本合并和人工校对；任一环节出错，最终文本就不可用。

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
| 阅读顺序恢复 | `page_id`、`crop_id`、`reading_order`、页面元数据 | 把 OCR 单元结果合并为可校对页面文本 |
| 彝文/彝汉混排 OCR | 固定提示词 `<image>OCR:` | 检查低资源文字和常见汉字解释、数字、标点的混排稳定性 |
| 输出风险审计 | [analyze_submission_eval.py](../scripts/analyze_submission_eval.py)、整页 audit | 报告 replacement、LaTeX-like、extra Latin、long_pred、空页和重复页等风险；审计信号不自动改写正文 |
| 页面文本合并 | [run_page_workflow.py](../demo/run_page_workflow.py) | 支撑书页、教材和旧文献的文本化，生成 `submission_pages.*` 与 `official_submission.*` |
| 注音与语料化 | [add_nuosu_pronunciation.py](../postprocess/add_nuosu_pronunciation.py) | 在页面文本完成后按需添加读音字段，连接教学、检字、校对和语料库建设 |
| 整页 demo | [run_page_workflow.py](../demo/run_page_workflow.py) | 证明普通页面样例能按页面切割、OCR 单元识别、页面文本合并、异常审计和可选注音顺序跑通 |

在评估集《雪族子史篇》65 页整页样本上，`PP-DocLayout` 页面切割后识别的 Avg NED 为 `0.0654`，直接整页 OCR 为 `0.5540`。该对比说明页面切割能降低复杂整页中的阅读顺序错位、彝汉混排拆散和非文字花纹误识别。

项目当前的诚实边界是：复杂整页、手写段落、多栏、脚注/注音密集区域仍建议配合页面切割结果和人工复核；模型可以输入 page，但稳定交付优先使用可检查的 OCR 单元。这种拆法把任务落到可以真正使用、也可以继续改进的粒度。

## 6. 训练数据构建

训练集遵循“真实样本打底、合成样本补覆盖、评估集固定不动”的原则。低资源文字训练不能只靠真实数据，因为 1165 个规范彝文字符、形近字、旧印刷视觉状态和混排格式覆盖不足；也不能靠大量无约束合成，因为模型容易学出多余 Latin、公式化片段、替换符和异常长输出。

所以这里的训练重点是“每一类新增数据要知道自己在修什么，也要知道可能带来什么副作用”，而不是简单追求数据越多越好。这也是为什么训练包同时记录真实来源、重渲染数量、高风险通道上限和训练/评估隔离结果。

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
| eval image path / basename / sample-id hits | 0 / 0 / 0 |

v5.16 的核心动作是“同标签受控重渲染”：不改变文本标签，只让同一段文本出现在更多字体、退化和页面视觉状态下。同时对 Latin、脚注、region-like 多行等高风险样本设上限，避免为了修局部问题重新打开输出漂移。它体现的是低资源训练中很朴素的一条经验：补覆盖要克制，控风险要可查。

## 7. 模型策略与分支实验

基础设置保持稳定：PaddleOCR-VL-1.6 0.9B、LoRA rank `8`、2 epoch、learning rate `5.0e-4`、单卡 4090D。分支比较主要改变数据分布，不把模型结构和数据策略混在一起。

| 分支 | 训练数据动作 | 旧 reviewed 611 结果 | 判断 |
|---|---|---|---|
| v5.8 Stable Balance | 稳定数据形状，补 region/multiline 与纯彝文防漂移样本 | total `0.0634`，yi `0.0512`，Han `0.0265`，long `0` | 早期稳定基线 |
| v5.15 Layout Latin Rebalance | 恢复字典注音、单行 Yi-Han、纯彝文形近字平衡 | total `0.0505`，yi `0.0473`，Han `0.0261`，long `0` | 曾为最强，仍有 LaTeX 风险 |
| v5.16 Synth Capped Rerender | 同标签重渲染 `9069` 行，Latin 不放大，footnote/region 设上限 | total `0.0342`，yi `0.0372`，Han `0.0225`，LaTeX `2`，long `0` | 最终提交模型 |
| v5.17 Micro Format Tail | 追加 `350` 行格式长尾约束样本 | total `0.0429`，LaTeX 回到 `10`，long `1` | 不替代 v5.16 |

这组实验的结论是：低资源 OCR 的提升不来自无脑加数据，而来自控制数据分布。Latin、脚注、region-like 多行和结尾安全样本都可能修好局部问题，也可能带来新的输出风险。因此最终选择 v5.16，是因为它在真实 reviewed 数据下同时降低 total NED、yi NED、Han NED，并把 replacement 和 long prediction 保持为 `0`。v5.17 没有被采用，也正说明本项目按评估结果选模型，而不是按版本号或训练轮次选模型。

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
| 主评估集是否使用合成样本 | 否。合成数据只用于训练覆盖和诊断样本，不用于证明主结果 |
| 标注是否直接使用模型输出 | 否。模型输出只作为预标注草稿，最终需要人工核对 |
| 评估集是否作为训练目标 | 否。训练侧保留排除清单和重合清理；路径、basename、sample-id 命中均为 `0` |
| 是否完整解决整页 OCR | 否。项目提供页面切割、阅读顺序和整页诊断，但复杂整页仍建议人工复核 |
| 是否完整解决手写 OCR | 否。规范手写已有泛化信号，但明显弱于印刷体，单独报告 |
| 是否提供线上 Space | 是，提供 Hugging Face Space 作为交互入口；完整模型推理需要 GPU，未配置 GPU 时以本地单图 demo、整页 demo 与脚本复现为主入口 |

## 10. 提交总结

本项目的核心贡献可以压成一句话：它把规范彝文 OCR 从“能不能识别几张干净行图”推进到“自然场景里的真实资料如何被可靠评估、训练、复现和进入 OCR 流程”。

评分最需要核验的不是单个漂亮样例，而是四件可查的东西：`603` 条真实主评估集、`21504` 行受控训练包、v5.8-v5.17 的分支实验取舍、以及整页/PDF/照片到 OCR 单元识别、页面文本合并、审计和按需注音输出的工程链路。当前最强模型是 v5.16；v5.17 已评估但未晋级，这一点反而说明项目没有用“最新版”替代真实评估判断。

如果说这个项目还有什么可以继续提高，那就是继续扩大真实整页和手写样本，并补充更稳定的在线体验。但就当前提交而言，它已经提供了一个低资源民族文字 OCR 项目最需要的基础：真实评估、可查训练、清楚边界和可以继续复现的公开入口。
