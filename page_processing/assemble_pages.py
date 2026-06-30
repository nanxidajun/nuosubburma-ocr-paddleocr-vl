#!/usr/bin/env python3
"""Assemble OCR units into page-level text with visual-line ordering.

This is the canonical page assembly script for the public page-processing
workflow. It accepts OCR-unit JSONL produced by either the local demo
(`answer` + `meta`) or the layout bridge runs (`ocr_text` + page/bbox fields),
then writes page-level review files and official submission files.
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import json
import mimetypes
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


REPLACEMENT_CHAR = "\ufffd"
ROUTE_ORDER = {
    "title": 0,
    "header": 1,
    "body": 2,
    "region": 2,
    "footnote": 3,
    "footer": 4,
    "page_number": 5,
}


@dataclass(frozen=True)
class AssemblyOutputs:
    submission_jsonl: Path
    submission_json: Path
    submission_md: Path
    submission_html: Path
    official_jsonl: Path
    official_csv: Path
    page_audit_csv: Path
    audit_summary_json: Path

    def as_dict(self) -> dict[str, Path]:
        return {
            "submission_jsonl": self.submission_jsonl,
            "submission_json": self.submission_json,
            "submission_md": self.submission_md,
            "submission_html": self.submission_html,
            "official_jsonl": self.official_jsonl,
            "official_csv": self.official_csv,
            "page_audit_csv": self.page_audit_csv,
            "audit_summary_json": self.audit_summary_json,
        }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(text + ("\n" if rows else ""), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        if not fields:
            return
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def clean_text(value: object) -> str:
    return "\n".join(line.strip() for line in str(value or "").replace("\r", "").splitlines() if line.strip())


def compact_text(value: object) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def text_similarity(a: object, b: object) -> float:
    left = compact_text(a)
    right = compact_text(b)
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    if len(shorter) >= 6 and shorter in longer:
        return len(shorter) / max(1, len(longer))
    return SequenceMatcher(None, left, right).ratio()


def sanitize_ocr_text(value: object) -> tuple[str, int, bool]:
    text = clean_text(value)
    replacement_count = text.count(REPLACEMENT_CHAR)
    if not replacement_count:
        return text, 0, False
    compact = compact_text(text)
    compact_replacements = compact.count(REPLACEMENT_CHAR)
    if compact_replacements >= 8 and compact_replacements / max(1, len(compact)) >= 0.5:
        return "", replacement_count, True
    return clean_text(text.replace(REPLACEMENT_CHAR, "")), replacement_count, False


def parse_box(value: Any) -> list[int]:
    raw = value
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return [0, 0, 0, 0]
    if isinstance(raw, (list, tuple)) and len(raw) == 4:
        try:
            box = [int(round(float(v))) for v in raw]
        except (TypeError, ValueError):
            return [0, 0, 0, 0]
        if box[2] > box[0] and box[3] > box[1]:
            return box
    return [0, 0, 0, 0]


def box_area(box: list[int]) -> int:
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def intersection(a: list[int], b: list[int]) -> int:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    return max(0, x2 - x1) * max(0, y2 - y1)


def center_x(row: dict[str, Any]) -> float:
    box = row.get("bbox") or [0, 0, 0, 0]
    return (box[0] + box[2]) / 2


def center_y(row: dict[str, Any]) -> float:
    box = row.get("bbox") or [0, 0, 0, 0]
    return (box[1] + box[3]) / 2


def height(row: dict[str, Any]) -> int:
    box = row.get("bbox") or [0, 0, 0, 0]
    return max(1, box[3] - box[1])


def child_overlap(parent: list[int], child: list[int]) -> float:
    return intersection(parent, child) / max(1, box_area(child))


def route_for(row: dict[str, Any], meta: dict[str, Any]) -> str:
    explicit = str(row.get("route") or meta.get("role") or meta.get("sub_bucket") or "").lower()
    label = str(meta.get("label_or_decision") or row.get("label") or row.get("model_label") or "").lower()
    note = str(meta.get("note") or row.get("note") or "").lower()
    combined = " ".join([explicit, label, note])
    if "page_number" in combined:
        return "page_number"
    if "header" in combined:
        return "header"
    if "footer" in combined:
        return "footer"
    if "footnote" in combined:
        return "footnote"
    if "title" in combined:
        return "title"
    if explicit == "region_keep" or "region" in combined:
        return "region"
    return explicit if explicit in ROUTE_ORDER else "body"


def sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    reading_order = str(row.get("reading_order") or "")
    if reading_order:
        return (0, reading_order)
    box = row.get("bbox") or [0, 0, 0, 0]
    return (1, box[1], box[0], ROUTE_ORDER.get(row.get("route"), 90), str(row.get("id") or ""))


def normalize_unit(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    raw_text = row.get("ocr_text")
    if raw_text is None:
        raw_text = row.get("answer")
    if raw_text is None:
        raw_text = row.get("text")
    text, replacement_count, cleared = sanitize_ocr_text(raw_text)

    page_id = str(row.get("page_id") or meta.get("page_id") or "unknown_page")
    page_file = str(row.get("file") or meta.get("page_file") or f"{page_id}.png")
    route = route_for(row, meta)
    bbox = parse_box(row.get("unit_bbox") or row.get("bbox") or meta.get("crop_bbox") or meta.get("bbox"))
    image = row.get("image") or row.get("crop_image") or meta.get("summary_path") or ""
    if not image and isinstance(row.get("images"), list) and row["images"]:
        image = row["images"][0]

    return {
        "id": str(row.get("id") or meta.get("crop_id") or ""),
        "page_id": page_id,
        "file": page_file,
        "page_file": page_file,
        "route": route,
        "status": str(row.get("ocr_status") or row.get("status") or "ok"),
        "error": str(row.get("ocr_error") or row.get("error") or ""),
        "image": str(image),
        "bbox": bbox,
        "reading_order": str(row.get("reading_order") or meta.get("reading_order") or ""),
        "source_box": str(meta.get("source_box") or row.get("source_box") or ""),
        "part_index": str(meta.get("part_index") or row.get("part_index") or ""),
        "raw_text": clean_text(raw_text),
        "text": text,
        "replacement_chars": replacement_count,
        "cleared_unit": cleared,
    }


def unit_text(row: dict[str, Any]) -> str:
    return str(row.get("text") or "")


def unit_lines(row: dict[str, Any], keep_empty_units: bool = False) -> list[str]:
    text = str(row.get("text") or "")
    if keep_empty_units and not text.strip():
        return [""]
    return [line.strip() for line in text.replace("\r", "").splitlines() if line.strip()]


def is_parent_child_overlap(a: dict[str, Any], b: dict[str, Any]) -> bool:
    a_box = a.get("bbox") or [0, 0, 0, 0]
    b_box = b.get("bbox") or [0, 0, 0, 0]
    a_area = box_area(a_box)
    b_area = box_area(b_box)
    if not a_area or not b_area:
        return False
    big, small = (a, b) if a_area >= b_area else (b, a)
    big_box = big.get("bbox") or [0, 0, 0, 0]
    small_box = small.get("bbox") or [0, 0, 0, 0]
    area_ratio = box_area(big_box) / max(1, box_area(small_box))
    height_ratio = height(big) / max(1, height(small))
    contains_small = child_overlap(big_box, small_box) >= 0.86
    if not contains_small or area_ratio < 1.55 or height_ratio < 1.45:
        return False
    return (big.get("route") or "body") != (small.get("route") or "body")


def suppress_contained_duplicates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [row for row in rows if unit_text(row)]
    drop: set[int] = set()
    for i, row in enumerate(candidates):
        text = compact_text(unit_text(row))
        box = row.get("bbox") or [0, 0, 0, 0]
        area = box_area(box)
        if not text or not area:
            continue
        for j, other in enumerate(candidates):
            if i == j:
                continue
            other_text = compact_text(unit_text(other))
            other_box = other.get("bbox") or [0, 0, 0, 0]
            other_area = box_area(other_box)
            if not other_text or not other_area:
                continue
            overlap = intersection(box, other_box) / max(1, min(area, other_area))
            if overlap < 0.65:
                continue
            if text == other_text:
                if (other_area > area) or (other_area == area and str(other.get("id")) < str(row.get("id"))):
                    drop.add(i)
                    break
            elif len(text) < len(other_text) and text in other_text:
                drop.add(i)
                break
            elif overlap >= 0.82 and min(len(text), len(other_text)) >= 12 and text_similarity(text, other_text) >= 0.88:
                if (len(other_text), other_area, str(other.get("id"))) > (len(text), area, str(row.get("id"))):
                    drop.add(i)
                    break
    return [row for idx, row in enumerate(candidates) if idx not in drop]


def same_visual_line(group: list[dict[str, Any]], row: dict[str, Any]) -> bool:
    row_route = str(row.get("route") or "body")
    group_routes = {str(item.get("route") or "body") for item in group}
    if row_route == "page_number" and group_routes != {"page_number"}:
        return False
    if row_route != "page_number" and "page_number" in group_routes:
        return False
    if any(is_parent_child_overlap(item, row) for item in group):
        return False
    box = row.get("bbox") or [0, 0, 0, 0]
    center = center_y(row)
    heights = [height(item) for item in group]
    median_h = sorted(heights)[len(heights) // 2] if heights else height(row)
    group_top = min((item.get("bbox") or [0, 0, 0, 0])[1] for item in group)
    group_bottom = max((item.get("bbox") or [0, 0, 0, 0])[3] for item in group)
    group_center = (group_top + group_bottom) / 2
    inter = max(0, min(group_bottom, box[3]) - max(group_top, box[1]))
    overlap = inter / max(1, min(group_bottom - group_top, box[3] - box[1]))
    if overlap >= 0.35:
        group_h = max(1, group_bottom - group_top)
        row_h = max(1, box[3] - box[1])
        if max(group_h, row_h) / min(group_h, row_h) > 1.45 and abs(center - group_center) > max(18, median_h * 0.55):
            return False
    return overlap >= 0.35 or abs(center - group_center) <= max(18, median_h * 0.55)


def visual_lines(rows: list[dict[str, Any]], keep_empty_units: bool = False) -> list[str]:
    boxed = [row for row in rows if box_area(row.get("bbox") or [0, 0, 0, 0])]
    unboxed = [row for row in rows if not box_area(row.get("bbox") or [0, 0, 0, 0])]
    if not boxed:
        return [unit_text(row) for row in sorted(rows, key=sort_key) if keep_empty_units or unit_text(row)]

    groups: list[list[dict[str, Any]]] = []
    for row in sorted(suppress_contained_duplicates(boxed), key=sort_key):
        for group in groups:
            if same_visual_line(group, row):
                group.append(row)
                break
        else:
            groups.append([row])

    lines: list[str] = []
    for group in sorted(groups, key=lambda items: min((item.get("bbox") or [0, 0, 0, 0])[1] for item in items)):
        parts = [
            unit_lines(item, keep_empty_units=keep_empty_units)
            for item in sorted(group, key=lambda item: (center_x(item), (item.get("bbox") or [0, 0, 0, 0])[0], sort_key(item)))
        ]
        if not parts:
            continue
        max_lines = max((len(part) for part in parts), default=0)
        multiline_parts = [part for part in parts if len(part) > 1]
        if max_lines <= 1:
            line = "".join((part[0] if part else "") for part in parts)
            if line or keep_empty_units:
                lines.append(line)
            continue
        if len(multiline_parts) < 2:
            for part in parts:
                for line in part:
                    if line or keep_empty_units:
                        lines.append(line)
            continue
        for index in range(max_lines):
            line = "".join(part[index] for part in parts if index < len(part))
            if line or keep_empty_units:
                lines.append(line)
    for row in sorted(unboxed, key=sort_key):
        for line in unit_lines(row, keep_empty_units=keep_empty_units):
            if line or keep_empty_units:
                lines.append(line)
    return lines


def route_lines(rows: list[dict[str, Any]], keep_empty_units: bool = False) -> list[str]:
    boxed = [row for row in rows if box_area(row.get("bbox") or [0, 0, 0, 0])]
    if boxed:
        return visual_lines(rows, keep_empty_units=keep_empty_units)
    return [unit_text(row) for row in sorted(rows, key=sort_key) if keep_empty_units or unit_text(row)]


def assemble_page(page_id: str, units: list[dict[str, Any]], keep_empty_units: bool = False) -> dict[str, Any]:
    units = sorted(units, key=sort_key)
    by_route: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in units:
        by_route[str(row.get("route") or "body")].append(row)
    fields = {route: "\n".join(route_lines(by_route.get(route, []), keep_empty_units=keep_empty_units)) for route in ROUTE_ORDER}
    text = "\n".join(visual_lines(units, keep_empty_units=keep_empty_units))
    page_file = next((str(unit.get("file") or "") for unit in units if unit.get("file")), f"{page_id}.png")
    return {
        "page_id": page_id,
        "file": page_file,
        "page_file": page_file,
        "title": fields["title"],
        "header": fields["header"],
        "body": fields["body"],
        "footnote": fields["footnote"],
        "footer": fields["footer"],
        "page_number": fields["page_number"],
        "text": text,
        "ocr_units": len(units),
        "ocr_unit_rows": units,
        "routes": {route: len(by_route.get(route, [])) for route in ROUTE_ORDER if by_route.get(route)},
    }


def official_rows(pages: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{"image_id": str(page.get("file") or page["page_id"]), "prediction": clean_text(page.get("text"))} for page in pages]


def image_data_uri(path_text: str, image_root: Path | None = None) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    if not path.is_absolute() and image_root is not None:
        path = image_root / path
    if not path.exists() or not path.is_file():
        return ""
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_page_audit(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in pages:
        text = str(page.get("text") or "")
        rows.append(
            {
                "page_id": page.get("page_id", ""),
                "page_file": page.get("file", ""),
                "char_count": len(text),
                "line_count": len([line for line in text.splitlines() if line.strip()]),
                "ocr_units": int(page.get("ocr_units") or len(page.get("ocr_unit_rows", []))),
                "routes": json.dumps(page.get("routes", {}), ensure_ascii=False),
                "empty": not bool(text.strip()),
            }
        )
    return rows


def build_audit_summary(pages: list[dict[str, Any]], units: list[dict[str, Any]], page_audit: list[dict[str, Any]]) -> dict[str, Any]:
    route_counts = Counter(str(unit.get("route") or "") for unit in units)
    status_counts = Counter(str(unit.get("status") or "ok") for unit in units)
    replacement_rows = [
        {
            "id": unit.get("id", ""),
            "page_id": unit.get("page_id", ""),
            "replacement_chars": unit.get("replacement_chars", 0),
            "cleared_unit": unit.get("cleared_unit", False),
        }
        for unit in units
        if unit.get("replacement_chars")
    ]
    text_groups: dict[str, list[str]] = defaultdict(list)
    for page in pages:
        text = str(page.get("text") or "").strip()
        if text:
            text_groups[text].append(str(page.get("page_id") or ""))
    duplicate_groups = [ids for ids in text_groups.values() if len(ids) > 1]
    return {
        "assembly_impl": "page_processing/assemble_pages.py",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "pages": len(pages),
        "official_rows": len(pages),
        "ocr_units": len(units),
        "ocr_status": dict(sorted(status_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "replacement_char_rows": replacement_rows,
        "removed_replacement_chars": sum(int(unit.get("replacement_chars") or 0) for unit in units),
        "final_contains_replacement_char": any(REPLACEMENT_CHAR in str(page.get("text") or "") for page in pages),
        "empty_pages": [row["page_id"] for row in page_audit if row["empty"]],
        "duplicate_page_text_groups": duplicate_groups,
        "avg_chars_per_page": sum(int(row["char_count"]) for row in page_audit) / max(len(page_audit), 1),
        "avg_lines_per_page": sum(int(row["line_count"]) for row in page_audit) / max(len(page_audit), 1),
    }


def write_markdown(path: Path, pages: list[dict[str, Any]]) -> None:
    lines = ["# Page OCR Assembly", ""]
    for page in pages:
        lines.extend([f"## {page['page_id']}", "", str(page.get("text") or ""), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_html(path: Path, pages: list[dict[str, Any]], audit: dict[str, Any], image_root: Path | None, max_image_side: int | None) -> None:
    page_cards = []
    for page in pages:
        unit_cards = []
        unit_rows = page.get("ocr_unit_rows", [])
        for unit in unit_rows:
            img_src = image_data_uri(str(unit.get("image") or ""), image_root=image_root)
            image_html = f'<img src="{img_src}" alt="OCR unit">' if img_src else '<div class="missing-image">OCR unit image not found</div>'
            meta = " · ".join(
                part
                for part in [
                    f"status: {html.escape(str(unit.get('status') or ''))}",
                    f"route: {html.escape(str(unit.get('route') or ''))}",
                    f"order: {html.escape(str(unit.get('reading_order') or ''))}",
                    f"bbox: {html.escape(json.dumps(unit.get('bbox') or [], ensure_ascii=False))}",
                ]
                if part
            )
            unit_cards.append(
                f"""
