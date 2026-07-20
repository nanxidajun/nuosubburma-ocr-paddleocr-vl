#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build deterministic Post-V3 Latin and residual-ink addon rows.

The generator reads only the frozen V3 Yi/Han tables, registered fonts, and
programmatic ASCII rules. It never reads historical patch rows, model output,
real documents, or evaluation material. Formal 400/80 and 200/40-pair counts
require the independent post-V3 owner authorization lock.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import os
import shutil
import string
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

import build_synth_layout_post_v3 as core


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_VERSION = "build_post_v3_addons/1.0"
GENERATOR_REL = "scripts/build_post_v3_addons.py"
SOURCE_ID = "normative_synthetic_post_v3_addons"
FORMAL_AUTHORIZATION_REL = "POST_V3_AUTHORIZATION.json"
FORMAL_SPEC_REL = "POST_V3_FORMAL_SPEC.json"
PROMPT = core.USER_PROMPT

TEMPLATE_WEIGHTS = {
    "general_word_shape": 0.65,
    "name_shape": 0.15,
    "year_number": 0.10,
    "abbreviation_code": 0.10,
}
ENVIRONMENT_WEIGHTS = {
    "pure_latin": 0.20,
    "yi_latin": 0.40,
    "yi_han_latin": 0.40,
}
GRANULARITY_WEIGHTS = {"line": 0.40, "region": 0.60}
RESIDUAL_TYPES = ("external_residual", "true_glyph_degradation")
ASCII_UPPER = string.ascii_uppercase
ASCII_LOWER = string.ascii_lowercase
ASCII_LETTERS = set(ASCII_UPPER + ASCII_LOWER)
ASCII_ALLOWED = set(string.ascii_letters + string.digits + " .,-/():")


class SmokeError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def weighted_counts(total: int, weights: dict[str, float]) -> dict[str, int]:
    if total <= 0:
        raise SmokeError("weighted count total must be positive")
    keys = list(weights)
    values = np.array([weights[key] for key in keys], dtype=float)
    if np.any(values < 0) or float(values.sum()) <= 0:
        raise SmokeError("weights must be non-negative with a positive sum")
    raw = values / values.sum() * total
    counts = np.floor(raw).astype(int)
    for index in np.argsort(-(raw - counts))[: total - int(counts.sum())]:
        counts[int(index)] += 1
    return {key: int(count) for key, count in zip(keys, counts)}


def exact_values(total: int, weights: dict[str, float], rng: np.random.Generator) -> list[str]:
    values = [
        value
        for value, count in weighted_counts(total, weights).items()
        for _ in range(count)
    ]
    order = rng.permutation(len(values))
    return [values[int(index)] for index in order]


def random_chars(pool: list[str], low: int, high: int, rng: np.random.Generator) -> str:
    count = int(rng.integers(low, high + 1))
    return "".join(pool[int(index)] for index in rng.integers(0, len(pool), size=count))


def lower_token(rng: np.random.Generator, anchor: str | None = None) -> str:
    size = int(rng.integers(3, 10))
    token = "".join(ASCII_LOWER[int(index)] for index in rng.integers(0, 26, size=size))
    return (anchor + token[1:]) if anchor else token


