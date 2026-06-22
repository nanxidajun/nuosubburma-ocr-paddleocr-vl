#!/usr/bin/env python3
"""Build a browsable folder of successful crop outputs.

This script gathers v3/v4 crop outputs into one directory:

- primary line crops from v3
- secondary line crops from v4
- region crops that should remain region OCR inputs
- ignored/special samples for reference

It copies files and never moves or deletes source artifacts.
"""

from __future__ import annotations

import argparse
import csv
import shutil
from collections import Counter
from pathlib import Path


PRIMARY_LINE_LABELS = {"body_line", "toc_line", "mixed_cover_line"}
REGION_KEEP_DECISIONS = {
    "secondary_split_possible_but_keep_region_default",
    "secondary_line_candidate_needs_review",
}
REFERENCE_LABELS = {
    "handwritten_mark",
    "ornament_or_cover_art",
    "header_line",
    "footer_or_page_number",
    "border_or_rule",
    "cover_or_low_quality",
}


def is_clean_header_text(row: dict[str, str]) -> bool:
    """Return true when a header crop is text-like enough for OCR.

    Header detections can either be useful text (book title/page number) or a
    long decorative/rule strip. Only the compact text-like crop should be
    promoted into OCR-ready rows.
    """
    if row.get("label") != "header_line":
        return False

    y = as_int(row.get("y"))
    w = as_int(row.get("w"))
    h = as_int(row.get("h"))

    if h < 28 or h > 130:
        return False
    if y <= 4 and h < 35:
        return False
    if w < 70 or w > 760:
        return False

    return True


def safe_name(name: str) -> str:
    return name.replace("/", "_").replace(" ", "_")


def copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def as_int(value: object, default: int = 0) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def page_id_for(file_value: str) -> str:
    return Path(file_value).stem


def crop_id_from_summary_path(summary_path: str, fallback_page: str = "") -> str:
    stem = Path(summary_path).stem
    if stem:
        if fallback_page and not stem.startswith(fallback_page):
            return f"{fallback_page}__{stem}"
        return stem
    return fallback_page


def make_reading_order(page: str, source_box: object, part_index: object = "", bucket_rank: int = 0) -> str:
    part = as_int(part_index, 0) if str(part_index) else 0
    return f"{page}__box_{as_int(source_box):06d}__part_{part:03d}__bucket_{bucket_rank:02d}"


def base_index_row(
    *,
    bucket: str,
    sub_bucket: str,
    file_value: str,
    source_box: object,
    part_index: object = "",
    label_or_decision: str,
    source_path: Path,
    summary_path: Path,
    output_root: Path,
    note: str,
    role: str,
    source_stage: str,
    is_primary_line: bool = False,
    is_line_ocr_ready: bool = False,
    needs_review: bool = False,
    bucket_rank: int = 0,
) -> dict[str, str]:
    rel_summary = str(summary_path.relative_to(output_root))
    page = page_id_for(file_value)
    crop_id = crop_id_from_summary_path(rel_summary, page)
    return {
        "crop_id": crop_id,
        "page_id": page,
        "page_file": file_value,
        "bucket": bucket,
        "sub_bucket": sub_bucket,
        "role": role,
        "source_stage": source_stage,
        "source_box": str(source_box),
        "part_index": str(part_index),
        "label_or_decision": label_or_decision,
        "is_primary_line": "1" if is_primary_line else "0",
        "is_line_ocr_ready": "1" if is_line_ocr_ready else "0",
        "needs_review": "1" if needs_review else "0",
        "reading_order": make_reading_order(page, source_box, part_index, bucket_rank),
        "source_path": str(source_path),
        "summary_path": rel_summary,
        "note": note,
    }


def gather_primary_lines(v3_root: Path, rows: list[dict[str, str]], output: Path) -> list[dict[str, str]]:
    index_rows: list[dict[str, str]] = []
    for row in rows:
        label = row["label"]
        clean_header = is_clean_header_text(row)
        if label not in PRIMARY_LINE_LABELS and not clean_header:
            continue
        src = v3_root / row["crop_path"]
        page = Path(row["file"]).stem
        out_label = "header_text_line" if clean_header else label
        dest_name = f"{page}__v3_box_{int(row['index']):03d}__{out_label}{src.suffix}"
        dest = output / "01_line_ocr_ready" / "primary_v3" / out_label / page / dest_name
        copy_file(src, dest)
        index_rows.append(
            base_index_row(
                bucket="01_line_ocr_ready",
                sub_bucket=f"primary_v3/{out_label}",
                file_value=row["file"],
                source_box=row["index"],
                label_or_decision=out_label,
                source_path=src,
                summary_path=dest,
                output_root=output,
                note="v3 clean header text crop; ready for line OCR" if clean_header else "v3 primary line crop; ready for line OCR",
                role="primary_line",
                source_stage="v3",
                is_primary_line=True,
                is_line_ocr_ready=True,
                needs_review=False,
                bucket_rank=0,
            )
        )
    return index_rows


