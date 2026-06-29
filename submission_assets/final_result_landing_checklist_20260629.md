# 最终结果落位工作台

这个文件只给内部收尾用，不作为公开说明提交。目的只有一个：最终评估结果回来后，先在这里核准数字，再同步到 GitHub、Hugging Face 模型卡和 Hugging Face 数据集卡，避免不同页面出现不同版本。

## 0. 使用顺序

1. 先填“评估集最终统计”。
2. 再填“模型最终结果”。
3. 按“同步位置”逐个文件替换。
4. 跑“最终公开检查命令”。
5. 检查无误后，再上传 Hugging Face 模型卡和数据集卡。

## 1. 评估集最终统计

这些数字来自最终冻结的评估集，不从旧 `603` 版本推断。

| 要填的数 | 最终值 | 从哪里确认 |
|---|---:|---|
| 样本总数 |  | 最终 `annotations.jsonl` 行数 |
| 涉及页面数 |  | 最终 manifest / 统计脚本 |
| line 样本数 |  | 输入粒度统计 |
| region 样本数 |  | 输入粒度统计 |
| page 样本数 |  | 输入粒度统计 |
| 真实来源样本数 |  | 数据来源统计 |
| 合成样本进入最终评估 | 否 | 固定为否 |

## 2. 四维统计

这部分用于 `README.md`、`docs/EVALUATION_DATASET.md`、Hugging Face 数据集卡。最终公开时尽量做成图表，不要写成长段文字。

| 维度 | 分组 | 最终数量 | 是否已核对 |
|---|---|---:|---|
| 视觉场景 | 新印刷扫描 |  |  |
| 视觉场景 | 旧书扫描 |  |  |
| 视觉场景 | 手机页面照片 |  |  |
| 视觉场景 | 屏幕拍照 |  |  |
| 视觉场景 | 实拍标牌 |  |  |
| 视觉场景 | 手写拍照 |  |  |
| 输入粒度 | line |  |  |
| 输入粒度 | region |  |  |
| 输入粒度 | page |  |  |
| 文字混合 | 彝文主体 |  |  |
| 文字混合 | 彝汉混排 |  |  |
| 文字混合 | 含 Latin / 数字 / 符号 |  |  |
| 难度分层 | easy |  |  |
| 难度分层 | medium |  |  |
| 难度分层 | hard |  |  |

## 3. 模型最终结果

这张表是所有公开文档的主结果来源。不要在不同文档里各自手写一版。

| 模型阶段 | Avg NED | Yi NED | Han NED | Digit NED | replacement | LaTeX-like | extra Latin | long prediction | empty output |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| PaddleOCR-VL Base |  |  |  |  |  |  |  |  |  |
| 1 阶微调 |  |  |  |  |  |  |  |  |  |
| 2 阶微调 |  |  |  |  |  |  |  |  |  |
| 最终模型 |  |  |  |  |  |  |  |  |  |

说明：

- `Avg NED` 是主指标，越低越好。
- `Yi NED` 看彝文主体能力。
- `Han NED` 看彝汉混排里的汉字能力。
- `Digit NED` 看页码、编号、数字等高风险小字段。
- 风险指标用于说明模型有没有输出漂移，不是装饰项。
- `Exact match` 不放首页主表；如果要保留，只放详细评估附表。

## 4. 同步位置

| 文件 | 最后要同步什么 |
|---|---|
| `README.md` | 最终样本数、四维统计图、主结果表、页面切割案例保留 |
| `docs/COMPETITION_SUBMISSION.md` | 六项评分入口、官方反馈回应、主结果表 |
| `docs/EVALUATION_DATASET.md` | 评估集来源、四维统计、难度分层、标注和质检说明 |
| `docs/EVALUATION_QUALITY_REPORT.md` | 质检结论、删除/保留原则、最终样本统计 |
| `docs/MODEL_AND_TRAINING.md` | Base / 1 阶 / 2 阶 / 最终模型同一评估设置结果 |
| `evaluation/README.md` | 最终评估摘要、风险指标、结果文件说明 |
| `model/HUGGINGFACE_MODEL_CARD.md` | Hugging Face 模型卡最终结果和使用边界 |
| `NuosuBburma_OCR_Evaluation_Set/README.md` | Hugging Face 数据集卡入口、字段说明、最终统计 |

## 5. 统一写法

公开文档里统一用这些说法：

| 类型 | 统一写法 |
|---|---|
| 模型托管 | Hugging Face 模型 |
| 数据托管 | Hugging Face 评估集 |
| 页面切割模型 | `PP-DocLayout_plus-L` |
| 页面流程 | 页面切割、OCR 单元识别、页面文本合并、异常审计、可选注音 |
| 最终结果占位 | 最终评估完成后补充 |
| 合成数据进入评估 | 合成样本不进入最终评估 |

公开文档里避免这些写法：

| 避免写法 | 处理方式 |
|---|---|
| `HF` | 改成 `Hugging Face` |
| `Paddle DocLayout` | 改成 `PP-DocLayout_plus-L` |
| `页面处理` | 改成 `页面切割` 或具体流程 |
| `待复跑`、`待补` | 最终提交前清掉 |
| `Exact match` 作为主指标 | 移到详细附表或不展示 |
| 旧切割流程名 | 不再公开提 |

## 6. 最终公开检查命令

在仓库根目录执行：

```bash
rg -n "待补|待复跑|后续补充|HF（|HF |CROP_PIPELINE|crop_pipeline|Paddle DocLayout|Paddle 的 DocLayout|页面处理|旧 Python|v3/v4|reproduce" \
  README.md docs model demo scripts page_processing hf_space evaluation NuosuBburma_OCR_Evaluation_Set
```

最终提交前，这条命令不应该命中公开残留。若命中，逐条判断是要删除、改写，还是只保留在内部清单中。

```bash
rg -n "603|Exact match|PaddleOCR-VL Base|1 阶|2 阶|最终模型" \
  README.md docs model evaluation NuosuBburma_OCR_Evaluation_Set
```

这条命令允许命中最终主结果表和必要说明，但不能出现新旧数字混用。
