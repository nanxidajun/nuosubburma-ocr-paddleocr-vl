# 脚本

本目录只保留提交复现需要的核心脚本。

- `eval_nuosubburma.py`：对 JSONL 评估集运行 OCR 推理。
- `run_eval.sh`：Paddle distributed launch 的评估封装。
- `run_train_lora.sh`：训练命令封装。
- `analyze_submission_eval.py`：计算 NED、纯彝文 NED、漂移标记和复核表。

依赖环境包括 `paddle`、`paddleformers`、`Pillow`、`tqdm` 和 `python-Levenshtein`。
