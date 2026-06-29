#!/usr/bin/env python3
"""Split the evaluation set by the final system route.

The final system uses two routes and merges their outputs before scoring:

- direct: line/region samples are sent directly to the OCR model.
- page: page samples are handled by page_processing + OCR + assembly.

This helper writes two self-contained annotation folders so cloud runs do not
need manual JSONL filtering. Use merge_final_route_results.py after both
routes finish to build the full result JSONL for the main score.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
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


def sample_type(row: dict[str, Any]) -> str:
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    return str(meta.get("sample_type") or meta.get("granularity") or "").strip().lower()


def resolve_image(image_ref: str, annotations: Path) -> Path:
    path = Path(image_ref)
    if path.is_absolute():
        return path
    return (annotations.parent / path).resolve()


def copy_or_link(src: Path, dst: Path, mode: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    if mode == "symlink":
        os.symlink(src, dst)
    else:
        shutil.copy2(src, dst)


def routed_row(row: dict[str, Any], annotations: Path, subset_root: Path, copy_mode: str) -> dict[str, Any]:
    out = dict(row)
    image_refs = list(row.get("images") or [])
    new_refs: list[str] = []
    for idx, image_ref in enumerate(image_refs):
        src = resolve_image(str(image_ref), annotations)
        if not src.exists():
            raise SystemExit(f"Missing image for {row.get('id')}: {src}")
        suffix = src.suffix.lower() or ".png"
        stem = str(row.get("id") or src.stem)
        name = f"{stem}{suffix}" if len(image_refs) == 1 else f"{stem}__img{idx + 1}{suffix}"
        rel = Path("images") / name
        dst = subset_root / rel
        copy_or_link(src, dst, copy_mode)
        new_refs.append(rel.as_posix())
    out["images"] = new_refs
    meta = dict(out.get("meta") or {})
    meta["final_eval_route"] = "page_workflow" if sample_type(row) == "page" else "direct_ocr"
    out["meta"] = meta
    return out


def write_subset(rows: list[dict[str, Any]], annotations: Path, subset_root: Path, copy_mode: str) -> list[dict[str, Any]]:
    routed = [routed_row(row, annotations, subset_root, copy_mode) for row in rows]
    write_jsonl(subset_root / "annotations.jsonl", routed)
    return routed


def main() -> None:
    parser = argparse.ArgumentParser(description="Split eval annotations into direct and page-workflow routes.")
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--copy-mode", choices=["copy", "symlink"], default="copy")
    args = parser.parse_args()

    annotations = args.annotations.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()
    rows = read_jsonl(annotations)
    page_rows = [row for row in rows if sample_type(row) == "page"]
    direct_rows = [row for row in rows if sample_type(row) != "page"]

    direct_out = write_subset(direct_rows, annotations, out_dir / "direct", args.copy_mode)
    page_out = write_subset(page_rows, annotations, out_dir / "page", args.copy_mode)

    page_stem_mismatches = []
    for row in page_out:
        image_refs = row.get("images") or []
        if image_refs and Path(str(image_refs[0])).stem != str(row.get("id")):
            page_stem_mismatches.append(row.get("id"))

    manifest = {
        "source_annotations": str(annotations),
        "out_dir": str(out_dir),
        "copy_mode": args.copy_mode,
        "total_rows": len(rows),
        "direct_rows": len(direct_out),
        "page_rows": len(page_out),
        "direct_annotations": str(out_dir / "direct" / "annotations.jsonl"),
        "page_annotations": str(out_dir / "page" / "annotations.jsonl"),
        "page_images": str(out_dir / "page" / "images"),
        "page_image_stem_mismatches": page_stem_mismatches,
    }
    (out_dir / "final_eval_routes_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
