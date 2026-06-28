#!/usr/bin/env python3
"""本地整页 demo：页面切割、OCR 单元识别、页面文本合并、异常审计和可选注音。"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import json
import mimetypes
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = REPO_ROOT / "models" / "NuosuBburma-OCR"
DEFAULT_INPUT = REPO_ROOT / "demo" / "sample_images" / "screen_page.jpg"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "outputs" / "demo_page_workflow"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="本地整页 demo：页面切割 -> OCR 单元识别 -> 页面文本合并")
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


def image_data_uri(path_text: str) -> str:
    path = Path(path_text)
    if not path.exists() or not path.is_file():
        return ""
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


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


def route_for(meta: dict[str, Any]) -> str:
    role = str(meta.get("role") or "").lower()
    label = str(meta.get("label_or_decision") or meta.get("sub_bucket") or "").lower()
    note = str(meta.get("note") or "").lower()
    combined = " ".join([role, label, note])
    if "page_number" in combined:
        return "page_number"
    if "header" in combined:
        return "header"
    if "footer" in combined:
        return "footer"
    if "title" in combined:
        return "title"
    if role == "region_keep" or "region" in combined:
        return "region"
    return "body"


def clean_replacement_chars(text: str) -> tuple[str, int, bool]:
    replacement_count = text.count("�")
    if not replacement_count:
        return text, 0, False
    mostly_replacement = replacement_count >= max(8, int(len(text) * 0.8))
    if mostly_replacement:
        return "", replacement_count, True
    return text.replace("�", ""), replacement_count, False


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


def merge_page_text(ocr_results_path: Path, page_text_dir: Path, keep_empty_units: bool, max_image_side: int) -> dict[str, Path]:
    rows = sorted(read_jsonl(ocr_results_path), key=unit_sort_key)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    route_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    replacement_rows: list[dict[str, Any]] = []
    removed_replacement_chars = 0

    for row in rows:
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        page_id = str(meta.get("page_id") or "unknown_page")
        raw_text = str(row.get("answer") or "").strip()
        clean_text, replacement_count, cleared = clean_replacement_chars(raw_text)
        removed_replacement_chars += replacement_count
        route = route_for(meta)
        route_counts[route] += 1
        status = str(row.get("status") or "ok")
        status_counts[status] += 1

        if replacement_count:
            replacement_rows.append(
                {
                    "id": row.get("id", ""),
                    "page_id": page_id,
                    "replacement_chars": replacement_count,
                    "cleared_unit": cleared,
                }
            )

        unit = {
            "id": row.get("id", ""),
            "page_id": page_id,
            "page_file": meta.get("page_file", ""),
            "route": route,
            "status": status,
            "image": row.get("image") or (row.get("images") or [""])[0],
            "source_box": meta.get("source_box", ""),
            "part_index": meta.get("part_index", ""),
            "reading_order": meta.get("reading_order", ""),
            "raw_text": raw_text,
            "text": clean_text,
            "replacement_chars": replacement_count,
        }
        grouped[page_id].append(unit)

    pages: list[dict[str, Any]] = []
    page_audit: list[dict[str, Any]] = []
    official_rows: list[dict[str, str]] = []

    for page_id, units in sorted(grouped.items()):
        units = sorted(units, key=unit_sort_key)
        text = "\n".join(unit["text"] for unit in units if keep_empty_units or str(unit.get("text") or "").strip())
        page_file = next((str(unit.get("page_file") or "") for unit in units if unit.get("page_file")), "")
        page_route_counts = Counter(str(unit.get("route") or "") for unit in units)
        page = {
            "page_id": page_id,
            "page_file": page_file,
            "text": text,
            "ocr_units": units,
            "routes": dict(sorted(page_route_counts.items())),
        }
        pages.append(page)
        official_rows.append({"image_id": page_id, "prediction": text})
        page_audit.append(
            {
                "page_id": page_id,
                "page_file": page_file,
                "char_count": len(text),
                "line_count": len([line for line in text.splitlines() if line.strip()]),
                "ocr_units": len(units),
                "routes": json.dumps(dict(sorted(page_route_counts.items())), ensure_ascii=False),
                "empty": not bool(text.strip()),
            }
        )

    text_groups: dict[str, list[str]] = defaultdict(list)
    for page in pages:
        text = str(page.get("text") or "").strip()
        if text:
            text_groups[text].append(str(page.get("page_id") or ""))
    duplicate_groups = [ids for ids in text_groups.values() if len(ids) > 1]

    page_text_dir.mkdir(parents=True, exist_ok=True)
    submission_jsonl = page_text_dir / "submission_pages.jsonl"
    official_jsonl = page_text_dir / "official_submission.jsonl"
    official_csv = page_text_dir / "official_submission.csv"
    page_audit_csv = page_text_dir / "page_audit.csv"
    audit_summary_json = page_text_dir / "audit_summary.json"
    submission_md = page_text_dir / "submission_pages.md"
    submission_html = page_text_dir / "submission_pages.html"

    write_jsonl(submission_jsonl, pages)
    write_jsonl(official_jsonl, official_rows)
    write_csv(official_csv, official_rows)
    write_csv(page_audit_csv, page_audit)
    write_markdown(submission_md, pages)

    audit_summary = {
        "pages": len(pages),
        "official_rows": len(official_rows),
        "ocr_units": len(rows),
        "ocr_status": dict(sorted(status_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "replacement_char_rows": replacement_rows,
        "removed_replacement_chars": removed_replacement_chars,
        "final_contains_replacement_char": any("�" in str(page.get("text") or "") for page in pages),
        "empty_pages": [row["page_id"] for row in page_audit if row["empty"]],
        "duplicate_page_text_groups": duplicate_groups,
        "avg_chars_per_page": sum(row["char_count"] for row in page_audit) / max(len(page_audit), 1),
        "avg_lines_per_page": sum(row["line_count"] for row in page_audit) / max(len(page_audit), 1),
    }
    audit_summary_json.write_text(json.dumps(audit_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_html(submission_html, pages, audit_summary, max_image_side)

    return {
        "submission_jsonl": submission_jsonl,
        "official_jsonl": official_jsonl,
        "official_csv": official_csv,
        "page_audit_csv": page_audit_csv,
        "audit_summary_json": audit_summary_json,
        "submission_md": submission_md,
        "submission_html": submission_html,
    }


def write_markdown(path: Path, pages: list[dict[str, Any]]) -> None:
    lines = ["# 本地整页 OCR demo 结果", ""]
    for page in pages:
        lines.extend([f"## {page['page_id']}", "", str(page.get("text") or ""), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_html(path: Path, pages: list[dict[str, Any]], audit: dict[str, Any], max_image_side: int) -> None:
    page_cards = []
    for page in pages:
        unit_cards = []
        for unit in page.get("ocr_units", []):
            img_src = image_data_uri(str(unit.get("image") or ""))
            image_html = (
                f'<img src="{img_src}" alt="OCR unit">'
                if img_src
                else '<div class="missing-image">OCR 单元图片未找到</div>'
            )
            status = html.escape(str(unit.get("status") or ""))
            route = html.escape(str(unit.get("route") or ""))
            reading_order = html.escape(str(unit.get("reading_order") or ""))
            text = html.escape(str(unit.get("text") or unit.get("raw_text") or ""))
            unit_cards.append(
                f"""
