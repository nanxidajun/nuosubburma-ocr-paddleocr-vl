#!/usr/bin/env python3
"""Export lightweight page structure from OCR-unit or assembled-page outputs."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from page_processing.assemble_pages import clean_text, normalize_unit, sort_key, suppress_contained_duplicates, visual_lines
except ModuleNotFoundError:
    from assemble_pages import clean_text, normalize_unit, sort_key, suppress_contained_duplicates, visual_lines


ROLE_ORDER = {
    "title": 0,
    "header": 1,
    "body": 2,
    "note": 3,
    "footnote": 4,
    "pronunciation": 5,
    "footer": 6,
    "page_number": 7,
    "unknown": 8,
}

PAGE_FIELD_ROLES = ["title", "header", "body", "footnote", "footer", "page_number"]
YI_CHAR_RE = re.compile(r"[\ua000-\ua48f]")
HAN_CHAR_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
LATIN_CHAR_RE = re.compile(r"[A-Za-z]")
CIRCLED_NOTE_RE = re.compile(r"^[\u2460-\u2473]")


@dataclass(frozen=True)
class StructureOutputs:
    structured_jsonl: Path
    structured_json: Path
    structured_md: Path
    audit_csv: Path
    summary_json: Path


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


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


def compact_text(value: object) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def count_pattern(pattern: re.Pattern[str], text: str) -> int:
    return len(pattern.findall(text))


def looks_like_note_line(text: str) -> bool:
    compact = compact_text(text)
    if not compact:
        return False
    if compact.startswith("注") or CIRCLED_NOTE_RE.match(compact):
        return True
    return bool(re.match(r"^[0-9０-９]+[).、）]", compact))


def extract_leading_yi_segment(text: str) -> str:
    line = str(text or "").strip()
    if not line or looks_like_note_line(line):
        return ""
    if "、" in line:
        return ""
    if not YI_CHAR_RE.search(line):
        return ""

    first_yi = next((idx for idx, char in enumerate(line) if YI_CHAR_RE.match(char)), -1)
    if first_yi < 0:
        return ""
    prefix = line[:first_yi]
    if HAN_CHAR_RE.search(prefix) or LATIN_CHAR_RE.search(prefix) or re.search(r"[0-9０-９]", prefix):
        return ""
    if len(compact_text(prefix)) > 4:
        return ""

    chars: list[str] = []
    for char in line[first_yi:]:
        if HAN_CHAR_RE.match(char) or LATIN_CHAR_RE.match(char) or re.match(r"[0-9０-９]", char):
            break
        chars.append(char)

    segment = clean_text("".join(chars))
    if count_pattern(YI_CHAR_RE, segment) < 2:
        return ""
    return segment


def extract_yi_original_lines(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return []
    boxed = [row for row in rows if row.get("bbox")]
    unboxed = [row for row in rows if not row.get("bbox")]
    extract_rows = sorted(suppress_contained_duplicates(boxed), key=sort_key) + sorted(unboxed, key=sort_key)
    lines = [
        line
        for row in extract_rows
        for line in split_nonempty_lines(row.get("text"))
    ]
    yi_lines = []
    for line in lines:
        segment = extract_leading_yi_segment(line)
        if segment:
            yi_lines.append(segment)
    return yi_lines


def valid_box(value: object) -> bool:
    return isinstance(value, list) and len(value) == 4 and value[2] > value[0] and value[3] > value[1]


def center_y_of(box: list[int]) -> float:
    return (box[1] + box[3]) / 2


def center_x_of(box: list[int]) -> float:
    return (box[0] + box[2]) / 2


def height_of(box: list[int]) -> int:
    return max(1, box[3] - box[1])


def vertical_overlap(a: list[int], b: list[int]) -> float:
    overlap = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return overlap / max(1, min(height_of(a), height_of(b)))


def dedupe_boxed_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    boxed = [row for row in rows if valid_box(row.get("bbox"))]
    unboxed = [row for row in rows if not valid_box(row.get("bbox"))]
    return sorted(suppress_contained_duplicates(boxed), key=sort_key) + sorted(unboxed, key=sort_key)


def is_han_translation_text(text: str) -> bool:
    if looks_like_note_line(text):
        return False
    compact = compact_text(text)
    if not compact:
        return False
    han_chars = count_pattern(HAN_CHAR_RE, compact)
    yi_chars = count_pattern(YI_CHAR_RE, compact)
    return han_chars >= 2 and han_chars >= yi_chars


def make_parallel_lines(page_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [row for row in dedupe_boxed_rows(rows) if valid_box(row.get("bbox"))]
    yi_rows: list[dict[str, Any]] = []
    han_rows: list[dict[str, Any]] = []
    for row in candidates:
        text = str(row.get("text") or "")
        yi_segment = extract_leading_yi_segment(text)
        if yi_segment:
            item = dict(row)
            item["yi_segment"] = yi_segment
            yi_rows.append(item)
        if is_han_translation_text(text):
            han_rows.append(row)

    pairs: list[dict[str, Any]] = []
    used_han: set[int] = set()
    for yi_row in sorted(yi_rows, key=lambda row: (center_y_of(row["bbox"]), center_x_of(row["bbox"]), str(row.get("id") or ""))):
        yi_box = yi_row["bbox"]
        yi_center_y = center_y_of(yi_box)
        best_idx: int | None = None
        best_score: tuple[float, float] | None = None
        for idx, han_row in enumerate(han_rows):
            if idx in used_han:
                continue
            han_box = han_row["bbox"]
            if center_x_of(han_box) <= center_x_of(yi_box):
                continue
            delta_y = abs(center_y_of(han_box) - yi_center_y)
            overlap = vertical_overlap(yi_box, han_box)
            if overlap < 0.25 and delta_y > max(24, height_of(yi_box) * 0.75, height_of(han_box) * 0.75):
                continue
            score = (delta_y, center_x_of(han_box) - center_x_of(yi_box))
            if best_score is None or score < best_score:
                best_score = score
                best_idx = idx
        if best_idx is None:
            continue
        used_han.add(best_idx)
        han_row = han_rows[best_idx]
        han_box = han_row["bbox"]
        line_y = (center_y_of(yi_box) + center_y_of(han_box)) / 2
        pairs.append(
            {
                "pair_id": f"{page_id}#parallel_{len(pairs) + 1:03d}",
                "yi_original": yi_row["yi_segment"],
                "han_translation": str(han_row.get("text") or ""),
                "yi_bbox": yi_box,
                "han_bbox": han_box,
                "yi_block_id": yi_row.get("id", ""),
                "han_block_id": han_row.get("id", ""),
                "line_y": round(line_y, 1),
                "vertical_delta": round(abs(center_y_of(han_box) - center_y_of(yi_box)), 1),
            }
        )
    return pairs


def extract_yi_original_text(text: str) -> str:
    rows = [{"text": line, "bbox": [], "reading_order": idx} for idx, line in enumerate(split_nonempty_lines(text), start=1)]
    return "\n".join(extract_yi_original_lines(rows))


def is_page_level_row(row: dict[str, Any]) -> bool:
    return any(key in row for key in PAGE_FIELD_ROLES) and ("ocr_text" not in row and "answer" not in row)


def split_nonempty_lines(text: object) -> list[str]:
    return [line.strip() for line in str(text or "").replace("\r", "").splitlines() if line.strip()]


def role_from_text(text: str, fallback: str = "body") -> str:
    compact = compact_text(text)
    if not compact:
        return "unknown"
    if re.fullmatch(r"[0-9０-９一二三四五六七八九十百第—\-]+", compact) and len(compact) <= 8:
        return "page_number"
    ascii_letters = count_pattern(LATIN_CHAR_RE, compact)
    yi_chars = count_pattern(YI_CHAR_RE, compact)
    if ascii_letters >= 3 and ascii_letters >= max(yi_chars, 1):
        return "pronunciation"
    return fallback if fallback in ROLE_ORDER else "body"


def page_extent(units: list[dict[str, Any]]) -> tuple[int, int]:
    max_x = 0
    max_y = 0
    for unit in units:
        box = unit.get("bbox") or [0, 0, 0, 0]
        if isinstance(box, list) and len(box) == 4:
            max_x = max(max_x, int(box[2] or 0))
            max_y = max(max_y, int(box[3] or 0))
    return max_x, max_y


def refine_unit_role(unit: dict[str, Any], page_width: int, page_height: int) -> str:
    route = str(unit.get("route") or "body")
    text = str(unit.get("text") or "")
    if route in {"title", "header", "footnote", "footer", "page_number"}:
        return route
    role = role_from_text(text, fallback="body")
    if role in {"page_number", "pronunciation"}:
        return role
    if route in {"body", "region"}:
        return "body"
    return route if route in ROLE_ORDER else "body"


def block_from_unit(unit: dict[str, Any], role: str, index: int) -> dict[str, Any]:
    return {
        "block_id": unit.get("id") or f"{unit.get('page_id', 'page')}#block_{index:03d}",
        "role": role,
        "reading_order": unit.get("reading_order", ""),
        "bbox": unit.get("bbox") or [0, 0, 0, 0],
        "text": unit.get("text") or "",
        "source_image": unit.get("image") or "",
        "ocr_status": unit.get("status") or "",
    }


def make_page_from_units(page_id: str, units: list[dict[str, Any]]) -> dict[str, Any]:
    units = sorted(units, key=sort_key)
    page_width, page_height = page_extent(units)
    blocks: list[dict[str, Any]] = []
    for idx, unit in enumerate(units, start=1):
        role = refine_unit_role(unit, page_width, page_height)
        blocks.append(block_from_unit(unit, role, idx))

    role_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for block in blocks:
        role_groups[str(block.get("role") or "unknown")].append(block)

    def joined(role: str) -> str:
        rows = [{"text": block.get("text", ""), "bbox": block.get("bbox", [0, 0, 0, 0]), "reading_order": block.get("reading_order", "")} for block in role_groups.get(role, [])]
        return "\n".join(visual_lines(rows)) if rows else ""

    body_rows = [
        {
            "id": block.get("block_id", ""),
            "text": block.get("text", ""),
            "bbox": block.get("bbox", [0, 0, 0, 0]),
            "reading_order": block.get("reading_order", ""),
        }
        for block in role_groups.get("body", [])
    ]
    parallel_lines = make_parallel_lines(page_id, body_rows)
    yi_original_text = "\n".join(extract_yi_original_lines(body_rows))
    han_translation_text = "\n".join(str(line.get("han_translation") or "") for line in parallel_lines if line.get("han_translation"))
    body_text = joined("body")
    note_text = "\n".join(part for part in [joined("note"), joined("footnote")] if part)
    page_number = joined("page_number")
    title = joined("title")
    warnings = []
    if not body_text and not title:
        warnings.append("empty_structured_text")
    if len(role_groups.get("unknown", [])):
        warnings.append("has_unknown_blocks")

    page_file = next((unit.get("file") or unit.get("page_file") for unit in units if unit.get("file") or unit.get("page_file")), f"{page_id}.png")
    return {
        "page_id": page_id,
        "page_file": page_file,
        "page_number": page_number,
        "title": title,
        "yi_original_text": yi_original_text,
        "han_translation_text": han_translation_text,
        "parallel_lines": parallel_lines,
        "body_text": body_text,
        "notes": split_nonempty_lines(note_text),
        "pronunciation_blocks": [block for block in role_groups.get("pronunciation", [])],
        "blocks": sorted(blocks, key=lambda block: (ROLE_ORDER.get(str(block.get("role") or "unknown"), 90), str(block.get("reading_order") or ""), str(block.get("block_id") or ""))),
        "role_counts": dict(sorted(Counter(str(block.get("role") or "unknown") for block in blocks).items())),
        "warnings": warnings,
    }


def make_pages_from_units(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    units = [normalize_unit(row) for row in rows]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for unit in units:
        grouped[str(unit.get("page_id") or "unknown_page")].append(unit)
    return [make_page_from_units(page_id, grouped[page_id]) for page_id in sorted(grouped)]


def make_block_from_page_field(page: dict[str, Any], role: str, text: str, index: int) -> dict[str, Any]:
    return {
        "block_id": f"{page.get('page_id', 'page')}#{role}_{index:03d}",
        "role": role_from_text(text, fallback=role),
        "reading_order": index,
        "bbox": [],
        "text": text,
        "source_image": "",
        "ocr_status": "assembled_page_field",
    }


def make_page_from_assembled(page: dict[str, Any]) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    idx = 1
    for role in PAGE_FIELD_ROLES:
        text = clean_text(page.get(role))
        if not text:
            continue
        for part in split_nonempty_lines(text):
            blocks.append(make_block_from_page_field(page, role, part, idx))
            idx += 1

    body_lines = [block["text"] for block in blocks if block["role"] == "body"]
    note_lines = [block["text"] for block in blocks if block["role"] in {"note", "footnote"}]
    title_lines = [block["text"] for block in blocks if block["role"] == "title"]
    page_number_lines = [block["text"] for block in blocks if block["role"] == "page_number"]
    body_text = "\n".join(body_lines) or clean_text(page.get("text"))
    warnings = []
    if not blocks:
        warnings.append("empty_page")
    if not body_lines and clean_text(page.get("text")):
        warnings.append("text_only_no_body_field")

    return {
        "page_id": str(page.get("page_id") or page.get("file") or ""),
        "page_file": str(page.get("file") or page.get("page_file") or ""),
        "page_number": "\n".join(page_number_lines),
        "title": "\n".join(title_lines),
        "yi_original_text": extract_yi_original_text(body_text),
        "han_translation_text": "",
        "parallel_lines": [],
        "body_text": body_text,
        "notes": note_lines,
        "pronunciation_blocks": [block for block in blocks if block["role"] == "pronunciation"],
        "blocks": blocks,
        "role_counts": dict(sorted(Counter(str(block.get("role") or "unknown") for block in blocks).items())),
        "warnings": warnings,
    }


def make_pages_from_assembled(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [make_page_from_assembled(row) for row in rows]


def audit_rows(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in pages:
        body = str(page.get("body_text") or "")
        yi_original = str(page.get("yi_original_text") or "")
        han_translation = str(page.get("han_translation_text") or "")
        parallel_lines = page.get("parallel_lines") if isinstance(page.get("parallel_lines"), list) else []
        notes = page.get("notes") if isinstance(page.get("notes"), list) else []
        rows.append(
            {
                "page_id": page.get("page_id", ""),
                "page_file": page.get("page_file", ""),
                "blocks": len(page.get("blocks", [])),
                "roles": json.dumps(page.get("role_counts", {}), ensure_ascii=False),
                "title_chars": len(str(page.get("title") or "")),
                "yi_original_chars": len(compact_text(yi_original)),
                "yi_original_lines": len(split_nonempty_lines(yi_original)),
                "han_translation_chars": len(compact_text(han_translation)),
                "han_translation_lines": len(split_nonempty_lines(han_translation)),
                "parallel_lines": len(parallel_lines),
                "body_chars": len(body),
                "body_lines": len(split_nonempty_lines(body)),
                "notes": len(notes),
                "page_number": clean_text(page.get("page_number")),
                "warnings": ";".join(page.get("warnings", [])),
            }
        )
    return rows


def write_markdown(path: Path, pages: list[dict[str, Any]]) -> None:
    lines = ["# Structured Pages", ""]
    for page in pages:
        lines.append(f"## {page.get('page_id', '')}")
        if page.get("title"):
            lines.extend(["", f"**Title**: {page['title']}"])
        if page.get("page_number"):
            lines.extend(["", f"**Page number**: {page['page_number']}"])
        if page.get("yi_original_text"):
            lines.extend(["", "**Yi original**", "", str(page.get("yi_original_text") or "")])
        if page.get("parallel_lines"):
            lines.extend(["", "**Yi-Han aligned lines**", ""])
            for item in page.get("parallel_lines") or []:
                lines.append(f"- {item.get('yi_original', '')} | {item.get('han_translation', '')}")
        lines.extend(["", "**Body**", "", str(page.get("body_text") or "")])
        notes = page.get("notes") if isinstance(page.get("notes"), list) else []
        if notes:
            lines.extend(["", "**Notes**", ""])
            lines.extend(f"- {note}" for note in notes)
        if page.get("warnings"):
            lines.extend(["", f"Warnings: {', '.join(page['warnings'])}"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def build_summary(input_path: Path, input_kind: str, pages: list[dict[str, Any]]) -> dict[str, Any]:
    role_counts = Counter()
    warnings = Counter()
    for page in pages:
        role_counts.update(page.get("role_counts", {}))
        warnings.update(page.get("warnings", []))
    yi_original_lines = sum(len(split_nonempty_lines(page.get("yi_original_text"))) for page in pages)
    parallel_lines = sum(len(page.get("parallel_lines") if isinstance(page.get("parallel_lines"), list) else []) for page in pages)
    return {
        "structure_impl": "page_processing/structure_pages.py",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "input": str(input_path),
        "input_kind": input_kind,
        "pages": len(pages),
        "blocks": sum(len(page.get("blocks", [])) for page in pages),
        "yi_original_lines": yi_original_lines,
        "pages_with_yi_original": sum(1 for page in pages if clean_text(page.get("yi_original_text"))),
        "parallel_lines": parallel_lines,
        "pages_with_parallel_lines": sum(1 for page in pages if page.get("parallel_lines")),
        "role_counts": dict(sorted(role_counts.items())),
        "warning_counts": dict(sorted(warnings.items())),
        "pages_with_warnings": [page.get("page_id") for page in pages if page.get("warnings")],
    }


def structure_pages(input_path: Path, out_dir: Path, input_kind: str = "auto", out_prefix: str = "structured_pages") -> StructureOutputs:
    rows = read_jsonl(input_path)
    if not rows:
        raise SystemExit(f"No rows found in {input_path}")
    detected_kind = "assembled_pages" if is_page_level_row(rows[0]) else "ocr_units"
    kind = detected_kind if input_kind == "auto" else input_kind
    if kind == "assembled_pages":
        pages = make_pages_from_assembled(rows)
    elif kind == "ocr_units":
        pages = make_pages_from_units(rows)
    else:
        raise SystemExit(f"Unknown input kind: {input_kind}")

    out_dir.mkdir(parents=True, exist_ok=True)
    structured_jsonl = out_dir / f"{out_prefix}.jsonl"
    structured_json = out_dir / f"{out_prefix}.json"
    structured_md = out_dir / f"{out_prefix}.md"
    audit_csv = out_dir / "page_structure_audit.csv"
    summary_json = out_dir / "structure_summary.json"

    write_jsonl(structured_jsonl, pages)
    structured_json.write_text(json.dumps({"pages": pages}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(structured_md, pages)
    write_csv(audit_csv, audit_rows(pages))
    summary_json.write_text(json.dumps(build_summary(input_path, kind, pages), ensure_ascii=False, indent=2), encoding="utf-8")
    return StructureOutputs(structured_jsonl, structured_json, structured_md, audit_csv, summary_json)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export lightweight structured page JSON from OCR page outputs.")
    parser.add_argument("--input", type=Path, required=True, help="OCR-unit JSONL or assembled submission_pages.jsonl.")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output directory.")
    parser.add_argument("--input-kind", choices=["auto", "ocr_units", "assembled_pages"], default="auto")
    parser.add_argument("--out-prefix", default="structured_pages")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = structure_pages(
        args.input.resolve(),
        args.out_dir.resolve(),
        input_kind=args.input_kind,
        out_prefix=args.out_prefix,
    )
    print(json.dumps({key: str(value) for key, value in outputs.__dict__.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
