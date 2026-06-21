# 脚本

核心脚本：

- `eval_nuosubburma.py`：对 JSONL 评估集运行 OCR 推理。
- `run_eval.sh`：Paddle distributed launch 的评估封装。
- `run_train_lora.sh`：训练命令封装。
- `run_export_and_eval.sh`：导出 LoRA 并运行评估。
- `run_final_real_eval.sh`：运行单个评估集。
- `analyze_submission_eval.py`：计算 NED、Yi-only/Han-only 指标、漂移标记和复核表。
- `build_submission_eval_set.py`：构建提交评估集的本地工具。
- `normalize_fullwidth_punctuation.py`：全角标点规范化辅助脚本。

依赖环境包括 `paddle`、`paddleformers`、`Pillow`、`tqdm` 和 `python-Levenshtein`。
