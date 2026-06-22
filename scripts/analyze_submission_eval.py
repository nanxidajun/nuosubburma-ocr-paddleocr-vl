#!/usr/bin/env python3
"""分析 NuosuBburma OCR 提交评估集输出。"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable


YI_RE = re.compile(r"[\ua000-\ua4cf]")
HAN_RE = re.compile(r"[\u4e00-\u9fff]")
ASCII_LETTER_RE = re.compile(r"[A-Za-z]")
ASCII_ANY_RE = re.compile(r"[\x00-\x7f]")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def assistant_text(row: dict[str, Any]) -> str:
    if isinstance(row.get("label"), str):
        return row["label"]
    for message in reversed(row.get("messages") or []):
        if message.get("role") == "assistant":
            return str(message.get("content") or "")
    return ""


def answer_text(row: dict[str, Any]) -> str:
    return str(row.get("answer") or "")


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (0 if ca == cb else 1),
                )
            )
        previous = current
    return previous[-1]


def ned(pred: str, label: str) -> float:
    return levenshtein(pred, label) / max(len(pred), len(label), 1)


def strip_ws(text: str) -> str:
    return "".join(ch for ch in text if not ch.isspace())


def nfkc_ws(text: str) -> str:
    return strip_ws(unicodedata.normalize("NFKC", text))


def keep_yi(text: str) -> str:
    return "".join(YI_RE.findall(text))


def keep_han(text: str) -> str:
    return "".join(HAN_RE.findall(text))


def keep_digit(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def has_latex(text: str) -> bool:
    tokens = ("\\(", "\\)", "\\frac", "\\underset", "\\cdot", "\\mathrm", "^{", "_{")
    return any(token in text for token in tokens)


def is_long_failure(pred: str, label: str) -> bool:
    if "�" * 20 in pred:
        return True
    return len(pred) >= max(120, len(label) * 4)


def danger_flags(pred: str, label: str) -> dict[str, bool]:
    pred_has_ascii_letter = bool(ASCII_LETTER_RE.search(pred))
    label_has_ascii_letter = bool(ASCII_LETTER_RE.search(label))
    return {
        "replacement": "�" in pred,
        "latex": has_latex(pred),
        "ascii_letter": pred_has_ascii_letter,
        "gt_ascii_letter": label_has_ascii_letter,
        "extra_ascii_letter": pred_has_ascii_letter and not label_has_ascii_letter,
        "ascii_any": bool(ASCII_ANY_RE.search(pred)),
        "long_pred": is_long_failure(pred, label),
    }


def fmt_float(value: float) -> str:
    if math.isnan(value):
        return ""
    return f"{value:.6f}"


def metric_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if not rows:
        return {
            "n": 0,
            "ned": math.nan,
            "exact": math.nan,
            "ws_ned": math.nan,
            "ws_exact": math.nan,
            "nfkc_ws_ned": math.nan,
            "nfkc_ws_exact": math.nan,
            "yi_ned": math.nan,
            "yi_exact": math.nan,
            "yi_rows": 0,
            "han_ned": math.nan,
            "han_exact": math.nan,
            "han_rows": 0,
            "digit_ned": math.nan,
            "digit_exact": math.nan,
            "digit_rows": 0,
            "replacement": 0,
            "latex": 0,
            "ascii_letter": 0,
            "gt_ascii_letter": 0,
            "extra_ascii_letter": 0,
            "ascii_any": 0,
            "long_pred": 0,
        }

    raw_ned = 0.0
    raw_exact = 0
    ws_ned = 0.0
    ws_exact = 0
    nfkc_sum = 0.0
    nfkc_exact = 0
    yi_sum = 0.0
    yi_exact = 0
    yi_rows = 0
    han_sum = 0.0
    han_exact = 0
    han_rows = 0
    digit_sum = 0.0
    digit_exact = 0
    digit_rows = 0
    flags = Counter()

    for row in rows:
        gt = row["gt"]
        pred = row["pred"]

        raw_ned += ned(pred, gt)
        raw_exact += int(pred == gt)

        gt_ws = strip_ws(gt)
        pred_ws = strip_ws(pred)
        ws_ned += ned(pred_ws, gt_ws)
        ws_exact += int(pred_ws == gt_ws)

        gt_nfkc = nfkc_ws(gt)
        pred_nfkc = nfkc_ws(pred)
        nfkc_sum += ned(pred_nfkc, gt_nfkc)
        nfkc_exact += int(pred_nfkc == gt_nfkc)

        gt_yi = keep_yi(gt)
        pred_yi = keep_yi(pred)
        if gt_yi:
            yi_rows += 1
            yi_sum += ned(pred_yi, gt_yi)
            yi_exact += int(pred_yi == gt_yi)

        gt_han = keep_han(gt)
        pred_han = keep_han(pred)
        if gt_han:
            han_rows += 1
            han_sum += ned(pred_han, gt_han)
            han_exact += int(pred_han == gt_han)

        gt_digit = keep_digit(gt)
        pred_digit = keep_digit(pred)
        if gt_digit:
            digit_rows += 1
            digit_sum += ned(pred_digit, gt_digit)
            digit_exact += int(pred_digit == gt_digit)

        flags.update(k for k, v in danger_flags(pred, gt).items() if v)

    return {
        "n": n,
        "ned": raw_ned / n,
        "exact": raw_exact / n,
        "ws_ned": ws_ned / n,
        "ws_exact": ws_exact / n,
        "nfkc_ws_ned": nfkc_sum / n,
        "nfkc_ws_exact": nfkc_exact / n,
        "yi_ned": yi_sum / yi_rows if yi_rows else math.nan,
        "yi_exact": yi_exact / yi_rows if yi_rows else math.nan,
        "yi_rows": yi_rows,
        "han_ned": han_sum / han_rows if han_rows else math.nan,
        "han_exact": han_exact / han_rows if han_rows else math.nan,
        "han_rows": han_rows,
        "digit_ned": digit_sum / digit_rows if digit_rows else math.nan,
        "digit_exact": digit_exact / digit_rows if digit_rows else math.nan,
        "digit_rows": digit_rows,
        "replacement": flags["replacement"],
        "latex": flags["latex"],
        "ascii_letter": flags["ascii_letter"],
        "gt_ascii_letter": flags["gt_ascii_letter"],
        "extra_ascii_letter": flags["extra_ascii_letter"],
        "ascii_any": flags["ascii_any"],
        "long_pred": flags["long_pred"],
    }


def flatten_metrics(prefix: str, metrics: dict[str, Any]) -> dict[str, Any]:
    out = {prefix: metrics.get(prefix, "")} if prefix in metrics else {}
    for key, value in metrics.items():
        if key == prefix:
            continue
        out[key] = fmt_float(value) if isinstance(value, float) else value
    return out


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


def load_eval_rows(annotations: Path, result: Path) -> list[dict[str, Any]]:
    anno_by_id: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(annotations):
        row = dict(row)
        row["gt"] = assistant_text(row)
        anno_by_id[row["id"]] = row

    rows: list[dict[str, Any]] = []
    missing_result_ids: list[str] = []
    result_by_id = {row.get("id"): row for row in read_jsonl(result)}
    for sid, anno in anno_by_id.items():
        result_row = result_by_id.get(sid)
        if not result_row:
            missing_result_ids.append(sid)
            continue
        meta = dict(anno.get("meta") or {})
        gt = anno["gt"]
        pred = answer_text(result_row)
        image_rel = str((anno.get("images") or [""])[0])
        image_path = (annotations.parent / image_rel).resolve()
        rows.append(
            {
                "id": sid,
                "gt": gt,
                "pred": pred,
                "image_rel": image_rel,
                "image_path": str(image_path),
                "meta": meta,
                "source_name": meta.get("source_name", ""),
                "source_code": meta.get("source_code", ""),
                "sample_type": meta.get("sample_type", ""),
                "script_mix": meta.get("script_mix", ""),
                "difficulty": meta.get("difficulty", ""),
                "scene": meta.get("scene", ""),
                "source_category": meta.get("source_category", ""),
                "has_digit": bool(meta.get("has_digit", False)),
                "original_id": meta.get("original_id", ""),
            }
        )

    if missing_result_ids:
        raise SystemExit(f"missing {len(missing_result_ids)} result rows, first={missing_result_ids[:5]}")
    return rows


def add_row_metrics(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        gt = row["gt"]
        pred = row["pred"]
        row["dist"] = levenshtein(pred, gt)
        row["ned"] = ned(pred, gt)
        row["ws_ned"] = ned(strip_ws(pred), strip_ws(gt))
        row["nfkc_ws_ned"] = ned(nfkc_ws(pred), nfkc_ws(gt))
        row["yi_ned"] = ned(keep_yi(pred), keep_yi(gt)) if keep_yi(gt) else math.nan
        row["han_ned"] = ned(keep_han(pred), keep_han(gt)) if keep_han(gt) else math.nan
        row["gt_len"] = len(gt)
        row["pred_len"] = len(pred)
        row["gt_yi_len"] = len(keep_yi(gt))
        row["pred_yi_len"] = len(keep_yi(pred))
        row["gt_han_len"] = len(keep_han(gt))
        row["pred_han_len"] = len(keep_han(pred))
        row.update({f"flag_{k}": v for k, v in danger_flags(pred, gt).items()})


def group_metrics(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key, ""))].append(row)
    out: list[dict[str, Any]] = []
    for value, items in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        metrics = metric_pack(items)
        line = {key: value, **flatten_metrics(key, metrics)}
        out.append(line)
    return out


def build_summary(out_dir: Path, rows: list[dict[str, Any]], title: str) -> None:
    summary = flatten_metrics("summary", metric_pack(rows))
    summary["title"] = title
    summary["rows"] = len(rows)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# {title}",
        "",
        f"- rows: {len(rows)}",
        f"- Avg NED: {summary['ned']}",
        f"- Exact: {summary['exact']}",
        f"- WS Avg NED: {summary['ws_ned']}",
        f"- NFKC+WS Avg NED: {summary['nfkc_ws_ned']}",
        f"- Yi-only Avg NED / exact: {summary['yi_ned']} / {summary['yi_exact']} ({summary['yi_rows']} rows)",
        f"- Han-only Avg NED / exact: {summary['han_ned']} / {summary['han_exact']} ({summary['han_rows']} rows)",
        f"- Digit-only Avg NED / exact: {summary['digit_ned']} / {summary['digit_exact']} ({summary['digit_rows']} rows)",
        f"- replacement / latex / extra_ascii_letter / long_pred: {summary['replacement']} / {summary['latex']} / {summary['extra_ascii_letter']} / {summary['long_pred']}",
        f"- ascii_letter / gt_ascii_letter: {summary['ascii_letter']} / {summary['gt_ascii_letter']}",
        "",
    ]
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def build_html(out_dir: Path, rows: list[dict[str, Any]], title: str, limit: int) -> None:
    img_dir = out_dir / "html_images"
    img_dir.mkdir(parents=True, exist_ok=True)
    selected = sorted(rows, key=lambda row: (row["ned"], row["ws_ned"], row["gt_len"]), reverse=True)[:limit]

    cards: list[str] = []
    for rank, row in enumerate(selected, 1):
        image_path = Path(row["image_path"])
        copied = ""
        if image_path.exists():
            copied = f"{row['id']}{image_path.suffix.lower()}"
            shutil.copy2(image_path, img_dir / copied)
        flags = [name.replace("flag_", "") for name, val in row.items() if name.startswith("flag_") and val]
        cards.append(
            f"""
