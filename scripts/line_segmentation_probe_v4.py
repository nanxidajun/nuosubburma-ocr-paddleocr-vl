#!/usr/bin/env python3
"""Secondary split probe for v3 region-fallback boxes.

v3 routes page crops into line OCR, region OCR, ignore, or special handling.
v4 only revisits the boxes that v3 routed to region OCR and asks:

1. Can this region be split into stable smaller lines?
2. If yes, should those smaller crops become secondary line OCR candidates?
3. If no, should the original region remain a region OCR training/eval sample?

This is still model-free OpenCV preprocessing. It is a diagnostic probe, not a
claim that all large regions can or should be split into single lines.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from line_segmentation_probe import (
    Box,
    binarize,
    find_intervals,
    make_contact_sheet,
    read_image,
    write_image,
)


REGION_LABELS = {
    "region_fallback",
    "mixed_region_fallback",
    "toc_region_fallback",
    "paired_yi_phonetic_region",
    "footnote_region",
}


@dataclass
class SecondarySplit:
    index: int
    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h


def merge_close_intervals(intervals: list[tuple[int, int]], max_gap: int) -> list[tuple[int, int]]:
    if not intervals:
        return []
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= max_gap:
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))
    return merged


def local_line_split(crop: np.ndarray, parent_label: str = "") -> list[SecondarySplit]:
    """Attempt a conservative local horizontal split inside one v3 region."""
    h, w = crop.shape[:2]
    if h < 32 or w < 40:
        return []

    binary = binarize(crop)

    projection = binary.sum(axis=1) / 255
    positive = projection[projection > 0]
    if len(positive) == 0:
        return []

    # Local splitting should be more sensitive than page-level detection, but
    # not so sensitive that a single Yi line fragments into stroke bands.
    floor_ratio = 0.0034 if parent_label == "toc_region_fallback" else 0.0018
    merge_gap_ratio = 0.004 if parent_label == "toc_region_fallback" else 0.006
    threshold = max(float(np.percentile(positive, 18)) * 0.45, w * floor_ratio, 1.0)
    active = projection > threshold
    intervals = find_intervals(active)
    intervals = merge_close_intervals(intervals, max_gap=max(1, int(h * merge_gap_ratio)))

    min_h = max(8, int(h * 0.030))
    y_pad = max(2, int(h * 0.010))
    x_pad = max(3, int(w * 0.008))
    splits: list[SecondarySplit] = []

    for start, end in intervals:
        if end - start < min_h:
            continue
        y1 = max(0, start - y_pad)
        y2 = min(h, end + y_pad)
        line_bin = binary[y1:y2, :]
        col_projection = line_bin.sum(axis=0) / 255
        col_active = col_projection > max(1, (y2 - y1) * 0.020)
        col_intervals = find_intervals(col_active)
        if not col_intervals:
            continue
        x1 = max(0, min(a for a, _ in col_intervals) - x_pad)
        x2 = min(w, max(b for _, b in col_intervals) + x_pad)
        if x2 - x1 < max(24, int(w * 0.08)):
            continue
        splits.append(SecondarySplit(len(splits) + 1, x1, y1, x2 - x1, y2 - y1))

    return filter_spurious_splits(splits)


def filter_spurious_splits(splits: list[SecondarySplit]) -> list[SecondarySplit]:
    """Drop very thin pseudo-lines that are usually borders/noise.

    This keeps legitimate small footnote lines because the threshold is relative
    to the median split height in the same parent region.
    """
    if len(splits) <= 1:
        return splits

    median_h = float(np.median([split.h for split in splits]))
    min_reasonable_h = max(14, int(median_h * 0.35))
    filtered = [split for split in splits if split.h >= min_reasonable_h]
    if not filtered:
        return splits

    return [
        SecondarySplit(index + 1, split.x, split.y, split.w, split.h)
        for index, split in enumerate(filtered)
    ]


def split_quality(splits: list[SecondarySplit], parent_h: int) -> dict[str, object]:
    if not splits:
        return {
            "split_count": 0,
            "median_h": 0.0,
            "min_gap": "",
            "height_cv": "",
            "stable": False,
        }

    heights = np.array([s.h for s in splits], dtype=np.float32)
    gaps = [splits[i + 1].y - splits[i].y2 for i in range(len(splits) - 1)]
    median_h = float(np.median(heights))
    height_cv = float(np.std(heights) / max(1.0, np.mean(heights)))
    min_gap = int(min(gaps)) if gaps else ""

    stable = True
    if len(splits) <= 1:
        stable = False
    if median_h > parent_h * 0.65:
        stable = False
    if height_cv > 0.75 and len(splits) >= 3:
        stable = False

    return {
        "split_count": len(splits),
        "median_h": round(median_h, 1),
        "min_gap": min_gap,
        "height_cv": round(height_cv, 3),
        "stable": stable,
    }


def decide_secondary_action(parent_label: str, quality: dict[str, object]) -> tuple[str, str]:
    split_count = int(quality["split_count"])
    stable = bool(quality["stable"])

    if split_count <= 1:
        return "keep_region_ocr", "secondary split found no reliable internal lines"

    if parent_label == "paired_yi_phonetic_region":
        return (
            "secondary_split_possible_but_keep_region_default",
            "Yi + phonetic paired text can be split visually, but keeping the pair as a region preserves layout semantics",
        )

    if parent_label == "footnote_region":
        if stable and split_count >= 3:
            return (
                "secondary_line_candidate_needs_review",
                "footnote region has visible internal line candidates but remains dense and should be reviewed",
            )
        return "keep_region_ocr", "dense footnote/annotation region is not reliably splittable"

    if stable:
        return "secondary_line_candidate", "stable local line candidates detected"

    return "keep_region_ocr", "secondary split looks unstable; keep original region"


def draw_v4_overlay(img: np.ndarray, parent_boxes: list[tuple[Box, str]], split_boxes: list[tuple[Box, str]]) -> np.ndarray:
    out = img.copy()
    parent_colors = {
        "region_fallback": (0, 120, 255),
        "mixed_region_fallback": (0, 100, 255),
        "toc_region_fallback": (60, 140, 255),
        "paired_yi_phonetic_region": (255, 120, 0),
        "footnote_region": (255, 0, 180),
    }
    for i, (box, label) in enumerate(parent_boxes, start=1):
        color = parent_colors.get(label, (0, 120, 255))
        cv2.rectangle(out, (box.x, box.y), (box.x2, box.y2), color, 4)
        cv2.putText(
            out,
            f"R{i}:{label}",
            (box.x, max(24, box.y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            color,
            2,
            cv2.LINE_AA,
        )

    for i, (box, decision) in enumerate(split_boxes, start=1):
        color = (0, 170, 0) if "secondary_line_candidate" in decision else (100, 100, 255)
        cv2.rectangle(out, (box.x, box.y), (box.x2, box.y2), color, 2)
        cv2.putText(
            out,
            f"s{i}",
            (box.x, min(out.shape[0] - 6, box.y2 + 18)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            color,
            2,
            cv2.LINE_AA,
        )
    return out


def read_v3_regions(summary_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with summary_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["label"] in REGION_LABELS or row["action"] == "region_ocr":
                rows.append(row)
    return rows


def process_regions(image_dir: Path, v3_summary: Path, out_dir: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows = read_v3_regions(v3_summary)
    rows_by_file: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        rows_by_file[row["file"]].append(row)

    region_rows: list[dict[str, object]] = []
    split_rows: list[dict[str, object]] = []

    for file_name, file_rows in rows_by_file.items():
        img = read_image(image_dir / file_name)
        parent_for_overlay: list[tuple[Box, str]] = []
        split_for_overlay: list[tuple[Box, str]] = []

        for row in file_rows:
            parent = Box(
                int(row["x"]),
                int(row["y"]),
                int(row["w"]),
                int(row["h"]),
                0,
            )
            parent_label = row["label"]
            parent_index = int(row["index"])
            crop = img[parent.y : parent.y2, parent.x : parent.x2]
            splits = local_line_split(crop, parent_label)
            quality = split_quality(splits, parent.h)
            decision, reason = decide_secondary_action(parent_label, quality)

            parent_for_overlay.append((parent, parent_label))

            region_crop_path = out_dir / "region_crops_by_decision" / decision / Path(file_name).stem / f"box_{parent_index:03d}.png"
            write_image(region_crop_path, crop)

            split_dir = out_dir / "secondary_splits_by_decision" / decision / Path(file_name).stem / f"box_{parent_index:03d}"
            secondary_paths: list[str] = []
            secondary_crops: list[np.ndarray] = []
            for split in splits:
                absolute = Box(parent.x + split.x, parent.y + split.y, split.w, split.h, 0)
                split_for_overlay.append((absolute, decision))
                split_crop = img[absolute.y : absolute.y2, absolute.x : absolute.x2]
                split_path = split_dir / f"part_{split.index:03d}.png"
                write_image(split_path, split_crop)
                secondary_paths.append(str(split_path.relative_to(out_dir)))
                secondary_crops.append(split_crop)
                split_rows.append(
                    {
                        "file": file_name,
                        "parent_index": parent_index,
                        "parent_label": parent_label,
                        "decision": decision,
                        "split_index": split.index,
                        "x": absolute.x,
                        "y": absolute.y,
                        "w": absolute.w,
                        "h": absolute.h,
                        "crop_path": str(split_path.relative_to(out_dir)),
                    }
                )

            sheet = make_contact_sheet(secondary_crops)
            if sheet is not None:
                write_image(out_dir / "secondary_contact_sheets" / Path(file_name).stem / f"box_{parent_index:03d}__sheet.png", sheet)

            region_rows.append(
                {
                    "file": file_name,
                    "parent_index": parent_index,
                    "parent_label": parent_label,
                    "x": parent.x,
                    "y": parent.y,
                    "w": parent.w,
                    "h": parent.h,
                    "split_count": quality["split_count"],
                    "median_split_h": quality["median_h"],
                    "min_gap": quality["min_gap"],
                    "height_cv": quality["height_cv"],
                    "stable": quality["stable"],
                    "decision": decision,
                    "reason": reason,
                    "region_crop_path": str(region_crop_path.relative_to(out_dir)),
                    "secondary_split_paths": ";".join(secondary_paths),
                }
            )

        overlay = draw_v4_overlay(img, parent_for_overlay, split_for_overlay)
        write_image(out_dir / "visualizations" / f"{Path(file_name).stem}__v4_secondary.png", overlay)

    return region_rows, split_rows


def write_reports(out_dir: Path, region_rows: list[dict[str, object]], split_rows: list[dict[str, object]]) -> None:
    report_dir = out_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    region_fields = [
        "file",
        "parent_index",
        "parent_label",
        "x",
        "y",
        "w",
        "h",
        "split_count",
        "median_split_h",
        "min_gap",
        "height_cv",
        "stable",
        "decision",
        "reason",
        "region_crop_path",
        "secondary_split_paths",
    ]
    with (report_dir / "secondary_region_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=region_fields)
        writer.writeheader()
        writer.writerows(region_rows)

    split_fields = [
        "file",
        "parent_index",
        "parent_label",
        "decision",
        "split_index",
        "x",
        "y",
        "w",
        "h",
        "crop_path",
    ]
    with (report_dir / "secondary_split_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=split_fields)
        writer.writeheader()
        writer.writerows(split_rows)

    decision_counts = Counter(str(row["decision"]) for row in region_rows)
    label_counts = Counter(str(row["parent_label"]) for row in region_rows)
    promoted_splits = sum(
        int(row["split_count"])
        for row in region_rows
        if str(row["decision"]).startswith("secondary_line_candidate")
    )

    with (report_dir / "secondary_split_probe.md").open("w", encoding="utf-8") as f:
        f.write("# Secondary Split Probe v4\n\n")
        f.write("This report only revisits v3 boxes routed to region OCR.\n\n")
        f.write("The goal is to decide whether each large/mixed region should be split again or kept as region OCR.\n\n")
        f.write("## Totals\n\n")
        f.write(f"- Parent regions checked: {len(region_rows)}\n")
        f.write(f"- Secondary split crops generated: {len(split_rows)}\n")
        f.write(f"- Split crops promoted/reviewed as line candidates: {promoted_splits}\n\n")

        f.write("## Decisions\n\n")
        f.write("| decision | regions |\n")
        f.write("|---|---:|\n")
        for decision, count in sorted(decision_counts.items()):
            f.write(f"| {decision} | {count} |\n")

        f.write("\n## Parent Labels\n\n")
        f.write("| parent_label | regions |\n")
        f.write("|---|---:|\n")
        for label, count in sorted(label_counts.items()):
            f.write(f"| {label} | {count} |\n")

        f.write("\n## Region Summary\n\n")
        f.write("| file | box | label | split_count | stable | decision | reason |\n")
        f.write("|---|---:|---|---:|---|---|---|\n")
        for row in region_rows:
            f.write(
                f"| {row['file']} | {row['parent_index']} | {row['parent_label']} | {row['split_count']} | "
                f"{row['stable']} | {row['decision']} | {row['reason']} |\n"
            )

        f.write("\n## Artifacts\n\n")
        f.write("- Parent region crops: `region_crops_by_decision/<decision>/<page>/box_*.png`\n")
        f.write("- Secondary line crops: `secondary_splits_by_decision/<decision>/<page>/box_*/part_*.png`\n")
        f.write("- Per-region contact sheets: `secondary_contact_sheets/<page>/box_*__sheet.png`\n")
        f.write("- Page overlays: `visualizations/*__v4_secondary.png`\n")
        f.write("- Region CSV: `reports/secondary_region_summary.csv`\n")
        f.write("- Split CSV: `reports/secondary_split_summary.csv`\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("page_images"))
    parser.add_argument(
        "--v3-summary",
        type=Path,
        default=Path("crop_pipeline_output/01_v3_routing/reports/hybrid_box_summary.csv"),
    )
    parser.add_argument("--output", type=Path, default=Path("crop_pipeline_output/02_v4_secondary_split"))
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    region_rows, split_rows = process_regions(args.input, args.v3_summary, args.output)
    write_reports(args.output, region_rows, split_rows)
    print(f"Done. Checked {len(region_rows)} v3 region boxes and wrote v4 probe to {args.output}")


if __name__ == "__main__":
    main()