<article class="unit">
  <div class="unit-image">{image_html}</div>
  <div class="unit-body">
    <p class="unit-meta">{meta}</p>
    <pre>{html.escape(str(unit.get("text") or unit.get("raw_text") or ""))}</pre>
  </div>
</article>
"""
            )
        page_cards.append(
            f"""
<article class="page">
  <h2>{html.escape(str(page.get("page_id") or ""))}</h2>
  <p class="page-meta">file: {html.escape(str(page.get("file") or ""))} · OCR units: {html.escape(str(page.get("ocr_units") or len(unit_rows)))}</p>
  <section class="result-card"><h3>Page Text</h3><pre>{html.escape(str(page.get("text") or ""))}</pre></section>
  <section class="units"><h3>OCR Unit Review</h3>{''.join(unit_cards)}</section>
</article>
"""
        )

    route_text = ", ".join(f"{html.escape(str(k))}: {v}" for k, v in audit.get("route_counts", {}).items())
    status_text = ", ".join(f"{html.escape(str(k))}: {v}" for k, v in audit.get("ocr_status", {}).items())
    empty_pages = ", ".join(html.escape(str(x)) for x in audit.get("empty_pages", [])) or "none"
    duplicate_groups = audit.get("duplicate_page_text_groups", [])
    duplicate_text = html.escape(json.dumps(duplicate_groups, ensure_ascii=False)) if duplicate_groups else "none"
    size_note = (
        f"Page images may have been resized before cutting when max-image-side={max_image_side}."
        if max_image_side and max_image_side > 0
        else "No max-image-side note was provided."
    )
    doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NuosuBburma OCR Page Assembly</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f6f7f4; color: #22251f; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", sans-serif; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px 16px 48px; }}
    header {{ margin-bottom: 14px; }}
    h1 {{ margin: 0 0 6px; font-size: 28px; }}
    h2 {{ margin: 0 0 6px; font-size: 20px; color: #48523f; }}
    h3 {{ margin: 0 0 8px; font-size: 15px; color: #48523f; }}
    .sub, .page-meta, .unit-meta, .audit-note {{ color: #66705f; line-height: 1.65; }}
    .audit, .page, .result-card {{ border: 1px solid #d7ddcf; border-radius: 8px; background: #fff; }}
    .audit {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; padding: 12px; margin: 16px 0; }}
    .metric {{ background: #f1f4ec; border: 1px solid #d7ddcf; border-radius: 6px; padding: 10px; }}
    .metric strong {{ display: block; font-size: 24px; color: #48523f; }}
    .metric span {{ display: block; font-size: 13px; color: #66705f; }}
    .audit-note {{ grid-column: 1 / -1; margin: 0; font-size: 13px; }}
    .page {{ padding: 14px; margin: 14px 0; }}
    .result-card {{ padding: 12px; margin: 12px 0; background: #fbfcf8; }}
    pre {{ white-space: pre-wrap; word-break: break-word; margin: 0; line-height: 1.8; font: 17px/1.8 "Kaiti SC", "Songti SC", "Noto Serif CJK SC", serif; }}
    .unit {{ display: grid; grid-template-columns: minmax(180px, .42fr) minmax(0, 1fr); gap: 12px; padding: 12px 0; border-top: 1px solid #d7ddcf; }}
    .unit:first-of-type {{ border-top: 0; }}
    .unit-image {{ background: #252920; border-radius: 6px; padding: 8px; align-self: start; }}
    .unit-image img {{ display: block; width: 100%; max-height: 240px; object-fit: contain; border-radius: 4px; background: white; }}
    .missing-image {{ color: #eef2e8; font-size: 13px; padding: 18px; text-align: center; }}
    @media (max-width: 820px) {{ .audit {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .unit {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>NuosuBburma OCR Page Assembly</h1>
      <p class="sub">Canonical visual-line assembly for page cutting outputs. {html.escape(size_note)}</p>
    </header>
    <section class="audit">
      <div class="metric"><strong>{audit.get("pages", 0)}</strong><span>pages</span></div>
      <div class="metric"><strong>{audit.get("ocr_units", 0)}</strong><span>OCR units</span></div>
      <div class="metric"><strong>{len(audit.get("replacement_char_rows", []))}</strong><span>replacement-char units</span></div>
      <div class="metric"><strong>{len(audit.get("empty_pages", []))}</strong><span>empty pages</span></div>
      <p class="audit-note">Generated: {html.escape(str(audit.get("generated_at") or ""))}</p>
      <p class="audit-note">OCR status: {status_text or "n/a"}; routes: {route_text or "n/a"}.</p>
      <p class="audit-note">Empty pages: {empty_pages}; duplicate page text groups: {duplicate_text}.</p>
    </section>
    {''.join(page_cards)}
  </main>
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")


def assemble_rows(rows: list[dict[str, Any]], keep_empty_units: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    units = [normalize_unit(row) for row in rows]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for unit in units:
        grouped[str(unit.get("page_id") or "unknown_page")].append(unit)
    pages = [assemble_page(page_id, grouped[page_id], keep_empty_units=keep_empty_units) for page_id in sorted(grouped)]
    page_audit = build_page_audit(pages)
    audit = build_audit_summary(pages, units, page_audit)
    return pages, audit, page_audit


def assemble_ocr_results(
    results_path: Path,
    out_dir: Path,
    *,
    image_root: Path | None = None,
    keep_empty_units: bool = False,
    max_image_side: int | None = None,
    out_prefix: str = "submission_pages",
) -> AssemblyOutputs:
    rows = read_jsonl(results_path)
    pages, audit, page_audit = assemble_rows(rows, keep_empty_units=keep_empty_units)

    out_dir.mkdir(parents=True, exist_ok=True)
    submission_jsonl = out_dir / f"{out_prefix}.jsonl"
    submission_json = out_dir / f"{out_prefix}.json"
    submission_md = out_dir / f"{out_prefix}.md"
    submission_html = out_dir / f"{out_prefix}.html"
    official_jsonl = out_dir / "official_submission.jsonl"
    official_csv = out_dir / "official_submission.csv"
    page_audit_csv = out_dir / "page_audit.csv"
    audit_summary_json = out_dir / "audit_summary.json"

    write_jsonl(submission_jsonl, pages)
    submission_json.write_text(json.dumps({"pages": pages}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(submission_md, pages)
    write_html(submission_html, pages, audit, image_root=image_root, max_image_side=max_image_side)
    official = official_rows(pages)
    write_jsonl(official_jsonl, official)
    write_csv(official_csv, official)
    write_csv(page_audit_csv, page_audit)
    audit_summary_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    return AssemblyOutputs(
        submission_jsonl=submission_jsonl,
        submission_json=submission_json,
        submission_md=submission_md,
        submission_html=submission_html,
        official_jsonl=official_jsonl,
        official_csv=official_csv,
        page_audit_csv=page_audit_csv,
        audit_summary_json=audit_summary_json,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assemble OCR-unit JSONL into page-level OCR outputs.")
    parser.add_argument("--results", type=Path, default=None, help="OCR-unit JSONL. Defaults to --run-dir official_rerun_v516 result path.")
    parser.add_argument("--run-dir", type=Path, default=None, help="Optional run directory for legacy layout runs.")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output directory for page-level assembly files.")
    parser.add_argument("--image-root", type=Path, default=None, help="Optional root for relative OCR-unit image paths in HTML review.")
    parser.add_argument("--out-prefix", default="submission_pages", help="Prefix for page review outputs.")
    parser.add_argument("--keep-empty-units", action="store_true", help="Keep empty OCR units as blank lines in assembled text.")
    parser.add_argument("--max-image-side", type=int, default=None, help="Optional note for the HTML review page.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve() if args.run_dir else None
    results = args.results.resolve() if args.results else None
    if results is None:
        if run_dir is None:
            raise SystemExit("Either --results or --run-dir is required.")
        results = run_dir / "official_rerun_v516" / "ocr_units_results_v516_1024.jsonl"
    outputs = assemble_ocr_results(
        results,
        args.out_dir.resolve(),
        image_root=args.image_root.resolve() if args.image_root else run_dir,
        keep_empty_units=args.keep_empty_units,
        max_image_side=args.max_image_side,
        out_prefix=args.out_prefix,
    )
    print(json.dumps({"pages_output": {key: str(value) for key, value in outputs.as_dict().items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
