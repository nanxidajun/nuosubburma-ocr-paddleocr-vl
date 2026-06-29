#!/usr/bin/env python3
"""本地整页 demo：页面切割、OCR 单元识别、页面文本合并、结构化输出、异常审计和可选注音。"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from page_processing.assemble_pages import assemble_ocr_results
from page_processing.structure_pages import structure_pages

DEFAULT_MODEL = REPO_ROOT / "models" / "NuosuBburma-OCR"
DEFAULT_INPUT = REPO_ROOT / "demo" / "sample_images" / "screen_page.jpg"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "outputs" / "demo_page_workflow"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="本地整页 demo：页面切割 -> OCR 单元识别 -> 页面文本合并 -> 结构化输出")
    parser.add_argument("--input", default=None, help="整页图片、PDF 或图片目录，默认 demo/sample_images/screen_page.jpg")
    parser.add_argument("--model", default=None, help="模型目录，默认 models/NuosuBburma-OCR")
    parser.add_argument("--output-root", default=None, help="输出目录，默认 outputs/demo_page_workflow")
    parser.add_argument("--prompt", default="<image>OCR:", help="OCR 提示词，默认 <image>OCR:")
    parser.add_argument("--max-new-tokens", type=int, default=1024, help="每个 OCR 单元的最大生成 token 数，默认 1024")
    parser.add_argument("--max-image-side", type=int, default=2400, help="页面切割前图片长边压缩上限，默认 2400；设为 0 保留原图")
    parser.add_argument("--device", default="gpu", help="Paddle 设备，默认 gpu")
    parser.add_argument("--python", default=sys.executable, help="子步骤使用的 Python 解释器")
    parser.add_argument("--pdf-dpi", type=int, default=220, help="PDF 渲染 DPI，默认 220")
    parser.add_argument("--max-pages", type=int, default=20, help="PDF 最多渲染页数，0 表示全部")
    parser.add_argument("--page-manifest", type=Path, help="可选：页面说明 CSV，仅用于批量追踪")
    parser.add_argument("--page-root", type=Path, help="复用已有页面切割输出，跳过页面切割")
    parser.add_argument("--ocr-results", type=Path, help="复用已有 OCR 单元结果，跳过 OCR 推理")
    parser.add_argument("--limit", type=int, default=0, help="可选：只识别前 N 个 OCR 单元，便于快速检查")
    parser.add_argument("--with-pronunciation", action="store_true", help="页面文本生成后添加注音字段")
    parser.add_argument("--keep-empty-units", action="store_true", help="页面文本中保留空 OCR 单元")
    return parser.parse_args()


def resolve_path(path_text: str | None, default_path: Path) -> Path:
    if not path_text:
        return default_path
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def run_step(cmd: list[str]) -> None:
    print("\n$", " ".join(str(part) for part in cmd), flush=True)
    subprocess.run(cmd, check=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_index(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def is_ocr_unit(row: dict[str, str]) -> bool:
    return row.get("ocr_ready") == "1" or row.get("is_line_ocr_ready") == "1" or row.get("bucket") == "ocr_units"


def unit_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else row
    reading_order = str(meta.get("reading_order") or "")
    if reading_order:
        return (0, reading_order)
    return (
        1,
        str(meta.get("page_id") or ""),
        as_int(meta.get("source_box")),
        as_int(meta.get("part_index")),
        str(meta.get("crop_id") or row.get("id") or ""),
    )


def ensure_model_exists(model_path: Path) -> None:
    if not model_path.exists():
        raise SystemExit(
            f"找不到模型目录：{model_path}\n\n"
            "请先下载模型：\n"
            "hf download nanxidajun/NuosuBburma-OCR --repo-type model --local-dir models/NuosuBburma-OCR"
        )
    if not (model_path / "config.json").exists():
        raise SystemExit(f"模型目录缺少 config.json：{model_path}")


def load_runtime():
    try:
        import paddle
        from PIL import Image
        from paddleformers.generation import GenerationConfig
        from paddleformers.transformers import AutoModelForConditionalGeneration, AutoProcessor
    except ImportError as exc:
        raise SystemExit(
            "缺少 OCR 推理依赖：{}\n\n"
            "请先安装依赖：\n"
            "python -m pip install -r requirements.txt".format(exc.name)
        ) from exc
    return paddle, Image, GenerationConfig, AutoModelForConditionalGeneration, AutoProcessor


def load_model_and_processor(model_path: Path, device: str):
    paddle, Image, GenerationConfig, AutoModelForConditionalGeneration, AutoProcessor = load_runtime()
    paddle.set_device(device)
    processor = AutoProcessor.from_pretrained(str(model_path))
    model = AutoModelForConditionalGeneration.from_pretrained(str(model_path), convert_from_hf=True)
    if hasattr(model, "config"):
        model.config._attn_implementation = "flashmask"
    if hasattr(model, "visual") and hasattr(model.visual, "config"):
        model.visual.config._attn_implementation = "flashmask"
    model.eval()
    generation_config = GenerationConfig(
        do_sample=False,
        bos_token_id=1,
        eos_token_id=2,
        pad_token_id=0,
        use_cache=True,
    )
    return paddle, Image, model, processor, generation_config


def generate_response(paddle, Image, model, processor, generation_config, image_path: Path, prompt: str, max_new_tokens: int) -> str:
    image = Image.open(image_path).convert("RGB")
    query = prompt.replace("<image>", "")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": query},
            ],
        }
    ]
    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pd",
    )
    with paddle.no_grad():
        outputs = model.generate(
            **inputs,
            generation_config=generation_config,
            max_new_tokens=max_new_tokens,
        )
    output_ids = outputs[0].tolist()[0]
    return processor.decode(output_ids, skip_special_tokens=True).strip()


def run_page_processing(args: argparse.Namespace, input_path: Path, page_root: Path) -> None:
    cmd = [
        args.python,
        str(REPO_ROOT / "page_processing" / "run.py"),
        "--input",
        str(input_path),
        "--output-root",
        str(page_root),
        "--pdf-dpi",
        str(args.pdf_dpi),
        "--max-pages",
        str(args.max_pages),
        "--max-image-side",
        str(args.max_image_side),
    ]
    if args.page_manifest:
        cmd.extend(["--page-manifest", str(args.page_manifest)])
    if args.device:
        cmd.extend(["--device", args.device])
    run_step(cmd)


def check_page_cutting(page_root: Path) -> None:
    report_path = page_root / "page_processing_validation.json"
    if not report_path.exists():
        raise SystemExit(f"Missing page cutting validation report: {report_path}")
    report = read_json(report_path)
    if not report.get("ok"):
        print(json.dumps(report, ensure_ascii=False, indent=2))
        raise SystemExit("页面切割校验失败。请先查看 03_cut_review，再继续 OCR。")


def run_ocr_units(
    *,
    index_path: Path,
    summary_root: Path,
    output_path: Path,
    model_path: Path,
    device: str,
    prompt: str,
    max_new_tokens: int,
    limit: int,
) -> None:
    ensure_model_exists(model_path)
    rows = sorted([row for row in read_index(index_path) if is_ocr_unit(row)], key=unit_sort_key)
    if limit > 0:
        rows = rows[:limit]
    if not rows:
        raise SystemExit(f"No OCR units found in {index_path}")

    paddle, Image, model, processor, generation_config = load_model_and_processor(model_path, device)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for pos, row in enumerate(rows, start=1):
            image_path = summary_root / row["summary_path"]
            status = "ok"
            answer = ""
            error = ""
            try:
                answer = generate_response(
                    paddle,
                    Image,
                    model,
                    processor,
                    generation_config,
                    image_path,
                    prompt,
                    max_new_tokens,
                )
            except Exception as exc:  # keep demo audit useful when a single crop fails
                status = "error"
                error = str(exc)
            out = {
                "id": row.get("crop_id") or image_path.stem,
                "image": str(image_path),
                "answer": answer,
                "status": status,
                "error": error,
                "position": pos,
                "meta": row,
            }
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
            print(f"[{pos}/{len(rows)}] {status} {out['id']}", flush=True)


def maybe_add_pronunciation(args: argparse.Namespace, submission_jsonl: Path, page_text_dir: Path) -> Path | None:
    if not args.with_pronunciation:
        return None
    output_path = page_text_dir / "submission_pages_pronounced.jsonl"
    run_step(
        [
            args.python,
            str(REPO_ROOT / "postprocess" / "add_nuosu_pronunciation.py"),
            "--input",
            str(submission_jsonl),
            "--field",
            "text",
            "--output",
            str(output_path),
        ]
    )
    return output_path


def export_page_structure(ocr_results: Path, structure_dir: Path) -> dict[str, str]:
    outputs = structure_pages(
        ocr_results.resolve(),
        structure_dir.resolve(),
        input_kind="ocr_units",
        out_prefix="structured_pages",
    )
    return {key: str(value) for key, value in outputs.__dict__.items()}


def main() -> None:
    args = parse_args()
    input_path = resolve_path(args.input, DEFAULT_INPUT)
    model_path = resolve_path(args.model, DEFAULT_MODEL)
    output_root = resolve_path(args.output_root, DEFAULT_OUTPUT_ROOT)

    page_root = args.page_root.resolve() if args.page_root else output_root / "01_page_cutting"
    ocr_dir = output_root / "02_ocr_units"
    page_text_dir = output_root / "03_page_text"
    page_structure_dir = output_root / "04_page_structure"
    ocr_results = args.ocr_results.resolve() if args.ocr_results else ocr_dir / "ocr_units_results.jsonl"
    summary_root = page_root / "02_ocr_units"
    index_path = summary_root / "index.csv"

    output_root.mkdir(parents=True, exist_ok=True)

    if args.page_root:
        print(f"Using existing page cutting root: {page_root}")
    else:
        run_page_processing(args, input_path, page_root)

    check_page_cutting(page_root)

    if args.ocr_results:
        print(f"Using existing OCR results: {ocr_results}")
    else:
        run_ocr_units(
            index_path=index_path,
            summary_root=summary_root,
            output_path=ocr_results,
            model_path=model_path,
            device=args.device,
            prompt=args.prompt,
            max_new_tokens=args.max_new_tokens,
            limit=args.limit,
        )

    outputs = assemble_ocr_results(
        ocr_results,
        page_text_dir,
        image_root=summary_root,
        keep_empty_units=args.keep_empty_units,
        max_image_side=args.max_image_side,
    ).as_dict()
    structure_outputs = export_page_structure(ocr_results, page_structure_dir)
    pronounced = maybe_add_pronunciation(args, outputs["submission_jsonl"], page_text_dir)

    manifest = {
        "input": str(input_path),
        "model": str(model_path),
        "output_root": str(output_root),
        "page_cutting_root": str(page_root),
        "max_image_side": args.max_image_side,
        "ocr_results": str(ocr_results),
        "page_text_outputs": {key: str(value) for key, value in outputs.items()},
        "page_structure_outputs": structure_outputs,
        "pronunciation_output": str(pronounced) if pronounced else "",
    }
    manifest_path = output_root / "workflow_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nDone. Page demo outputs:")
    print(json.dumps({**manifest, "workflow_manifest": str(manifest_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
