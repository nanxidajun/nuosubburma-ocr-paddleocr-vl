#!/usr/bin/env python3
"""Hybrid line/region segmentation probe for scanned book pages.

Version 1/2 answered: "Can this page be split into lines?"
Version 3 answers: "Which detected regions should go to line OCR, region OCR,
or page-type-specific handling?"

The script remains model-free. It uses OpenCV/numpy only and writes visual
debug artifacts for human review.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from line_segmentation_probe import (
    IMAGE_EXTS,
    Box,
    binarize,
    detect_columns,
    detect_lines_in_region,
    draw_boxes,
    make_contact_sheet,
    read_image,
    remove_page_rules,
    sort_boxes,
    write_image,
)


@dataclass
class ClassifiedBox:
    index: int
    box: Box
    label: str
    action: str
    reason: str


LABEL_COLORS = {
    "body_line": (0, 150, 0),
    "toc_line": (60, 140, 255),
    "toc_region_fallback": (0, 120, 255),
    "mixed_cover_line": (0, 150, 0),
    "mixed_region_fallback": (0, 120, 255),
    "paired_yi_phonetic_region": (0, 100, 255),
    "footnote_region": (255, 0, 180),
    "header_line": (160, 160, 160),
    "footer_or_page_number": (120, 120, 120),
    "border_or_rule": (0, 0, 255),
    "cover_or_low_quality": (80, 80, 255),
    "ornament_or_cover_art": (90, 90, 220),
    "handwritten_mark": (80, 80, 80),
    "region_fallback": (0, 80, 255),
}

VALID_PAGE_HINTS = {
    "body_page",
    "toc",
    "mixed_page",
    "mixed_cover_page",
    "cover_or_low_quality",
}

PAGE_HINT_ALIASES = {
    "body": "body_page",
    "body_page": "body_page",
    "normal": "body_page",
    "正文": "body_page",
    "普通正文": "body_page",
    "toc": "toc",
    "目录": "toc",
    "mixed": "mixed_page",
    "mixed_page": "mixed_page",
    "混排": "mixed_page",
    "正文混排": "mixed_page",
    "mixed_cover": "mixed_cover_page",
    "mixed_cover_page": "mixed_cover_page",
    "封面混排": "mixed_cover_page",
    "cover": "cover_or_low_quality",
    "low_quality": "cover_or_low_quality",
    "cover_or_low_quality": "cover_or_low_quality",
    "封面": "cover_or_low_quality",
    "低质量": "cover_or_low_quality",
}


def normalize_page_hint(raw_hint: str) -> str:
    hint = raw_hint.strip()
    if not hint:
        raise ValueError("page_hint is empty")
    normalized = PAGE_HINT_ALIASES.get(hint) or PAGE_HINT_ALIASES.get(hint.lower())
    if normalized not in VALID_PAGE_HINTS:
        allowed = ", ".join(sorted(VALID_PAGE_HINTS))
        raise ValueError(f"Unknown page_hint `{raw_hint}`. Allowed values: {allowed}")
    return normalized


def read_page_manifest(path: Path | None) -> dict[str, str]:
    """Read an optional file/page_hint manifest.

    The manifest makes the pipeline reusable on books whose image names do not
    contain useful words like "目录" or "混排". It accepts either exact file
    names (`page_001.png`) or stems (`page_001`) in the `file` column.
    """
    if path is None:
        return {}

    hints: dict[str, str] = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"file", "page_hint"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Page manifest {path} is missing columns: {', '.join(sorted(missing))}")

        for line_no, row in enumerate(reader, start=2):
            file_key = (row.get("file") or "").strip()
            raw_hint = (row.get("page_hint") or "").strip()
            if not file_key and not raw_hint:
                continue
            if not file_key or not raw_hint:
                raise ValueError(f"Invalid manifest row {line_no}: both file and page_hint are required")

            hint = normalize_page_hint(raw_hint)
            keys = {file_key, Path(file_key).name, Path(file_key).stem}
            for key in keys:
                existing = hints.get(key)
                if existing is not None and existing != hint:
                    raise ValueError(f"Conflicting page_hint for `{key}` in {path}: {existing} vs {hint}")
                hints[key] = hint

    return hints


def infer_page_hint(path: Path, img: np.ndarray, boxes: list[Box], manifest_hints: dict[str, str] | None = None) -> str:
    """Infer a coarse page hint for this probe.

    File names are allowed as hints here because the current folder is a
    manually curated diagnostic set. Production code should replace this with
    page classifiers or layout heuristics.
    """
    manifest_hints = manifest_hints or {}
    if path.name in manifest_hints:
        return manifest_hints[path.name]
    if path.stem in manifest_hints:
        return manifest_hints[path.stem]

    name = path.stem
    h, _ = img.shape[:2]
    if "低质量" in name:
        return "cover_or_low_quality"
    if "封面混排" in name:
        return "mixed_cover_page"
    if "封面" in name:
        return "cover_or_low_quality"
    if "目录" in name:
        return "toc"
    if "混排" in name:
        return "mixed_page"
    if len(boxes) <= 1 and boxes and boxes[0].h > 0.55 * h:
        return "cover_or_low_quality"
    return "body_page"


def classify_box(box: Box, page_hint: str, page_h: int, page_w: int, reference_h: float) -> tuple[str, str, str]:
    """Classify a detected box into a routing label."""
    safe_ref_h = max(1.0, reference_h)

    if box.w > 0.72 * page_w and box.h < max(24, int(0.018 * page_h)):
        return "border_or_rule", "ignore", "thin full-width horizontal rule"

    if page_hint == "cover_or_low_quality":
        return "cover_or_low_quality", "special_page_handling", "cover/low-quality page is not a body-line target"

    if page_hint == "mixed_cover_page":
        if box.w > 0.88 * page_w and (box.y < 0.22 * page_h or box.y2 > 0.90 * page_h) and box.h > 0.10 * page_h:
            return "ornament_or_cover_art", "ignore_or_special_page_region", "large cover ornament/art block"
        if box.w < 0.23 * page_w and box.y > 0.70 * page_h:
            return "handwritten_mark", "ignore", "small handwritten/mark-like cover crop"
        if box.h > max(1.60 * safe_ref_h, 0.070 * page_h):
            return "mixed_region_fallback", "region_ocr", "mixed cover text block likely contains multiple logical lines"
        return "mixed_cover_line", "line_ocr", "usable line-like text on mixed cover"

    if box.y < 0.075 * page_h and box.h < 1.6 * safe_ref_h:
        return "header_line", "optional_ignore_or_metadata", "top-page header band"

    if box.y < 0.13 * page_h and box.w < 0.45 * page_w and box.h < 1.35 * safe_ref_h:
        return "header_line", "optional_ignore_or_metadata", "top-page short header/page-number band"

    if box.y2 > 0.945 * page_h and box.h < 1.35 * safe_ref_h:
        return "footer_or_page_number", "optional_ignore_or_metadata", "bottom-page footer/page-number band"

    if page_hint != "body_page" and box.y > 0.70 * page_h and box.h > max(1.55 * safe_ref_h, 0.045 * page_h):
        return "footnote_region", "region_ocr", "bottom dense/merged annotation region"

    if page_hint == "toc":
        if box.y2 < 0.36 * page_h:
            return "header_line", "optional_ignore_or_metadata", "toc header/front-matter band"
        if box.w < 0.18 * page_w and box.y < 0.45 * page_h:
            return "header_line", "optional_ignore_or_metadata", "small upper-page toc artifact"
        if box.h > max(1.70 * safe_ref_h, 0.070 * page_h):
            return "toc_region_fallback", "region_ocr", "table-of-contents block likely contains multiple lines"
        return "toc_line", "line_ocr_with_toc_reconstruction", "table-of-contents line"

    if page_hint == "mixed_page" and box.h > max(1.55 * safe_ref_h, 0.055 * page_h):
        return "paired_yi_phonetic_region", "region_ocr", "mixed Yi/phonetic lines likely merged as a paired region"

    if box.h > max(1.55 * safe_ref_h, 0.060 * page_h):
        return "region_fallback", "region_ocr", "box is much taller than normal line height"

    return "body_line", "line_ocr", "normal body line"


def draw_classified_boxes(img: np.ndarray, classified: list[ClassifiedBox]) -> np.ndarray:
    out = img.copy()
    for item in classified:
        box = item.box
        color = LABEL_COLORS.get(item.label, (0, 0, 255))
        cv2.rectangle(out, (box.x, box.y), (box.x2, box.y2), color, 3)
        label = f"{item.index}:{item.label}"
        cv2.putText(
            out,
            label,
            (box.x, max(22, box.y - 7)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )
    return out


def estimate_reference_line_h(boxes: list[Box], page_h: int) -> float:
    """Estimate normal line height without letting merged paragraphs dominate."""
    heights = [box.h for box in boxes if box.h > 0]
    if not heights:
        return 0.0

    plausible_ceiling = max(90, int(page_h * 0.085))
    plausible = [height for height in heights if height <= plausible_ceiling]
    if plausible:
        return float(np.percentile(plausible, 35))

    # If every detected box is large, assume the page-level detector merged
    # lines and keep the reference height small enough to trigger v4 fallback.
    fallback_cap = max(70, int(page_h * 0.045))
    return min(float(np.percentile(heights, 35)), float(fallback_cap))


def process_image(
    path: Path,
    out_dir: Path,
    manifest_hints: dict[str, str] | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    img = read_image(path)
    page_h, page_w = img.shape[:2]
    binary = remove_page_rules(binarize(img))
    columns = detect_columns(binary)

    boxes: list[Box] = []
    for col_idx, region in enumerate(columns):
        boxes.extend(detect_lines_in_region(binary, region, col_idx))
    boxes = sort_boxes(boxes)

    page_hint = infer_page_hint(path, img, boxes, manifest_hints)
    heights = [box.h for box in boxes]
    median_h = float(np.median(heights)) if heights else 0.0
    reference_h = estimate_reference_line_h(boxes, page_h)

    classified: list[ClassifiedBox] = []
    box_rows: list[dict[str, object]] = []
    for idx, box in enumerate(boxes, start=1):
        label, action, reason = classify_box(box, page_hint, page_h, page_w, reference_h)
        item = ClassifiedBox(idx, box, label, action, reason)
        classified.append(item)

        crop = img[box.y : box.y2, box.x : box.x2]
        crop_path = out_dir / "crops_by_label" / label / path.stem / f"box_{idx:03d}.png"
        write_image(crop_path, crop)

        box_rows.append(
            {
                "file": path.name,
                "page_hint": page_hint,
                "index": idx,
                "x": box.x,
                "y": box.y,
                "w": box.w,
                "h": box.h,
                "label": label,
                "action": action,
                "reason": reason,
                "crop_path": str(crop_path.relative_to(out_dir)),
            }
        )

    vis = draw_classified_boxes(img, classified)
    write_image(out_dir / "visualizations" / f"{path.stem}__classified_boxes.png", vis)

    crops = [img[item.box.y : item.box.y2, item.box.x : item.box.x2] for item in classified]
    sheet = make_contact_sheet(crops)
    if sheet is not None:
        write_image(out_dir / "contact_sheets" / f"{path.stem}__sheet.png", sheet)

    counts = Counter(item.label for item in classified)
    page_row = {
        "file": path.name,
        "page_hint": page_hint,
        "boxes": len(classified),
        "reference_line_h": round(reference_h, 1),
        "median_line_h": round(median_h, 1),
        "body_line": counts["body_line"],
        "toc_line": counts["toc_line"],
        "mixed_cover_line": counts["mixed_cover_line"],
        "region_ocr": sum(1 for item in classified if item.action == "region_ocr"),
        "ignored_or_metadata": sum(
            1 for item in classified if item.action in {"ignore", "optional_ignore_or_metadata", "ignore_or_special_page_region"}
        ),
        "special_page": sum(1 for item in classified if item.action == "special_page_handling"),
        "labels": ";".join(f"{k}={v}" for k, v in sorted(counts.items())),
        "next_action": recommend_next_action(page_hint, counts),
    }
    return page_row, box_rows


def recommend_next_action(page_hint: str, counts: Counter[str]) -> str:
    if page_hint == "cover_or_low_quality":
        return "exclude_from_body_line_test_or_handle_as_special_page"
    if page_hint == "mixed_cover_page":
        return "line_ocr_for_text_boxes_ignore_ornaments_region_ocr_for_merged_mixed_boxes"
    if counts["footnote_region"] or counts["mixed_region_fallback"] or counts["region_fallback"]:
        return "line_ocr_for_clean_boxes_plus_region_ocr_for_fallback_boxes"
    if counts["paired_yi_phonetic_region"]:
        return "region_ocr_for_yi_phonetic_pairs"
    if page_hint == "toc":
        return "line_ocr_plus_toc_reconstruction"
    return "line_ocr"


def write_reports(out_dir: Path, page_rows: list[dict[str, object]], box_rows: list[dict[str, object]]) -> None:
    report_dir = out_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    page_fields = [
        "file",
        "page_hint",
        "boxes",
        "reference_line_h",
        "median_line_h",
        "body_line",
        "toc_line",
        "mixed_cover_line",
        "region_ocr",
        "ignored_or_metadata",
        "special_page",
        "labels",
        "next_action",
    ]
    with (report_dir / "hybrid_page_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=page_fields)
        writer.writeheader()
        writer.writerows(page_rows)

    box_fields = [
        "file",
        "page_hint",
        "index",
        "x",
        "y",
        "w",
        "h",
        "label",
        "action",
        "reason",
        "crop_path",
    ]
    with (report_dir / "hybrid_box_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=box_fields)
        writer.writeheader()
        writer.writerows(box_rows)

    totals = Counter()
    for row in box_rows:
        totals[str(row["label"])] += 1

    with (report_dir / "hybrid_segmentation_probe.md").open("w", encoding="utf-8") as f:
        f.write("# Hybrid Line-Region Segmentation Probe v3\n\n")
        f.write("This report is generated by CPU-only OpenCV preprocessing. No OCR model is called.\n\n")
        f.write("The goal is routing, not universal line cutting:\n\n")
        f.write("```text\n")
        f.write("body_line / toc_line / mixed_cover_line -> line OCR\n")
        f.write("footnote_region / mixed_region_fallback / paired_yi_phonetic_region / region_fallback / toc_region_fallback -> region OCR\n")
        f.write("header/footer/border -> ignore or metadata\n")
        f.write("cover_or_low_quality / ornament_or_cover_art / handwritten_mark -> special handling or ignore\n")
        f.write("```\n\n")
        f.write("## Totals\n\n")
        f.write("| label | boxes |\n")
        f.write("|---|---:|\n")
        for label, count in sorted(totals.items()):
            f.write(f"| {label} | {count} |\n")

        f.write("\n## Page Summary\n\n")
        f.write(
            "| file | page_hint | boxes | body_line | toc_line | mixed_cover_line | region_ocr | ignored/meta | special | next_action |\n"
        )
        f.write("|---|---|---:|---:|---:|---:|---:|---:|---:|---|\n")
        for row in page_rows:
            f.write(
                f"| {row['file']} | {row['page_hint']} | {row['boxes']} | {row['body_line']} | "
                f"{row['toc_line']} | {row['mixed_cover_line']} | {row['region_ocr']} | {row['ignored_or_metadata']} | "
                f"{row['special_page']} | {row['next_action']} |\n"
            )

        f.write("\n## Artifacts\n\n")
        f.write("- Classified boxes: `visualizations/*__classified_boxes.png`\n")
        f.write("- Contact sheets: `contact_sheets/*__sheet.png`\n")
        f.write("- Routed crops: `crops_by_label/<label>/<page>/box_*.png`\n")
        f.write("- Per-box CSV: `reports/hybrid_box_summary.csv`\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("page_images"))
    parser.add_argument("--output", type=Path, default=Path("crop_pipeline_output/01_v3_routing"))
    parser.add_argument(
        "--page-manifest",
        type=Path,
        help="Optional CSV with columns: file,page_hint. Overrides filename-based page hint inference.",
    )
    args = parser.parse_args()

    images = sorted(p for p in args.input.iterdir() if p.suffix.lower() in IMAGE_EXTS and p.is_file())
    args.output.mkdir(parents=True, exist_ok=True)
    manifest_hints = read_page_manifest(args.page_manifest)

    page_rows: list[dict[str, object]] = []
    box_rows: list[dict[str, object]] = []
    for path in images:
        print(f"Processing {path.name}...")
        page_row, per_box = process_image(path, args.output, manifest_hints)
        page_rows.append(page_row)
        box_rows.extend(per_box)

    write_reports(args.output, page_rows, box_rows)
    print(f"Done. Wrote hybrid routing probe to {args.output}")


if __name__ == "__main__":
    main()
