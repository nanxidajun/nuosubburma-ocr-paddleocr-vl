#!/usr/bin/env python3
"""Run NuosuBburma OCR on a single image."""

from __future__ import annotations

import argparse
from pathlib import Path

import paddle
from PIL import Image
from paddleformers.generation import GenerationConfig
from paddleformers.transformers import AutoModelForConditionalGeneration, AutoProcessor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single-image NuosuBburma OCR demo")
    parser.add_argument("--model", required=True, help="Path to merged PaddleOCR-VL export")
    parser.add_argument("--image", required=True, help="Path to input image")
    parser.add_argument("--prompt", default="<image>OCR:")
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument("--device", default="gpu")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paddle.set_device(args.device)

    model_path = Path(args.model)
    image = Image.open(args.image).convert("RGB")

    processor = AutoProcessor.from_pretrained(str(model_path))
    model = AutoModelForConditionalGeneration.from_pretrained(str(model_path), convert_from_hf=True)
    model.config._attn_implementation = "flashmask"
    model.visual.config._attn_implementation = "flashmask"
    model.eval()

    query = args.prompt.replace("<image>", "")
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
            max_new_tokens=args.max_new_tokens,
        )
    output_ids = outputs[0].tolist()[0]
    print(processor.decode(output_ids, skip_special_tokens=True))


if __name__ == "__main__":
    main()