<article class="unit">
  <div class="unit-image">{image_html}</div>
  <div class="unit-body">
    <p class="unit-meta">状态：{status or "n/a"} · 类型：{route or "n/a"} · 顺序：{reading_order or "n/a"}</p>
    <pre>{text}</pre>
  </div>
</article>
"""
            )

        page_cards.append(
            f"""
<article class="page">
  <h2>页面：{html.escape(str(page.get("page_id") or ""))}</h2>
  <p class="page-meta">文件：{html.escape(str(page.get("page_file") or ""))} · OCR 单元：{len(page.get("ocr_units", []))}</p>
  <section class="result-card">
    <h3>页面文本</h3>
    <pre>{html.escape(str(page.get("text") or ""))}</pre>
  </section>
  <section class="units">
    <h3>OCR 单元复核</h3>
    {''.join(unit_cards)}
  </section>
</article>
"""
        )

    route_text = ", ".join(f"{html.escape(str(k))}: {v}" for k, v in audit.get("route_counts", {}).items())
    status_text = ", ".join(f"{html.escape(str(k))}: {v}" for k, v in audit.get("ocr_status", {}).items())
    empty_pages = ", ".join(html.escape(str(x)) for x in audit.get("empty_pages", [])) or "无"
    duplicate_groups = audit.get("duplicate_page_text_groups", [])
    duplicate_text = html.escape(json.dumps(duplicate_groups, ensure_ascii=False)) if duplicate_groups else "无"
    size_note = (
        f"输入页面超过长边限制 {max_image_side} 时，会先等比例压缩后再进入页面切割和 OCR；原始文件不会被修改。"
        if max_image_side > 0
        else "当前未启用长边压缩限制。"
    )
    doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NuosuBburma OCR 本地整页 demo</title>
  <style>
    :root {{
      --bg: #f4ead8;
      --ink: #211d18;
      --muted: #706657;
      --card: #fffaf1;
      --line: #dacbb5;
      --accent: #8a4329;
      --accent-soft: #f0d7bf;
    }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at 10% 0%, #fff8de 0, transparent 34%),
        linear-gradient(135deg, #f8f1df, var(--bg));
      color: var(--ink);
      font-family: "Songti SC", "Noto Serif CJK SC", serif;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 34px 18px 54px;
    }}
    header {{
      margin-bottom: 18px;
    }}
    h1 {{ margin: 0 0 8px; font-size: 31px; letter-spacing: 0.02em; }}
    .sub {{ margin: 0; color: var(--muted); line-height: 1.7; }}
    .audit, .page, .result-card {{
      border: 1px solid var(--line);
      background: var(--card);
      border-radius: 16px;
      box-shadow: 0 16px 38px rgba(74, 53, 28, 0.12);
    }}
    .audit {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      padding: 14px;
      margin: 18px 0;
    }}
    .metric {{
      background: #fff3da;
      border: 1px solid var(--accent-soft);
      border-radius: 12px;
      padding: 12px;
    }}
    .metric strong {{
      display: block;
      font-size: 25px;
      color: var(--accent);
      line-height: 1.1;
    }}
    .metric span {{
      display: block;
      margin-top: 5px;
      color: var(--muted);
      font-size: 13px;
    }}
    .audit-note {{
      grid-column: 1 / -1;
      margin: 0;
      color: var(--muted);
      line-height: 1.7;
    }}
    .page {{
      padding: 16px;
      margin: 18px 0;
    }}
    h2 {{ margin: 0 0 6px; font-size: 21px; color: var(--accent); }}
    h3 {{ margin: 0 0 10px; font-size: 16px; color: var(--accent); }}
    .page-meta, .unit-meta {{
      margin: 0 0 12px;
      color: var(--muted);
      font-size: 13px;
    }}
    .result-card {{
      padding: 14px;
      margin: 14px 0;
      box-shadow: none;
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      margin: 0;
      line-height: 1.8;
      font-size: 19px;
      font-family: "Kaiti SC", "Songti SC", "Noto Serif CJK SC", serif;
    }}
    .units {{
      margin-top: 14px;
    }}
    .unit {{
      display: grid;
      grid-template-columns: minmax(180px, 0.42fr) minmax(0, 1fr);
      gap: 12px;
      padding: 12px 0;
      border-top: 1px solid var(--line);
    }}
    .unit:first-of-type {{
      border-top: 0;
    }}
    .unit-image {{
      background: #2a241d;
      border-radius: 12px;
      padding: 8px;
      align-self: start;
    }}
    .unit-image img {{
      display: block;
      width: 100%;
      max-height: 240px;
      object-fit: contain;
      border-radius: 8px;
      background: white;
    }}
    .missing-image {{
      color: #f8ead4;
      font-size: 13px;
      padding: 20px;
      text-align: center;
    }}
    @media (max-width: 820px) {{
      .audit {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .unit {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>NuosuBburma OCR 本地整页 demo</h1>
      <p class="sub">本页展示同一条本地流程：页面切割、OCR 单元识别、页面文本合并、异常审计和可选注音。异常审计只提示风险，不自动改写 OCR 正文。</p>
      <p class="sub">{html.escape(size_note)}</p>
    </header>
    <section class="audit">
      <div class="metric"><strong>{audit.get("pages", 0)}</strong><span>页面</span></div>
      <div class="metric"><strong>{audit.get("ocr_units", 0)}</strong><span>OCR 单元</span></div>
      <div class="metric"><strong>{len(audit.get("replacement_char_rows", []))}</strong><span>含替换符单元</span></div>
      <div class="metric"><strong>{len(audit.get("empty_pages", []))}</strong><span>空结果页面</span></div>
      <p class="audit-note">生成时间：{html.escape(datetime.now().astimezone().isoformat(timespec="seconds"))}</p>
      <p class="audit-note">大图限制：{html.escape(str(max_image_side if max_image_side > 0 else "不压缩"))}。</p>
      <p class="audit-note">OCR 状态：{status_text or "n/a"}；页面块类型：{route_text or "n/a"}。</p>
      <p class="audit-note">空结果页面：{empty_pages}；重复页面文本：{duplicate_text}。</p>
    </section>
    {''.join(page_cards)}
  </main>
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")


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


def main() -> None:
    args = parse_args()
    input_path = resolve_path(args.input, DEFAULT_INPUT)
    model_path = resolve_path(args.model, DEFAULT_MODEL)
    output_root = resolve_path(args.output_root, DEFAULT_OUTPUT_ROOT)

    page_root = args.page_root.resolve() if args.page_root else output_root / "01_page_cutting"
    ocr_dir = output_root / "02_ocr_units"
    page_text_dir = output_root / "03_page_text"
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

    outputs = merge_page_text(ocr_results, page_text_dir, args.keep_empty_units, args.max_image_side)
    pronounced = maybe_add_pronunciation(args, outputs["submission_jsonl"], page_text_dir)

    manifest = {
        "input": str(input_path),
        "model": str(model_path),
        "output_root": str(output_root),
        "page_cutting_root": str(page_root),
        "max_image_side": args.max_image_side,
        "ocr_results": str(ocr_results),
        "page_text_outputs": {key: str(value) for key, value in outputs.items()},
        "pronunciation_output": str(pronounced) if pronounced else "",
    }
    manifest_path = output_root / "workflow_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nDone. Page demo outputs:")
    print(json.dumps({**manifest, "workflow_manifest": str(manifest_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
