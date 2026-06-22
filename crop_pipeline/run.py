#!/usr/bin/env python3
"""Run the reusable book-page crop pipeline end to end.

Pipeline:
1. v3: page-level line/region routing
2. v4: secondary split for region-fallback boxes
3. visual review folder for humans
4. successful crop summary for OCR/annotation
"""

from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}
PDF_EXTS = {".pdf"}


def run_step(cmd: list[str]) -> None:
    print("\n$", " ".join(str(part) for part in cmd), flush=True)
    subprocess.run(cmd, check=True)


def image_files(input_dir: Path) -> list[Path]:
    return sorted(path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTS)


def safe_stem(path: Path) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in path.stem)
    return cleaned.strip("_") or "input"


def copy_single_image(src: Path, pages_dir: Path) -> Path:
    pages_dir.mkdir(parents=True, exist_ok=True)
    dest = pages_dir / f"{safe_stem(src)}_p001{src.suffix.lower()}"
    shutil.copy2(src, dest)
    return dest


def render_pdf_to_pages(pdf_path: Path, pages_dir: Path, *, dpi: int, max_pages: int) -> list[Path]:
    pages_dir.mkdir(parents=True, exist_ok=True)
    prefix = pages_dir / f"{safe_stem(pdf_path)}_page"
    cmd = [
        "pdftoppm",
        "-png",
        "-r",
        str(dpi),
        "-f",
        "1",
    ]
    if max_pages > 0:
        cmd.extend(["-l", str(max_pages)])
    cmd.extend([str(pdf_path), str(prefix)])

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError as exc:
        raise SystemExit("PDF input requires Poppler `pdftoppm`. Install poppler first.") from exc

    pages = sorted(pages_dir.glob(f"{prefix.name}-*.png"))
    renamed: list[Path] = []
    for idx, page in enumerate(pages, start=1):
        dest = pages_dir / f"{safe_stem(pdf_path)}_p{idx:03d}.png"
        page.rename(dest)
        renamed.append(dest)
    if not renamed:
        raise SystemExit(f"No pages were rendered from PDF: {pdf_path}")
    return renamed


def prepare_input_pages(input_path: Path, output_root: Path, *, pdf_dpi: int, max_pages: int) -> Path:
    if input_path.is_dir():
        return input_path
    if not input_path.exists():
        raise SystemExit(f"Input does not exist: {input_path}")

    pages_dir = output_root / "00_input_pages"
    if input_path.suffix.lower() in IMAGE_EXTS:
        copy_single_image(input_path, pages_dir)
        return pages_dir
    if input_path.suffix.lower() in PDF_EXTS:
        render_pdf_to_pages(input_path, pages_dir, dpi=pdf_dpi, max_pages=max_pages)
        return pages_dir

    allowed = ", ".join(sorted(IMAGE_EXTS | PDF_EXTS))
    raise SystemExit(f"Unsupported input type `{input_path.suffix}`. Expected a folder or one of: {allowed}")


def filename_page_hint(path: Path) -> str:
    name = path.stem
    if "低质量" in name or ("封面" in name and "封面混排" not in name):
        return "cover_or_low_quality"
    if "封面混排" in name:
        return "mixed_cover_page"
    if "目录" in name:
        return "toc"
    if "混排" in name:
        return "mixed_page"
    return "body_page"


