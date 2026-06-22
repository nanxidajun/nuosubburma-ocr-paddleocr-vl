#!/usr/bin/env python3
"""Validate production crop pipeline outputs before OCR or review.

The validator is intentionally strict about identity:

- every crop_id must be unique;
- every summary_path/image path must exist;
- secondary_v4 line crops must include part_index in metadata and file name;
- line OCR rows must be sortable by page, source_box, and part_index.

It accepts the official crop summary index.csv and optionally a prelabel JSONL.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


PART_RE = re.compile(r"(?:__|/)part_(\d{1,4})(?:\.|/|$)")


def as_int(value: object, default: int = 0) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def row_id_from_jsonl(row: dict) -> str:
    meta = row.get("meta") or {}
    return str(meta.get("crop_id") or row.get("id") or (row.get("images") or [""])[0])


def part_from_path(path: str) -> str:
    match = PART_RE.search(path)
    if not match:
        return ""
    return str(int(match.group(1)))


def add_duplicate_errors(errors: list[str], label: str, values: list[str]) -> None:
    counts = Counter(values)
    duplicates = [(key, count) for key, count in counts.items() if key and count > 1]
    if duplicates:
        sample = ", ".join(f"{key} x{count}" for key, count in duplicates[:8])
        errors.append(f"{label} has {len(duplicates)} duplicate keys: {sample}")


def validate_index(index_path: Path, root: Path) -> tuple[list[str], list[str], dict[str, object]]:
    rows = read_csv(index_path)
    errors: list[str] = []
    warnings: list[str] = []

    if not rows:
        errors.append(f"{index_path} has no rows")
        return errors, warnings, {"rows": 0}

    required = {
        "crop_id",
        "page_id",
        "page_file",
        "bucket",
        "sub_bucket",
        "role",
        "source_box",
        "part_index",
        "summary_path",
    }
    missing = required - set(rows[0].keys())
    if missing:
        errors.append(f"{index_path} missing columns: {', '.join(sorted(missing))}")
        return errors, warnings, {"rows": len(rows)}

    add_duplicate_errors(errors, "index crop_id", [row["crop_id"] for row in rows])
    add_duplicate_errors(errors, "index summary_path", [row["summary_path"] for row in rows])

    missing_files = []
    secondary_missing_part = []
    secondary_part_mismatch = []
    line_rows = []
    for row in rows:
        summary = row.get("summary_path", "")
        path = root / summary
        if not path.exists():
            missing_files.append(summary)

        if row.get("is_line_ocr_ready") == "1":
            line_rows.append(row)

        if row.get("sub_bucket") == "secondary_v4" or row.get("role") == "secondary_line":
            part = row.get("part_index", "")
            path_part = part_from_path(summary)
            if not part:
                secondary_missing_part.append(row.get("crop_id", summary))
            if path_part and part and as_int(path_part) != as_int(part):
                secondary_part_mismatch.append(f"{row.get('crop_id', summary)} path={path_part} meta={part}")

    if missing_files:
        errors.append(f"index references {len(missing_files)} missing files, first: {missing_files[:5]}")
    if secondary_missing_part:
        errors.append(f"secondary_v4 rows missing part_index: {secondary_missing_part[:8]}")
    if secondary_part_mismatch:
        errors.append(f"secondary_v4 part_index mismatches: {secondary_part_mismatch[:8]}")

    by_page: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in line_rows:
        by_page[row["page_id"]].append(row)

    for page, page_rows in by_page.items():
        keys = [(as_int(row["source_box"]), as_int(row["part_index"]), row["crop_id"]) for row in page_rows]
        if keys != sorted(keys):
            warnings.append(f"line OCR rows for page {page} are not in reading-order sort in index.csv")
            break

    summary = {
        "rows": len(rows),
        "line_rows": len(line_rows),
        "secondary_line_rows": sum(1 for row in rows if row.get("role") == "secondary_line"),
        "region_keep_rows": sum(1 for row in rows if row.get("role") == "region_keep"),
        "reference_rows": sum(1 for row in rows if row.get("role") == "reference"),
    }
    return errors, warnings, summary


def validate_jsonl(jsonl_path: Path) -> tuple[list[str], list[str], dict[str, object]]:
    rows = read_jsonl(jsonl_path)
    errors: list[str] = []
    warnings: list[str] = []

    ids = [row_id_from_jsonl(row) for row in rows]
    add_duplicate_errors(errors, "jsonl crop_id", ids)

    missing_images = []
    secondary_missing_part = []
    for row in rows:
        meta = row.get("meta") or {}
        images = row.get("images") or []
        if not images:
            errors.append(f"jsonl row {row_id_from_jsonl(row)} has no image")
            continue
        image_path = Path(images[0])
        if image_path.is_absolute() and not image_path.exists():
            missing_images.append(str(image_path))
        if meta.get("sub_bucket") == "secondary_v4":
            crop_id = str(meta.get("crop_id") or "")
            part = str(meta.get("part_index") or "")
            if not part and "part_" not in crop_id and not part_from_path(str(images[0])):
                secondary_missing_part.append(crop_id or str(images[0]))

    if missing_images:
        warnings.append(f"jsonl has {len(missing_images)} absolute image paths missing locally; first: {missing_images[:3]}")
    if secondary_missing_part:
        errors.append(f"jsonl secondary_v4 rows missing part identity: {secondary_missing_part[:8]}")

    return errors, warnings, {"rows": len(rows), "unique_ids": len(set(ids))}


def write_report(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, help="04_successful_crop_summary/index.csv")
    parser.add_argument("--summary-root", type=Path, help="Root folder containing index.csv summary_path files")
    parser.add_argument("--jsonl", type=Path, help="Optional prelabel/OCR input JSONL")
    parser.add_argument("--report", type=Path, help="Optional JSON report path")
    parser.add_argument("--warn-only", action="store_true", help="Print errors but exit 0")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    summary: dict[str, object] = {}

    if args.index:
        root = args.summary_root or args.index.resolve().parent
        index_errors, index_warnings, index_summary = validate_index(args.index, root)
        errors.extend(index_errors)
        warnings.extend(index_warnings)
        summary["index"] = index_summary

    if args.jsonl:
        jsonl_errors, jsonl_warnings, jsonl_summary = validate_jsonl(args.jsonl)
        errors.extend(jsonl_errors)
        warnings.extend(jsonl_warnings)
        summary["jsonl"] = jsonl_summary

    payload = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.report:
        write_report(args.report, payload)

    if errors and not args.warn_only:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
