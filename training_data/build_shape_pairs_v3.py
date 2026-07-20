#!/usr/bin/env python3
"""Derive the frozen v3 Yi shape-pair bank from normative inputs only.

v3 retains every accepted CNN r2 pair.  It then applies one global generic
coverage-floor rule using alternate render sizes: a glyph with stable
multi-font shape neighbors but no pair coverage receives one deterministic
neighbor edge.  No real image, annotation, prediction, or evaluation input is
read by this module.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

import build_shape_pairs as r2


ALGORITHM_VERSION = "blind_multifont_v3_coverage_floor"
SELECTION_SIZES = (32, 42, 54)
SELECTION_MUTUAL_TOP_K = 8
SELECTION_MIN_MULTIFONT_SUPPORT = 2
COVERAGE_SOURCE = "coverage_floor_multifont_generic"
COVERAGE_RULE = "minimum_greedy_cover_of_zero_covered_stable_neighbors"
FROZEN_PAIR_REL = "assets/derived/yi_confusable_pairs_v3_coverage_floor.json"
EXPECTED_PAIR_COUNT = 2162
EXPECTED_SHAPE_PAIRS_SHA256 = (
    "cc9dd6cdfa38fd4ed03815fb2875d282a84a3e8141e47948864cf4bd47488455"
)
EXPECTED_SOURCE_COUNTS = {
    "tone_arc": 342,
    "cluster_multifont": 1657,
    "cluster_font_specific": 122,
    COVERAGE_SOURCE: 41,
}

# Re-export the r2 evidence parameters for the base pair bank's manifest.
CLUSTER_MIN_FONT_SUPPORT = r2.CLUSTER_MIN_FONT_SUPPORT
CLUSTER_TOP_K = r2.CLUSTER_TOP_K
FONT_SPECIFIC_MIN_CLEAN_SIZES = r2.FONT_SPECIFIC_MIN_CLEAN_SIZES
FONT_SPECIFIC_MIN_VIEW_RATIO = r2.FONT_SPECIFIC_MIN_VIEW_RATIO
SHAPE_FEATURE_SIZES = r2.SHAPE_FEATURE_SIZES
write_shape_pairs = r2.write_shape_pairs


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pair_key(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))


def generic_stable_edges(
    chars: list[str],
    font_paths: list[Path],
) -> dict[tuple[int, int], dict[str, float | int]]:
    """Return selection-only generic neighbor edges with multi-font evidence."""
    support: Counter[tuple[int, int]] = Counter()
    scores: defaultdict[tuple[int, int], list[float]] = defaultdict(list)
    for font_path in font_paths:
        features = np.stack(
            [
                r2.render_glyph_feature(ch, font_path, sizes=SELECTION_SIZES)
                for ch in chars
            ]
        ).astype(np.float64)
        if not np.isfinite(features).all():
            raise RuntimeError(f"non-finite generic glyph feature for {font_path.name}")
        norms = np.linalg.norm(features, axis=1, keepdims=True)
        if np.any(norms <= 0):
            raise RuntimeError(f"zero-norm generic glyph feature for {font_path.name}")
        features /= norms
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            similarity = np.nan_to_num(
                features @ features.T,
                nan=0.0,
                posinf=0.0,
                neginf=0.0,
            )
        for edge in r2.mutual_top_k_edges(similarity, SELECTION_MUTUAL_TOP_K):
            support[edge] += 1
            scores[edge].append(float(similarity[edge[0], edge[1]]))
    return {
        edge: {
            "font_support": int(count),
            "median_similarity": round(float(np.median(scores[edge])), 8),
        }
        for edge, count in support.items()
        if count >= SELECTION_MIN_MULTIFONT_SUPPORT
    }


def add_coverage_floor(
    base_pairs: list[dict[str, object]],
    chars: list[str],
    font_paths: list[Path],
) -> list[dict[str, object]]:
    """Append the deterministic minimum set needed to cover zero-edge glyphs."""
    accepted = {pair_key(str(pair["a"]), str(pair["b"])) for pair in base_pairs}
    stable = generic_stable_edges(chars, font_paths)
    stable_degree: defaultdict[int, int] = defaultdict(int)
    covered_degree: defaultdict[int, int] = defaultdict(int)
    for first, second in stable:
        stable_degree[first] += 1
        stable_degree[second] += 1
        if pair_key(chars[first], chars[second]) in accepted:
            covered_degree[first] += 1
            covered_degree[second] += 1
    remaining = {
        index
        for index, degree in stable_degree.items()
        if degree and not covered_degree.get(index)
    }
    additions: list[dict[str, object]] = []
    while remaining:
        ranked: list[tuple[tuple[object, ...], tuple[int, int]]] = []
        for edge, evidence in stable.items():
            first, second = edge
            if not ({first, second} & remaining):
                continue
            a, b = pair_key(chars[first], chars[second])
            if (a, b) in accepted:
                continue
            ranked.append(
                (
                    (
                        -len({first, second} & remaining),
                        -int(evidence["font_support"]),
                        -float(evidence["median_similarity"]),
                        (a, b),
                    ),
                    edge,
                )
            )
        if not ranked:
            raise RuntimeError("v3 coverage-floor rule could not cover an eligible glyph")
        _, edge = min(ranked, key=lambda item: item[0])
        first, second = edge
        a, b = pair_key(chars[first], chars[second])
        evidence = stable[edge]
        additions.append(
            {
                "a": a,
                "b": b,
                "source": COVERAGE_SOURCE,
                "font_support": int(evidence["font_support"]),
                "median_similarity": float(evidence["median_similarity"]),
                "selection_sizes": list(SELECTION_SIZES),
                "selection_rule": COVERAGE_RULE,
            }
        )
        accepted.add((a, b))
        remaining.discard(first)
        remaining.discard(second)
    return [*base_pairs, *additions]


def build_shape_pairs(
    yi_rows: list[dict[str, str]],
    font_paths: list[Path],
) -> list[dict[str, object]]:
    chars = [str(row["char"]) for row in yi_rows]
    if len(chars) != len(set(chars)):
        raise ValueError("normative Yi table contains duplicate characters")
    base_pairs = r2.build_shape_pairs(yi_rows, font_paths)
    pairs = add_coverage_floor(base_pairs, chars, font_paths)
    if len(pairs) != EXPECTED_PAIR_COUNT:
        raise RuntimeError(
            f"v3 shape-pair count changed: {len(pairs)} != {EXPECTED_PAIR_COUNT}"
        )
    return pairs


def validate_accepted_r3(path: Path, pairs: list[dict[str, object]]) -> None:
    if len(pairs) != EXPECTED_PAIR_COUNT:
        raise ValueError(
            f"v3 shape-pair count changed: {len(pairs)} != {EXPECTED_PAIR_COUNT}"
        )
    actual_sha = sha256_file(path)
    if actual_sha != EXPECTED_SHAPE_PAIRS_SHA256:
        raise ValueError(
            "v3 shape-pair derivation differs from accepted coverage-floor bank: "
            f"{actual_sha} != {EXPECTED_SHAPE_PAIRS_SHA256}"
        )


def load_frozen_shape_pairs(path: Path, yi_chars: set[str]) -> list[dict[str, object]]:
    """Load the platform-independent, generic v3 pair asset with full checks.

    Pair derivation is validated locally from the normative table and locked
    fonts.  The resulting SHA-pinned asset is used by every build so minor
    FreeType/Pillow raster differences cannot silently change supervision.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("frozen v3 shape-pair asset must be a JSON list")
    pairs = [dict(pair) for pair in raw if isinstance(pair, dict)]
    if len(pairs) != len(raw):
        raise ValueError("frozen v3 shape-pair asset contains a non-object pair")
    validate_accepted_r3(path, pairs)
    seen: set[tuple[str, str]] = set()
    source_counts: Counter[str] = Counter()
    allowed_sources = set(EXPECTED_SOURCE_COUNTS)
    for index, pair in enumerate(pairs):
        a = str(pair.get("a", ""))
        b = str(pair.get("b", ""))
        source = str(pair.get("source", ""))
        if a not in yi_chars or b not in yi_chars:
            raise ValueError(f"frozen v3 pair {index} is outside the normative Yi table")
        if not a < b or (a, b) in seen:
            raise ValueError(f"frozen v3 pair {index} is not a canonical unique edge")
        if source not in allowed_sources:
            raise ValueError(f"frozen v3 pair {index} has unsupported source {source}")
        if source == COVERAGE_SOURCE:
            if pair.get("selection_sizes") != list(SELECTION_SIZES):
                raise ValueError(f"frozen v3 pair {index} has wrong coverage selection sizes")
            if pair.get("selection_rule") != COVERAGE_RULE:
                raise ValueError(f"frozen v3 pair {index} has wrong coverage selection rule")
        seen.add((a, b))
        source_counts[source] += 1
    if dict(source_counts) != EXPECTED_SOURCE_COUNTS:
        raise ValueError("frozen v3 pair source counts differ from the locked policy")
    return pairs


def pair_bank_sha256(pairs: list[dict[str, object]]) -> str:
    """Return the SHA used by `write_shape_pairs` without creating a temp file."""
    return hashlib.sha256(
        (json.dumps(pairs, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    ).hexdigest()
