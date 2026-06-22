#!/usr/bin/env python3
"""Build a minimal visual before/after review folder for crop segmentation.

This is intentionally human-facing and small:

one folder per page, with original image, v3 classified boxes, v3 contact sheet,
and v4 secondary split overlays/contact sheets when available.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}


def copy_file(src: Path, dest: Path) -> bool:
    if not src.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("page_images"))
    parser.add_argument("--v3-root", type=Path, default=Path("crop_pipeline_output/01_v3_routing"))
    parser.add_argument("--v4-root", type=Path, default=Path("crop_pipeline_output/02_v4_secondary_split"))
    parser.add_argument("--output", type=Path, default=Path("crop_pipeline_output/03_cut_before_after_review"))
    args = parser.parse_args()

    images = sorted(path for path in args.input.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTS)
    output_rows: list[tuple[str, int]] = []

    for order, image in enumerate(images, start=1):
        stem = image.stem
        page_dir = args.output / f"{order:02d}_{stem}"
        copied = 0

        if copy_file(image, page_dir / f"00_original{image.suffix}"):
            copied += 1
        if copy_file(
            args.v3_root / "visualizations" / f"{stem}__classified_boxes.png",
            page_dir / "01_v3_boxes.png",
        ):
            copied += 1
        if copy_file(
            args.v3_root / "contact_sheets" / f"{stem}__sheet.png",
            page_dir / "02_v3_cut_sheet.png",
        ):
            copied += 1
        if copy_file(
            args.v4_root / "visualizations" / f"{stem}__v4_secondary.png",
            page_dir / "03_v4_secondary_boxes.png",
        ):
            copied += 1

        v4_sheet_dir = args.v4_root / "secondary_contact_sheets" / stem
        if v4_sheet_dir.exists():
            for sheet in sorted(v4_sheet_dir.glob("*.png")):
                if copy_file(sheet, page_dir / "04_v4_secondary_sheets" / sheet.name):
                    copied += 1

        output_rows.append((f"{order:02d}_{stem}", copied))

    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "README.md").open("w", encoding="utf-8") as f:
        f.write("# 切图前后对照\n\n")
        f.write("这个目录只用于直观看切前切后，不放碎图数据集。\n\n")
        f.write("每张页面一个文件夹：\n\n")
        f.write("| 文件 | 含义 |\n")
        f.write("|---|---|\n")
        f.write("| `00_original.*` | 原图 |\n")
        f.write("| `01_v3_boxes.png` | v3 粗分流框 |\n")
        f.write("| `02_v3_cut_sheet.png` | v3 一次切图拼接 |\n")
        f.write("| `03_v4_secondary_boxes.png` | v4 对大块二次切分的位置图，仅有需要二次切分的页才有 |\n")
        f.write("| `04_v4_secondary_sheets/` | v4 二次切分后的拼接图，仅有需要二次切分的页才有 |\n\n")
        f.write("## 页面列表\n\n")
        f.write("| 页面 | 文件数 |\n")
        f.write("|---|---:|\n")
        for page, count in output_rows:
            f.write(f"| `{page}` | {count} |\n")

    print(f"Done. Wrote visual review folder to {args.output}")


if __name__ == "__main__":
    main()
