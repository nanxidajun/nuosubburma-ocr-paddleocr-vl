#!/usr/bin/env python3
"""Merge line-level OCR results back into page-level text.

The crop pipeline writes 04_successful_crop_summary/index.csv with stable
identity and reading-order metadata. This script joins OCR results to that
index, sorts line crops inside each page, and writes merged page text.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


TEXT_FIELDS = ("answer", "text", "ocr_text", "prediction", "pred")
ID_FIELDS = ("crop_id", "id", "image_id")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge line OCR outputs into page text")
    parser.add_argument("--results", type=Path, required=True, help="Line-level OCR result JSONL or JSON list")
    parser.add_argument("--index", type=Path, help="Optional 04_successful_crop_summary/index.csv")
    parser.add_argument("--out-jsonl", type=Path, required=True, help="Merged page-level JSONL output")
    parser.add_argument("--out-txt-dir", type=Path, help="Optional folder for one .txt file per page")
    parser.add_argument(
        "--text-field",
        default="auto",
        help="OCR text field in result rows. Use auto to try answer/text/ocr_text/prediction/pred.",
    )
    parser.add_argument(
        "--separator",
        default="\\n",
        help=r"Separator used between merged lines. Default is '\n'.",
    )
    parser.add_argument(
        "--keep-empty",
        action="store_true",
        help="Keep empty OCR lines in merged text instead of dropping them.",
    )
    return parser.parse_args()


def decode_separator(value: str) -> str:
    return value.encode("utf-8").decode("unicode_escape")


def read_json_rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return payload["rows"]
    raise ValueError(f"Unsupported result JSON shape in {path}")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def get_nested(row: dict[str, Any], key: str) -> Any:
    if key in row:
        return row[key]
    meta = row.get("meta")
    if isinstance(meta, dict) and key in meta:
        return meta[key]
    return None


def first_text(row: dict[str, Any], field: str) -> str:
    if field != "auto":
        value = get_nested(row, field)
        return "" if value is None else str(value)
    for key in TEXT_FIELDS:
        value = get_nested(row, key)
        if value is not None:
            return str(value)
    messages = row.get("messages")
    if isinstance(messages, list) and messages:
        last = messages[-1]
        if isinstance(last, dict) and last.get("content") is not None:
            return str(last["content"])
    return ""


def image_values(row: dict[str, Any]) -> list[str]:
    values: list[str] = []
    images = row.get("images")
    if isinstance(images, list):
        values.extend(str(item) for item in images if item)
    for key in ("image", "image_path", "path"):
        value = get_nested(row, key)
        if value:
            values.append(str(value))
    return values


def candidate_keys(row: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for key in ID_FIELDS:
        value = get_nested(row, key)
        if value:
            keys.append(str(value))
    for image in image_values(row):
        path = Path(image)
        keys.extend([image, path.name, path.stem])
    return unique_nonempty(keys)


def index_candidate_keys(row: dict[str, str]) -> list[str]:
    keys = [
        row.get("crop_id", ""),
        row.get("summary_path", ""),
        Path(row.get("summary_path", "")).name,
        Path(row.get("summary_path", "")).stem,
        row.get("source_path", ""),
        Path(row.get("source_path", "")).name,
        Path(row.get("source_path", "")).stem,
    ]
    return unique_nonempty(keys)


def unique_nonempty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if not value:
            continue
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def build_index_lookup(index_path: Path | None) -> dict[str, dict[str, str]]:
    if not index_path:
        return {}
    lookup: dict[str, dict[str, str]] = {}
    for row in read_csv_rows(index_path):
        for key in index_candidate_keys(row):
            lookup.setdefault(key, row)
    return lookup


def find_index_row(result_row: dict[str, Any], lookup: dict[str, dict[str, str]]) -> dict[str, str]:
    for key in candidate_keys(result_row):
        if key in lookup:
            return lookup[key]
    return {}


def safe_page_id(value: str) -> str:
    value = value.strip() or "unknown_page"
    return re.sub(r"[^0-9A-Za-z_.\-\u4e00-\u9fff\uA000-\uA48F]+", "_", value).strip("_") or "unknown_page"


def merged_line(result_row: dict[str, Any], index_row: dict[str, str], text_field: str) -> dict[str, Any]:
    text = first_text(result_row, text_field)
    meta = result_row.get("meta") if isinstance(result_row.get("meta"), dict) else {}

    page_id = (
        index_row.get("page_id")
        or str(meta.get("page_id") or meta.get("page_file") or meta.get("page") or "")
        or "unknown_page"
    )
    page_file = index_row.get("page_file") or str(meta.get("page_file") or "")
    crop_id = index_row.get("crop_id") or str(meta.get("crop_id") or result_row.get("id") or "")
    source_box = index_row.get("source_box") or str(meta.get("source_box") or meta.get("box") or "")
    part_index = index_row.get("part_index") or str(meta.get("part_index") or meta.get("part") or "")
    reading_order = index_row.get("reading_order") or ""

    return {
        "page_id": page_id,
        "page_file": page_file,
        "crop_id": crop_id,
        "source_box": source_box,
        "part_index": part_index,
        "reading_order": reading_order,
        "text": text,
        "result_id": result_row.get("id", ""),
        "image": image_values(result_row)[0] if image_values(result_row) else "",
        "matched_index": bool(index_row),
    }


def line_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    reading_order = str(row.get("reading_order") or "")
    if reading_order:
        return (0, reading_order)
    return (
        1,
        as_int(row.get("source_box")),
        as_int(row.get("part_index")),
        str(row.get("crop_id") or row.get("result_id") or ""),
    )


def merge_pages(lines: list[dict[str, Any]], separator: str, keep_empty: bool) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in lines:
        if not keep_empty and not str(line.get("text") or "").strip():
            continue
        grouped[str(line["page_id"])].append(line)

    pages: list[dict[str, Any]] = []
    for page_id, page_lines in sorted(grouped.items()):
        ordered = sorted(page_lines, key=line_sort_key)
        text = separator.join(str(line.get("text") or "") for line in ordered)
        page_file = next((str(line.get("page_file") or "") for line in ordered if line.get("page_file")), "")
        pages.append(
            {
                "page_id": page_id,
                "page_file": page_file,
                "line_count": len(ordered),
                "text": text,
                "lines": ordered,
            }
        )
    return pages


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_txt_dir(path: Path, pages: list[dict[str, Any]]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for page in pages:
        page_id = safe_page_id(str(page.get("page_id") or "unknown_page"))
        (path / f"{page_id}.txt").write_text(str(page.get("text") or ""), encoding="utf-8")


def main() -> None:
    args = parse_args()
    index_lookup = build_index_lookup(args.index)
    result_rows = read_json_rows(args.results)
    lines = [merged_line(row, find_index_row(row, index_lookup), args.text_field) for row in result_rows]
    pages = merge_pages(lines, decode_separator(args.separator), args.keep_empty)
    write_jsonl(args.out_jsonl, pages)
    if args.out_txt_dir:
        write_txt_dir(args.out_txt_dir, pages)

    matched = sum(1 for line in lines if line["matched_index"])
    print(
        json.dumps(
            {
                "result_rows": len(result_rows),
                "matched_index_rows": matched,
                "pages": len(pages),
                "out_jsonl": str(args.out_jsonl),
                "out_txt_dir": str(args.out_txt_dir) if args.out_txt_dir else "",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

