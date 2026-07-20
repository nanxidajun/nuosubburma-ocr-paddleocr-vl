#!/usr/bin/env python3
"""Derive the accepted CNN r2 Nuosu shape-pair bank from locked inputs."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ALGORITHM_VERSION = "blind_multifont_v2"
SHAPE_FEATURE_SIZES = (28, 36, 46)
SHAPE_VIEW_COUNT_PER_SIZE = 5
CLUSTER_TOP_K = 6
CLUSTER_MIN_FONT_SUPPORT = 2
FONT_SPECIFIC_MIN_VIEW_RATIO = 0.80
FONT_SPECIFIC_MIN_CLEAN_SIZES = 2
EXPECTED_PAIR_COUNT = 2121
EXPECTED_SHAPE_PAIRS_SHA256 = (
    "e43967adc60961f3b93cedc44fd9299f8bf0cb8daa34923609ca23f98a1ade0b"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_shape_pairs(path: Path, pairs: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(pairs, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def center_ink_mask(mask: np.ndarray) -> np.ndarray:
    total = float(mask.sum())
    if total <= 0:
        return mask
    height, width = mask.shape
    y_coords, x_coords = np.indices(mask.shape)
    center_x = float((mask * x_coords).sum()) / total
    center_y = float((mask * y_coords).sum()) / total
    shift_x = round((width - 1) / 2 - center_x)
    shift_y = round((height - 1) / 2 - center_y)

    shifted = np.zeros_like(mask)
    src_x1 = max(0, -shift_x)
    src_x2 = min(width, width - shift_x)
    src_y1 = max(0, -shift_y)
    src_y2 = min(height, height - shift_y)
    dst_x1 = max(0, shift_x)
    dst_y1 = max(0, shift_y)
    shifted[
        dst_y1 : dst_y1 + (src_y2 - src_y1),
        dst_x1 : dst_x1 + (src_x2 - src_x1),
    ] = mask[src_y1:src_y2, src_x1:src_x2]
    return shifted


def render_glyph_mask(
    ch: str,
    font_path: Path,
    size: int = 52,
    normalized_size: int = 32,
) -> np.ndarray:
    font = ImageFont.truetype(str(font_path), size=size)
    image_size = max(80, size * 2)
    image = Image.new("L", (image_size, image_size), 0)
    draw = ImageDraw.Draw(image)
    box = draw.textbbox((0, 0), ch, font=font)
    x = (image_size - (box[2] - box[0])) // 2 - box[0]
    y = (image_size - (box[3] - box[1])) // 2 - box[1]
    draw.text((x, y), ch, fill=255, font=font)
    ink_box = image.getbbox()
    if ink_box is None:
        return np.zeros((normalized_size, normalized_size), dtype=np.float32)

    crop = image.crop(ink_box)
    max_side = normalized_size - 4
    scale = min(max_side / crop.width, max_side / crop.height)
    width = max(1, round(crop.width * scale))
    height = max(1, round(crop.height * scale))
    crop = crop.resize((width, height), Image.Resampling.LANCZOS)
    normalized = Image.new("L", (normalized_size, normalized_size), 0)
    normalized.paste(
        crop,
        ((normalized_size - width) // 2, (normalized_size - height) // 2),
    )
    mask = np.asarray(normalized, dtype=np.float32) / 255.0
    return center_ink_mask(mask)


def glyph_mask_views(mask: np.ndarray) -> list[np.ndarray]:
    image = Image.fromarray(np.uint8(np.clip(mask * 255, 0, 255)))
    low_resolution = image.resize((16, 16), Image.Resampling.BILINEAR).resize(
        image.size, Image.Resampling.BILINEAR
    )
    views = [
        image,
        image.filter(ImageFilter.GaussianBlur(radius=0.65)),
        low_resolution,
        image.filter(ImageFilter.MaxFilter(size=3)),
        image.filter(ImageFilter.MinFilter(size=3)),
    ]
    return [
        center_ink_mask(np.asarray(view, dtype=np.float32) / 255.0)
        for view in views
        if np.asarray(view, dtype=np.uint8).max() > 0
    ]


def glyph_shape_feature(mask: np.ndarray) -> np.ndarray:
    image = Image.fromarray(np.uint8(np.clip(mask * 255, 0, 255)))
    coarse = np.asarray(
        image.resize((16, 16), Image.Resampling.BILINEAR), dtype=np.float32
    ) / 255.0
    projections = np.concatenate((mask.sum(axis=0), mask.sum(axis=1))) / max(
        1, mask.shape[0]
    )
    return np.concatenate(
        (
            mask.reshape(-1),
            0.70 * coarse.reshape(-1),
            0.80 * projections,
        )
    ).astype(np.float32)


def render_glyph_feature(
    ch: str,
    font_path: Path,
    sizes: tuple[int, ...] = SHAPE_FEATURE_SIZES,
) -> np.ndarray:
    view_features: list[np.ndarray] = []
    for size in sizes:
        mask = render_glyph_mask(ch, font_path, size=size)
        for view in glyph_mask_views(mask):
            feature = glyph_shape_feature(view)
            feature = feature / (np.linalg.norm(feature) + 1e-8)
            view_features.append(feature)
    feature = np.mean(np.stack(view_features), axis=0)
    return feature / (np.linalg.norm(feature) + 1e-8)


def glyph_similarity_matrix(chars: list[str], font_path: Path) -> np.ndarray:
    features = np.stack(
        [render_glyph_feature(ch, font_path) for ch in chars]
    ).astype(np.float64)
    norms = np.linalg.norm(features, axis=1, keepdims=True) + 1e-8
    features = features / norms
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        return np.nan_to_num(
            features @ features.T,
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )


def similarity_ranks(similarity: np.ndarray) -> np.ndarray:
    similarity = similarity.copy()
    np.fill_diagonal(similarity, -1.0)
    order = np.argsort(-similarity, axis=1, kind="stable")
    rank = np.empty_like(order)
    positions = np.arange(len(similarity))
    for index in range(len(similarity)):
        rank[index, order[index]] = positions
    return rank


def mutual_top_k_edges(similarity: np.ndarray, top_k: int) -> set[tuple[int, int]]:
    similarity = similarity.copy()
    np.fill_diagonal(similarity, -1.0)
    neighbors = np.argsort(-similarity, axis=1, kind="stable")[:, :top_k]
    neighbor_sets = [set(row.tolist()) for row in neighbors]
    return {
        (i, j)
        for i, row in enumerate(neighbors)
        for j in row
        if i < j and i in neighbor_sets[j]
    }


def glyph_view_edge_support(
    chars: list[str],
    font_path: Path,
    top_k: int,
) -> tuple[Counter[tuple[int, int]], Counter[tuple[int, int]]]:
    features_by_view: list[list[np.ndarray]] = [
        [] for _ in range(len(SHAPE_FEATURE_SIZES) * SHAPE_VIEW_COUNT_PER_SIZE)
    ]
    for ch in chars:
        view_index = 0
        for size in SHAPE_FEATURE_SIZES:
            views = glyph_mask_views(render_glyph_mask(ch, font_path, size=size))
            if len(views) != SHAPE_VIEW_COUNT_PER_SIZE:
                raise ValueError(
                    f"unexpected shape view count for {ch} in {font_path}: {len(views)}"
                )
            for view in views:
                feature = glyph_shape_feature(view).astype(np.float64)
                feature = np.nan_to_num(
                    feature, nan=0.0, posinf=0.0, neginf=0.0
                )
                feature = feature / (np.linalg.norm(feature) + 1e-8)
                features_by_view[view_index].append(feature)
                view_index += 1

    all_view_support: Counter[tuple[int, int]] = Counter()
    clean_size_support: Counter[tuple[int, int]] = Counter()
    for view_index, features in enumerate(features_by_view):
        feature_matrix = np.stack(features)
        with np.errstate(
            divide="ignore", invalid="ignore", over="ignore", under="ignore"
        ):
            similarity = np.nan_to_num(
                feature_matrix @ feature_matrix.T,
                nan=0.0,
                posinf=0.0,
                neginf=0.0,
            )
        edges = mutual_top_k_edges(similarity, top_k)
        all_view_support.update(edges)
        if view_index % SHAPE_VIEW_COUNT_PER_SIZE == 0:
            clean_size_support.update(edges)
    return all_view_support, clean_size_support


def build_shape_pairs(
    yi_rows: list[dict[str, str]],
    font_paths: list[Path],
    *,
    cluster_top_k: int = CLUSTER_TOP_K,
    cluster_min_font_support: int = CLUSTER_MIN_FONT_SUPPORT,
    font_specific_min_view_ratio: float = FONT_SPECIFIC_MIN_VIEW_RATIO,
    font_specific_min_clean_sizes: int = FONT_SPECIFIC_MIN_CLEAN_SIZES,
) -> list[dict[str, object]]:
    if cluster_top_k < 1:
        raise ValueError("cluster_top_k must be positive")
    if not 1 <= cluster_min_font_support <= len(font_paths):
        raise ValueError("cluster_min_font_support is out of range")
    if not 0.0 < font_specific_min_view_ratio <= 1.0:
        raise ValueError("font_specific_min_view_ratio must be in (0, 1]")
    if not 1 <= font_specific_min_clean_sizes <= len(SHAPE_FEATURE_SIZES):
        raise ValueError("font_specific_min_clean_sizes is out of range")

    roman_to_char = {
        row["romanization"]: row["char"]
        for row in yi_rows
        if row.get("romanization")
    }
    pairs: list[dict[str, object]] = []
    pair_index: dict[tuple[str, str], int] = {}
    for roman, ch in sorted(roman_to_char.items()):
        if roman.endswith("x") and roman[:-1] in roman_to_char:
            a, b = sorted((ch, roman_to_char[roman[:-1]]))
            if a != b and (a, b) not in pair_index:
                pair_index[(a, b)] = len(pairs)
                pairs.append({"a": a, "b": b, "source": "tone_arc"})

    chars = [row["char"] for row in yi_rows]
    font_similarities = [
        glyph_similarity_matrix(chars, font_path) for font_path in font_paths
    ]
    font_ranks = [similarity_ranks(matrix) for matrix in font_similarities]
    view_support_by_font: list[Counter[tuple[int, int]]] = []
    clean_support_by_font: list[Counter[tuple[int, int]]] = []
    for font_path in font_paths:
        view_support, clean_support = glyph_view_edge_support(
            chars, font_path, cluster_top_k
        )
        view_support_by_font.append(view_support)
        clean_support_by_font.append(clean_support)

    total_views = len(SHAPE_FEATURE_SIZES) * SHAPE_VIEW_COUNT_PER_SIZE
    min_view_support = math.ceil(total_views * font_specific_min_view_ratio)
    candidates: list[dict[str, object]] = []
    for i, ch in enumerate(chars):
        for j in range(i + 1, len(chars)):
            mutual_ranks = [
                max(int(rank[i, j]) + 1, int(rank[j, i]) + 1)
                for rank in font_ranks
            ]
            supporting = [value for value in mutual_ranks if value <= cluster_top_k]
            stable_fonts = [
                font_index
                for font_index in range(len(font_paths))
                if view_support_by_font[font_index][(i, j)] >= min_view_support
                and clean_support_by_font[font_index][(i, j)]
                >= font_specific_min_clean_sizes
            ]
            is_crossfont = len(supporting) >= cluster_min_font_support
            if not is_crossfont and not stable_fonts:
                continue
            a, b = sorted((ch, chars[j]))
            font_scores = [float(matrix[i, j]) for matrix in font_similarities]
            candidates.append(
                {
                    "a": a,
                    "b": b,
                    "source": (
                        "cluster_multifont"
                        if is_crossfont
                        else "cluster_font_specific"
                    ),
                    "score": round(float(np.median(font_scores)), 4),
                    "font_support": len(supporting),
                    "median_mutual_rank": round(float(np.median(mutual_ranks)), 2),
                    "font_min_score": round(min(font_scores), 4),
                    "font_max_score": round(max(font_scores), 4),
                    "stable_fonts": [
                        font_paths[index].name for index in stable_fonts
                    ],
                    "max_view_support": max(
                        (
                            view_support_by_font[index][(i, j)]
                            for index in stable_fonts
                        ),
                        default=0,
                    ),
                    "max_clean_size_support": max(
                        (
                            clean_support_by_font[index][(i, j)]
                            for index in stable_fonts
                        ),
                        default=0,
                    ),
                }
            )

    candidates.sort(
        key=lambda item: (
            item["source"] != "cluster_multifont",
            -int(item["font_support"]),
            float(item["median_mutual_rank"]),
            -float(item["score"]),
            str(item["a"]),
            str(item["b"]),
        )
    )
    for candidate in candidates:
        key = (str(candidate["a"]), str(candidate["b"]))
        if key in pair_index:
            pairs[pair_index[key]].update(
                {
                    name: value
                    for name, value in candidate.items()
                    if name not in {"a", "b", "source"}
                }
            )
            pairs[pair_index[key]]["cluster_source"] = candidate["source"]
            continue
        pair_index[key] = len(pairs)
        pairs.append(candidate)
    return pairs


def validate_accepted_r2(path: Path, pairs: list[dict[str, object]]) -> None:
    if len(pairs) != EXPECTED_PAIR_COUNT:
        raise ValueError(
            f"shape-pair count changed: {len(pairs)} != {EXPECTED_PAIR_COUNT}"
        )
    actual_sha = sha256_file(path)
    if actual_sha != EXPECTED_SHAPE_PAIRS_SHA256:
        raise ValueError(
            "shape-pair derivation differs from accepted CNN r2: "
            f"{actual_sha} != {EXPECTED_SHAPE_PAIRS_SHA256}"
        )