def gather_reference_crops(v3_root: Path, rows: list[dict[str, str]], output: Path) -> list[dict[str, str]]:
    index_rows: list[dict[str, str]] = []
    for row in rows:
        label = row["label"]
        if is_clean_header_text(row):
            continue
        if label not in REFERENCE_LABELS:
            continue
        src = v3_root / row["crop_path"]
        page = Path(row["file"]).stem
        dest_name = f"{page}__v3_box_{int(row['index']):03d}__{label}{src.suffix}"
        dest = output / "04_ignore_or_special_reference" / label / page / dest_name
        copy_file(src, dest)
        index_rows.append(
            base_index_row(
                bucket="04_ignore_or_special_reference",
                sub_bucket=label,
                file_value=row["file"],
                source_box=row["index"],
                label_or_decision=label,
                source_path=src,
                summary_path=dest,
                output_root=output,
                note="reference crop; not line OCR training data",
                role="reference",
                source_stage="v3",
                needs_review=True,
                bucket_rank=4,
            )
        )
    return index_rows


def gather_secondary_lines(v4_root: Path, rows: list[dict[str, str]], output: Path) -> list[dict[str, str]]:
    index_rows: list[dict[str, str]] = []
    for row in rows:
        decision = row["decision"]
        if decision != "secondary_line_candidate":
            continue
        src = v4_root / row["crop_path"]
        page = Path(row["file"]).stem
        dest_name = (
            f"{page}__v4_box_{int(row['parent_index']):03d}"
            f"__part_{int(row['split_index']):03d}{src.suffix}"
        )
        dest = output / "01_line_ocr_ready" / "secondary_v4" / page / f"box_{int(row['parent_index']):03d}" / dest_name
        copy_file(src, dest)
        index_rows.append(
            base_index_row(
                bucket="01_line_ocr_ready",
                sub_bucket="secondary_v4",
                file_value=row["file"],
                source_box=row["parent_index"],
                part_index=row["split_index"],
                label_or_decision=decision,
                source_path=src,
                summary_path=dest,
                output_root=output,
                note="v4 secondary split; reviewed as line OCR candidate",
                role="secondary_line",
                source_stage="v4",
                is_line_ocr_ready=True,
                needs_review=True,
                bucket_rank=1,
            )
        )
    return index_rows


def gather_region_keep(v4_root: Path, rows: list[dict[str, str]], output: Path) -> list[dict[str, str]]:
    index_rows: list[dict[str, str]] = []
    for row in rows:
        decision = row["decision"]
        if decision not in REGION_KEEP_DECISIONS:
            continue
        src = v4_root / row["region_crop_path"]
        page = Path(row["file"]).stem
        dest_name = f"{page}__v4_box_{int(row['parent_index']):03d}__{decision}{src.suffix}"
        dest = output / "03_region_ocr_keep" / decision / page / dest_name
        copy_file(src, dest)
        index_rows.append(
            base_index_row(
                bucket="03_region_ocr_keep",
                sub_bucket=decision,
                file_value=row["file"],
                source_box=row["parent_index"],
                label_or_decision=decision,
                source_path=src,
                summary_path=dest,
                output_root=output,
                note=row["reason"],
                role="region_keep",
                source_stage="v4",
                needs_review=True,
                bucket_rank=3,
            )
        )
    return index_rows


def gather_review_sheets(v4_root: Path, output: Path) -> list[dict[str, str]]:
    index_rows: list[dict[str, str]] = []
    sheet_root = v4_root / "secondary_contact_sheets"
    if not sheet_root.exists():
        return index_rows
    for src in sorted(sheet_root.rglob("*.png")):
        rel = src.relative_to(sheet_root)
        page = rel.parts[0] if rel.parts else ""
        source_box = src.stem.replace("__sheet", "").replace("box_", "")
        dest = output / "02_review_contact_sheets" / rel
        copy_file(src, dest)
        index_rows.append(
            base_index_row(
                bucket="02_review_contact_sheets",
                sub_bucket=str(rel.parent),
                file_value=page,
                source_box=source_box,
                label_or_decision="contact_sheet",
                source_path=src,
                summary_path=dest,
                output_root=output,
                note="human review sheet for v4 secondary split",
                role="review_sheet",
                source_stage="v4",
                needs_review=True,
                bucket_rank=2,
            )
        )
    return index_rows


