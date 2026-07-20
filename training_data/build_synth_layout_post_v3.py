#!/usr/bin/env python3
"""Deterministic post-V3 layout-aware PaddleOCR-VL training core builder.

Reads ONLY the two normative standard tables and the locked fonts, renders
synthetic line / region / page images through a print-degradation pipeline,
and emits a PaddleOCR-VL ``messages``/``images`` JSONL build plus a
``build_manifest.json`` for the post-V3 no-eval training gate.

Design contract (mirrors the audit):
- Every label glyph comes from ``nuosu_unicode.csv`` (彝) or ``han_3500_level1.txt`` (汉).
- Yi glyphs render with a Yi font; Han glyphs render with an external CJK font
  (per-glyph font selection -> no tofu / garbage labels).
- 100% synthetic. Never reads any eval root; never emits a forbidden source token.
- A randomized, seeded broad print/scanner degradation pipeline covers a
  general document domain without matching any evaluation source.
- Fully deterministic: per-sample RNG is spawned from one SeedSequence(seed),
  so output is reproducible and independent of iteration order.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, __version__ as PIL_VERSION

from build_shape_pairs_v3 import (
    ALGORITHM_VERSION as SHAPE_ALGORITHM_VERSION,
    CLUSTER_MIN_FONT_SUPPORT,
    CLUSTER_TOP_K,
    COVERAGE_RULE as SHAPE_COVERAGE_RULE,
    COVERAGE_SOURCE as SHAPE_COVERAGE_SOURCE,
    EXPECTED_PAIR_COUNT,
    EXPECTED_SHAPE_PAIRS_SHA256,
    FONT_SPECIFIC_MIN_CLEAN_SIZES,
    FONT_SPECIFIC_MIN_VIEW_RATIO,
    FROZEN_PAIR_REL as FROZEN_PAIR_ASSET_REL,
    SELECTION_MIN_MULTIFONT_SUPPORT as SHAPE_SELECTION_MIN_MULTIFONT_SUPPORT,
    SELECTION_MUTUAL_TOP_K as SHAPE_SELECTION_MUTUAL_TOP_K,
    SELECTION_SIZES as SHAPE_SELECTION_SIZES,
    SHAPE_FEATURE_SIZES,
    load_frozen_shape_pairs,
    validate_accepted_r3,
    write_shape_pairs,
)
from confusable_injection import (
    ConfusableEvent,
    ConfusableScheduler,
    adjacent_yi_positions,
    inject_confusable_pairs as _inject_confusable_pairs,
)
import post_v3_degradation_policy as attenuation_policy

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_VERSION = "build_synth_layout_post_v3/1.0-v3-core-circled-tail-cap"
FORMAL_PROFILE_ID = "normative_layout_post_v3_core"
DEVELOPMENT_PROFILE = "development"
FORMAL_TRAIN_N = 18000
FORMAL_DEV_N = 800
GENERATOR_REL = "scripts/build_synth_layout_post_v3.py"
PARENT_V3_GENERATOR_REL = "scripts/build_synth_layout_v3.py"
EXPECTED_PARENT_V3_GENERATOR_SHA256 = "3d5addb2cd5b900ae9188d1ff89ecc85a73e65f27ed3dc4a02a1fbb2a29c9d03"
FORMAL_SPEC_REL = "POST_V3_FORMAL_SPEC.json"
FORMAL_AUTHORIZATION_REL = "POST_V3_AUTHORIZATION.json"
SHAPE_GENERATOR_REL = "scripts/build_shape_pairs_v3.py"
CONFUSABLE_GENERATOR_REL = "scripts/confusable_injection.py"
SOURCE_ID = "normative_synthetic_layout_post_v3_core"
USER_PROMPT = "<image>OCR:"

YI_UNICODE_REL = "data/standards/nuosu_unicode.csv"
HAN_LEVEL1_REL = "data/standards/han_3500_level1.txt"
YI_FONT_RELS = [
    "assets/fonts/NotoSansNuosu-Regular.ttf",
    "assets/fonts/思源黑体彝文.ttf",
    "assets/fonts/方正彝文宋体.TTF",
    "assets/fonts/方正彝文手写体.TTF",
]
CJK_FONT_RELS = [
    "assets/fonts/cjk_heiti.ttc",
    "assets/fonts/cjk_songti.ttc",
]
CIRCLED_FONT_SPECS = (
    {
        "font_id": "uniform_sans",
        "path": "assets/fonts/circled_1_20_uniform_sans.ttf",
        "face_index": 0,
    },
    {
        "font_id": "songti_bold",
        "path": "assets/fonts/circled_1_20_songti_bold.ttf",
        "face_index": 0,
    },
    {
        "font_id": "cjk_songti",
        "path": "assets/fonts/circled_1_20_songti_regular.ttf",
        "face_index": 0,
    },
)

CLASSES = ("pure_yi", "pure_common", "mixed")
GRANULARITIES = ("line", "region", "page")

# per-granularity line-count and per-line char-count ranges
GRAN_SPEC = {
    "line": {"lines": (1, 1), "chars": (4, 14)},
    "region": {"lines": (3, 8), "chars": (4, 16)},
    "page": {"lines": (15, 34), "chars": (4, 20)},
}

# --- Symbol inventory: standard Chinese typography (general, not eval-derived) ---
# Any normative Chinese/bilingual publication uses these; the set and density are
# fixed from general typographic convention, independent of any specific book.
# Enclosed numbers are injected only by the exact three-font schedule below.
PAUSE_PUNCT = list("，、；：")
END_PUNCT = list("。？！")
QUOTE_PAIRS = [("“", "”"), ("‘", "’"), ("（", "）"), ("《", "》")]
INLINE_SYMBOLS = ["——", "…", "·"]
DIGITS = list("0123456789")
CIRCLED = [chr(c) for c in range(0x2460, 0x2474)]  # ①..⑳
SYMBOL_CHARS = set("".join(PAUSE_PUNCT + END_PUNCT + INLINE_SYMBOLS + DIGITS + CIRCLED))
SYMBOL_CHARS.update(ch for pair in QUOTE_PAIRS for ch in pair)

# Frozen diagnostic distribution. Every sweep candidate uses byte-identical dev
# data for the same seed/dev-n, independent of the candidate's train mixture.
DEV_RATIO = {"pure_yi": 0.40, "mixed": 0.40, "pure_common": 0.20}
DEV_MIXED_YI_FRAC = 0.65
DEV_SYMBOL_RATE = 0.35
DEV_HEAVY_RATIO = 0.30
SYMBOL_FREE_PAGE_RATE = 0.30
TRAIN_CONFUSABLE_REPEATS = 6
DEV_CONFUSABLE_REPEATS = 1
SHAPE_CLUSTER_FONT_COUNT = 3
PAGE_LAYOUT_FAMILIES = (
    "single_column_anchor",
    "two_column_flow",
    "stacked_interleaved_a",
    "aligned_bilingual_rows",
    "independent_spatial_columns",
)
TRAIN_GEOMETRY_PROFILES = ("train_balanced", "train_wide", "train_compact")
DEV_GEOMETRY_PROFILES = ("dev_narrow_wide_gutter", "dev_wide_large_margin")


class BuildCfg:
    """Threaded generation config (all defaults are general, not eval-tuned)."""

    def __init__(
        self,
        ratio: dict[str, float],
        mixed_yi_frac: float,
        symbol_rate: float,
        heavy_ratio: float,
        confusable_repeats: int,
        geometry_split: str = "train",
    ) -> None:
        self.ratio = ratio
        self.mixed_yi_frac = mixed_yi_frac
        self.symbol_rate = symbol_rate
        self.heavy_ratio = heavy_ratio
        self.confusable_repeats = confusable_repeats
        self.geometry_split = geometry_split


@dataclass
class SampleDraft:
    cls: str
    granularity: str
    lines: list[str]
    render_attempt_seqs: list[np.random.SeedSequence]
    confusable_eligible_lines: int = 0
    confusable_events: list[ConfusableEvent] | None = None
    circled_events: list[dict[str, object]] | None = None
    layout_family: str = "none"
    layout_data: dict[str, object] | None = None
    layout_profile: str = "none"
    degrade_profile: str = "standard"


def _marker(k: int, rng: np.random.Generator) -> str:
    """Return an ordinary numbered-list marker outside the circled schedule."""
    del rng
    return f"{k + 1}、"


def _decorate(
    line: str,
    cls: str,
    rng: np.random.Generator,
    cfg: BuildCfg,
    allow_symbols: bool = True,
) -> str:
    """Sprinkle punctuation at general prose density; most lines stay symbol-free
    (negatives) so the model learns symbols are image-conditional, not default."""
    if not line:
        return line
    if not allow_symbols or rng.random() >= cfg.symbol_rate:
        return line  # majority stay symbol-free

    s = line
    insert_at = int(rng.integers(1, len(s))) if len(s) > 1 else len(s)
    operation = str(rng.choice(
        ["pause", "end", "quote", "inline", "digits"],
        p=np.array([0.55, 0.25, 0.08, 0.05, 0.07]),
    ))
    if operation == "pause":
        mark = str(rng.choice(PAUSE_PUNCT, p=np.array([0.70, 0.20, 0.05, 0.05])))
        s = s[:insert_at] + mark + s[insert_at:]
    elif operation == "end":
        s += str(rng.choice(END_PUNCT, p=np.array([0.80, 0.10, 0.10])))
    elif operation == "quote":
        left, right = QUOTE_PAIRS[int(rng.integers(0, len(QUOTE_PAIRS)))]
        s = left + s + right
    elif operation == "inline":
        s = s[:insert_at] + str(rng.choice(INLINE_SYMBOLS)) + s[insert_at:]
    else:
        number = "".join(str(rng.choice(DIGITS)) for _ in range(int(rng.integers(1, 4))))
        s = s[:insert_at] + number + s[insert_at:]
    return s


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_formal_authorization() -> None:
    spec_path = PROJECT_ROOT / FORMAL_SPEC_REL
    authorization_path = PROJECT_ROOT / FORMAL_AUTHORIZATION_REL
    if not spec_path.is_file() or not authorization_path.is_file():
        raise RuntimeError(
            "formal post-V3 core build is not authorized: locked spec and authorization file required"
        )
    try:
        authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("cannot read formal post-V3 authorization") from exc
    if not isinstance(authorization, dict):
        raise RuntimeError("formal post-V3 authorization must be a JSON object")
    if authorization.get("phase") != "formal_build_authorized" or authorization.get("formal_build") is not True:
        raise RuntimeError("formal post-V3 build has not been owner-authorized")
    if authorization.get("training") is not False:
        raise RuntimeError("formal build authorization must not implicitly authorize training")
    if authorization.get("spec_sha256") != sha256_file(spec_path):
        raise RuntimeError("formal authorization spec SHA differs from the locked prebuild spec")


def load_charsets() -> tuple[list[dict[str, str]], list[str], list[str]]:
    with (PROJECT_ROOT / YI_UNICODE_REL).open(encoding="utf-8-sig") as fh:
        yi_rows = [dict(row) for row in csv.DictReader(fh) if row.get("char")]
    yi = [row["char"] for row in yi_rows]
    han = [
        line.strip()
        for line in (PROJECT_ROOT / HAN_LEVEL1_REL).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return yi_rows, yi, han


def font_cmap(path: Path, face_index: int = 0) -> set[int]:
    from fontTools.ttLib import TTFont

    ft = TTFont(str(path), fontNumber=face_index, lazy=True)
    cmap: set[int] = set()
    for table in ft["cmap"].tables:
        cmap |= set(table.cmap.keys())
    ft.close()
    return cmap


# --------------------------------------------------------------------------- #
# fonts
# --------------------------------------------------------------------------- #
class FontBook:
    """Loads Yi and CJK fonts and selects a glyph-covering font per character."""

    def __init__(self) -> None:
        self.yi_paths = [PROJECT_ROOT / rel for rel in YI_FONT_RELS]
        self.cjk_paths = [PROJECT_ROOT / rel for rel in CJK_FONT_RELS]
        self.circled_specs = tuple(
            {
                **spec,
                "path": PROJECT_ROOT / str(spec["path"]),
            }
            for spec in CIRCLED_FONT_SPECS
        )
        for p in self.yi_paths + self.cjk_paths + [Path(spec["path"]) for spec in self.circled_specs]:
            if not p.is_file():
                raise FileNotFoundError(f"required font missing: {p}")
        self.yi_cmaps = [font_cmap(p) for p in self.yi_paths]
        self.cjk_cmaps = [font_cmap(p) for p in self.cjk_paths]
        self.circled_cmaps = [
            font_cmap(Path(spec["path"]), int(spec["face_index"]))
            for spec in self.circled_specs
        ]
        for spec, cmap in zip(self.circled_specs, self.circled_cmaps):
            missing_circled = [ch for ch in CIRCLED if ord(ch) not in cmap]
            if missing_circled:
                raise ValueError(
                    f"circled font {spec['font_id']} lacks required markers: "
                    f"{''.join(missing_circled)}"
                )
        self._cache: dict[tuple[str, int, int], ImageFont.FreeTypeFont] = {}

    def _font(self, kind: str, idx: int, size: int) -> ImageFont.FreeTypeFont:
        key = (kind, idx, size)
        f = self._cache.get(key)
        if f is None:
            if kind == "yi":
                path = self.yi_paths[idx]
            elif kind == "cjk":
                path = self.cjk_paths[idx]
            elif kind == "circled":
                spec = self.circled_specs[idx]
                path = Path(spec["path"])
            else:
                raise ValueError(f"unknown font kind: {kind}")
            face_index = int(self.circled_specs[idx]["face_index"]) if kind == "circled" else 0
            f = ImageFont.truetype(str(path), size, index=face_index)
            self._cache[key] = f
        return f

    def pick(self, ch: str, size: int, rng: np.random.Generator) -> ImageFont.FreeTypeFont | None:
        """Return a rendering font that covers ``ch``; None if uncovered."""
        cp = ord(ch)
        if ch in CIRCLED:
            cands = [i for i, cmap in enumerate(self.circled_cmaps) if cp in cmap]
            if not cands:
                return None
            return self._font("circled", int(rng.choice(cands)), size)
        if 0xA000 <= cp <= 0xA4CF:  # Yi Syllables / Radicals block
            cands = [i for i, cm in enumerate(self.yi_cmaps) if cp in cm]
            kind = "yi"
            if not cands:  # some Yi fonts also expose via CJK? fall through
                cands = [i for i, cm in enumerate(self.cjk_cmaps) if cp in cm]
                kind = "cjk"
        else:  # Han (and anything else) -> CJK font
            cands = [i for i, cm in enumerate(self.cjk_cmaps) if cp in cm]
            kind = "cjk"
        if not cands:
            return None
        idx = int(rng.choice(cands))
        return self._font(kind, idx, size)

    def force_circled(self, ch: str, size: int, font_index: int) -> ImageFont.FreeTypeFont:
        if ch not in CIRCLED:
            raise ValueError(f"forced circled character is not U+2460-U+2473: {ch!r}")
        if not 0 <= font_index < len(self.circled_specs):
            raise ValueError(f"invalid forced circled font index: {font_index}")
        if ord(ch) not in self.circled_cmaps[font_index]:
            raise ValueError(
                f"circled font {self.circled_specs[font_index]['font_id']} "
                f"does not cover U+{ord(ch):04X}"
            )
        return self._font("circled", font_index, size)

    def force_yi(self, ch: str, size: int, font_index: int) -> ImageFont.FreeTypeFont:
        if not 0 <= font_index < SHAPE_CLUSTER_FONT_COUNT:
            raise ValueError(f"invalid forced Yi font index: {font_index}")
        if ord(ch) not in self.yi_cmaps[font_index]:
            raise ValueError(
                f"forced Yi font {self.yi_paths[font_index]} lacks U+{ord(ch):04X}"
            )
        return self._font("yi", font_index, size)


# --------------------------------------------------------------------------- #
# text sampling
# --------------------------------------------------------------------------- #
def sample_line(
    cls: str, n: int, yi: list[str], han: list[str], rng: np.random.Generator, cfg: "BuildCfg"
) -> str:
    if cls == "pure_yi":
        pool = yi
        return "".join(pool[int(i)] for i in rng.integers(0, len(pool), size=n))
    if cls == "pure_common":
        pool = han
        return "".join(pool[int(i)] for i in rng.integers(0, len(pool), size=n))
    # mixed: interleave short runs of yi and han (Yi-dominant per cfg.mixed_yi_frac)
    out: list[str] = []
    while len(out) < n:
        use_yi = rng.random() < cfg.mixed_yi_frac
        run = min(int(rng.integers(1, 5)), n - len(out))
        pool = yi if use_yi else han
        out.extend(pool[int(i)] for i in rng.integers(0, len(pool), size=run))
    return "".join(out[:n])


def sample_lines(
    cls: str,
    gran: str,
    yi: list[str],
    han: list[str],
    rng: np.random.Generator,
    cfg: "BuildCfg",
) -> list[str]:
    spec = GRAN_SPEC[gran]
    n_lines = int(rng.integers(spec["lines"][0], spec["lines"][1] + 1))
    lo, hi = spec["chars"]
    base: list[str] = []
    for _ in range(n_lines):
        n = int(rng.integers(lo, hi + 1))
        line = sample_line(cls, n, yi, han, rng, cfg)
        base.append(line)

    # symbols: punctuation (image-conditional), then section markers / page number
    lines = [_decorate(b, cls, rng, cfg) for b in base]
    if gran in ("region", "page") and cls != "pure_yi" and rng.random() < cfg.symbol_rate:
        for k in range(len(lines)):
            if rng.random() < 0.25:
                lines[k] = _marker(k, rng) + lines[k]
    if gran == "page" and cls != "pure_yi" and rng.random() < cfg.symbol_rate * 0.30:
        lines.append("".join(str(rng.choice(DIGITS)) for _ in range(int(rng.integers(1, 4)))))
    return lines


def _sample_plain_line(
    cls: str,
    lo: int,
    hi: int,
    yi: list[str],
    han: list[str],
    rng: np.random.Generator,
    cfg: BuildCfg,
    allow_symbols: bool = True,
) -> str:
    n = int(rng.integers(lo, hi + 1))
    return _decorate(
        sample_line(cls, n, yi, han, rng, cfg), cls, rng, cfg, allow_symbols
    )


def _canvas_geometry(profile: str, rng: np.random.Generator) -> dict[str, int]:
    if profile == "train_balanced":
        width, margin_ratio, gutter_ratio = int(rng.integers(980, 1281)), rng.uniform(0.05, 0.105), rng.uniform(0.035, 0.085)
    elif profile == "train_wide":
        width, margin_ratio, gutter_ratio = int(rng.integers(1280, 1501)), rng.uniform(0.06, 0.125), rng.uniform(0.025, 0.07)
    elif profile == "train_compact":
        width, margin_ratio, gutter_ratio = int(rng.integers(900, 1081)), rng.uniform(0.04, 0.08), rng.uniform(0.055, 0.10)
    elif profile == "dev_narrow_wide_gutter":
        width, margin_ratio, gutter_ratio = int(rng.integers(820, 901)), rng.uniform(0.025, 0.04), rng.uniform(0.115, 0.155)
    elif profile == "dev_wide_large_margin":
        width, margin_ratio, gutter_ratio = int(rng.integers(1520, 1681)), rng.uniform(0.145, 0.18), rng.uniform(0.018, 0.032)
    else:
        raise ValueError(f"unknown geometry profile: {profile}")
    margin = int(width * margin_ratio)
    gutter = int(width * gutter_ratio)
    base_size = int(rng.integers(27, 37))
    line_step = int(base_size * rng.uniform(1.45, 1.75))
    return {
        "canvas_width": width,
        "margin": margin,
        "gutter": gutter,
        "base_size": base_size,
        "line_step": line_step,
    }


def _block(
    block_id: str,
    text: str,
    x: int,
    y: int,
    w: int,
    h: int,
    role: str,
    script: str,
    group_id: str,
) -> dict[str, object]:
    return {
        "id": block_id,
        "text": text,
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "role": role,
        "script": script,
        "group_id": group_id,
    }


def coordinate_reading_order(
    blocks: list[dict[str, object]], canvas_width: int
) -> tuple[list[str], list[list[str]], str]:
    """One rule for every family: visual rows by y, then blocks by x."""
    if not blocks:
        return [], [], "single_column_y"
    ordered_by_y = sorted(blocks, key=lambda b: (int(b["y"]), int(b["x"]), str(b["id"])))
    line_groups: list[list[dict[str, object]]] = []
    for block in ordered_by_y:
        if not line_groups:
            line_groups.append([block])
            continue
        anchor = line_groups[-1][0]
        tolerance = max(3, int(min(int(anchor["h"]), int(block["h"])) * 0.35))
        if abs(int(block["y"]) - int(anchor["y"])) <= tolerance:
            line_groups[-1].append(block)
        else:
            line_groups.append([block])
    line_groups = [sorted(group, key=lambda b: (int(b["x"]), str(b["id"]))) for group in line_groups]
    return (
        ["".join(str(b["text"]) for b in group) for group in line_groups],
        [[str(b["id"]) for b in group] for group in line_groups],
        "global_rows_y_then_x",
    )


def _finalize_page(
    blocks: list[dict[str, object]], geometry: dict[str, int], family_data: dict[str, object]
) -> tuple[list[str], dict[str, object]]:
    lines, groups, mode = coordinate_reading_order(blocks, int(geometry["canvas_width"]))
    by_id = {str(block["id"]): block for block in blocks}
    for line_index, group in enumerate(groups):
        char_start = 0
        for block_id in group:
            block = by_id[block_id]
            block["target_line_index"] = line_index
            block["target_char_start"] = char_start
            char_start += len(str(block["text"]))
            block["target_char_end"] = char_start
    canvas_height = max(640, max(int(b["y"]) + int(b["h"]) for b in blocks) + int(geometry["margin"]))
    return lines, {
        **family_data,
        **geometry,
        "canvas_height": canvas_height,
        "blocks": blocks,
        "reading_order_mode": mode,
        "target_line_block_ids": groups,
    }


def sample_page_document(
    cls: str,
    yi: list[str],
    han: list[str],
    rng: np.random.Generator,
    cfg: BuildCfg,
    forced_family: str | None = None,
    layout_profile: str = "train_balanced",
) -> tuple[list[str], str, dict[str, object]]:
    """Create positioned blocks, then derive labels only through coordinates."""
    if forced_family is not None and forced_family not in PAGE_LAYOUT_FAMILIES:
        raise ValueError(f"unsupported forced layout family: {forced_family}")
    family = forced_family or str(
        rng.choice(
            PAGE_LAYOUT_FAMILIES,
            p=np.array([0.22, 0.12, 0.44, 0.11, 0.11]),
        )
    )

    geometry = _canvas_geometry(layout_profile, rng)
    width, margin, gutter = geometry["canvas_width"], geometry["margin"], geometry["gutter"]
    base_size, line_step = geometry["base_size"], geometry["line_step"]
    full_width = width - 2 * margin
    symbols_enabled = bool(rng.random() >= SYMBOL_FREE_PAGE_RATE)
    blocks: list[dict[str, object]] = []
    block_serial = 0

    def add(text: str, x: int, y: int, w: int, role: str, script: str, group: str) -> None:
        nonlocal block_serial
        blocks.append(_block(f"b{block_serial:03d}", text, x, y, w, line_step, role, script, group))
        block_serial += 1

    cursor_y = margin
    if rng.random() < 0.40:
        title_cls = cls if cls != "mixed" else str(rng.choice(["pure_yi", "pure_common", "mixed"]))
        add(_sample_plain_line(title_cls, 5, 11, yi, han, rng, cfg, symbols_enabled), margin, cursor_y, full_width, "title", title_cls, "title")
        cursor_y += int(base_size * 2.2)

    def finish(family_data: dict[str, object]) -> tuple[list[str], dict[str, object]]:
        if symbols_enabled and rng.random() < cfg.symbol_rate * 0.30:
            footer_y = max(int(block["y"]) + int(block["h"]) for block in blocks) + base_size
            footer = "".join(str(rng.choice(DIGITS)) for _ in range(int(rng.integers(1, 4))))
            add(footer, margin, footer_y, full_width, "footer", "pure_common", "footer")
        return _finalize_page(blocks, geometry, family_data)

    if family == "stacked_interleaved_a":
        block_count = int(rng.integers(3, 10))
        regular = bool(rng.random() < 0.55)
        start = str(rng.choice(["yi", "han"]))
        if regular:
            block_scripts = [start if index % 2 == 0 else ("han" if start == "yi" else "yi") for index in range(block_count)]
        else:
            block_scripts = [str(rng.choice(["yi", "han"])) for _ in range(block_count)]
            if len(set(block_scripts)) == 1:
                block_scripts[int(rng.integers(0, block_count))] = "han" if block_scripts[0] == "yi" else "yi"
            if block_count >= 3 and not any(block_scripts[i] == block_scripts[i + 1] for i in range(block_count - 1)):
                block_scripts[1] = block_scripts[0]
            if len(set(block_scripts)) == 1:
                block_scripts[-1] = "han" if block_scripts[0] == "yi" else "yi"
        block_line_counts: list[int] = []
        for paragraph_index, script in enumerate(block_scripts):
            line_count = int(rng.integers(1, 6))
            block_line_counts.append(line_count)
            line_cls = "pure_yi" if script == "yi" else "pure_common"
            indent = int(base_size * rng.uniform(0.0, 2.8))
            for _ in range(line_count):
                add(_sample_plain_line(line_cls, 6, 22, yi, han, rng, cfg, symbols_enabled), margin + indent, cursor_y, full_width - indent, "body", script, f"p{paragraph_index}")
                cursor_y += line_step
            cursor_y += int(base_size * rng.uniform(0.45, 1.35))
        lines, data = finish({
            "block_count": block_count,
            "block_scripts": block_scripts,
            "block_line_counts": block_line_counts,
            "layout_regularity": "regular" if regular else "high_entropy",
            "symbols_enabled": symbols_enabled,
        })
        return lines, family, data

    if family == "aligned_bilingual_rows":
        row_count = int(rng.integers(6, 13))
        small_gap = int(width * rng.uniform(0.015, 0.035))
        column_width = (full_width - small_gap) // 2
        for row in range(row_count):
            for side, x in (("left", margin), ("right", margin + column_width + small_gap)):
                script_cls = str(rng.choice(["pure_yi", "pure_common", "mixed"]))
                add(_sample_plain_line(script_cls, 5, 13, yi, han, rng, cfg, symbols_enabled), x, cursor_y, column_width, "body", script_cls, f"r{row}")
            cursor_y += line_step
        lines, data = finish({"row_count": row_count, "symbols_enabled": symbols_enabled})
        return lines, family, data

    if family == "independent_spatial_columns":
        left_count = int(rng.integers(9, 17))
        right_count = int(rng.integers(8, 16))
        wide_gap = max(gutter, int(width * 0.09))
        column_width = (full_width - wide_gap) // 2
        body_y = cursor_y
        for side, count, x in (("left", left_count, margin), ("right", right_count, margin + column_width + wide_gap)):
            y = body_y
            for row in range(count):
                script_cls = str(rng.choice(["pure_yi", "pure_common", "mixed"]))
                add(_sample_plain_line(script_cls, 6, 15, yi, han, rng, cfg, symbols_enabled), x, y, column_width, "body", script_cls, f"{side}{row}")
                y += line_step
        lines, data = finish({"left_count": left_count, "right_count": right_count, "symbols_enabled": symbols_enabled})
        return lines, family, data

    body_count = int(rng.integers(16, 31))
    if family == "two_column_flow":
        left_count = (body_count + 1) // 2
        right_count = body_count - left_count
        wide_gap = max(gutter, int(width * 0.09))
        column_width = (full_width - wide_gap) // 2
        for side, count, x in (("left", left_count, margin), ("right", right_count, margin + column_width + wide_gap)):
            y = cursor_y
            for row in range(count):
                add(_sample_plain_line(cls, 5, 15, yi, han, rng, cfg, symbols_enabled), x, y, column_width, "body", cls, f"{side}{row}")
                y += line_step
        lines, data = finish({"left_count": left_count, "right_count": right_count, "symbols_enabled": symbols_enabled})
        return lines, family, data

    for row in range(body_count):
        indent = int(base_size * rng.uniform(0.0, 1.8)) if rng.random() < 0.28 else 0
        add(_sample_plain_line(cls, 5, 18, yi, han, rng, cfg, symbols_enabled), margin + indent, cursor_y, full_width - indent, "body", cls, "body")
        cursor_y += line_step
    lines, data = finish({"body_count": body_count, "symbols_enabled": symbols_enabled})
    return lines, family, data


def inject_confusable_pairs(
    drafts: list[SampleDraft],
    pairs: list[dict[str, object]],
    repeats: int,
    rng: np.random.Generator,
) -> dict[str, int]:
    return _inject_confusable_pairs(
        drafts,
        pairs,
        repeats,
        rng,
        tuple(YI_FONT_RELS[:SHAPE_CLUSTER_FONT_COUNT]),
        complex_page_fraction=0.0,
    )


def circled_occurrences_per_marker(split: str, count: int) -> int:
    if split == "train" and count == FORMAL_TRAIN_N:
        return 20
    if split == "dev" and count == FORMAL_DEV_N:
        return 3
    if count >= 60:
        return 3
    if count >= len(CIRCLED):
        return 1
    return 0


def inject_circled_markers(
    drafts: list[SampleDraft],
    split: str,
    rng: np.random.Generator,
) -> dict[str, object]:
    """Inject an exact, three-font ①-⑳ schedule without adding dataset rows."""
    repeats = circled_occurrences_per_marker(split, len(drafts))
    for draft in drafts:
        draft.circled_events = []
    if repeats == 0:
        return {"events": 0, "occurrences_per_marker": 0, "font_counts": {}, "position_counts": {}}

    eligible = [
        index
        for index, draft in enumerate(drafts)
        if draft.granularity in {"line", "region"}
        and draft.cls != "pure_yi"
        and bool(draft.lines)
    ]
    required = len(CIRCLED) * repeats
    if len(eligible) < required:
        raise RuntimeError(
            f"circled schedule needs {required} non-pure-Yi line/region rows, "
            f"found {len(eligible)}"
        )
    eligible = [eligible[int(index)] for index in rng.permutation(len(eligible))[:required]]

    position_names = ("line_start", "line_middle", "line_end")
    planned: list[dict[str, object]] = []
    for marker_index, marker in enumerate(CIRCLED):
        if repeats == 20:
            font_counts = [7, 7, 7]
            font_counts[marker_index % 3] = 6
            position_counts = [7, 7, 7]
            position_counts[(marker_index + 1) % 3] = 6
            fonts = [font for font, total in enumerate(font_counts) for _ in range(total)]
            positions = [position for position, total in enumerate(position_counts) for _ in range(total)]
            fonts = [fonts[int(index)] for index in rng.permutation(len(fonts))]
            positions = [positions[int(index)] for index in rng.permutation(len(positions))]
        elif repeats == 3:
            fonts = [0, 1, 2]
            positions = [
                marker_index % 3,
                (marker_index + 1) % 3,
                (marker_index + 2) % 3,
            ]
        else:
            fonts = [marker_index % 3]
            positions = [marker_index % 3]
        planned.extend(
            {
                "marker": marker,
                "codepoint": f"U+{ord(marker):04X}",
                "font_index": font_index,
                "font_id": str(CIRCLED_FONT_SPECS[font_index]["font_id"]),
                "position_kind": position_names[position_index],
            }
            for font_index, position_index in zip(fonts, positions)
        )

    planned = [planned[int(index)] for index in rng.permutation(len(planned))]
    font_histogram: Counter[str] = Counter()
    position_histogram: Counter[str] = Counter()
    marker_histogram: Counter[str] = Counter()
    for draft_index, event in zip(eligible, planned):
        draft = drafts[draft_index]
        line_index = int(rng.integers(0, len(draft.lines)))
        line = draft.lines[line_index]
        kind = str(event["position_kind"])
        if kind == "line_start":
            position = 0
        elif kind == "line_end":
            position = len(line)
        else:
            position = int(rng.integers(1, len(line))) if len(line) > 1 else len(line)
        marker = str(event["marker"])
        draft.lines[line_index] = line[:position] + marker + line[position:]
        resolved = {
            **event,
            "line_index": line_index,
            "position": position,
        }
        assert draft.circled_events is not None
        draft.circled_events.append(resolved)
        marker_histogram[marker] += 1
        font_histogram[str(event["font_id"])] += 1
        position_histogram[kind] += 1

    expected_markers = {marker: repeats for marker in CIRCLED}
    if dict(marker_histogram) != expected_markers:
        raise RuntimeError("circled marker schedule does not match exact per-marker counts")
    if set(font_histogram) != {str(spec["font_id"]) for spec in CIRCLED_FONT_SPECS}:
        raise RuntimeError("circled schedule does not cover all three fonts")
    if set(position_histogram) != set(position_names):
        raise RuntimeError("circled schedule does not cover line start, middle, and end")
    return {
        "events": required,
        "occurrences_per_marker": repeats,
        "marker_counts": dict(sorted(marker_histogram.items(), key=lambda item: ord(item[0]))),
        "font_counts": dict(sorted(font_histogram.items())),
        "position_counts": dict(sorted(position_histogram.items())),
    }


# --------------------------------------------------------------------------- #
# rendering + degradation
# --------------------------------------------------------------------------- #
def paper_background(w: int, h: int, rng: np.random.Generator) -> Image.Image:
    base = int(rng.integers(238, 253))
    arr = np.full((h, w, 3), base, dtype=np.float32)
    # low-frequency tint gradient
    gy = np.linspace(rng.uniform(-8, 8), rng.uniform(-8, 8), h)[:, None]
    gx = np.linspace(rng.uniform(-6, 6), rng.uniform(-6, 6), w)[None, :]
    arr += (gy + gx)[..., None]
    # fiber noise
    arr += rng.normal(0, rng.uniform(1.5, 4.0), size=(h, w, 1))
    arr = np.clip(arr, 200, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def render_block(
    lines: list[str],
    fonts: FontBook,
    rng: np.random.Generator,
    confusable_events: list[ConfusableEvent] | None = None,
    circled_events: list[dict[str, object]] | None = None,
) -> Image.Image:
    size = int(rng.integers(28, 46))
    tracking = rng.uniform(0.0, 0.18) * size
    line_gap = rng.uniform(0.25, 0.6) * size
    margin = int(rng.integers(18, 44))
    ink = int(rng.integers(15, 55))  # dark ink, slightly randomized

    # measure
    line_imgs: list[tuple[list[tuple[str, ImageFont.FreeTypeFont]], float, int]] = []
    max_w = 1
    forced_fonts: dict[tuple[int, int], int] = {}
    forced_circled_fonts: dict[tuple[int, int], int] = {}
    for event in confusable_events or []:
        forced_fonts[(event.line_index, event.position)] = event.font_index
        forced_fonts[(event.line_index, event.position + 1)] = event.font_index
    for event in circled_events or []:
        forced_circled_fonts[(int(event["line_index"]), int(event["position"]))] = int(
            event["font_index"]
        )

    for line_index, line in enumerate(lines):
        glyphs: list[tuple[str, ImageFont.FreeTypeFont]] = []
        width = 0.0
        asc = 0
        for char_index, ch in enumerate(line):
            circled_index = forced_circled_fonts.get((line_index, char_index))
            f = (
                fonts.force_circled(ch, size, circled_index)
                if circled_index is not None
                else fonts.pick(ch, size, rng)
            )
            if f is None:
                raise ValueError(f"no locked font covers U+{ord(ch):04X} {ch!r}")
            forced_index = forced_fonts.get((line_index, char_index))
            if forced_index is not None:
                f = fonts.force_yi(ch, size, forced_index)
            glyphs.append((ch, f))
            width += f.getlength(ch) + tracking
            asc = max(asc, f.getbbox(ch)[3] if ch.strip() else asc)
        line_imgs.append((glyphs, width, size))
        max_w = max(max_w, int(width))

    line_h = int(size * 1.35)
    total_h = int(margin * 2 + len(lines) * (line_h + line_gap))
    total_w = int(max_w + margin * 2)
    total_w = max(total_w, 64)
    total_h = max(total_h, 48)

    img = paper_background(total_w, total_h, rng)
    draw = ImageDraw.Draw(img)
    y = float(margin)
    for glyphs, _width, _sz in line_imgs:
        x = float(margin) + rng.uniform(0, 6)
        jitter_ink = ink
        for ch, f in glyphs:
            dy = rng.uniform(-1.5, 1.5)
            shade = int(np.clip(jitter_ink + rng.normal(0, 8), 0, 90))
            draw.text((x, y + dy), ch, font=f, fill=(shade, shade, shade))
            x += f.getlength(ch) + tracking
        y += line_h + line_gap
    return img


def render_page(
    draft: SampleDraft,
    fonts: FontBook,
    rng: np.random.Generator,
    geometry_split: str,
) -> Image.Image:
    """Render positioned blocks without any family-specific reading logic."""
    if draft.layout_family not in PAGE_LAYOUT_FAMILIES or not draft.layout_data:
        raise ValueError("page draft lacks a supported layout plan")
    if geometry_split not in {"train", "dev"}:
        raise ValueError("geometry_split must be train or dev")

    if geometry_split == "train" and draft.layout_profile not in TRAIN_GEOMETRY_PROFILES:
        raise ValueError("train page lacks a registered train geometry profile")
    if geometry_split == "dev" and draft.layout_profile not in DEV_GEOMETRY_PROFILES:
        raise ValueError("dev page lacks a held-out dev geometry profile")
    data = draft.layout_data
    width = int(data["canvas_width"])
    height = int(data["canvas_height"])
    base_size = int(data["base_size"])
    ink = int(rng.integers(15, 55))
    blocks = data.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("page layout has no positioned blocks")

    forced_fonts: dict[tuple[int, int], int] = {}
    forced_circled_fonts: dict[tuple[int, int], int] = {}
    for event in draft.confusable_events or []:
        forced_fonts[(event.line_index, event.position)] = event.font_index
        forced_fonts[(event.line_index, event.position + 1)] = event.font_index
    for event in draft.circled_events or []:
        forced_circled_fonts[(int(event["line_index"]), int(event["position"]))] = int(
            event["font_index"]
        )

    prepared: dict[tuple[int, int, int, int, int], tuple[list[tuple[str, ImageFont.FreeTypeFont]], float]] = {}

    def prepare(
        line_index: int,
        max_width: int,
        requested_size: int,
        start: int = 0,
        end: int | None = None,
    ) -> tuple[list[tuple[str, ImageFont.FreeTypeFont]], float]:
        stop = len(draft.lines[line_index]) if end is None else end
        key = (line_index, max_width, requested_size, start, stop)
        if key in prepared:
            return prepared[key]
        for size in range(requested_size, 9, -1):
            tracking = size * 0.06
            glyphs: list[tuple[str, ImageFont.FreeTypeFont]] = []
            measured = 0.0
            for char_index, ch in enumerate(draft.lines[line_index][start:stop], start=start):
                forced_index = forced_fonts.get((line_index, char_index))
                circled_index = forced_circled_fonts.get((line_index, char_index))
                font = (
                    fonts.force_circled(ch, size, circled_index)
                    if circled_index is not None
                    else fonts.force_yi(ch, size, forced_index)
                    if forced_index is not None
                    else fonts.pick(ch, size, rng)
                )
                if font is None:
                    raise ValueError(f"no locked font covers U+{ord(ch):04X} {ch!r}")
                glyphs.append((ch, font))
                measured += font.getlength(ch) + tracking
            if measured <= max_width:
                prepared[key] = (glyphs, tracking)
                return prepared[key]
        raise ValueError(f"line {line_index} cannot fit its page block")

    image = paper_background(width, height, rng)
    draw = ImageDraw.Draw(image)

    def draw_line(
        line_index: int,
        x: float,
        y: float,
        max_width: int,
        requested_size: int = base_size,
        centered: bool = False,
        indent: float = 0.0,
        start: int = 0,
        end: int | None = None,
    ) -> None:
        usable_width = max(1, int(max_width - indent))
        glyphs, tracking = prepare(line_index, usable_width, requested_size, start, end)
        measured = sum(font.getlength(ch) + tracking for ch, font in glyphs)
        cursor = x + (max(0.0, (max_width - measured) / 2) if centered else indent)
        for ch, font in glyphs:
            shade = int(np.clip(ink + rng.normal(0, 7), 0, 90))
            draw.text(
                (cursor, y + rng.uniform(-1.3, 1.3)),
                ch,
                font=font,
                fill=(shade, shade, shade),
            )
            cursor += font.getlength(ch) + tracking

    for raw_block in blocks:
        if not isinstance(raw_block, dict):
            raise ValueError("positioned block is not an object")
        draw_line(
            int(raw_block["target_line_index"]),
            float(raw_block["x"]),
            float(raw_block["y"]),
            int(raw_block["w"]),
            requested_size=base_size + 5 if raw_block.get("role") == "title" else base_size,
            centered=raw_block.get("role") == "title",
            start=int(raw_block["target_char_start"]),
            end=int(raw_block["target_char_end"]),
        )
    return image


def degrade(
    img: Image.Image,
    rng: np.random.Generator,
    profile: str,
    allow_margin_artifacts: bool,
    safe_margin: int = 0,
) -> tuple[Image.Image, dict[str, object]]:
    """Apply V2/V3 bounded degradation, then cap the seven rejected tails."""
    if profile not in {"clear_print", "light", "heavy"}:
        raise ValueError(f"unsupported degradation profile: {profile}")
    artifacts: list[dict[str, object]] = []
    operations: list[str] = []
    if profile == "clear_print":
        return img, {
            "profile": profile,
            "operations": operations,
            "ink_mode": None,
            "parameters": {},
            "artifacts": artifacts,
            "attenuation": {"applied": False, "class_key": "clear_print", "strength": 1.0},
        }

    clean = img.copy()
    heavy = profile == "heavy"
    candidates = ["geometry", "ink", "blur", "resample", "jpeg"]
    if heavy:
        candidates.append("binarize")
    budget = 2 if heavy else 1
    chosen = [str(value) for value in rng.choice(candidates, size=budget, replace=False)]
    parameters: dict[str, object] = {}
    ink_mode: str | None = None
    for operation in chosen:
        operations.append(operation)
        if operation == "geometry":
            angle = float(rng.uniform(-2.0, 2.0) if heavy else rng.uniform(-0.8, 0.8))
            parameters["geometry_angle"] = angle
            img = img.rotate(angle, resample=Image.BILINEAR, expand=False, fillcolor=(245, 245, 243))
        elif operation == "ink":
            if rng.random() < 0.75:
                ink_mode = "spread_minfilter"
                img = img.filter(ImageFilter.MinFilter(3))
            else:
                ink_mode = "thinning_maxfilter"
                img = img.filter(ImageFilter.MaxFilter(3))
            parameters["ink_mode"] = ink_mode
        elif operation == "blur":
            radius = float(rng.uniform(0.35, 1.35 if heavy else 0.75))
            parameters["blur_radius"] = radius
            img = img.filter(ImageFilter.GaussianBlur(radius))
        elif operation == "resample":
            w, h = img.size
            scale = float(rng.uniform(0.58, 0.82) if heavy else rng.uniform(0.78, 0.95))
            parameters["resample_scale"] = scale
            img = img.resize((max(8, int(w * scale)), max(8, int(h * scale))), Image.BILINEAR).resize((w, h), Image.BILINEAR)
        elif operation == "binarize":
            gray = np.asarray(img.convert("L")).astype(np.float32)
            threshold_delta = float(rng.uniform(2, 14))
            threshold = float(gray.mean() - threshold_delta)
            parameters["binarize_threshold_delta"] = threshold_delta
            parameters["binarize_threshold"] = threshold
            img = Image.fromarray((gray > threshold).astype(np.uint8) * 255, "L").convert("RGB")
        elif operation == "jpeg":
            quality = int(rng.integers(45, 88))
            parameters["jpeg_quality"] = quality
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality)
            buffer.seek(0)
            img = Image.open(buffer).convert("RGB")

    # Large, faint edge/corner effects cannot be confused with punctuation tokens.
    if allow_margin_artifacts and rng.random() < 0.15:
        draw = ImageDraw.Draw(img, "RGBA")
        w, h = img.size
        count = int(rng.integers(1, 3))
        for _ in range(count):
            if rng.random() < 0.5:
                side = str(rng.choice(["left", "right"]))
                artifact_w = max(2, min(max(2, safe_margin // 3), int(w * rng.uniform(0.012, 0.025))))
                bbox = [0, 0, artifact_w, h] if side == "left" else [w - artifact_w, 0, w, h]
                draw.rectangle(tuple(bbox), fill=(80, 80, 70, int(rng.integers(8, 24))))
                artifact_type = "edge_shadow"
            else:
                corner = str(rng.choice(["tl", "tr", "bl", "br"]))
                radius = max(3, min(max(3, safe_margin // 2), int(min(w, h) * rng.uniform(0.02, 0.04))))
                cx = 0 if "l" in corner else w
                cy = 0 if "t" in corner else h
                bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
                draw.ellipse(tuple(bbox), fill=(105, 95, 75, int(rng.integers(8, 20))))
                artifact_type = "corner_stain"
            artifacts.append({"type": artifact_type, "bbox": bbox})

    tone_scale = float(rng.uniform(0.92 if not heavy else 0.86, 1.07))
    tone_offset = float(rng.uniform(-6 if not heavy else -12, 8))
    tone_sigma = float(rng.uniform(0.5, 3.0 if not heavy else 7.0))
    parameters["tone_sensor"] = {
        "scale": tone_scale,
        "offset": tone_offset,
        "noise_sigma": tone_sigma,
    }
    arr = np.asarray(img).astype(np.float32)
    arr = arr * tone_scale + tone_offset
    arr += rng.normal(0, tone_sigma, size=arr.shape)
    full_degraded = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    operations.append("tone_sensor")
    degradation: dict[str, object] = {
        "profile": profile,
        "operations": operations,
        "ink_mode": ink_mode,
        "parameters": parameters,
        "artifacts": artifacts,
    }
    output, attenuation = attenuation_policy.apply_attenuation(
        clean,
        full_degraded,
        degradation,
    )
    degradation["attenuation"] = attenuation
    return output, degradation


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #
def _weighted_counts(total: int, weights: dict[str, float]) -> dict[str, int]:
    keys = list(weights)
    values = np.array([weights[key] for key in keys], dtype=float)
    values /= values.sum()
    raw = values * total
    counts = np.floor(raw).astype(int)
    for index in np.argsort(-(raw - counts))[: total - int(counts.sum())]:
        counts[int(index)] += 1
    return {key: int(count) for key, count in zip(keys, counts)}


def plan_samples(
    total: int,
    ratio: dict[str, float],
    rng: np.random.Generator,
    split: str = "train",
) -> list[tuple[str, str, str | None, str]]:
    """Create an auditable anchor-plus-layout plan before any text is sampled."""
    plan: list[tuple[str, str, str | None]] = []

    def add_classes(granularity: str, family: str | None, count: int) -> None:
        for script_class, class_count in _weighted_counts(count, ratio).items():
            plan.extend((script_class, granularity, family) for _ in range(class_count))

    if split == "train" and total == FORMAL_TRAIN_N:
        # Byte-for-byte V1 anchor cardinalities: 4k line + 4k region + 4k page.
        frozen = {"pure_yi": 1600, "mixed": 1800, "pure_common": 600}
        for granularity, family in (
            ("line", None),
            ("region", None),
            ("page", "single_column_anchor"),
        ):
            for script_class, count in frozen.items():
                plan.extend((script_class, granularity, family) for _ in range(count))
        plan.extend(("mixed", "page", "stacked_interleaved_a") for _ in range(4000))
        plan.extend(("mixed", "page", "aligned_bilingual_rows") for _ in range(500))
        plan.extend(("mixed", "page", "independent_spatial_columns") for _ in range(500))
        add_classes("page", "two_column_flow", 1000)
    elif split == "dev" and total == FORMAL_DEV_N:
        add_classes("line", None, 120)
        add_classes("region", None, 520)
        add_classes("page", "single_column_anchor", 30)
        plan.extend(("mixed", "page", "stacked_interleaved_a") for _ in range(60))
        plan.extend(("mixed", "page", "aligned_bilingual_rows") for _ in range(15))
        plan.extend(("mixed", "page", "independent_spatial_columns") for _ in range(15))
        add_classes("page", "two_column_flow", 40)
    else:
        family_weights = {
            "line_anchor": 0.22,
            "region_anchor": 0.22,
            "single_column_anchor": 0.22,
            "stacked_interleaved_a": 0.22,
            "two_column_flow": 0.06,
            "aligned_bilingual_rows": 0.03,
            "independent_spatial_columns": 0.03,
        }
        for family, count in _weighted_counts(total, family_weights).items():
            if family == "line_anchor":
                add_classes("line", None, count)
            elif family == "region_anchor":
                add_classes("region", None, count)
            elif family == "stacked_interleaved_a":
                plan.extend(("mixed", "page", family) for _ in range(count))
            elif family in {"aligned_bilingual_rows", "independent_spatial_columns"}:
                plan.extend(("mixed", "page", family) for _ in range(count))
            else:
                add_classes("page", family, count)

    if len(plan) != total:
        raise RuntimeError(f"sample plan has {len(plan)} rows, expected {total}")
    profile_counters: Counter[tuple[str, str]] = Counter()
    tagged: list[tuple[str, str, str | None, str]] = []
    for script_class, granularity, family in plan:
        key = (granularity, family or f"{granularity}_anchor")
        clear_print = split == "dev" and profile_counters[key] % 5 == 0
        profile_counters[key] += 1
        tagged.append(
            (script_class, granularity, family, "clear_print" if clear_print else "standard")
        )
    order = rng.permutation(len(tagged))
    return [tagged[int(index)] for index in order]


def sync_positioned_blocks(draft: SampleDraft) -> None:
    if draft.granularity != "page" or not draft.layout_data:
        return
    blocks = draft.layout_data.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("page draft lacks positioned blocks")
    for block in blocks:
        if not isinstance(block, dict):
            raise ValueError("positioned block is not an object")
        line_index = int(block["target_line_index"])
        start = int(block["target_char_start"])
        end = int(block["target_char_end"])
        block["text"] = draft.lines[line_index][start:end]


def build_split(
    split: str,
    count: int,
    seed_seq: np.random.SeedSequence,
    fonts: FontBook,
    yi: list[str],
    han: list[str],
    build_dir: Path,
    seen_hashes: set[str],
    cfg: "BuildCfg",
    shape_pairs: list[dict[str, object]],
    workers: int = 1,
) -> list[dict]:
    plan_seq, samples_seq, circled_seq, confusable_seq = seed_seq.spawn(4)
    plan = plan_samples(count, cfg.ratio, np.random.default_rng(plan_seq), split)
    child_states = samples_seq.spawn(count)
    drafts: list[SampleDraft] = []
    for i, (cls, gran, forced_family, degrade_profile) in enumerate(plan):
        text_seq, render_root_seq = child_states[i].spawn(2)
        text_rng = np.random.default_rng(text_seq)
        if gran == "page":
            geometry_profiles = (
                TRAIN_GEOMETRY_PROFILES if cfg.geometry_split == "train" else DEV_GEOMETRY_PROFILES
            )
            layout_profile = str(text_rng.choice(geometry_profiles))
            lines, layout_family, layout_data = sample_page_document(
                cls, yi, han, text_rng, cfg, forced_family, layout_profile
            )
        else:
            lines = sample_lines(cls, gran, yi, han, text_rng, cfg)
            layout_family = f"{gran}_anchor"
            layout_data = {}
            layout_profile = layout_family
        drafts.append(
            SampleDraft(
                cls=cls,
                granularity=gran,
                lines=lines,
                render_attempt_seqs=render_root_seq.spawn(6),
                layout_family=layout_family,
                layout_data=layout_data,
                layout_profile=layout_profile,
                degrade_profile=degrade_profile,
            )
        )

    inject_circled_markers(
        drafts,
        split,
        np.random.default_rng(circled_seq),
    )
    inject_confusable_pairs(
        drafts,
        shape_pairs,
        cfg.confusable_repeats,
        np.random.default_rng(confusable_seq),
    )
    for draft in drafts:
        sync_positioned_blocks(draft)

    seen_lock = threading.Lock()
    thread_state = threading.local()

    def render_one(item: tuple[int, SampleDraft]) -> dict:
        i, draft = item
        cls = draft.cls
        gran = draft.granularity
        events = draft.confusable_events or []
        if workers == 1:
            render_fonts = fonts
        else:
            render_fonts = getattr(thread_state, "fonts", None)
            if render_fonts is None:
                render_fonts = FontBook()
                thread_state.fonts = render_fonts
        png_bytes = b""
        label = "\n".join(draft.lines) + "\n"
        degradation: dict[str, object] = {}
        for attempt_seq in draft.render_attempt_seqs:
            render_seq, degrade_seq = attempt_seq.spawn(2)
            render_rng = np.random.default_rng(render_seq)
            degrade_rng = np.random.default_rng(degrade_seq)
            img = (
                render_page(draft, render_fonts, render_rng, cfg.geometry_split)
                if gran == "page"
                else render_block(
                    draft.lines,
                    render_fonts,
                    render_rng,
                    events,
                    draft.circled_events,
                )
            )
            profile = (
                "clear_print"
                if draft.degrade_profile == "clear_print"
                else "heavy" if degrade_rng.random() < cfg.heavy_ratio else "light"
            )
            img, degradation = degrade(
                img,
                degrade_rng,
                profile,
                allow_margin_artifacts=gran == "page",
                safe_margin=int(draft.layout_data.get("margin", 0)) if draft.layout_data else 0,
            )
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            png_bytes = buf.getvalue()
            h = sha256_bytes(png_bytes)
            with seen_lock:
                if h not in seen_hashes:
                    seen_hashes.add(h)
                    break
        else:
            raise RuntimeError(f"could not produce unique image for sample {split}:{i}")

        rel = f"images/{split}/{cls}/{gran}/{i:06d}.png"
        out_path = build_dir / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(png_bytes)

        return {
                "id": f"synth_{split}_{i:06d}",
                "images": [rel],
                "messages": [
                    {"role": "user", "content": USER_PROMPT},
                    {"role": "assistant", "content": label},
                ],
                "meta": {
                    "source_kind": "synthetic",
                    "source_id": SOURCE_ID,
                    "script_class": cls,
                    "granularity": gran,
                    "layout_family": draft.layout_family,
                    "layout_profile": draft.layout_profile,
                    "layout_data": draft.layout_data,
                    "geometry_split": cfg.geometry_split,
                    "reading_order": "global_visual_rows_y_then_x",
                    "has_symbol": any(ch in SYMBOL_CHARS for ch in label),
                    "symbol_count": sum(ch in SYMBOL_CHARS for ch in label),
                    "degrade": str(degradation["profile"]),
                    "degradation": degradation,
                    "artifact_count": len(degradation["artifacts"]),
                    "artifacts": degradation["artifacts"],
                    "clear_print_probe": degradation["profile"] == "clear_print",
                    "confusable_eligible_lines": draft.confusable_eligible_lines,
                    "has_forced_confusable": bool(events),
                    "forced_confusable_count": len(events),
                    "confusable_events": [event.as_meta() for event in events],
                    "circled_events": list(draft.circled_events or []),
                    "has_forced_circled": bool(draft.circled_events),
                    "generator": GENERATOR_VERSION,
                },
            }

    items = list(enumerate(drafts))
    if workers == 1:
        return [render_one(item) for item in items]
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="layout-render") as pool:
        return list(pool.map(render_one, items))


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def manifest_inputs(include_formal_locks: bool = False) -> list[dict]:
    inputs: list[dict] = []
    for rel in (YI_UNICODE_REL, HAN_LEVEL1_REL):
        inputs.append(
            {"path": rel, "kind": "normative_standard", "sha256": sha256_file(PROJECT_ROOT / rel)}
        )
    for rel in YI_FONT_RELS:
        inputs.append({"path": rel, "kind": "font_asset", "sha256": sha256_file(PROJECT_ROOT / rel)})
    for rel in CJK_FONT_RELS:
        inputs.append(
            {"path": rel, "kind": "external_cjk_font", "sha256": sha256_file(PROJECT_ROOT / rel)}
        )
    for spec in CIRCLED_FONT_SPECS:
        rel = str(spec["path"])
        inputs.append(
            {
                "path": rel,
                "kind": "locked_circled_font",
                "font_id": spec["font_id"],
                "face_index": spec["face_index"],
                "sha256": sha256_file(PROJECT_ROOT / rel),
            }
        )
    for rel in (
        GENERATOR_REL,
        "scripts/post_v3_degradation_policy.py",
        SHAPE_GENERATOR_REL,
        "scripts/build_shape_pairs.py",
        CONFUSABLE_GENERATOR_REL,
    ):
        inputs.append(
            {
                "path": rel,
                "kind": "generator_code",
                "sha256": sha256_file(PROJECT_ROOT / rel),
            }
        )
    inputs.append(
        {
            "path": attenuation_policy.POLICY_REL,
            "kind": "owner_locked_degradation_policy",
            "sha256": sha256_file(PROJECT_ROOT / attenuation_policy.POLICY_REL),
        }
    )
    inputs.append(
        {
            "path": FROZEN_PAIR_ASSET_REL,
            "kind": "frozen_generic_shape_asset",
            "sha256": sha256_file(PROJECT_ROOT / FROZEN_PAIR_ASSET_REL),
        }
    )
    inputs.append(
        {
            "path": PARENT_V3_GENERATOR_REL,
            "kind": "frozen_parent_generator",
            "sha256": sha256_file(PROJECT_ROOT / PARENT_V3_GENERATOR_REL),
        }
    )
    if include_formal_locks:
        for rel, kind in (
            (FORMAL_SPEC_REL, "formal_build_spec"),
            (FORMAL_AUTHORIZATION_REL, "owner_formal_build_authorization"),
        ):
            inputs.append(
                {"path": rel, "kind": kind, "sha256": sha256_file(PROJECT_ROOT / rel)}
            )
    return inputs


def summarize(rows: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for r in rows:
        key = f"{r['meta']['script_class']}/{r['meta']['granularity']}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def summarize_layouts(rows: list[dict]) -> dict[str, int]:
    return dict(
        sorted(Counter(str(row["meta"]["layout_family"]) for row in rows).items())
    )


def summarize_layout_profiles(rows: list[dict]) -> dict[str, int]:
    return dict(
        sorted(Counter(str(row["meta"]["layout_profile"]) for row in rows).items())
    )


def summarize_circled(rows: list[dict]) -> dict[str, object]:
    marker_counts: Counter[str] = Counter()
    font_counts: Counter[str] = Counter()
    position_counts: Counter[str] = Counter()
    by_marker_font: dict[str, Counter[str]] = {marker: Counter() for marker in CIRCLED}
    for row in rows:
        for event in row["meta"].get("circled_events", []):
            marker = str(event["marker"])
            font_id = str(event["font_id"])
            position = str(event["position_kind"])
            marker_counts[marker] += 1
            font_counts[font_id] += 1
            position_counts[position] += 1
            by_marker_font[marker][font_id] += 1
    return {
        "events": sum(marker_counts.values()),
        "marker_counts": dict(sorted(marker_counts.items(), key=lambda item: ord(item[0]))),
        "font_counts": dict(sorted(font_counts.items())),
        "position_counts": dict(sorted(position_counts.items())),
        "by_marker_font": {
            marker: dict(sorted(counts.items()))
            for marker, counts in sorted(by_marker_font.items(), key=lambda item: ord(item[0]))
        },
    }


def validate_circled_summary(summary: dict[str, object], repeats: int) -> None:
    marker_counts = summary["marker_counts"]
    by_marker_font = summary["by_marker_font"]
    if not isinstance(marker_counts, dict) or marker_counts != {marker: repeats for marker in CIRCLED}:
        raise RuntimeError(f"circled marker counts differ from {repeats} each")
    if not isinstance(by_marker_font, dict):
        raise RuntimeError("circled per-marker font report is missing")
    for marker_index, marker in enumerate(CIRCLED):
        counts = by_marker_font.get(marker)
        if not isinstance(counts, dict):
            raise RuntimeError(f"circled font counts missing for {marker}")
        values = [int(counts.get(str(spec["font_id"]), 0)) for spec in CIRCLED_FONT_SPECS]
        expected = [7, 7, 7]
        expected[marker_index % 3] = 6
        if repeats == 20 and values != expected:
            raise RuntimeError(f"circled 6/7/7 rotation differs for {marker}: {values}")
        if repeats == 3 and values != [1, 1, 1]:
            raise RuntimeError(f"circled dev font counts differ for {marker}: {values}")
    positions = summary["position_counts"]
    if not isinstance(positions, dict) or set(positions) != {"line_start", "line_middle", "line_end"}:
        raise RuntimeError("circled position schedule lacks start, middle, or end")


def summarize_confusables_by_granularity(rows: list[dict]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts[str(row["meta"]["granularity"])] += len(row["meta"]["confusable_events"])
    return dict(sorted(counts.items()))


def summarize_symbols(rows: list[dict]) -> dict[str, int]:
    with_symbol = sum(bool(row["meta"]["has_symbol"]) for row in rows)
    page_rows = [row for row in rows if row["meta"]["granularity"] == "page"]
    return {
        "with_symbol": with_symbol,
        "without_symbol": len(rows) - with_symbol,
        "symbol_characters": sum(int(row["meta"]["symbol_count"]) for row in rows),
        "pages_with_symbol": sum(bool(row["meta"]["has_symbol"]) for row in page_rows),
        "pages_without_symbol": sum(not bool(row["meta"]["has_symbol"]) for row in page_rows),
    }


def summarize_degradation(rows: list[dict]) -> dict[str, object]:
    profiles: Counter[str] = Counter()
    operations: Counter[str] = Counter()
    artifacts: Counter[str] = Counter()
    ink_modes: Counter[str] = Counter()
    attenuation_strengths: Counter[str] = Counter()
    attenuated_classes: Counter[str] = Counter()
    clear_by_stratum: Counter[str] = Counter()
    for row in rows:
        meta = row["meta"]
        degradation = meta["degradation"]
        profiles[str(degradation["profile"])] += 1
        operations.update(str(value) for value in degradation["operations"])
        artifacts.update(str(value["type"]) for value in degradation["artifacts"])
        if degradation.get("ink_mode") is not None:
            ink_modes[str(degradation["ink_mode"])] += 1
        attenuation = degradation["attenuation"]
        attenuation_strengths[f"{float(attenuation['strength']):.2f}"] += 1
        if attenuation.get("applied"):
            attenuated_classes[str(attenuation["class_key"])] += 1
        if meta["clear_print_probe"]:
            clear_by_stratum[str(meta["layout_family"])] += 1
    return {
        "profiles": dict(sorted(profiles.items())),
        "operations": dict(sorted(operations.items())),
        "artifacts": dict(sorted(artifacts.items())),
        "ink_modes": dict(sorted(ink_modes.items())),
        "attenuation_strengths": dict(sorted(attenuation_strengths.items())),
        "attenuated_classes": dict(sorted(attenuated_classes.items())),
        "clear_print_by_stratum": dict(sorted(clear_by_stratum.items())),
    }


def symbol_histogram(rows: list[dict]) -> dict[str, int]:
    counts = {ch: 0 for ch in sorted(SYMBOL_CHARS)}
    for row in rows:
        label = row["messages"][1]["content"]
        for ch in label:
            if ch in counts:
                counts[ch] += 1
    return counts


def summarize_confusables(
    rows: list[dict],
    pair_count: int,
    repeats: int,
) -> dict[str, object]:
    pair_histogram: Counter[str] = Counter()
    font_histogram: Counter[str] = Counter()
    source_histogram: Counter[str] = Counter()
    by_script_class: Counter[str] = Counter()
    pair_font_histogram: Counter[tuple[str, str]] = Counter()
    eligible_lines = 0
    focus_samples = 0
    pair_occurrences = 0
    for row in rows:
        meta = row["meta"]
        eligible_lines += int(meta["confusable_eligible_lines"])
        events = meta["confusable_events"]
        if events:
            focus_samples += 1
        pair_occurrences += len(events)
        by_script_class[str(meta["script_class"])] += len(events)
        for event in events:
            pair_histogram[str(event["pair_id"])] += 1
            font_histogram[str(event["font_asset"])] += 1
            pair_font_histogram[
                (str(event["pair_id"]), str(event["font_asset"]))
            ] += 1
            source_histogram[str(event["source"])] += 1

    target = pair_count * repeats
    if sum(pair_histogram.values()) != pair_occurrences:
        raise RuntimeError("confusable pair histogram does not match event count")
    nested_pair_font_histogram: dict[str, dict[str, int]] = {}
    for (pair_id, font_asset), count in sorted(pair_font_histogram.items()):
        nested_pair_font_histogram.setdefault(pair_id, {})[font_asset] = count
    return {
        "eligible_lines": eligible_lines,
        "focus_samples": focus_samples,
        "pair_occurrences": pair_occurrences,
        "forced_characters": pair_occurrences * 2,
        "target_occurrences": target,
        "full_target_reached": pair_occurrences == target,
        "unique_pairs": len(pair_histogram),
        "pair_histogram": dict(sorted(pair_histogram.items())),
        "font_histogram": dict(sorted(font_histogram.items())),
        "pair_font_histogram": nested_pair_font_histogram,
        "source_histogram": dict(sorted(source_histogram.items())),
        "by_script_class": dict(sorted(by_script_class.items())),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build-id", required=True)
    ap.add_argument("--train-n", type=int, default=FORMAL_TRAIN_N)
    ap.add_argument("--dev-n", type=int, default=800)
    ap.add_argument("--seed", type=int, default=23)
    ap.add_argument("--overwrite", action="store_true")
    # class ratio (general direction: mixed + pure_yi dominant, pure_common small).
    # Exact split is a starting default only — sweep on the synthetic dev, not eval.
    ap.add_argument("--ratio-yi", type=float, default=0.40)
    ap.add_argument("--ratio-mixed", type=float, default=0.45)
    ap.add_argument("--ratio-common", type=float, default=0.15)
    ap.add_argument("--mixed-yi-frac", type=float, default=0.65)  # Yi-dominant within mixed
    ap.add_argument("--symbol-rate", type=float, default=0.35)  # frac of eligible lines with symbols
    ap.add_argument("--heavy-degrade", type=float, default=0.30)  # bounded heavy profile share
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args()

    is_formal = args.train_n == FORMAL_TRAIN_N and args.dev_n == FORMAL_DEV_N
    if is_formal:
        require_formal_authorization()

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.build_id):
        raise SystemExit("build-id must use only letters, numbers, dot, underscore, or hyphen")
    if args.train_n <= 0 or args.dev_n <= 0:
        raise SystemExit("train-n and dev-n must be positive")
    if args.workers <= 0 or args.workers > 32:
        raise SystemExit("workers must be within [1, 32]")
    ratio_values = (args.ratio_yi, args.ratio_mixed, args.ratio_common)
    if any(value < 0 for value in ratio_values) or sum(ratio_values) <= 0:
        raise SystemExit("training ratios must be non-negative and sum to more than zero")
    for name, value in (
        ("mixed-yi-frac", args.mixed_yi_frac),
        ("symbol-rate", args.symbol_rate),
        ("heavy-degrade", args.heavy_degrade),
    ):
        if not 0.0 <= value <= 1.0:
            raise SystemExit(f"{name} must be within [0, 1]")

    cfg = BuildCfg(
        ratio={
            "pure_yi": args.ratio_yi,
            "mixed": args.ratio_mixed,
            "pure_common": args.ratio_common,
        },
        mixed_yi_frac=args.mixed_yi_frac,
        symbol_rate=args.symbol_rate,
        heavy_ratio=args.heavy_degrade,
        confusable_repeats=TRAIN_CONFUSABLE_REPEATS,
        geometry_split="train",
    )
    dev_cfg = BuildCfg(
        ratio=DEV_RATIO,
        mixed_yi_frac=DEV_MIXED_YI_FRAC,
        symbol_rate=DEV_SYMBOL_RATE,
        heavy_ratio=DEV_HEAVY_RATIO,
        confusable_repeats=DEV_CONFUSABLE_REPEATS,
        geometry_split="dev",
    )

    folded_build_id = args.build_id.casefold()
    for tok in ("xuezu", "luoe", "雪族", "勒俄特依"):
        if tok.casefold() in folded_build_id:
            raise SystemExit(f"build-id contains forbidden token: {tok}")

    builds_root = PROJECT_ROOT / "builds"
    final_dir = builds_root / args.build_id
    stage_dir = builds_root / f".{args.build_id}.staging"
    if final_dir.exists():
        if not args.overwrite:
            raise SystemExit(f"build dir exists: {final_dir}")
        if not args.build_id.startswith("smoke_"):
            raise SystemExit("--overwrite is allowed only for smoke_* builds")
        shutil.rmtree(final_dir)
    if stage_dir.exists():
        raise SystemExit(f"staging dir already exists; inspect it before retrying: {stage_dir}")
    stage_dir.mkdir(parents=True)

    try:
        parent_v3_sha256 = sha256_file(PROJECT_ROOT / PARENT_V3_GENERATOR_REL)
        if parent_v3_sha256 != EXPECTED_PARENT_V3_GENERATOR_SHA256:
            raise RuntimeError(
                f"frozen V3 parent generator changed: {parent_v3_sha256}"
            )
        yi_rows, yi, han = load_charsets()
        print(f"[charset] yi={len(yi)} han={len(han)}")
        fonts = FontBook()
        print("[boundary] generator inputs are standards + locked fonts only")

        print("[confusable] loading frozen generic v3 coverage-floor shape pairs ...")
        frozen_pair_path = PROJECT_ROOT / FROZEN_PAIR_ASSET_REL
        shape_pairs = load_frozen_shape_pairs(
            frozen_pair_path,
            set(yi),
        )
        shape_pairs_path = stage_dir / "derived" / "yi_confusable_pairs.json"
        write_shape_pairs(shape_pairs_path, shape_pairs)
        validate_accepted_r3(shape_pairs_path, shape_pairs)
        shape_source_counts = dict(
            sorted(Counter(str(pair["source"]) for pair in shape_pairs).items())
        )
        print(
            f"[confusable] pairs={len(shape_pairs)} "
            f"sha256={sha256_file(shape_pairs_path)}"
        )

        root_seq = np.random.SeedSequence(args.seed)
        train_seq, dev_seq = root_seq.spawn(2)
        train_seen: set[str] = set()
        dev_seen: set[str] = set()

        print(f"[build] rendering train n={args.train_n} ...")
        train_rows = build_split(
            "train",
            args.train_n,
            train_seq,
            fonts,
            yi,
            han,
            stage_dir,
            train_seen,
            cfg,
            shape_pairs,
            args.workers,
        )
        print(f"[build] rendering frozen dev n={args.dev_n} ...")
        dev_rows = build_split(
            "dev",
            args.dev_n,
            dev_seq,
            fonts,
            yi,
            han,
            stage_dir,
            dev_seen,
            dev_cfg,
            shape_pairs,
            args.workers,
        )
        cross_split_hashes = train_seen & dev_seen
        if cross_split_hashes:
            raise RuntimeError("train/dev image hash overlap; refuse to publish build")

        train_jsonl = stage_dir / "jsonl" / "train.jsonl"
        dev_jsonl = stage_dir / "jsonl" / "dev.jsonl"
        write_jsonl(train_jsonl, train_rows)
        write_jsonl(dev_jsonl, dev_rows)

        train_confusables = summarize_confusables(
            train_rows, len(shape_pairs), cfg.confusable_repeats
        )
        dev_confusables = summarize_confusables(
            dev_rows, len(shape_pairs), dev_cfg.confusable_repeats
        )
        if is_formal and not train_confusables["full_target_reached"]:
            raise RuntimeError(
                "formal train build lacks full 2162-pair x 3-font x 2-context coverage"
            )
        if is_formal and not dev_confusables["full_target_reached"]:
            raise RuntimeError(
                "formal dev build lacks one complete v3 confusable cycle"
            )
        train_symbol_histogram = symbol_histogram(train_rows)
        train_circled = summarize_circled(train_rows)
        dev_circled = summarize_circled(dev_rows)
        missing_circled = [marker for marker in CIRCLED if train_symbol_histogram.get(marker, 0) == 0]
        if is_formal and missing_circled:
            raise RuntimeError(
                f"formal train build lacks circled markers: {''.join(missing_circled)}"
            )
        if is_formal:
            validate_circled_summary(train_circled, 20)
            validate_circled_summary(dev_circled, 3)

        manifest = {
            "build_id": args.build_id,
            "build_profile": FORMAL_PROFILE_ID if is_formal else DEVELOPMENT_PROFILE,
            "generator": GENERATOR_VERSION,
            "seed": args.seed,
            "training_data_origin": "synthetic_only",
            "source_id": SOURCE_ID,
            "v3_core_preservation": {
                "parent_generator": PARENT_V3_GENERATOR_REL,
                "parent_generator_sha256": parent_v3_sha256,
                "han_source": HAN_LEVEL1_REL,
                "han_source_sha256": sha256_file(PROJECT_ROOT / HAN_LEVEL1_REL),
                "yi_fonts": YI_FONT_RELS,
                "confusable_scheduler": CONFUSABLE_GENERATOR_REL,
                "confusable_scheduler_sha256": sha256_file(
                    PROJECT_ROOT / CONFUSABLE_GENERATOR_REL
                ),
                "only_core_change": (
                    "circled markers extended to ①-⑳ with an exact three-font, "
                    "line-start/middle/end schedule"
                ),
            },
            "render_workers": args.workers,
            "config": {
                "train": {
                    "ratio": cfg.ratio,
                    "mixed_yi_frac": cfg.mixed_yi_frac,
                    "symbol_rate": cfg.symbol_rate,
                    "heavy_degrade": cfg.heavy_ratio,
                    "confusable_pair_repeats": cfg.confusable_repeats,
                    "geometry_split": cfg.geometry_split,
                },
                "dev": {
                    "frozen_across_sweeps": True,
                    "ratio": dev_cfg.ratio,
                    "mixed_yi_frac": dev_cfg.mixed_yi_frac,
                    "symbol_rate": dev_cfg.symbol_rate,
                    "heavy_degrade": dev_cfg.heavy_ratio,
                    "confusable_pair_repeats": dev_cfg.confusable_repeats,
                    "geometry_split": dev_cfg.geometry_split,
                },
            },
            "inputs": manifest_inputs(include_formal_locks=is_formal),
            "outputs": {
                "train_jsonl": {
                    "path": "jsonl/train.jsonl",
                    "sha256": sha256_file(train_jsonl),
                    "rows": len(train_rows),
                },
                "dev_jsonl": {
                    "path": "jsonl/dev.jsonl",
                    "sha256": sha256_file(dev_jsonl),
                    "rows": len(dev_rows),
                },
                "confusable_pairs": {
                    "path": "derived/yi_confusable_pairs.json",
                    "sha256": sha256_file(shape_pairs_path),
                    "pairs": len(shape_pairs),
                },
            },
            "confusable_derivation": {
                "algorithm": SHAPE_ALGORITHM_VERSION,
                "accepted_shape_pair_sha256": EXPECTED_SHAPE_PAIRS_SHA256,
                "frozen_pair_asset": {
                    "path": FROZEN_PAIR_ASSET_REL,
                    "sha256": sha256_file(frozen_pair_path),
                },
                "pair_count": EXPECTED_PAIR_COUNT,
                "source_counts": shape_source_counts,
                "cluster_fonts": YI_FONT_RELS[:SHAPE_CLUSTER_FONT_COUNT],
                "parameters": {
                    "feature_sizes": list(SHAPE_FEATURE_SIZES),
                    "views_per_size": 5,
                    "cluster_top_k": CLUSTER_TOP_K,
                    "cluster_min_font_support": CLUSTER_MIN_FONT_SUPPORT,
                    "font_specific_min_view_ratio": FONT_SPECIFIC_MIN_VIEW_RATIO,
                    "font_specific_min_clean_sizes": FONT_SPECIFIC_MIN_CLEAN_SIZES,
                    "coverage_floor": {
                        "source": SHAPE_COVERAGE_SOURCE,
                        "rule": SHAPE_COVERAGE_RULE,
                        "selection_sizes": list(SHAPE_SELECTION_SIZES),
                        "selection_mutual_top_k": SHAPE_SELECTION_MUTUAL_TOP_K,
                        "selection_minimum_multifont_support": SHAPE_SELECTION_MIN_MULTIFONT_SUPPORT,
                    },
                },
                "runtime": {
                    "numpy": np.__version__,
                    "pillow": PIL_VERSION,
                    "freetype": getattr(ImageFont.core, "freetype2_version", "unknown"),
                },
            },
            "counts": {"train": summarize(train_rows), "dev": summarize(dev_rows)},
            "layouts": {
                "contract": {
                    "input": "whole_page_image",
                    "output": "plain_ocr_text_with_newlines",
                    "direction": "global_visual_rows_y_then_x",
                    "same_baseline_blocks": "concatenate_left_to_right_into_one_target_line",
                    "coordinate_blocks": "x_y_w_h_absolute_pixels",
                    "target_from_coordinates_only": True,
                    "audit_independently_recomputes_target": True,
                    "script_affects_order": False,
                    "unlabelled_scan_artifacts": "margin_edge_shadow_or_corner_stain_only",
                    "max_degradation_operations": {"light": 1, "heavy": 2},
                    "direction_randomized": False,
                    "external_layout_preprocessing": False,
                    "train_dev_geometry_profiles_disjoint": True,
                },
                "train": summarize_layouts(train_rows),
                "dev": summarize_layouts(dev_rows),
                "profiles": {
                    "train": summarize_layout_profiles(train_rows),
                    "dev": summarize_layout_profiles(dev_rows),
                },
            },
            "symbols": {
                "train": summarize_symbols(train_rows),
                "dev": summarize_symbols(dev_rows),
                "train_histogram": train_symbol_histogram,
                "dev_histogram": symbol_histogram(dev_rows),
                "circled_train": train_circled,
                "circled_dev": dev_circled,
            },
            "degradation": {
                "train": summarize_degradation(train_rows),
                "dev": summarize_degradation(dev_rows),
            },
            "confusables": {
                "train": {
                    **train_confusables,
                    "by_granularity": summarize_confusables_by_granularity(train_rows),
                },
                "dev": {
                    **dev_confusables,
                    "by_granularity": summarize_confusables_by_granularity(dev_rows),
                },
            },
            "unique_image_hashes": len(train_seen | dev_seen),
            "train_dev_image_hash_overlap": 0,
        }
        (stage_dir / "build_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        stage_dir.rename(final_dir)
    except Exception:
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise

    print(f"[done] build at {final_dir}")
    print(
        f"[done] train_rows={len(train_rows)} dev_rows={len(dev_rows)} "
        f"unique_images={len(train_seen | dev_seen)}"
    )
    print(f"[done] train counts: {manifest['counts']['train']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
