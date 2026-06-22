#!/usr/bin/env python3
"""Probe rule-based line segmentation on scanned book pages.

This script is intentionally model-free: it uses OpenCV image processing only.
It renders debug images so a human can judge whether automatic line splitting is
good enough before connecting the OCR model.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}


@dataclass
class Box:
    x: int
    y: int
    w: int
    h: int
    column: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h


def read_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Could not read image: {path}")
    return img


def write_image(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix or ".png"
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        raise ValueError(f"Could not encode image: {path}")
    buf.tofile(str(path))


def binarize(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    block = max(31, (min(img.shape[:2]) // 30) | 1)
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block,
        15,
    )
    # Remove tiny speckles while keeping thin printed strokes.
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return binary


def remove_page_rules(binary: np.ndarray) -> np.ndarray:
    """Remove long page-edge/rule components before projection splitting.

    Page scans from novels can contain a full-height border line. If it remains
    in the binary image, horizontal projection sees ink on almost every row and
    collapses the whole page into one giant box.
    """
    h, w = binary.shape[:2]
    num, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    cleaned = binary.copy()

    for idx in range(1, num):
        x, y, cw, ch, area = [int(v) for v in stats[idx]]
        fill = area / max(1, cw * ch)

        is_vertical_rule = ch > 0.55 * h and cw < max(14, 0.025 * w) and fill > 0.20
        is_page_edge_rule = (
            (x < 0.12 * w or x + cw > 0.88 * w)
            and ch > 0.35 * h
            and cw < max(28, 0.040 * w)
        )
        is_horizontal_rule = cw > 0.65 * w and ch < max(20, 0.018 * h) and fill > 0.18

        if is_vertical_rule or is_page_edge_rule or is_horizontal_rule:
            cleaned[labels == idx] = 0

    return cleaned


def content_bbox(binary: np.ndarray, pad: int = 8) -> tuple[int, int, int, int]:
    ys, xs = np.where(binary > 0)
    h, w = binary.shape
    if len(xs) == 0:
        return 0, 0, w, h
    x1 = max(0, int(xs.min()) - pad)
    y1 = max(0, int(ys.min()) - pad)
    x2 = min(w, int(xs.max()) + pad + 1)
    y2 = min(h, int(ys.max()) + pad + 1)
    return x1, y1, x2, y2


def find_intervals(mask: np.ndarray) -> list[tuple[int, int]]:
    intervals: list[tuple[int, int]] = []
    start: int | None = None
    for i, active in enumerate(mask.astype(bool)):
        if active and start is None:
            start = i
        elif not active and start is not None:
            intervals.append((start, i))
            start = None
    if start is not None:
        intervals.append((start, len(mask)))
    return intervals


def merge_intervals(intervals: list[tuple[int, int]], max_gap: int) -> list[tuple[int, int]]:
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


def detect_columns(binary: np.ndarray, min_gap_ratio: float = 0.055) -> list[tuple[int, int]]:
    h, w = binary.shape
    x1, y1, x2, y2 = content_bbox(binary, pad=0)
    roi = binary[y1:y2, x1:x2]
    if roi.size == 0:
        return [(0, w)]

    # Connect characters within each text run but keep large inter-column gaps.
    kernel_w = max(25, int(w * 0.035))
    kernel_h = max(3, int(h * 0.004))
    dilated = cv2.dilate(roi, np.ones((kernel_h, kernel_w), np.uint8), iterations=1)
    projection = dilated.sum(axis=0) / 255
    active = projection > max(2, roi.shape[0] * 0.01)
    intervals = merge_intervals(find_intervals(active), max_gap=max(8, int(w * 0.01)))

    intervals = [(x1 + a, x1 + b) for a, b in intervals if b - a > max(40, int(w * 0.08))]
    if len(intervals) <= 1:
        return [(x1, x2)]

    # If the detected split is only a tiny page-number column, keep full width.
    widths = [b - a for a, b in intervals]
    if min(widths) < 0.22 * max(widths):
        return [(x1, x2)]
    return intervals


def body_band(binary: np.ndarray, top_ratio: float = 0.06, bottom_ratio: float = 0.06) -> tuple[int, int]:
    h, w = binary.shape
    x1, y1, x2, y2 = content_bbox(binary, pad=0)
    top_floor = int(h * top_ratio)
    bottom_ceiling = int(h * (1.0 - bottom_ratio))
    y1 = max(y1, top_floor)
    y2 = min(y2, bottom_ceiling)
    if y2 <= y1:
        return top_floor, bottom_ceiling
    return y1, y2


def detect_lines_in_region(binary: np.ndarray, region: tuple[int, int], column_index: int) -> list[Box]:
    h, w = binary.shape
    x1, x2 = region
    x1 = max(0, x1)
    x2 = min(w, x2)
    roi = binary[:, x1:x2]
    if roi.size == 0:
        return []

    projection = roi.sum(axis=1) / 255
    smooth_len = max(9, int(h * 0.009))
    kernel = np.ones(smooth_len, dtype=np.float32) / smooth_len
    smooth = np.convolve(projection, kernel, mode="same")

    positive = smooth[smooth > 0]
    if len(positive) == 0:
        return []
    threshold = max(float(np.percentile(positive, 28)) * 0.35, (x2 - x1) * 0.002)
    active = smooth > threshold

    intervals = find_intervals(active)
    intervals = merge_intervals(intervals, max_gap=max(5, int(h * 0.006)))

    boxes: list[Box] = []
    min_h = max(10, int(h * 0.006))
    max_h = max(90, int(h * 0.08))
    y_pad = max(3, int(h * 0.004))
    x_pad = max(8, int(w * 0.01))

    for y_start, y_end in intervals:
        if y_end - y_start < min_h:
            continue
        if y_end - y_start > max_h:
            # Large title blocks are valid, but huge graphics/noise regions are not.
            ink_density = roi[y_start:y_end, :].sum() / 255 / max(1, (y_end - y_start) * (x2 - x1))
            if ink_density < 0.012:
                continue

        y0 = max(0, y_start - y_pad)
        y3 = min(h, y_end + y_pad)
        line_roi = binary[y0:y3, x1:x2]
        col_projection = line_roi.sum(axis=0) / 255
        col_active = col_projection > max(1, (y3 - y0) * 0.025)
        col_intervals = find_intervals(col_active)
        if not col_intervals:
            continue
        cx1 = min(a for a, _ in col_intervals)
        cx2 = max(b for _, b in col_intervals)
        bx1 = max(0, x1 + cx1 - x_pad)
        bx2 = min(w, x1 + cx2 + x_pad)

        if bx2 - bx1 < max(25, int(w * 0.04)):
            continue
        boxes.append(Box(bx1, y0, bx2 - bx1, y3 - y0, column_index))

    return boxes


def filter_body_boxes(binary: np.ndarray, boxes: list[Box]) -> list[Box]:
    if not boxes:
        return []
    h, w = binary.shape
    y_min, y_max = body_band(binary)
    filtered: list[Box] = []
    for box in boxes:
        if box.y2 < y_min or box.y > y_max:
            continue
        # Thin horizontal rules often span almost the full page but have tiny height.
        if box.w > 0.72 * w and box.h < max(24, int(0.018 * h)):
            continue
        filtered.append(box)
    return filtered


def sort_boxes(boxes: list[Box]) -> list[Box]:
    if not boxes:
        return []
    columns = sorted(set(b.column for b in boxes))
    ordered: list[Box] = []
    for col in columns:
        ordered.extend(sorted((b for b in boxes if b.column == col), key=lambda b: (b.y, b.x)))
    return ordered


def draw_boxes(img: np.ndarray, boxes: list[Box]) -> np.ndarray:
    out = img.copy()
    palette = [(0, 0, 255), (0, 140, 255), (255, 0, 0), (0, 160, 0)]
    for i, box in enumerate(boxes, start=1):
        color = palette[box.column % len(palette)]
        cv2.rectangle(out, (box.x, box.y), (box.x2, box.y2), color, 3)
        label = str(i)
        cv2.putText(
            out,
            label,
            (box.x, max(20, box.y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
            cv2.LINE_AA,
        )
    return out


def make_contact_sheet(crops: list[np.ndarray], max_width: int = 900) -> np.ndarray | None:
    if not crops:
        return None
    rows: list[np.ndarray] = []
    for idx, crop in enumerate(crops, start=1):
        h, w = crop.shape[:2]
        scale = min(1.0, (max_width - 90) / max(1, w))
        resized = cv2.resize(crop, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
        label_w = 72
        row_h = max(44, resized.shape[0] + 12)
        row = np.full((row_h, max_width, 3), 255, dtype=np.uint8)
        cv2.putText(row, f"{idx:02d}", (10, min(row_h - 12, 32)), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 180), 2)
        y = (row_h - resized.shape[0]) // 2
        row[y : y + resized.shape[0], label_w : label_w + resized.shape[1]] = resized
        rows.append(row)
    return np.vstack(rows)


def process_image(path: Path, out_dir: Path) -> dict[str, object]:
    img = read_image(path)
    h, w = img.shape[:2]
    binary = remove_page_rules(binarize(img))
    columns = detect_columns(binary)
    boxes: list[Box] = []
    for col_idx, region in enumerate(columns):
        boxes.extend(detect_lines_in_region(binary, region, col_idx))
    raw_box_count = len(boxes)
    boxes = filter_body_boxes(binary, boxes)
    boxes = sort_boxes(boxes)

    stem = path.stem
    crop_dir = out_dir / "crops" / stem
    crop_dir.mkdir(parents=True, exist_ok=True)
    crops: list[np.ndarray] = []
    for idx, box in enumerate(boxes, start=1):
        crop = img[box.y : box.y2, box.x : box.x2]
        crops.append(crop)
        write_image(crop_dir / f"line_{idx:03d}.png", crop)

    vis = draw_boxes(img, boxes)
    write_image(out_dir / "visualizations" / f"{stem}__boxes.png", vis)
    sheet = make_contact_sheet(crops)
    if sheet is not None:
        write_image(out_dir / "contact_sheets" / f"{stem}__sheet.png", sheet)

    heights = [b.h for b in boxes]
    widths = [b.w for b in boxes]
    gaps = [boxes[i + 1].y - boxes[i].y2 for i in range(len(boxes) - 1)]
    warnings: list[str] = []
    if len(boxes) == 0:
        warnings.append("no_lines")
    if len(columns) > 1:
        warnings.append(f"columns={len(columns)}")
    if heights and max(heights) > 2.3 * np.median(heights):
        warnings.append("large_height_variance")
    if gaps and min(gaps) < -3:
        warnings.append("overlapping_boxes")

    return {
        "file": path.name,
        "width": w,
        "height": h,
        "columns": len(columns),
        "lines": len(boxes),
        "raw_lines": raw_box_count,
        "median_line_h": round(float(np.median(heights)), 1) if heights else 0,
        "median_line_w": round(float(np.median(widths)), 1) if widths else 0,
        "min_gap": int(min(gaps)) if gaps else "",
        "warnings": ";".join(warnings),
    }


def write_report(out_dir: Path, rows: list[dict[str, object]]) -> None:
    report_dir = out_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    csv_path = report_dir / "segmentation_summary.csv"
    fields = [
        "file",
        "width",
        "height",
        "columns",
        "raw_lines",
        "lines",
        "median_line_h",
        "median_line_w",
        "min_gap",
        "warnings",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    md_path = report_dir / "segmentation_probe.md"
    total_lines = sum(int(r["lines"]) for r in rows)
    with md_path.open("w", encoding="utf-8") as f:
        f.write("# Line Segmentation Probe\n\n")
        f.write("This report is generated by CPU-only OpenCV preprocessing. No OCR model is called.\n\n")
        f.write(f"- Pages: {len(rows)}\n")
        f.write(f"- Detected line crops: {total_lines}\n")
        f.write("- Visual checks: see `visualizations/*__boxes.png` and `contact_sheets/*__sheet.png`\n\n")
        f.write("| file | size | columns | raw lines | kept lines | median line h | warnings |\n")
        f.write("|---|---:|---:|---:|---:|---:|---|\n")
        for r in rows:
            f.write(
                f"| {r['file']} | {r['width']}x{r['height']} | {r['columns']} | {r['raw_lines']} | {r['lines']} | "
                f"{r['median_line_h']} | {r['warnings']} |\n"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("page_images"))
    parser.add_argument("--output", type=Path, default=Path("crop_pipeline_probe"))
    args = parser.parse_args()

    images = sorted(p for p in args.input.iterdir() if p.suffix.lower() in IMAGE_EXTS and p.is_file())
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in images:
        print(f"Processing {path.name}...")
        rows.append(process_image(path, args.output))
    write_report(args.output, rows)
    print(f"Done. Wrote {len(rows)} page reports to {args.output}")


if __name__ == "__main__":
    main()
