#!/usr/bin/env python3
"""Run OCR on line crops produced by crop_pipeline/run.py."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import paddle
from PIL import Image
from paddleformers.generation import GenerationConfig
from paddleformers.transformers import AutoModelForConditionalGeneration, AutoProcessor
from tqdm import tqdm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NuosuBburma OCR on crop pipeline line outputs")
    parser.add_argument("--model", required=True, help="Path to merged PaddleOCR-VL export")
    parser.add_argument("--index", type=Path, required=True, help="04_successful_crop_summary/index.csv")
    parser.add_argument(
        "--summary-root",
        type=Path,
        help="Root folder containing index.csv summary_path files. Defaults to index.csv parent.",
    )
    parser.add_argument("--output", type=Path, required=True, help="Output JSONL path")
    parser.add_argument("--prompt", default="<image>OCR:")
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument("--device", default="gpu")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for quick smoke tests")
    return parser.parse_args()


def read_index(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return [row for row in rows if row.get("is_line_ocr_ready") == "1"]


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def line_sort_key(row: dict[str, str]) -> tuple[Any, ...]:
    reading_order = row.get("reading_order") or ""
    if reading_order:
        return (0, reading_order)
    return (1, row.get("page_id", ""), as_int(row.get("source_box")), as_int(row.get("part_index")), row.get("crop_id", ""))


def load_model_and_processor(model_path: str, device: str):
    paddle.set_device(device)
    processor = AutoProcessor.from_pretrained(model_path)
    model = AutoModelForConditionalGeneration.from_pretrained(model_path, convert_from_hf=True)
    model.config._attn_implementation = "flashmask"
    model.visual.config._attn_implementation = "flashmask"
    model.eval()
    return model, processor


def generate_response(model, processor, image: Image.Image, prompt: str, max_new_tokens: int) -> str:
    query = prompt.replace("<image>", "")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": query},
            ],
        }
    ]
    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pd",
    )
    generation_config = GenerationConfig(
        do_sample=False,
        bos_token_id=1,
        eos_token_id=2,
        pad_token_id=0,
        use_cache=True,
    )
    with paddle.no_grad():
        outputs = model.generate(
            **inputs,
            generation_config=generation_config,
            max_new_tokens=max_new_tokens,
        )
    output_ids = outputs[0].tolist()[0]
    return processor.decode(output_ids, skip_special_tokens=True)


def main() -> None:
    args = parse_args()
    summary_root = args.summary_root or args.index.resolve().parent
    rows = sorted(read_index(args.index), key=line_sort_key)
    if args.limit > 0:
        rows = rows[: args.limit]

    model, processor = load_model_and_processor(args.model, args.device)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for row in tqdm(rows, desc="OCR line crops"):
            image_path = summary_root / row["summary_path"]
            image = Image.open(image_path).convert("RGB")
            answer = generate_response(model, processor, image, args.prompt, args.max_new_tokens)
            out = {
                "id": row.get("crop_id") or image_path.stem,
                "images": [str(image_path)],
                "answer": answer,
                "meta": row,
            }
            f.write(json.dumps(out, ensure_ascii=False) + "\n")

    print(json.dumps({"line_rows": len(rows), "output": str(args.output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

