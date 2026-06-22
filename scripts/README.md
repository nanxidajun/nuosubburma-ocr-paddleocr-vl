# 脚本

本目录只保留训练、评估和统计复现需要的核心脚本。

- `eval_nuosubburma.py`：对 JSONL 评估集运行 OCR 推理。
- `run_eval.sh`：Paddle distributed launch 的评估封装。
- `run_train_lora.sh`：训练命令封装。
- `analyze_submission_eval.py`：计算 NED、纯彝文 NED、漂移标记和复核表。

评估/训练依赖包括 `paddle`、`paddleformers`、`Pillow`、`tqdm` 和 `python-Levenshtein`。

切图流程已单独放到一级目录 [`../crop_pipeline/`](../crop_pipeline/)。
