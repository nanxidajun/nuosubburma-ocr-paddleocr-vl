#!/usr/bin/env python3
"""Convert assembled page workflow outputs to eval result JSONL.

`analyze_submission_eval.py` expects one row per annotation id with an `answer`
field. Page workflow assembly writes one row per page with `page_id` and `text`.
This script bridges the two formats so page outputs can be merged back into the
full final-system result. The page-only score is a diagnostic table.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def assistant_text(row: dict[str, Any]) -> str:
    for message in reversed(row.get("messages") or []):
        if message.get("role") == "assistant":
            return str(message.get("content") or "")
    return ""


def page_key(row: dict[str, Any]) -> str:
    for key in ("page_id", "id"):
        value = row.get(key)
        if value:
            return Path(str(value)).stem
    for key in ("file", "page_file"):
        value = row.get(key)
        if value:
            return Path(str(value)).stem
    return ""


def assembled_text(row: dict[str, Any], text_field: str) -> str:
    return str(row.get(text_field) or row.get("prediction") or row.get("answer") or "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert assembled page JSONL into evaluation result JSONL.")
    parser.add_argument("--annotations", type=Path, required=True, help="Page-route annotations.jsonl")
    parser.add_argument("--assembled-pages", type=Path, required=True, help="submission_pages.jsonl from assemble_pages.py")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--text-field", default="text")
    args = parser.parse_args()

    annotations = read_jsonl(args.annotations)
    assembled_rows = read_jsonl(args.assembled_pages)
    assembled_by_key = {page_key(row): row for row in assembled_rows if page_key(row)}

    out_rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for anno in annotations:
        sid = str(anno.get("id") or "")
        assembled = assembled_by_key.get(sid)
        if assembled is None:
            missing.append(sid)
            continue
        row = dict(anno)
        row["answer"] = assembled_text(assembled, args.text_field)
        row["label"] = assistant_text(anno)
        meta = dict(row.get("meta") or {})
        meta["final_eval_route"] = "page_workflow"
        meta["page_workflow_source"] = str(args.assembled_pages)
        row["meta"] = meta
        out_rows.append(row)

    extra = sorted(set(assembled_by_key) - {str(row.get("id") or "") for row in annotations})
    if missing:
        raise SystemExit(f"Missing assembled pages for {len(missing)} annotations, first={missing[:10]}")

    write_jsonl(args.output, out_rows)
    summary = {
        "annotations": str(args.annotations),
        "assembled_pages": str(args.assembled_pages),
        "output": str(args.output),
        "rows": len(out_rows),
        "extra_assembled_pages": extra[:50],
        "extra_assembled_pages_count": len(extra),
    }
    summary_path = args.output.with_suffix(args.output.suffix + ".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