def latin_segment(
    template: str,
    rng: np.random.Generator,
    lower_anchor: str | None = None,
    upper_anchors: str = "",
) -> str:
    if template == "general_word_shape":
        words = [lower_token(rng, lower_anchor)]
        words.extend(lower_token(rng) for _ in range(int(rng.integers(0, 3))))
        pattern = int(rng.integers(0, 5))
        if pattern == 1:
            return f"({' '.join(words)})"
        if pattern == 2 and len(words) > 1:
            return "-".join(words)
        if pattern == 3:
            return " ".join(words) + "."
        if pattern == 4 and len(words) > 1:
            return f"{words[0]}, {' '.join(words[1:])}"
        return " ".join(words)
    if template == "name_shape":
        initials = list(upper_anchors) or [ASCII_UPPER[int(rng.integers(0, 26))]]
        while len(initials) < int(rng.integers(1, 3)):
            initials.append(ASCII_UPPER[int(rng.integers(0, 26))])
        return " ".join(initial + lower_token(rng) for initial in initials)
    if template == "year_number":
        year = int(rng.integers(1900, 2101))
        number = int(rng.integers(1, 500))
        patterns = (f"No.{number} ({year})", f"p.{number} {year}", f"Vol.{int(rng.integers(1, 31))} {year}", f"{year}-{number}")
        return patterns[int(rng.integers(0, len(patterns)))]
    if template == "abbreviation_code":
        prefix = upper_anchors or "".join(
            ASCII_UPPER[int(index)] for index in rng.integers(0, 26, size=int(rng.integers(2, 6)))
        )
        while len(prefix) < 2:
            prefix += ASCII_UPPER[int(rng.integers(0, 26))]
        suffixes = ("", f"-{int(rng.integers(1, 100))}", f"/{int(rng.integers(1, 10))}")
        return prefix + suffixes[int(rng.integers(0, len(suffixes)))]
    raise SmokeError(f"unknown Latin template: {template}")


def build_latin_plan(total: int, rng: np.random.Generator) -> list[dict[str, Any]]:
    if total < 52:
        raise SmokeError("Latin smoke needs at least 52 rows for explicit A-Z/a-z coverage")
    templates = exact_values(total, TEMPLATE_WEIGHTS, rng)
    environments = exact_values(total, ENVIRONMENT_WEIGHTS, rng)
    granularities = exact_values(total, GRANULARITY_WEIGHTS, rng)
    plan = [
        {"template": template, "environment": environment, "granularity": granularity}
        for template, environment, granularity in zip(templates, environments, granularities)
    ]
    lower_indexes = [i for i, row in enumerate(plan) if row["template"] == "general_word_shape"]
    upper_indexes = [i for i, row in enumerate(plan) if row["template"] in {"name_shape", "abbreviation_code"}]
    if len(lower_indexes) < 26 or not upper_indexes:
        raise SmokeError("Latin template plan cannot carry explicit alphabet coverage")
    for index, anchor in zip(lower_indexes, ASCII_LOWER):
        plan[index]["lower_anchor"] = anchor
    upper_groups = [[] for _ in upper_indexes]
    for offset, anchor in enumerate(ASCII_UPPER):
        upper_groups[offset % len(upper_groups)].append(anchor)
    for index, anchors in zip(upper_indexes, upper_groups):
        plan[index]["upper_anchors"] = "".join(anchors)
    return plan


def latin_lines(
    plan: dict[str, Any],
    yi: list[str],
    han: list[str],
    rng: np.random.Generator,
) -> list[list[tuple[str, str]]]:
    line_count = 1 if plan["granularity"] == "line" else int(rng.integers(2, 6))
    lines: list[list[tuple[str, str]]] = []
    for line_index in range(line_count):
        latin = latin_segment(
            str(plan["template"]),
            rng,
            str(plan.get("lower_anchor")) if line_index == 0 and plan.get("lower_anchor") else None,
            str(plan.get("upper_anchors", "")) if line_index == 0 else "",
        )
        environment = str(plan["environment"])
        if environment == "pure_latin":
            runs = [("latin", latin)]
        elif environment == "yi_latin":
            runs = [("yi", random_chars(yi, 3, 9, rng)), ("latin", latin)]
        elif environment == "yi_han_latin":
            runs = [
                ("yi", random_chars(yi, 3, 8, rng)),
                ("han", random_chars(han, 3, 8, rng)),
                ("latin", latin),
            ]
        else:
            raise SmokeError(f"unknown Latin environment: {environment}")
        order = rng.permutation(len(runs))
        lines.append([runs[int(index)] for index in order])
    return lines


