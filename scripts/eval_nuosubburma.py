#!/usr/bin/env python3
import argparse
import json
import os
import time
from pathlib import Path

import Levenshtein
import paddle
import paddle.distributed as dist
from PIL import Image
from tqdm import tqdm

from paddleformers.generation import GenerationConfig
from paddleformers.transformers import AutoModelForConditionalGeneration, AutoProcessor


def parse_args():
    parser = argparse.ArgumentParser(description="NuosuBburma OCR eval for PaddleOCR-VL")
    parser.add_argument("--model_name_or_path", required=True)
    parser.add_argument("--data_path", required=True)
    parser.add_argument("--output_path", default="outputs/eval_result.jsonl")
    parser.add_argument("--max_length", type=int, default=1024)
    parser.add_argument("--device", default="gpu")
    return parser.parse_args()


def resolve_image(image_path: str, data_path: str) -> Path:
    path = Path(image_path)
    if path.is_absolute():
        return path
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path
    return Path(data_path).resolve().parent / path


def load_model_and_processor(model_path, device):
    paddle.set_device(device)
    processor = AutoProcessor.from_pretrained(model_path)
    model = AutoModelForConditionalGeneration.from_pretrained(model_path, convert_from_hf=True)
    model.config._attn_implementation = "flashmask"
    model.visual.config._attn_implementation = "flashmask"
    model.eval()
    return model, processor


def compute_ned(predictions, references):
    if not predictions:
        return 0.0
    total = 0.0
    for pred, ref in zip(predictions, references):
        max_len = max(len(pred), len(ref))
        if max_len:
            total += Levenshtein.distance(pred, ref) / max_len
    return total / len(predictions)


def generate_response(model, processor, messages, max_length):
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
        outputs = model.generate(**inputs, generation_config=generation_config, max_new_tokens=max_length)
        output_ids = outputs[0].tolist()[0]
        return processor.decode(output_ids, skip_special_tokens=True)


def main():
    start_time = time.time()
    args = parse_args()
    try:
        dist.init_parallel_env()
        rank = dist.get_rank()
        world_size = dist.get_world_size()
    except Exception:
        rank = 0
        world_size = 1

    model, processor = load_model_and_processor(args.model_name_or_path, args.device)
    with open(args.data_path, encoding="utf-8") as f:
        all_samples = [json.loads(line) for line in f if line.strip()]
    samples = all_samples[rank::world_size]

    results = []
    for sample in tqdm(samples, desc=f"rank {rank}"):
        query = sample["messages"][0]["content"].replace("<image>", "")
        image = Image.open(resolve_image(sample["images"][0], args.data_path)).convert("RGB")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": query},
                ],
            }
        ]
        output = generate_response(model, processor, messages, args.max_length)
        sample["answer"] = output
        sample["label"] = sample["messages"][1]["content"]
        results.append(sample)

    part_file = f"{args.output_path}.part{rank}"
    Path(part_file).parent.mkdir(parents=True, exist_ok=True)
    with open(part_file, "w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    if world_size > 1:
        dist.barrier()

    if rank == 0:
        merged = []
        for r in range(world_size):
            part = Path(f"{args.output_path}.part{r}")
            if part.exists():
                with part.open(encoding="utf-8") as f:
                    merged.extend(json.loads(line) for line in f if line.strip())
                part.unlink()
        predictions = [row.get("answer", "") for row in merged]
        references = [row.get("label", "") for row in merged]
        avg_ned = compute_ned(predictions, references)
        with open(args.output_path, "w", encoding="utf-8") as f:
            for row in merged:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("=" * 40)
        print(f"Model: {args.model_name_or_path}")
        print(f"Dataset: {args.data_path}")
        print(f"Total Samples: {len(merged)}")
        print(f"Avg. NED: {avg_ned:.4f} (Lower is better)")
        print(f"Output: {args.output_path}")
        print(f"Elapsed: {time.time() - start_time:.2f}s")
        print("=" * 40)


if __name__ == "__main__":
    main()