def write_index(output: Path, rows: list[dict[str, str]]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    rows = sorted(
        rows,
        key=lambda row: (
            row.get("page_id", ""),
            as_int(row.get("source_box")),
            as_int(row.get("part_index")),
            row.get("role", ""),
            row.get("bucket", ""),
            row.get("summary_path", ""),
        ),
    )
    fields = [
        "crop_id",
        "page_id",
        "page_file",
        "bucket",
        "sub_bucket",
        "role",
        "source_stage",
        "source_box",
        "part_index",
        "label_or_decision",
        "is_primary_line",
        "is_line_ocr_ready",
        "needs_review",
        "reading_order",
        "source_path",
        "summary_path",
        "note",
    ]
    with (output / "index.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(row["bucket"] for row in rows)
    sub_counts = Counter(f"{row['bucket']}/{row['sub_bucket']}" for row in rows)

    with (output / "README.md").open("w", encoding="utf-8") as f:
        f.write("# 切图成功汇总\n\n")
        f.write("该目录汇总 v3/v4 输出，便于浏览、标注和接入 OCR。源文件没有被移动或删除。\n\n")
        f.write("## 目录说明\n\n")
        f.write("| 目录 | 用途 |\n")
        f.write("|---|---|\n")
        f.write("| `01_line_ocr_ready/primary_v3/` | v3 一次切分已经可直接进入行级 OCR 的图 |\n")
        f.write("| `01_line_ocr_ready/secondary_v4/` | v4 二次切分后通过人工验收的行候选图 |\n")
        f.write("| `02_review_contact_sheets/` | v4 二次切分 contact sheet，便于复核 |\n")
        f.write("| `03_region_ocr_keep/` | 不建议继续拆行，保留给 region OCR 的区域图 |\n")
        f.write("| `04_ignore_or_special_reference/` | 手写记号、花纹、页眉页脚、低质量封面等参考样本 |\n")
        f.write("| `index.csv` | 全部文件索引、来源路径和处理说明 |\n\n")

        f.write("## 数量汇总\n\n")
        f.write("| bucket | count |\n")
        f.write("|---|---:|\n")
        for bucket, count in sorted(counts.items()):
            f.write(f"| `{bucket}` | {count} |\n")

        f.write("\n## 细分数量\n\n")
        f.write("| sub bucket | count |\n")
        f.write("|---|---:|\n")
        for bucket, count in sorted(sub_counts.items()):
            f.write(f"| `{bucket}` | {count} |\n")

        f.write("\n## 使用建议\n\n")
        f.write("1. 训练/评估行级 OCR：优先使用 `01_line_ocr_ready/primary_v3/`，`secondary_v4` 需要保留 `part_index` 并单独复核。\n")
        f.write("2. 构造 region OCR 小试验集：优先使用 `03_region_ocr_keep/`。\n")
        f.write("3. 不要把 `04_ignore_or_special_reference/` 混入 OCR 正样本，它只用于调试页面分流。\n")
        f.write("4. 下游推理和人工复核必须使用 `crop_id` 去重，不能只用 `page_id + source_box`，否则 v4 二切行会被跳过。\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v3-root", type=Path, default=Path("crop_pipeline_output/01_v3_routing"))
    parser.add_argument("--v4-root", type=Path, default=Path("crop_pipeline_output/02_v4_secondary_split"))
    parser.add_argument("--output", type=Path, default=Path("crop_pipeline_output/04_successful_crop_summary"))
    args = parser.parse_args()

    rows: list[dict[str, str]] = []
    v3_rows = read_csv(args.v3_root / "reports" / "hybrid_box_summary.csv")
    v4_region_rows = read_csv(args.v4_root / "reports" / "secondary_region_summary.csv")
    v4_split_rows = read_csv(args.v4_root / "reports" / "secondary_split_summary.csv")

    rows.extend(gather_primary_lines(args.v3_root, v3_rows, args.output))
    rows.extend(gather_secondary_lines(args.v4_root, v4_split_rows, args.output))
    rows.extend(gather_region_keep(args.v4_root, v4_region_rows, args.output))
    rows.extend(gather_review_sheets(args.v4_root, args.output))
    rows.extend(gather_reference_crops(args.v3_root, v3_rows, args.output))
    write_index(args.output, rows)
    print(f"Done. Wrote {len(rows)} summarized files to {args.output}")


if __name__ == "__main__":
    main()
