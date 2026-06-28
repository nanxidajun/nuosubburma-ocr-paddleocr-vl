#!/usr/bin/env python3
"""Run the single page cutting flow with Paddle DocLayout.

The script turns page images or a PDF into OCR-ready units and keeps enough
metadata for downstream OCR, page text merging, audit, and optional
pronunciation.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageOps


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}
PDF_EXTS = {".pdf"}

ROUTE_ORDER = {
    "title": 0,
    "header": 1,
    "body": 2,
    "footnote": 3,
    "footer": 4,
    "page_number": 5,
}

ROUTE_LABEL_ZH = {
    "title": "标题",
    "header": "页眉",
    "body": "正文",
    "footnote": "脚注",
    "footer": "页脚",
    "page_number": "页码",
    "skip": "跳过",
}

LABEL_TO_ROUTE = {
    "doc_title": "title",
    "paragraph_title": "title",
    "title": "title",
    "table_title": "title",
    "text": "body",
    "content": "body",
    "aside_text": "body",
    "figure": "body",
    "chart": "body",
    "table": "body",
    "paragraph": "body",
    "formula": "body",
    "algorithm": "body",
    "number": "page_number",
    "page_number": "page_number",
    "footnote": "footnote",
    "header": "header",
    "page_header": "header",
    "footer": "footer",
    "page_footer": "footer",
}

SKIP_LABEL_PARTS = ("image", "seal", "stamp", "barcode", "qr")


@dataclass(frozen=True)
class LayoutBlock:
    page_id: str
    page_file: str
    index: int
    label: str
    route: str | None
    score: float | None
    bbox: tuple[int, int, int, int]

    @property
    def reading_order(self) -> str:
        x1, y1, _, _ = self.bbox
        return f"{ROUTE_ORDER.get(self.route or 'body', 9):02d}_{y1:06d}_{x1:06d}_{self.index:04d}"

    @property
    def crop_id(self) -> str:
        route = self.route or "skip"
        return f"{self.page_id}__doclayout_{self.index:03d}__{route}"

    @property
    def caption(self) -> str:
        score_text = "" if self.score is None else f" {self.score:.3f}"
        route_text = ROUTE_LABEL_ZH.get(self.route or "skip", self.route or "跳过")
        return f"{self.index:02d} {route_text} {self.label}{score_text}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cut page images into OCR-ready units with Paddle DocLayout.",
    )
    parser.add_argument("--input", type=Path, required=True, help="Folder of page images, a single image, or a PDF")
    parser.add_argument("--output-root", type=Path, required=True, help="Folder for page cutting outputs")
    parser.add_argument("--layout-model", default="PP-DocLayout_plus-L", help="Paddle DocLayout model name")
    parser.add_argument("--layout-threshold", type=float, default=0.25, help="DocLayout confidence threshold")
    parser.add_argument("--device", default=None, help="Optional Paddle device, for example gpu or cpu")
    parser.add_argument("--pdf-dpi", type=int, default=220, help="PDF render DPI when --input is a PDF")
    parser.add_argument("--max-pages", type=int, default=20, help="Maximum PDF pages to render. Use 0 for all pages")
    parser.add_argument("--max-image-side", type=int, default=2400, help="Resize pages whose long side is larger. Use 0 to keep original size")
    parser.add_argument("--page-manifest", type=Path, help="Optional page note CSV. Kept for batch tracking; DocLayout still decides blocks")
    return parser.parse_args()


def safe_stem(path: Path) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in path.stem)
    return cleaned.strip("_") or "input"


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def resize_for_processing(image: Image.Image, max_side: int) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    if max_side <= 0:
        return image
    w, h = image.size
    long_side = max(w, h)
    if long_side <= max_side:
        return image
    scale = max_side / long_side
    return image.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)


def save_page_copy(src: Path, dest: Path, max_side: int) -> None:
    image = Image.open(src)
    try:
        processed = resize_for_processing(image, max_side)
        processed.save(dest)
    finally:
        image.close()


def image_files(input_dir: Path) -> list[Path]:
    return sorted(path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTS)


def copy_image_folder(input_dir: Path, pages_dir: Path, max_side: int) -> list[Path]:
    pages: list[Path] = []
    for src in image_files(input_dir):
        dest = pages_dir / f"{safe_stem(src)}{src.suffix.lower()}"
        save_page_copy(src, dest, max_side)
        pages.append(dest)
    return pages


def copy_single_image(src: Path, pages_dir: Path, max_side: int) -> list[Path]:
    dest = pages_dir / f"{safe_stem(src)}_p001{src.suffix.lower()}"
    save_page_copy(src, dest, max_side)
    return [dest]


def render_pdf_to_pages(pdf_path: Path, pages_dir: Path, *, dpi: int, max_pages: int, max_side: int) -> list[Path]:
    tmp_prefix = pages_dir / f"{safe_stem(pdf_path)}_page"
    cmd = ["pdftoppm", "-png", "-r", str(dpi), "-f", "1"]
    if max_pages > 0:
        cmd.extend(["-l", str(max_pages)])
    cmd.extend([str(pdf_path), str(tmp_prefix)])

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError as exc:
        raise SystemExit("PDF input requires Poppler `pdftoppm`. Install poppler first.") from exc

    rendered = sorted(pages_dir.glob(f"{tmp_prefix.name}-*.png"))
    pages: list[Path] = []
    for idx, page in enumerate(rendered, start=1):
        dest = pages_dir / f"{safe_stem(pdf_path)}_p{idx:03d}.png"
        save_page_copy(page, dest, max_side)
        page.unlink(missing_ok=True)
        pages.append(dest)
    if not pages:
        raise SystemExit(f"No pages were rendered from PDF: {pdf_path}")
    return pages


def prepare_input_pages(input_path: Path, output_root: Path, *, pdf_dpi: int, max_pages: int, max_side: int) -> list[Path]:
    if not input_path.exists():
        raise SystemExit(f"Input does not exist: {input_path}")

    pages_dir = output_root / "00_input_pages"
    reset_dir(pages_dir)

    if input_path.is_dir():
        pages = copy_image_folder(input_path, pages_dir, max_side)
    elif input_path.suffix.lower() in IMAGE_EXTS:
        pages = copy_single_image(input_path, pages_dir, max_side)
    elif input_path.suffix.lower() in PDF_EXTS:
        pages = render_pdf_to_pages(input_path, pages_dir, dpi=pdf_dpi, max_pages=max_pages, max_side=max_side)
    else:
        allowed = ", ".join(sorted(IMAGE_EXTS | PDF_EXTS))
        raise SystemExit(f"Unsupported input type `{input_path.suffix}`. Expected a folder or one of: {allowed}")

    if not pages:
        raise SystemExit(f"No page images found in input: {input_path}")
    return pages


def load_layout_model(model_name: str, threshold: float, device: str | None):
    try:
        from paddleocr import LayoutDetection
    except Exception as exc:
        raise SystemExit("Missing PaddleOCR LayoutDetection. Install dependencies with `python -m pip install -r requirements.txt`.") from exc

    kwargs: dict[str, Any] = {"model_name": model_name, "threshold": threshold}
    if device:
        kwargs["device"] = device
    return LayoutDetection(**kwargs)


def result_to_dict(res: Any) -> dict[str, Any]:
    if hasattr(res, "json"):
        data = res.json
        return data() if callable(data) else data
    if hasattr(res, "to_json"):
        return res.to_json()
    if isinstance(res, dict):
        return res
    return {"repr": repr(res)}


def iter_raw_blocks(data: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for key in ("boxes", "layout_det_res", "layout_result", "res", "result"):
        val = data.get(key)
        if isinstance(val, list):
            candidates.extend(x for x in val if isinstance(x, dict))
    if not candidates:
        for val in data.values():
            if isinstance(val, list):
                candidates.extend(x for x in val if isinstance(x, dict))
    return candidates


def parse_bbox(value: Any) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    raw = value
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None
    if isinstance(raw, list) and len(raw) == 4 and all(isinstance(x, (int, float)) for x in raw):
        x1, y1, x2, y2 = [int(round(float(v))) for v in raw]
    elif isinstance(raw, list) and raw and isinstance(raw[0], (list, tuple)):
        xs = [float(point[0]) for point in raw if len(point) >= 2]
        ys = [float(point[1]) for point in raw if len(point) >= 2]
        if not xs or not ys:
            return None
        x1, y1, x2, y2 = [int(round(v)) for v in (min(xs), min(ys), max(xs), max(ys))]
    else:
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def route_for_label(label: str) -> str | None:
    normalized = str(label or "").strip().lower()
    if not normalized:
        return None
    if any(part in normalized for part in SKIP_LABEL_PARTS):
        return None
    return LABEL_TO_ROUTE.get(normalized, "body")


def clip_bbox(bbox: tuple[int, int, int, int], width: int, height: int, pad: int = 6) -> tuple[int, int, int, int] | None:
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(width - 1, x1 - pad))
    y1 = max(0, min(height - 1, y1 - pad))
    x2 = max(1, min(width, x2 + pad))
    y2 = max(1, min(height, y2 + pad))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def detect_page_blocks(model: Any, page_path: Path, layout_root: Path) -> tuple[list[LayoutBlock], list[dict[str, Any]]]:
    page_id = page_path.stem
    outputs = model.predict(str(page_path))
    raw_pages: list[dict[str, Any]] = []
    blocks: list[LayoutBlock] = []

    for res in outputs:
        data = result_to_dict(res)
        raw_pages.append(data)
        for raw in iter_raw_blocks(data):
            label = str(
                raw.get("label")
                or raw.get("cls")
                or raw.get("category")
                or raw.get("class_name")
                or raw.get("block_type")
                or "unknown"
            )
            bbox = parse_bbox(raw.get("coordinate") or raw.get("bbox") or raw.get("box") or raw.get("poly"))
            if bbox is None:
                continue
            score_raw = raw.get("score") or raw.get("confidence")
            try:
                score = float(score_raw) if score_raw is not None and score_raw != "" else None
            except (TypeError, ValueError):
                score = None
            blocks.append(
                LayoutBlock(
                    page_id=page_id,
                    page_file=page_path.name,
                    index=len(blocks) + 1,
                    label=label,
                    route=route_for_label(label),
                    score=score,
                    bbox=bbox,
                )
            )

    raw_dir = layout_root / "raw_json"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / f"{page_id}.json").write_text(json.dumps(raw_pages, ensure_ascii=False, indent=2), encoding="utf-8")

    with Image.open(page_path) as image:
        width, height = image.size
    if not blocks:
        blocks.append(
            LayoutBlock(
                page_id=page_id,
                page_file=page_path.name,
                index=1,
                label="fallback_full_page",
                route="body",
                score=None,
                bbox=(0, 0, width, height),
            )
        )

    return sorted(blocks, key=lambda item: (item.bbox[1], item.bbox[0], item.index)), raw_pages


def draw_review_page(page_path: Path, blocks: list[LayoutBlock], review_dir: Path, crop_paths: list[Path]) -> None:
    review_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(page_path, review_dir / f"00_original{page_path.suffix.lower()}")

    image = Image.open(page_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    colors = {
        "title": "#d97706",
        "header": "#2563eb",
        "body": "#0f766e",
        "footnote": "#7c3aed",
        "footer": "#2563eb",
        "page_number": "#dc2626",
        None: "#6b7280",
    }
    for block in blocks:
        color = colors.get(block.route, "#111827")
        draw.rectangle(block.bbox, outline=color, width=3)
        draw.text((block.bbox[0] + 4, block.bbox[1] + 4), block.caption, fill=color)
    image.save(review_dir / "01_doclayout_boxes.png")
    image.close()

    if not crop_paths:
        return
    thumbs: list[Image.Image] = []
    try:
        for crop_path in crop_paths[:40]:
            thumb = Image.open(crop_path).convert("RGB")
            thumb.thumbnail((260, 120))
            canvas = Image.new("RGB", (280, 140), "white")
            canvas.paste(thumb, (10, 10))
            thumbs.append(canvas)
            thumb.close()
        cols = 2
        rows = (len(thumbs) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * 280, rows * 140), "#f8f5ef")
        for idx, thumb in enumerate(thumbs):
            sheet.paste(thumb, ((idx % cols) * 280, (idx // cols) * 140))
        sheet.save(review_dir / "02_ocr_units_sheet.png")
        sheet.close()
    finally:
        for thumb in thumbs:
            thumb.close()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def build_outputs(pages: list[Path], output_root: Path, model: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    layout_root = output_root / "01_doclayout"
    units_root = output_root / "02_ocr_units"
    review_root = output_root / "03_cut_review"
    reset_dir(layout_root)
    reset_dir(units_root)
    reset_dir(review_root)

    index_rows: list[dict[str, Any]] = []
    layout_rows: list[dict[str, Any]] = []
    page_rows: list[dict[str, Any]] = []

    for page_path in pages:
        print(f"[layout] {page_path.name}", flush=True)
        blocks, _ = detect_page_blocks(model, page_path, layout_root)
        page_rows.append({"page_id": page_path.stem, "page_file": page_path.name, "layout_blocks": len(blocks)})

        crop_paths: list[Path] = []
        page_image = Image.open(page_path).convert("RGB")
        try:
            for block in blocks:
                layout_rows.append(
                    {
                        "page_id": block.page_id,
                        "page_file": block.page_file,
                        "index": block.index,
                        "label": block.label,
                        "route": block.route or "skip",
                        "score": "" if block.score is None else block.score,
                        "bbox": json.dumps(list(block.bbox), ensure_ascii=False),
                        "reading_order": block.reading_order,
                    }
                )
                if block.route is None:
                    continue
                crop_box = clip_bbox(block.bbox, page_image.width, page_image.height)
                if crop_box is None:
                    continue
                crop = page_image.crop(crop_box)
                route = block.route or "body"
                rel_path = Path("images") / route / block.page_id / f"{block.crop_id}.png"
                crop_path = units_root / rel_path
                crop_path.parent.mkdir(parents=True, exist_ok=True)
                crop.save(crop_path)
                crop.close()
                crop_paths.append(crop_path)

                index_rows.append(
                    {
                        "crop_id": block.crop_id,
                        "page_id": block.page_id,
                        "page_file": block.page_file,
                        "bucket": "ocr_units",
                        "sub_bucket": route,
                        "role": route,
                        "source_stage": "doclayout",
                        "source_box": block.index,
                        "part_index": 0,
                        "label_or_decision": block.label,
                        "ocr_ready": "1",
                        "is_line_ocr_ready": "1",
                        "summary_path": str(rel_path),
                        "original_path": str(page_path),
                        "reading_order": block.reading_order,
                        "bbox": json.dumps(list(block.bbox), ensure_ascii=False),
                        "crop_bbox": json.dumps(list(crop_box), ensure_ascii=False),
                        "score": "" if block.score is None else block.score,
                        "note": "Paddle DocLayout text block; ready for OCR",
                    }
                )
        finally:
            page_image.close()

        draw_review_page(page_path, blocks, review_root / page_path.stem, crop_paths)

    write_csv(layout_root / "layout_block_summary.csv", layout_rows)
    write_csv(units_root / "index.csv", sorted(index_rows, key=lambda row: row["reading_order"]))
    write_jsonl(units_root / "ocr_units.jsonl", sorted(index_rows, key=lambda row: row["reading_order"]))

    errors: list[str] = []
    crop_ids = [row["crop_id"] for row in index_rows]
    if len(crop_ids) != len(set(crop_ids)):
        errors.append("duplicate crop_id found")
    for row in index_rows:
        if not (units_root / row["summary_path"]).exists():
            errors.append(f"missing crop file: {row['summary_path']}")
            break

    validation = {
        "ok": not errors,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "pages": len(page_rows),
        "layout_blocks": len(layout_rows),
        "ocr_units": len(index_rows),
        "errors": errors,
    }
    (output_root / "page_processing_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    return page_rows, index_rows, validation


def write_run_docs(args: argparse.Namespace, pages: list[Path], page_rows: list[dict[str, Any]], index_rows: list[dict[str, Any]], validation: dict[str, Any]) -> None:
    output_root = args.output_root
    route_counts: dict[str, int] = {}
    for row in index_rows:
        route = str(row.get("role") or "body")
        route_counts[route] = route_counts.get(route, 0) + 1

    with (output_root / "run_summary.md").open("w", encoding="utf-8") as f:
        f.write("# Page Cutting Run Summary\n\n")
        f.write(f"- Input: `{args.input}`\n")
        f.write(f"- DocLayout model: `{args.layout_model}`\n")
        f.write(f"- Pages processed: {len(pages)}\n")
        f.write(f"- OCR units: {len(index_rows)}\n")
        f.write(f"- Validation: {'ok' if validation.get('ok') else 'failed'}\n\n")
        f.write("## OCR Unit Routes\n\n")
        f.write("| route | units |\n")
        f.write("|---|---:|\n")
        for route, count in sorted(route_counts.items()):
            f.write(f"| `{route}` | {count} |\n")
        f.write("\n## Review Entry Points\n\n")
        f.write("- Visual review: `03_cut_review/`\n")
        f.write("- OCR unit index: `02_ocr_units/index.csv`\n")
        f.write("- Validation report: `page_processing_validation.json`\n")

    with (output_root / "README.md").open("w", encoding="utf-8") as f:
        f.write("# Page Cutting Output\n\n")
        f.write("This folder was generated by the single Paddle DocLayout page cutting flow.\n\n")
        f.write("| Folder/File | Purpose |\n")
        f.write("|---|---|\n")
        f.write("| `00_input_pages/` | Page images used by the run |\n")
        f.write("| `01_doclayout/` | Raw DocLayout results and block summary |\n")
        f.write("| `02_ocr_units/index.csv` | OCR-ready units and reading order |\n")
        f.write("| `03_cut_review/` | Visual review for each page |\n")
        f.write("| `page_processing_validation.json` | Basic output validation |\n")
        f.write("| `run_summary.md` | Run-level counts |\n\n")
        f.write("Start manual review from `03_cut_review/`.\n")
        f.write("Downstream OCR should read `02_ocr_units/index.csv`.\n")


def main() -> None:
    args = parse_args()
    args.input = args.input.expanduser().resolve()
    args.output_root = args.output_root.expanduser().resolve()
    args.output_root.mkdir(parents=True, exist_ok=True)

    pages = prepare_input_pages(
        args.input,
        args.output_root,
        pdf_dpi=args.pdf_dpi,
        max_pages=args.max_pages,
        max_side=args.max_image_side,
    )
    model = load_layout_model(args.layout_model, args.layout_threshold, args.device)
    page_rows, index_rows, validation = build_outputs(pages, args.output_root, model)
    write_run_docs(args, pages, page_rows, index_rows, validation)

    if not validation.get("ok"):
        raise SystemExit("Page cutting validation failed. Inspect page_processing_validation.json.")
    print(f"\nDone. Page cutting outputs are in: {args.output_root}")


if __name__ == "__main__":
    main()