def draw_lines(
    lines: list[list[tuple[str, str]]],
    fonts: core.FontBook,
    rng: np.random.Generator,
) -> tuple[Image.Image, Image.Image, str, list[dict[str, Any]]]:
    size = int(rng.integers(30, 47))
    tracking = float(rng.uniform(0.01, 0.11) * size)
    margin = int(rng.integers(34, 65))
    line_step = int(size * rng.uniform(1.45, 1.75))
    target_lines = [" ".join(text for _script, text in runs) for runs in lines]
    width_units = max(len(line) for line in target_lines)
    width = max(360, int(margin * 2 + width_units * size * 1.08))
    height = max(120, margin * 2 + line_step * len(lines))
    image = core.paper_background(width, height, rng)
    glyph_mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(image)
    mask_draw = ImageDraw.Draw(glyph_mask)
    rendered: list[dict[str, Any]] = []
    for line_index, runs in enumerate(lines):
        x = float(margin + rng.uniform(0, 8))
        y = float(margin + line_index * line_step + rng.uniform(-1.0, 1.0))
        line_meta: list[dict[str, Any]] = []
        for run_index, (script, text) in enumerate(runs):
            if run_index:
                x += size * rng.uniform(0.55, 0.95)
            start_x = x
            for char in text:
                font = fonts.pick(char, size, rng)
                if font is None:
                    raise SmokeError(f"no locked font covers U+{ord(char):04X} {char!r}")
                shade = int(rng.integers(15, 56))
                draw.text((x, y), char, font=font, fill=(shade, shade, shade))
                mask_draw.text((x, y), char, font=font, fill=255)
                x += float(font.getlength(char) + tracking)
            line_meta.append({"script": script, "text": text, "x": start_x, "end_x": x})
        if x > width - margin / 2:
            raise SmokeError("rendered line exceeds its deterministic canvas")
        rendered.append({"line_index": line_index, "runs": line_meta})
    return image, glyph_mask, "\n".join(target_lines) + "\n", rendered


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False)
    return buffer.getvalue()


def add_external_residual(
    image: Image.Image,
    glyph_mask: Image.Image,
    rng: np.random.Generator,
) -> tuple[Image.Image, dict[str, Any]]:
    desired = int(rng.integers(10, 19))
    variant = image.copy()
    glyph = np.asarray(glyph_mask) > 0
    occupied = np.zeros_like(glyph)
    focus = glyph_mask.getbbox() or (10, 10, image.width - 10, image.height - 10)
    left = max(8, focus[0] - 18)
    top = max(8, focus[1] - 18)
    right = min(image.width - 9, focus[2] + 18)
    bottom = min(image.height - 9, focus[3] + 18)
    marks: list[dict[str, Any]] = []
    for _ in range(2400):
        if len(marks) == desired:
            break
        x = int(rng.integers(left, right + 1))
        y = int(rng.integers(top, bottom + 1))
        radius_x = int(rng.integers(1, 6))
        radius_y = int(rng.integers(1, 5))
        shape = Image.new("L", image.size, 0)
        shape_draw = ImageDraw.Draw(shape)
        bbox = (x - radius_x, y - radius_y, x + radius_x, y + radius_y)
        shape_draw.ellipse(bbox, fill=255)
        active = np.asarray(shape) > 0
        if np.any(active & glyph) or np.any(active & occupied):
            continue
        occupied |= active
        shade = int(rng.integers(30, 116))
        ImageDraw.Draw(variant).ellipse(bbox, fill=(shade, shade, shade))
        marks.append({"bbox": list(bbox), "shade": shade})
    if len(marks) != desired:
        raise SmokeError(f"could not place exact external residual count {desired}")
    if int(np.count_nonzero(occupied & glyph)) != 0:
        raise SmokeError("external residual overlaps rendered glyph pixels")
    return variant, {
        "mark_count": desired,
        "marks": marks,
        "glyph_overlap_pixels": 0,
        "placement": "near_text_negative_space",
    }


