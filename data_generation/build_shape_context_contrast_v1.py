#!/usr/bin/env python3
"""Build matched long-context A/B pages from the locked generic Yi pair bank."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PAIR_BANK_REL = "assets/derived/yi_confusable_pairs_v3_coverage_floor.json"
PAIR_BANK_SHA256 = "cc9dd6cdfa38fd4ed03815fb2875d282a84a3e8141e47948864cf4bd47488455"
YI_TABLE_REL = "data/standards/nuosu_unicode.csv"
YI_TABLE_SHA256 = "ef2589900866c539273f478fbcd6fcd2a8fdc938674b561d6bccee7330647209"
FONT_RELS = (
    "assets/fonts/NotoSansNuosu-Regular.ttf",
    "assets/fonts/思源黑体彝文.ttf",
    "assets/fonts/方正彝文宋体.TTF",
    "assets/fonts/方正彝文手写体.TTF",
)
CONDITIONS = ("clear", "mild_old_print")
FONT_SIZES = (20, 24, 28, 32)
CANVAS_SIZE = (1024, 1024)
LINES_PER_PAGE = len(FONT_RELS) * len(CONDITIONS)
PAIR_COUNT = 2162
PAIR_STRIDE = 271
PROMPT = "<image>OCR:"
GENERATOR = "shape_context_contrast_v1/1.0"


class BuildError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def encode_png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=False, compress_level=6)
    return buffer.getvalue()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def load_pairs() -> list[dict[str, Any]]:
    path = PROJECT_ROOT / PAIR_BANK_REL
    if sha256_file(path) != PAIR_BANK_SHA256:
        raise BuildError("locked pair-bank SHA differs")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or len(value) != PAIR_COUNT:
        raise BuildError("locked pair bank does not contain 2,162 rows")
    return value


def load_yi() -> list[str]:
    path = PROJECT_ROOT / YI_TABLE_REL
    if sha256_file(path) != YI_TABLE_SHA256:
        raise BuildError("locked Yi-table SHA differs")
    with path.open(encoding="utf-8-sig") as handle:
        chars = [str(row["char"]) for row in csv.DictReader(handle) if row.get("char")]
    if len(chars) != 1165 or len(set(chars)) != 1165:
        raise BuildError("locked Yi table does not contain 1,165 unique characters")
    return chars


def paper_background(seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    width, height = CANVAS_SIZE
    base = float(rng.integers(244, 251))
    y = np.linspace(rng.uniform(-3, 3), rng.uniform(-3, 3), height, dtype=np.float32)[:, None]
    x = np.linspace(rng.uniform(-2, 2), rng.uniform(-2, 2), width, dtype=np.float32)[None, :]
    gray = base + y + x + rng.normal(0, 0.8, size=(height, width)).astype(np.float32)
    gray = np.clip(gray, 232, 255).astype(np.uint8)
    rgb = np.repeat(gray[:, :, None], 3, axis=2)
    rgb[:, :, 1] = np.clip(rgb[:, :, 1].astype(np.int16) - 1, 0, 255).astype(np.uint8)
    rgb[:, :, 2] = np.clip(rgb[:, :, 2].astype(np.int16) - 3, 0, 255).astype(np.uint8)
    return Image.fromarray(rgb, "RGB")


def context_line(
    pair_index: int,
    slot: int,
    yi: list[str],
    pair_chars: set[str],
    seed: int,
) -> tuple[list[str], int]:
    rng = np.random.default_rng(np.random.SeedSequence([seed, pair_index, slot, 17]))
    length = int(rng.integers(12, 21))
    target_position = int(rng.integers(4, length - 4))
    pool = [char for char in yi if char not in pair_chars]
    chars = [str(pool[int(index)]) for index in rng.integers(0, len(pool), size=length - 1)]
    chars.insert(target_position, "")
    return chars, target_position


def mild_old_print(patch: Image.Image) -> Image.Image:
    width, height = patch.size
    reduced = patch.resize((max(8, int(width * 0.92)), max(8, int(height * 0.92))), Image.Resampling.BILINEAR)
    restored = reduced.resize((width, height), Image.Resampling.BILINEAR)
    restored = restored.filter(ImageFilter.GaussianBlur(0.55))
    array = np.asarray(restored, dtype=np.float32)
    array = (array - 128.0) * 0.92 + 128.0
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), "RGB")


def draw_line_patch(
    background: Image.Image,
    line_y: int,
    chars: list[str],
    target_position: int,
    target_char: str,
    font: ImageFont.FreeTypeFont,
    font_size: int,
    condition: str,
) -> tuple[Image.Image, str, list[int]]:
    line_height = 90
    left, right = 52, CANVAS_SIZE[0] - 52
    top = line_y - line_height // 2
    bottom = top + line_height
    patch = background.crop((left, top, right, bottom))
    sequence = list(chars)
    sequence[target_position] = target_char
    cell_width = int(round(font_size * 1.15))
    total_width = len(sequence) * cell_width
    first_center = patch.width / 2 - total_width / 2 + cell_width / 2
    draw = ImageDraw.Draw(patch)
    target_box: list[int] | None = None
    for index, char in enumerate(sequence):
        box = draw.textbbox((0, 0), char, font=font)
        glyph_width = box[2] - box[0]
        glyph_height = box[3] - box[1]
        center_x = first_center + index * cell_width
        x = center_x - glyph_width / 2 - box[0]
        y = patch.height / 2 - glyph_height / 2 - box[1]
        draw.text((x, y), char, font=font, fill=(27, 27, 25))
        if index == target_position:
            target_box = [
                int(np.floor(left + x + box[0])),
                int(np.floor(top + y + box[1])),
                int(np.ceil(left + x + box[2])),
                int(np.ceil(top + y + box[3])),
            ]
    if target_box is None:
        raise BuildError("target glyph box was not recorded")
    if condition == "mild_old_print":
        patch = mild_old_print(patch)
    elif condition != "clear":
        raise BuildError(f"unknown condition: {condition}")
    image = background.copy()
    image.paste(patch, (left, top))
    return image, "".join(sequence), target_box


def changed_pixel_check(
    left_image: Image.Image,
    right_image: Image.Image,
    boxes: list[list[int]],
    expansion: int = 8,
) -> dict[str, Any]:
    left = np.asarray(left_image, dtype=np.int16)
    right = np.asarray(right_image, dtype=np.int16)
    changed = np.any(left != right, axis=2)
    allowed = np.zeros(changed.shape, dtype=bool)
    expanded: list[list[int]] = []
    for box in boxes:
        value = [
            max(0, box[0] - expansion),
            max(0, box[1] - expansion),
            min(CANVAS_SIZE[0], box[2] + expansion),
            min(CANVAS_SIZE[1], box[3] + expansion),
        ]
        expanded.append(value)
        allowed[value[1] : value[3], value[0] : value[2]] = True
    outside = changed & ~allowed
    if not changed.any():
        raise BuildError("matched A/B pages are pixel-identical")
    if outside.any():
        raise BuildError(f"{int(outside.sum())} changed pixels escape target neighborhoods")
    return {
        "changed_pixels": int(changed.sum()),
        "changed_pixels_outside_target_neighborhoods": 0,
        "target_neighborhoods": expanded,
    }


def build(output_dir: Path, page_pairs: int, seed: int) -> dict[str, Any]:
    if not 1 <= page_pairs <= 64:
        raise BuildError("the design-smoke generator is capped at 64 page pairs; formal scale requires a new locked authorization")
    if output_dir.exists():
        raise BuildError(f"output already exists: {output_dir}")
    stage = output_dir.with_name(f".{output_dir.name}.staging")
    if stage.exists():
        raise BuildError(f"staging output exists: {stage}")
    images_dir = stage / "images"
    images_dir.mkdir(parents=True)
    try:
        pairs = load_pairs()
        yi = load_yi()
        font_paths = [PROJECT_ROOT / rel for rel in FONT_RELS]
        if not all(path.is_file() for path in font_paths):
            raise BuildError("one or more locked Yi fonts are missing")
        input_rows: list[dict[str, Any]] = []
        pairing_rows: list[dict[str, Any]] = []
        image_hashes: set[str] = set()
        font_condition_counts: Counter[str] = Counter()
        pair_indices_seen: list[int] = []

        for page_index in range(page_pairs):
            background = paper_background(seed + page_index * 1009)
            variant_images = {"a": background.copy(), "b": background.copy()}
            variant_lines = {"a": [], "b": []}
            variant_boxes = {"a": [], "b": []}
            cells: list[dict[str, Any]] = []
            for slot in range(LINES_PER_PAGE):
                font_index = slot // len(CONDITIONS)
                condition_index = slot % len(CONDITIONS)
                condition = CONDITIONS[condition_index]
                pair_index = (page_index + slot * PAIR_STRIDE) % PAIR_COUNT
                pair = pairs[pair_index]
                a, b = str(pair["a"]), str(pair["b"])
                font_size = FONT_SIZES[(pair_index + font_index + condition_index) % len(FONT_SIZES)]
                font = ImageFont.truetype(str(font_paths[font_index]), font_size, index=0)
                chars, target_position = context_line(pair_index, slot, yi, {a, b}, seed)
                line_y = 98 + slot * 116
                line_record: dict[str, Any] = {
                    "line_index": slot,
                    "pair_index": pair_index,
                    "pair_source": str(pair.get("source", "unknown")),
                    "a": a,
                    "b": b,
                    "font_index": font_index,
                    "font": FONT_RELS[font_index],
                    "condition": condition,
                    "font_size": font_size,
                    "target_position": target_position,
                }
                for variant, target_char in (("a", a), ("b", b)):
                    rendered, text, target_box = draw_line_patch(
                        background,
                        line_y,
                        chars,
                        target_position,
                        target_char,
                        font,
                        font_size,
                        condition,
                    )
                    line_top = line_y - 45
                    line_bottom = line_top + 90
                    variant_images[variant].paste(rendered.crop((0, line_top, CANVAS_SIZE[0], line_bottom)), (0, line_top))
                    variant_lines[variant].append(text)
                    variant_boxes[variant].append(target_box)
                    line_record[f"{variant}_text"] = text
                    line_record[f"{variant}_target_box"] = target_box
                cells.append(line_record)
                pair_indices_seen.append(pair_index)
                font_condition_counts[f"font_{font_index}:{condition}"] += 1

            pixel_check = changed_pixel_check(
                variant_images["a"],
                variant_images["b"],
                variant_boxes["a"] + variant_boxes["b"],
            )
            variants: dict[str, Any] = {}
            for variant in ("a", "b"):
                sample_id = f"shape_context_smoke_{page_index:04d}_{variant}"
                image_rel = f"images/{sample_id}.png"
                png = encode_png(variant_images[variant])
                image_sha = sha256_bytes(png)
                if image_sha in image_hashes:
                    raise BuildError(f"duplicate image SHA: {sample_id}")
                image_hashes.add(image_sha)
                (stage / image_rel).write_bytes(png)
                target = "\n".join(variant_lines[variant]) + "\n"
                input_rows.append(
                    {
                        "id": sample_id,
                        "images": [image_rel],
                        "messages": [
                            {"role": "user", "content": PROMPT},
                            {"role": "assistant", "content": target},
                        ],
                        "meta": {
                            "source_kind": "synthetic",
                            "source_id": "shape_context_contrast_v1_smoke",
                            "role": "training_design_smoke_not_training_authorization",
                            "page_pair_index": page_index,
                            "variant": variant,
                            "generator": GENERATOR,
                        },
                    }
                )
                variants[variant] = {
                    "id": sample_id,
                    "image": image_rel,
                    "image_sha256": image_sha,
                    "target_sha256": hashlib.sha256(target.encode("utf-8")).hexdigest(),
                }
            pairing_rows.append(
                {
                    "page_pair_index": page_index,
                    "variants": variants,
                    "cells": cells,
                    "pixel_check": pixel_check,
                }
            )

        input_path = stage / "input.jsonl"
        pairing_path = stage / "pairing_metadata.jsonl"
        write_jsonl(input_path, input_rows)
        write_jsonl(pairing_path, pairing_rows)
        manifest = {
            "schema": GENERATOR,
            "generator_sha256": sha256_file(Path(__file__).resolve()),
            "status": "PASS_SHAPE_CONTEXT_CONTRAST_STRUCTURE_BUILD",
            "role": "training_design_smoke_only_not_formal_build_or_training_authorization",
            "evaluation_inputs_read": False,
            "real_images_read": False,
            "seed": seed,
            "page_pairs": page_pairs,
            "images": len(input_rows),
            "lines_per_image": LINES_PER_PAGE,
            "matched_cells": page_pairs * LINES_PER_PAGE,
            "a_target_occurrences": page_pairs * LINES_PER_PAGE,
            "b_target_occurrences": page_pairs * LINES_PER_PAGE,
            "unique_pair_indices": len(set(pair_indices_seen)),
            "font_condition_counts": dict(sorted(font_condition_counts.items())),
            "full_build_projection": {
                "page_pairs": PAIR_COUNT,
                "images": PAIR_COUNT * 2,
                "pair_font_condition_cells": PAIR_COUNT * len(FONT_RELS) * len(CONDITIONS),
            },
            "inputs": {
                "pair_bank": {"path": PAIR_BANK_REL, "sha256": sha256_file(PROJECT_ROOT / PAIR_BANK_REL)},
                "yi_table": {"path": YI_TABLE_REL, "sha256": sha256_file(PROJECT_ROOT / YI_TABLE_REL)},
                "fonts": [{"path": rel, "sha256": sha256_file(PROJECT_ROOT / rel)} for rel in FONT_RELS],
            },
            "outputs": {
                "input.jsonl": {"rows": len(input_rows), "sha256": sha256_file(input_path)},
                "pairing_metadata.jsonl": {"rows": len(pairing_rows), "sha256": sha256_file(pairing_path)},
            },
        }
        (stage / "build_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        stage.rename(output_dir)
        return manifest
    except BaseException:
        if stage.exists():
            shutil.rmtree(stage)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--page-pairs", type=int, default=4)
    parser.add_argument("--seed", type=int, default=97)
    args = parser.parse_args()
    manifest = build(args.output.resolve(), args.page_pairs, args.seed)
    print(json.dumps({"status": manifest["status"], "images": manifest["images"], "matched_cells": manifest["matched_cells"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