def write_manifest_template(input_dir: Path, output_root: Path) -> None:
    rows = []
    for image in image_files(input_dir):
        rows.append(
            {
                "file": image.name,
                "page_hint": filename_page_hint(image),
                "note": "edit page_hint if filename-based guess is wrong",
            }
        )

    with (output_root / "page_manifest_template.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "page_hint", "note"])
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_run_summary(input_dir: Path, output_root: Path, page_manifest: Path | None) -> None:
    page_rows = read_csv_rows(output_root / "01_v3_routing" / "reports" / "hybrid_page_summary.csv")
    box_rows = read_csv_rows(output_root / "01_v3_routing" / "reports" / "hybrid_box_summary.csv")
    region_rows = read_csv_rows(output_root / "02_v4_secondary_split" / "reports" / "secondary_region_summary.csv")
    summary_rows = read_csv_rows(output_root / "04_successful_crop_summary" / "index.csv")

    page_hint_counts = Counter(row["page_hint"] for row in page_rows)
    label_counts = Counter(row["label"] for row in box_rows)
    decision_counts = Counter(row["decision"] for row in region_rows)
    bucket_counts = Counter(row["bucket"] for row in summary_rows)

    promoted_splits = sum(
        int(row.get("split_count") or 0)
        for row in region_rows
        if row.get("decision", "").startswith("secondary_line_candidate")
    )

    with (output_root / "run_summary.md").open("w", encoding="utf-8") as f:
        f.write("# Book Crop Pipeline Run Summary\n\n")
        f.write(f"- Input: `{input_dir}`\n")
        f.write(f"- Page manifest: `{page_manifest}`\n" if page_manifest else "- Page manifest: not provided; used filename/page heuristics\n")
        f.write(f"- Pages processed: {len(page_rows)}\n")
        f.write(f"- v3 boxes: {len(box_rows)}\n")
        f.write(f"- v4 parent regions checked: {len(region_rows)}\n")
        f.write(f"- v4 promoted/review-needed secondary line crops: {promoted_splits}\n")
        f.write(f"- Summary index rows: {len(summary_rows)}\n\n")

        f.write("## Page Hints\n\n")
        f.write("| page_hint | pages |\n")
        f.write("|---|---:|\n")
        for key, count in sorted(page_hint_counts.items()):
            f.write(f"| `{key}` | {count} |\n")

        f.write("\n## v3 Labels\n\n")
        f.write("| label | boxes |\n")
        f.write("|---|---:|\n")
        for key, count in sorted(label_counts.items()):
            f.write(f"| `{key}` | {count} |\n")

        f.write("\n## v4 Decisions\n\n")
        f.write("| decision | regions |\n")
        f.write("|---|---:|\n")
        for key, count in sorted(decision_counts.items()):
            f.write(f"| `{key}` | {count} |\n")

        f.write("\n## Final Buckets\n\n")
        f.write("| bucket | files |\n")
        f.write("|---|---:|\n")
        for key, count in sorted(bucket_counts.items()):
            f.write(f"| `{key}` | {count} |\n")

        f.write("\n## Review Entry Points\n\n")
        f.write("- Human visual review: `03_cut_before_after_review/`\n")
        f.write("- Training/annotation crop summary: `04_successful_crop_summary/`\n")
        f.write("- Page-type template for the next run: `page_manifest_template.csv`\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True, help="Folder of page images, a single image, or a PDF")
    parser.add_argument("--output-root", type=Path, required=True, help="Folder for all pipeline outputs")
    parser.add_argument(
        "--page-manifest",
        type=Path,
        help="Optional CSV with columns file,page_hint. Use this when image file names do not encode page type.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable. Defaults to the interpreter running this script.",
    )
    parser.add_argument("--pdf-dpi", type=int, default=220, help="PDF render DPI when --input is a PDF")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=20,
        help="Maximum PDF pages to render. Use 0 to render all pages.",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    output_root = args.output_root
    v3_root = output_root / "01_v3_routing"
    v4_root = output_root / "02_v4_secondary_split"
    visual_root = output_root / "03_cut_before_after_review"
    summary_root = output_root / "04_successful_crop_summary"
    validation_report = output_root / "crop_pipeline_validation.json"

    output_root.mkdir(parents=True, exist_ok=True)
    input_pages = prepare_input_pages(args.input, output_root, pdf_dpi=args.pdf_dpi, max_pages=args.max_pages)
    write_manifest_template(input_pages, output_root)

    v3_cmd = [
        args.python,
        str(script_dir / "line_segmentation_probe_v3.py"),
        "--input",
        str(input_pages),
        "--output",
        str(v3_root),
    ]
    if args.page_manifest:
        v3_cmd.extend(["--page-manifest", str(args.page_manifest)])

    run_step(v3_cmd)
    run_step(
        [
            args.python,
            str(script_dir / "line_segmentation_probe_v4.py"),
            "--input",
            str(input_pages),
            "--v3-summary",
            str(v3_root / "reports" / "hybrid_box_summary.csv"),
            "--output",
            str(v4_root),
        ]
    )
    run_step(
        [
            args.python,
            str(script_dir / "build_crop_visual_review.py"),
            "--input",
            str(input_pages),
            "--v3-root",
            str(v3_root),
            "--v4-root",
            str(v4_root),
            "--output",
            str(visual_root),
        ]
    )
    run_step(
        [
            args.python,
            str(script_dir / "build_successful_crop_summary.py"),
            "--v3-root",
            str(v3_root),
            "--v4-root",
            str(v4_root),
            "--output",
            str(summary_root),
        ]
    )
    run_step(
        [
            args.python,
            str(script_dir / "validate_outputs.py"),
            "--index",
            str(summary_root / "index.csv"),
            "--summary-root",
            str(summary_root),
            "--report",
            str(validation_report),
        ]
    )

    with (output_root / "README.md").open("w", encoding="utf-8") as f:
        f.write("# Book Crop Pipeline Output\n\n")
        f.write(f"Input: `{args.input}`\n\n")
        if input_pages != args.input:
            f.write(f"Rendered/copied page images: `{input_pages}`\n\n")
        if args.page_manifest:
            f.write(f"Page manifest: `{args.page_manifest}`\n\n")
        else:
            f.write("Page manifest: not provided. v3 used filename/page heuristics.\n\n")
        f.write("## Output Folders\n\n")
        f.write("| Folder | Purpose |\n")
        f.write("|---|---|\n")
        f.write("| `01_v3_routing/` | v3 page-level routing: primary lines, region fallbacks, ignore/special labels |\n")
        f.write("| `02_v4_secondary_split/` | v4 local secondary splitting for v3 region-fallback boxes |\n")
        f.write("| `03_cut_before_after_review/` | Minimal before/after visual review, one folder per page |\n")
        f.write("| `04_successful_crop_summary/` | OCR/annotation-oriented crop summary with index.csv |\n\n")
        f.write(f"Validation report: `{validation_report.name}`\n\n")
        f.write("Human review should start from `03_cut_before_after_review/`.\n")
        f.write("Training/annotation should start from `04_successful_crop_summary/`.\n")
        f.write("Run-level counts are in `run_summary.md`.\n")
        f.write("For a new book, copy/edit `page_manifest_template.csv` and rerun with `--page-manifest`.\n")

    write_run_summary(input_pages, output_root, args.page_manifest)

    print(f"\nDone. Pipeline outputs are in: {output_root}")


if __name__ == "__main__":
    main()