<article class="card">
  <div class="rank">#{rank}</div>
  <div class="meta">
    <b>{html.escape(row['id'])}</b>
    <span>{html.escape(row['source_name'])}</span>
    <span>{html.escape(row['sample_type'])}</span>
    <span>{html.escape(row['script_mix'])}</span>
    <span>{html.escape(row['difficulty'])}</span>
    <span>old: {html.escape(str(row['original_id']))}</span>
  </div>
  <div class="metrics">
    NED {row['ned']:.4f} · ws {row['ws_ned']:.4f} · yi {'' if math.isnan(row['yi_ned']) else f'{row["yi_ned"]:.4f}'} · dist {row['dist']} · len {row['gt_len']} · flags {html.escape(','.join(flags) or 'normal')}
  </div>
  <div class="grid">
    <div>{f'<img src="html_images/{html.escape(copied)}">' if copied else '<div class="missing">missing image</div>'}</div>
    <div>
      <h3>GT</h3>
      <pre>{html.escape(row['gt'])}</pre>
      <h3>Pred</h3>
      <pre>{html.escape(row['pred'])}</pre>
    </div>
  </div>
</article>
"""
        )

    doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{
  margin: 0;
  background: #f5f1e8;
  color: #1d1a16;
  font-family: "Songti SC", "Noto Serif CJK SC", serif;
}}
header {{
  position: sticky;
  top: 0;
  z-index: 2;
  padding: 18px 24px;
  background: rgba(245, 241, 232, 0.96);
  border-bottom: 1px solid #d8cdbb;
}}
h1 {{ margin: 0; font-size: 24px; }}
.wrap {{ max-width: 1280px; margin: 0 auto; padding: 20px 24px 60px; }}
.card {{
  background: #fffdf8;
  border: 1px solid #d7c6a8;
  border-radius: 16px;
  padding: 16px;
  margin: 0 0 18px;
  box-shadow: 0 8px 28px rgba(60, 42, 20, 0.08);
}}
.rank {{ float: right; font-size: 28px; color: #9d5829; font-weight: 700; }}
.meta {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: center; padding-right: 90px; }}
.meta span, .metrics {{
  display: inline-block;
  border-radius: 999px;
  background: #eee2cf;
  padding: 3px 9px;
  font-size: 13px;
}}
.metrics {{ margin: 10px 0 14px; background: #f2d2b8; }}
.grid {{ display: grid; grid-template-columns: minmax(320px, 45%) 1fr; gap: 18px; }}
img {{
  max-width: 100%;
  max-height: 440px;
  object-fit: contain;
  background: white;
  border: 1px solid #ddd1bd;
  border-radius: 10px;
}}
h3 {{ margin: 0 0 6px; font-size: 15px; color: #79411e; }}
pre {{
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0 0 14px;
  padding: 12px;
  border-radius: 10px;
  background: #211d18;
  color: #fff8ed;
  font-size: 20px;
  line-height: 1.55;
  font-family: "Kaiti SC", "Noto Serif CJK SC", serif;
}}
.missing {{ padding: 40px; background: #fff; color: #a33; border: 1px dashed #a33; }}
@media (max-width: 800px) {{
  .grid {{ grid-template-columns: 1fr; }}
  pre {{ font-size: 17px; }}
}}
</style>
</head>
<body>
<header><h1>{html.escape(title)}</h1></header>
<main class="wrap">
{''.join(cards)}
</main>
</body>
</html>
"""
    (out_dir / "worst180_submission_eval.html").write_text(doc, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--title", default="NuosuBburma OCR Evaluation Set")
    parser.add_argument("--html-limit", type=int, default=180)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = load_eval_rows(args.annotations, args.result)
    add_row_metrics(rows)

    build_summary(args.out_dir, rows, args.title)
    write_csv(args.out_dir / "by_source.csv", group_metrics(rows, "source_name"))
    write_csv(args.out_dir / "by_sample_type.csv", group_metrics(rows, "sample_type"))
    write_csv(args.out_dir / "by_script_mix.csv", group_metrics(rows, "script_mix"))
    write_csv(args.out_dir / "by_difficulty.csv", group_metrics(rows, "difficulty"))
    write_csv(args.out_dir / "by_scene.csv", group_metrics(rows, "scene"))
    write_csv(args.out_dir / "by_has_digit.csv", group_metrics(rows, "has_digit"))

    detail_rows = []
    for row in sorted(rows, key=lambda item: (item["ned"], item["ws_ned"]), reverse=True):
        detail_rows.append(
            {
                "id": row["id"],
                "source_name": row["source_name"],
                "sample_type": row["sample_type"],
                "script_mix": row["script_mix"],
                "difficulty": row["difficulty"],
                "has_digit": row["has_digit"],
                "ned": f"{row['ned']:.6f}",
                "ws_ned": f"{row['ws_ned']:.6f}",
                "nfkc_ws_ned": f"{row['nfkc_ws_ned']:.6f}",
                "yi_ned": "" if math.isnan(row["yi_ned"]) else f"{row['yi_ned']:.6f}",
                "han_ned": "" if math.isnan(row["han_ned"]) else f"{row['han_ned']:.6f}",
                "dist": row["dist"],
                "gt_len": row["gt_len"],
                "pred_len": row["pred_len"],
                "flags": ",".join(
                    name.replace("flag_", "")
                    for name, val in row.items()
                    if name.startswith("flag_") and val
                ),
                "original_id": row["original_id"],
                "gt": row["gt"],
                "pred": row["pred"],
            }
        )
    write_csv(args.out_dir / "all_scored_rows.csv", detail_rows)
    write_csv(
        args.out_dir / "danger_rows.csv",
        [row for row in detail_rows if row["flags"]],
    )
    build_html(args.out_dir, rows, args.title, args.html_limit)

    print((args.out_dir / "summary.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
