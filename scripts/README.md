# 脚本

本目录只保留提交复现和页面切图需要的核心脚本。

- `eval_nuosubburma.py`：对 JSONL 评估集运行 OCR 推理。
- `run_eval.sh`：Paddle distributed launch 的评估封装。
- `run_train_lora.sh`：训练命令封装。
- `analyze_submission_eval.py`：计算 NED、纯彝文 NED、漂移标记和复核表。
- `run_book_crop_pipeline.py`：整页书页切图入口，串联 v3 分流、v4 二次切分、人工复核目录和成功切图汇总。
- `line_segmentation_probe.py`：基础 OpenCV 行切分探针。
- `line_segmentation_probe_v3.py`：按页型把检测框分流为 line OCR、region OCR、忽略项或特殊页型。
- `line_segmentation_probe_v4.py`：只对 v3 的 region fallback 大块做局部二次切分。
- `build_crop_visual_review.py`：生成切图前后对照目录，便于人工快速检查。
- `build_successful_crop_summary.py`：汇总可进入 OCR 的行图、保留 region 和参考忽略项。
- `validate_crop_pipeline_outputs.py`：校验切图汇总的 `crop_id`、路径和二次切分行顺序。

评估/训练依赖包括 `paddle`、`paddleformers`、`Pillow`、`tqdm` 和 `python-Levenshtein`。

切图流程额外依赖 `opencv-python` 和 `numpy`。用法见 [`../docs/CROP_PIPELINE.md`](../docs/CROP_PIPELINE.md)。