def degrade_true_glyphs(
    image: Image.Image,
    glyph_mask: Image.Image,
    rng: np.random.Generator,
) -> tuple[Image.Image, dict[str, Any]]:
    radius = float(rng.uniform(0.7, 1.0))
    contrast = float(rng.uniform(0.72, 0.88))
    variant = image.filter(ImageFilter.GaussianBlur(radius))
    variant = ImageEnhance.Contrast(variant).enhance(contrast)
    clean_gray = np.asarray(image.convert("L"), dtype=np.int16)
    variant_gray = np.asarray(variant.convert("L"), dtype=np.int16)
    glyph = np.asarray(glyph_mask) > 0
    changed = int(np.count_nonzero((np.abs(clean_gray - variant_gray) >= 2) & glyph))
    background = float(np.median(variant_gray[~glyph]))
    ink = float(np.percentile(variant_gray[glyph], 25))
    readability_contrast = background - ink
    if changed <= 0 or readability_contrast < 40.0:
        raise SmokeError("true-glyph degradation failed its readability floor")
    return variant, {
        "blur_radius": radius,
        "contrast": contrast,
        "changed_glyph_pixels": changed,
        "readability_contrast": readability_contrast,
        "readability_floor": 40.0,
    }


def write_image(stage: Path, relative: str, image: Image.Image) -> dict[str, Any]:
    data = png_bytes(image)
    path = stage / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"path": relative, "sha256": sha256_bytes(data), "size": [image.width, image.height]}


