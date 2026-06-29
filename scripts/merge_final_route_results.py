#!/usr/bin/env python3
"""Merge direct OCR and page-workflow outputs into one final eval result.

The final system uses two routes:

- line/region samples: direct OCR result.
- page samples: DocLayout -> OCR units -> page assembly result.

This script writes one JSONL in the original annotation order, so
`analyze_submission_eval.py` can compute the main score over the full
evaluation set. Route-level scores remain useful diagnostics, but this merged
file is the final system output.
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
    if isinstance(row.get("label"), str):
        return row["label"]
    for message in reversed(row.get("messages") or []):
        if message.get("role") == "assistant":
            return str(message.get("content") or "")
    return ""


def answer_text(row: dict[str, Any]) -> str:
    for key in ("answer", "prediction", "text", "ocr_text"):
        value = row.get(key)
        if value is not None:
            return str(value)
    return ""


def sample_type(row: dict[str, Any]) -> str:
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    return str(meta.get("sample_type") or meta.get("granularity") or "").strip().lower()


def index_results(path: Path, route_name: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    duplicate_ids: list[str] = []
    for row in read_jsonl(path):
        sid = str(row.get("id") or "")
        if not sid:
            raise SystemExit(f"{route_name} result has a row without id: {path}")
        if sid in indexed:
            duplicate_ids.append(sid)
        indexed[sid] = row
    if duplicate_ids:
        raise SystemExit(f"{route_name} result has duplicate ids, first={duplicate_ids[:10]}")
    return indexed


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge final direct/page route results into one JSONL.")
    parser.add_argument("--annotations", type=Path, required=True, help="Full evaluation annotations.jsonl")
    parser.add_argument("--direct-result", type=Path, required=True, help="Result JSONL for line/region samples")
    parser.add_argument("--page-result", type=Path, required=True, help="Result JSONL for page workflow samples")
    parser.add_argument("--output", type=Path, required=True, help="Merged final system result JSONL")
    args = parser.parse_args()

    annotations_path = args.annotations.expanduser().resolve()
    direct_result_path = args.direct_result.expanduser().resolve()
    page_result_path = args.page_result.expanduser().resolve()
    output_path = args.output.expanduser().resolve()

    annotations = read_jsonl(annotations_path)
    direct_by_id = index_results(direct_result_path, "direct")
    page_by_id = index_results(page_result_path, "page")

    overlap = sorted(set(direct_by_id) & set(page_by_id))
    if overlap:
        raise SystemExit(f"Result ids appear in both direct and page routes, first={overlap[:10]}")

    annotation_ids = [str(row.get("id") or "") for row in annotations]
    if any(not sid for sid in annotation_ids):
        raise SystemExit("Full annotations contain rows without id")
    annotation_id_set = set(annotation_ids)

    extra_direct = sorted(set(direct_by_id) - annotation_id_set)
    extra_page = sorted(set(page_by_id) - annotation_id_set)
    if extra_direct or extra_page:
        raise SystemExit(
            "Result files contain ids outside full annotations: "
            f"direct={extra_direct[:10]}, page={extra_page[:10]}"
        )

    out_rows: list[dict[str, Any]] = []
    missing_direct: list[str] = []
    missing_page: list[str] = []
    wrong_direct_page_ids: list[str] = []
    wrong_page_direct_ids: list[str] = []

    direct_count = 0
    page_count = 0
    for anno in annotations:
        sid = str(anno.get("id") or "")
        is_page = sample_type(anno) == "page"
        route = "page_workflow" if is_page else "direct_ocr"
        result_row = page_by_id.get(sid) if is_page else direct_by_id.get(sid)

        if result_row is None:
            if is_page:
                missing_page.append(sid)
            else:
                missing_direct.append(sid)
            continue

        if is_page and sid in direct_by_id:
            wrong_direct_page_ids.append(sid)
        if not is_page and sid in page_by_id:
            wrong_page_direct_ids.append(sid)

        merged = dict(anno)
        merged["answer"] = answer_text(result_row)
        merged["label"] = assistant_text(anno)
        meta = dict(merged.get("meta") or {})
        meta["final_eval_route"] = route
        merged["meta"] = meta
        out_rows.append(merged)
        if is_page:
            page_count += 1
        else:
            direct_count += 1

    problems = []
    if missing_direct:
        problems.append(f"missing direct rows={len(missing_direct)}, first={missing_direct[:10]}")
    if missing_page:
        problems.append(f"missing page rows={len(missing_page)}, first={missing_page[:10]}")
    if wrong_direct_page_ids:
        problems.append(f"page ids also present in direct result, first={wrong_direct_page_ids[:10]}")
    if wrong_page_direct_ids:
        problems.append(f"direct ids also present in page result, first={wrong_page_direct_ids[:10]}")
    if problems:
        raise SystemExit("; ".join(problems))

    write_jsonl(output_path, out_rows)
    summary = {
        "annotations": str(annotations_path),
        "direct_result": str(direct_result_path),
        "page_result": str(page_result_path),
        "output": str(output_path),
        "total_rows": len(out_rows),
        "direct_rows": direct_count,
        "page_rows": page_count,
        "annotation_rows": len(annotations),
        "missing_rows": 0,
    }
    summary_path = output_path.with_suffix(output_path.suffix + ".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