def build_latin_rows(
    split: str,
    total: int,
    seed: np.random.SeedSequence,
    stage: Path,
    fonts: core.FontBook,
    yi: list[str],
    han: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    plan_seed, sample_seed = seed.spawn(2)
    plan = build_latin_plan(total, np.random.default_rng(plan_seed))
    rows: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    for index, (item, state) in enumerate(zip(plan, sample_seed.spawn(total))):
        text_seed, render_seed = state.spawn(2)
        lines = latin_lines(item, yi, han, np.random.default_rng(text_seed))
        image, _mask, target, rendered = draw_lines(lines, fonts, np.random.default_rng(render_seed))
        row_id = f"postv3_{split}_latin_{index:04d}"
        image_meta = write_image(stage, f"images/{split}/latin/{row_id}.png", image)
        meta = {
            "id": row_id,
            "split": split,
            "family": "latin_retention",
            "template": item["template"],
            "environment": item["environment"],
            "granularity": item["granularity"],
            "target": target,
            "rendered_lines": rendered,
            "alphabet_anchors": {
                "lower": item.get("lower_anchor", ""),
                "upper": item.get("upper_anchors", ""),
            },
            "image": image_meta,
            "source_id": SOURCE_ID,
            "generator": GENERATOR_VERSION,
        }
        rows.append({
            "id": row_id,
            "images": [image_meta["path"]],
            "messages": [
                {"role": "user", "content": PROMPT},
                {"role": "assistant", "content": target},
            ],
            "meta": {
                "source_kind": "synthetic",
                "source_id": SOURCE_ID,
                "family": "latin_retention",
                "environment": item["environment"],
                "granularity": item["granularity"],
                "latin_template": item["template"],
                "generator": GENERATOR_VERSION,
            },
        })
        metadata.append(meta)
    return rows, metadata


def residual_lines(yi: list[str], han: list[str], rng: np.random.Generator) -> list[list[tuple[str, str]]]:
    lines: list[list[tuple[str, str]]] = []
    for _ in range(int(rng.integers(2, 5))):
        runs = [
            ("yi", random_chars(yi, 5, 11, rng)),
            ("han", random_chars(han, 4, 9, rng)),
        ]
        if rng.random() < 0.5:
            runs.reverse()
        lines.append(runs)
    return lines


def build_residual_rows(
    split: str,
    pairs: int,
    seed: np.random.SeedSequence,
    stage: Path,
    fonts: core.FontBook,
    yi: list[str],
    han: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if pairs < 2 or pairs % 2:
        raise SmokeError("residual smoke pair count must be an even number of at least two")
    type_plan = exact_values(pairs, {name: 1.0 for name in RESIDUAL_TYPES}, np.random.default_rng(seed.spawn(1)[0]))
    rows: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    for index, (pair_type, state) in enumerate(zip(type_plan, seed.spawn(pairs))):
        text_seed, render_seed, variant_seed = state.spawn(3)
        lines = residual_lines(yi, han, np.random.default_rng(text_seed))
        clear, glyph_mask, target, rendered = draw_lines(lines, fonts, np.random.default_rng(render_seed))
        pair_id = f"postv3_{split}_residual_{index:04d}"
        glyph_mask_meta = write_image(
            stage,
            f"audit_masks/{split}/{pair_id}_glyph_mask.png",
            glyph_mask,
        )
        variant_rng = np.random.default_rng(variant_seed)
        if pair_type == "external_residual":
            variant, variant_meta = add_external_residual(clear, glyph_mask, variant_rng)
        else:
            variant, variant_meta = degrade_true_glyphs(clear, glyph_mask, variant_rng)
        for role, image in (("clear", clear), ("variant", variant)):
            row_id = f"{pair_id}_{role}"
            image_meta = write_image(stage, f"images/{split}/residual/{row_id}.png", image)
            record = {
                "id": row_id,
                "split": split,
                "family": "residual_pair",
                "pair_id": pair_id,
                "pair_type": pair_type,
                "pair_role": role,
                "environment": "yi_han",
                "granularity": "region",
                "target": target,
                "rendered_lines": rendered,
                "glyph_mask": glyph_mask_meta,
                "variant_metadata": variant_meta if role == "variant" else {},
                "image": image_meta,
                "source_id": SOURCE_ID,
                "generator": GENERATOR_VERSION,
            }
            rows.append({
                "id": row_id,
                "images": [image_meta["path"]],
                "messages": [
                    {"role": "user", "content": PROMPT},
                    {"role": "assistant", "content": target},
                ],
                "meta": {
                    "source_kind": "synthetic",
                    "source_id": SOURCE_ID,
                    "family": "residual_pair",
                    "pair_id": pair_id,
                    "pair_type": pair_type,
                    "pair_role": role,
                    "environment": "yi_han",
                    "granularity": "region",
                    "variant_metadata": variant_meta if role == "variant" else {},
                    "generator": GENERATOR_VERSION,
                },
            })
            metadata.append(record)
    return rows, metadata


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")


def validate_split(
    split: str,
    rows: list[dict[str, Any]],
    metadata: list[dict[str, Any]],
    latin_n: int,
    residual_pairs: int,
    yi: set[str],
    han: set[str],
    stage: Path,
) -> dict[str, Any]:
    if len(rows) != latin_n + residual_pairs * 2 or len(metadata) != len(rows):
        raise SmokeError(f"{split} row count differs from the requested smoke plan")
    if len({row["id"] for row in rows}) != len(rows):
        raise SmokeError(f"{split} contains duplicate row ids")
    allowed = yi | han | ASCII_ALLOWED | {"\n"}
    image_hashes: set[str] = set()
    latin_upper: set[str] = set()
    latin_lower: set[str] = set()
    pairs: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row, meta in zip(rows, metadata):
        target = row["messages"][1]["content"]
        if target != meta["target"] or not target.endswith("\n"):
            raise SmokeError(f"target mismatch: {row['id']}")
        unexpected = set(target) - allowed
        if unexpected:
            raise SmokeError(f"target contains characters outside registered pools: {unexpected}")
        image_path = stage / row["images"][0]
        actual_sha = sha256_file(image_path)
        if actual_sha != meta["image"]["sha256"] or actual_sha in image_hashes:
            raise SmokeError(f"missing, changed, or duplicate image: {row['id']}")
        image_hashes.add(actual_sha)
        with Image.open(image_path) as image:
            low, high = image.convert("L").getextrema()
            if low > 220 or high < 225:
                raise SmokeError(f"blank or invalid image: {row['id']}")
        if meta["family"] == "latin_retention":
            latin_upper |= set(target) & set(ASCII_UPPER)
            latin_lower |= set(target) & set(ASCII_LOWER)
        else:
            pairs[meta["pair_id"]].append(meta)
    if latin_upper != set(ASCII_UPPER) or latin_lower != set(ASCII_LOWER):
        raise SmokeError(f"{split} Latin alphabet coverage is incomplete")
    pair_types: Counter[str] = Counter()
    for pair_id, pair_rows in pairs.items():
        if len(pair_rows) != 2 or {row["pair_role"] for row in pair_rows} != {"clear", "variant"}:
            raise SmokeError(f"invalid residual roles: {pair_id}")
        clear = next(row for row in pair_rows if row["pair_role"] == "clear")
        variant = next(row for row in pair_rows if row["pair_role"] == "variant")
        if clear["target"].encode("utf-8") != variant["target"].encode("utf-8"):
            raise SmokeError(f"residual targets differ bytewise: {pair_id}")
        if clear["glyph_mask"] != variant["glyph_mask"]:
            raise SmokeError(f"residual pair glyph-mask provenance differs: {pair_id}")
        mask_path = stage / clear["glyph_mask"]["path"]
        if sha256_file(mask_path) != clear["glyph_mask"]["sha256"]:
            raise SmokeError(f"residual pair glyph mask changed: {pair_id}")
        clear_pixels = np.asarray(Image.open(stage / clear["image"]["path"]).convert("L"), dtype=np.int16)
        variant_pixels = np.asarray(Image.open(stage / variant["image"]["path"]).convert("L"), dtype=np.int16)
        glyph_pixels = np.asarray(Image.open(mask_path).convert("L")) > 0
        changed_pixels = np.abs(clear_pixels - variant_pixels) >= 1
        if not np.any(changed_pixels):
            raise SmokeError(f"residual pair images are identical: {pair_id}")
        pair_types[str(clear["pair_type"])] += 1
        if clear["pair_type"] == "external_residual":
            info = variant["variant_metadata"]
            if not 10 <= int(info["mark_count"]) <= 18 or int(info["glyph_overlap_pixels"]) != 0:
                raise SmokeError(f"external residual gate failed: {pair_id}")
            if np.any(changed_pixels & glyph_pixels):
                raise SmokeError(f"external residual changes glyph pixels: {pair_id}")
        else:
            info = variant["variant_metadata"]
            if not 0.7 <= float(info["blur_radius"]) <= 1.0 or not 0.72 <= float(info["contrast"]) <= 0.88:
                raise SmokeError(f"true-glyph parameter gate failed: {pair_id}")
            if not np.any(changed_pixels & glyph_pixels):
                raise SmokeError(f"true-glyph degradation misses glyph pixels: {pair_id}")
    expected_pair_types = {name: residual_pairs // 2 for name in RESIDUAL_TYPES}
    if dict(pair_types) != expected_pair_types:
        raise SmokeError(f"{split} residual type counts differ: {dict(pair_types)}")
    latin_meta = [row for row in metadata if row["family"] == "latin_retention"]
    return {
        "rows": len(rows),
        "latin_rows": len(latin_meta),
        "residual_pairs": len(pairs),
        "residual_rows": len(pairs) * 2,
        "latin_templates": dict(sorted(Counter(row["template"] for row in latin_meta).items())),
        "latin_environments": dict(sorted(Counter(row["environment"] for row in latin_meta).items())),
        "latin_granularities": dict(sorted(Counter(row["granularity"] for row in latin_meta).items())),
        "residual_pair_types": dict(sorted(pair_types.items())),
        "uppercase_coverage": ASCII_UPPER,
        "lowercase_coverage": ASCII_LOWER,
        "unique_image_hashes": len(image_hashes),
    }


def build_review(stage: Path, metadata: list[dict[str, Any]]) -> None:
    latin = [row for row in metadata if row["family"] == "latin_retention"]
    selected_latin: list[dict[str, Any]] = []
    for environment in ENVIRONMENT_WEIGHTS:
        pool = [row for row in latin if row["environment"] == environment]
        selected_latin.extend(pool[: min(8, len(pool))])
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in metadata:
        if row["family"] == "residual_pair":
            grouped[row["pair_id"]].append(row)
    latin_cards = "".join(
        f'<article><header><b>{html.escape(row["environment"])}</b><span>{html.escape(row["template"])}</span></header><img src="{html.escape(row["image"]["path"])}"><pre>{html.escape(row["target"])}</pre></article>'
        for row in selected_latin
    )
    residual_cards: list[str] = []
    for pair_id, pair in sorted(grouped.items()):
        clear = next(row for row in pair if row["pair_role"] == "clear")
        variant = next(row for row in pair if row["pair_role"] == "variant")
        residual_cards.append(
            f'<article class="pair"><header><b>{html.escape(pair_id)}</b><span>{html.escape(clear["pair_type"])}</span></header><div><figure><figcaption>clean</figcaption><img src="{html.escape(clear["image"]["path"])}"></figure><figure><figcaption>variant</figcaption><img src="{html.escape(variant["image"]["path"])}"></figure></div><pre>{html.escape(clear["target"])}</pre></article>'
        )
    document = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Post-V3 addons smoke</title><style>@font-face{{font-family:Nuosu;src:url('../../assets/fonts/NotoSansNuosu-Regular.ttf')}}*{{box-sizing:border-box}}body{{margin:0;background:#f3f4f3;color:#171918;font:14px/1.5 system-ui,sans-serif;letter-spacing:0}}main{{max-width:1680px;margin:auto;padding:18px}}h1{{font-size:22px;margin:0 0 6px}}h2{{font-size:18px;margin:26px 0 10px}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}}article{{background:#fff;border:1px solid #ccd1cf;border-radius:6px;overflow:hidden}}header{{display:flex;justify-content:space-between;padding:9px 11px;border-bottom:1px solid #dde1df}}article>img,figure img{{display:block;width:100%;height:210px;object-fit:contain;background:#eee}}pre{{margin:0;padding:10px 11px;white-space:pre-wrap;overflow-wrap:anywhere;font:15px/1.55 Nuosu,ui-monospace,monospace}}.pair{{grid-column:span 2}}.pair>div{{display:grid;grid-template-columns:1fr 1fr}}figure{{margin:0}}figcaption{{padding:6px 10px;background:#f2f3f2}}@media(max-width:760px){{.pair{{grid-column:span 1}}.pair>div{{grid-template-columns:1fr}}}}</style></head><body><main><h1>Post-V3 本地 smoke</h1><p>Latin 三种环境与成对残墨。所有文本和图像均为程序生成。</p><h2>Latin</h2><section class="grid">{latin_cards}</section><h2>残墨</h2><section class="grid">{''.join(residual_cards)}</section></main></body></html>'''
    (stage / "review.html").write_text(document, encoding="utf-8")


def manifest_inputs(include_formal_locks: bool = False) -> list[dict[str, Any]]:
    paths = [
        core.YI_UNICODE_REL,
        core.HAN_LEVEL1_REL,
        *core.YI_FONT_RELS,
        *core.CJK_FONT_RELS,
        core.GENERATOR_REL,
        GENERATOR_REL,
    ]
    inputs = [
        {"path": path, "sha256": sha256_file(PROJECT_ROOT / path)}
        for path in paths
    ]
    if include_formal_locks:
        inputs.extend(
            {
                "path": path,
                "sha256": sha256_file(PROJECT_ROOT / path),
            }
            for path in (FORMAL_SPEC_REL, FORMAL_AUTHORIZATION_REL)
        )
    return inputs


def require_formal_authorization() -> None:
    path = PROJECT_ROOT / FORMAL_AUTHORIZATION_REL
    if not path.is_file():
        raise SmokeError("formal post-V3 addon build lacks owner authorization")
    authorization = json.loads(path.read_text(encoding="utf-8"))
    if authorization.get("phase") != "formal_build_authorized":
        raise SmokeError("post-V3 authorization phase is not formal_build_authorized")
    if authorization.get("formal_build") is not True:
        raise SmokeError("post-V3 formal build is not authorized")


def build(args: argparse.Namespace) -> Path:
    requested = (
        args.latin_train_n,
        args.latin_dev_n,
        args.residual_train_pairs,
        args.residual_dev_pairs,
    )
    limits = (400, 80, 200, 40)
    if any(value <= 0 or value > limit for value, limit in zip(requested, limits)):
        raise SmokeError(f"addon counts exceed registered limits: {requested}")
    is_formal = requested == limits
    if is_formal:
        require_formal_authorization()
    output = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir
    output = output.resolve()
    output.relative_to((PROJECT_ROOT / ("builds" if is_formal else "probes")).resolve())
    stage = output.parent / f".{output.name}.staging"
    if output.exists() or stage.exists():
        raise SmokeError(f"refusing to overwrite existing smoke or staging path: {output}")
    stage.mkdir(parents=True)
    try:
        _yi_rows, yi, han = core.load_charsets()
        fonts = core.FontBook()
        root = np.random.SeedSequence(args.seed)
        train_latin_seed, dev_latin_seed, train_residual_seed, dev_residual_seed = root.spawn(4)
        train_latin, train_latin_meta = build_latin_rows("train", args.latin_train_n, train_latin_seed, stage, fonts, yi, han)
        dev_latin, dev_latin_meta = build_latin_rows("dev", args.latin_dev_n, dev_latin_seed, stage, fonts, yi, han)
        train_residual, train_residual_meta = build_residual_rows("train", args.residual_train_pairs, train_residual_seed, stage, fonts, yi, han)
        dev_residual, dev_residual_meta = build_residual_rows("dev", args.residual_dev_pairs, dev_residual_seed, stage, fonts, yi, han)
        train_rows = train_latin + train_residual
        dev_rows = dev_latin + dev_residual
        train_meta = train_latin_meta + train_residual_meta
        dev_meta = dev_latin_meta + dev_residual_meta
        train_summary = validate_split("train", train_rows, train_meta, args.latin_train_n, args.residual_train_pairs, set(yi), set(han), stage)
        dev_summary = validate_split("dev", dev_rows, dev_meta, args.latin_dev_n, args.residual_dev_pairs, set(yi), set(han), stage)
        train_targets = {row["messages"][1]["content"] for row in train_rows}
        dev_targets = {row["messages"][1]["content"] for row in dev_rows}
        if train_targets & dev_targets:
            raise SmokeError("train/dev smoke target overlap is not zero")
        write_jsonl(stage / "jsonl/train_addons.jsonl", train_rows)
        write_jsonl(stage / "jsonl/dev_addons.jsonl", dev_rows)
        write_jsonl(stage / "metadata/train.jsonl", train_meta)
        write_jsonl(stage / "metadata/dev.jsonl", dev_meta)
        build_review(stage, train_meta + dev_meta)
        manifest = {
            "schema": "post_v3_addons/1.0",
            "status": "PASS_FORMAL_ADDONS" if is_formal else "PASS_LOCAL_SMOKE_NOT_FORMAL_BUILD",
            "build_id": output.name,
            "seed": args.seed,
            "generator": GENERATOR_VERSION,
            "data_boundary": "v3_normative_tables_registered_fonts_and_programmatic_ascii_only_no_eval_or_model_selection",
            "formal_counts_authorized": is_formal,
            "counts": {"train": train_summary, "dev": dev_summary},
            "contracts": {
                "latin_environments": list(ENVIRONMENT_WEIGHTS),
                "latin_templates": TEMPLATE_WEIGHTS,
                "residual_external_marks": [10, 18],
                "external_residual_glyph_overlap_pixels": 0,
                "true_glyph_blur": [0.7, 1.0],
                "true_glyph_contrast": [0.72, 0.88],
                "paired_target_byte_identity": True,
                "train_dev_target_overlap": 0,
            },
            "inputs": manifest_inputs(include_formal_locks=is_formal),
            "outputs": {},
        }
        for relative in (
            "jsonl/train_addons.jsonl",
            "jsonl/dev_addons.jsonl",
            "metadata/train.jsonl",
            "metadata/dev.jsonl",
            "review.html",
        ):
            manifest["outputs"][relative] = {"sha256": sha256_file(stage / relative)}
        (stage / "build_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(stage, output)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("probes/post_v3_addons_smoke_seed23"))
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--latin-train-n", type=int, default=80)
    parser.add_argument("--latin-dev-n", type=int, default=80)
    parser.add_argument("--residual-train-pairs", type=int, default=12)
    parser.add_argument("--residual-dev-pairs", type=int, default=12)
    return parser.parse_args()


def main() -> int:
    output = build(parse_args())
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
