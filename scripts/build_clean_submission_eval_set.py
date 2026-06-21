#!/usr/bin/env python3
"""构建 NuosuBburma OCR clean 评估集。"""

from __future__ import annotations

import argparse
import csv
import html
import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path


SRC_ROOT = Path("data/source_eval_set_nuosubburma_ocr")
OUT_ROOT = Path("data/NuosuBburma_OCR_Evaluation_Set")

SOURCE_INFO = {
    "根与花": {
        "source_code": "gen_yu_hua",
        "title": "根与花",
        "publisher": "四川民族出版社",
        "year": "1999",
        "source_material": "扫描件",
    },
    "勒俄玛牧导读教程": {
        "source_code": "le_e_ma_mu_guide",
        "title": "勒俄玛牧导读教程",
        "publisher": "民族出版社",
        "year": "2015",
        "source_material": "扫描件",
    },
    "凉山彝语语法": {
        "source_code": "liangshan_yi_grammar",
        "title": "凉山彝语语法",
        "publisher": "民族出版社",
        "year": "1987",
        "source_material": "扫描件",
    },
    "《勒俄特依》译注": {
        "source_code": "luoe_teyi",
        "title": "《勒俄特依》译注",
        "publisher": "民族出版社",
        "year": "2017",
        "source_material": "扫描件",
    },
    "凉山彝文资料选译第2集": {
        "source_code": "xuan_yi_2",
        "title": "凉山彝文资料选译（2）：《阿莫尼惹》《玛木特农》",
        "publisher": "四川民族出版社",
        "year": "1978",
        "source_material": "扫描件",
    },
    "凉山彝文资料选译第3集": {
        "source_code": "xuan_yi_3",
        "title": "凉山彝文资料选译（3）：《尔比尔吉》",
        "publisher": "四川民族出版社",
        "year": "1978",
        "source_material": "扫描件",
    },
    "彝文检字本": {
        "source_code": "yi_dictionary",
        "title": "彝文检字本",
        "publisher": "四川民族出版社",
        "year": "1984",
        "source_material": "扫描件",
    },
    "真实手写": {
        "source_code": "handwriting",
        "title": "真实手写样本",
        "publisher": "",
        "year": "2026",
        "source_material": "用户采集手写样本",
    },
    "真实照片": {
        "source_code": "real_photo",
        "title": "真实照片样本",
        "publisher": "",
        "year": "2026",
        "source_material": "用户拍摄照片",
    },
    "屏幕页面": {
        "source_code": "screen",
        "title": "屏幕页面样本",
        "publisher": "",
        "year": "2026",
        "source_material": "用户截屏或屏幕拍摄",
    },
}


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def label_text(row: dict) -> str:
    for message in row.get("messages", []):
        if message.get("role") == "assistant":
            return str(message.get("content") or "")
    return ""


def char_counts(text: str) -> dict[str, int]:
    return {
        "line_count": text.count("\n") + 1 if text else 0,
        "nonspace_len": sum(1 for ch in text if not ch.isspace()),
        "yi_count": sum(1 for ch in text if "\ua000" <= ch <= "\ua4cf"),
        "han_count": sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff"),
        "latin_count": sum(1 for ch in text if ("A" <= ch <= "Z") or ("a" <= ch <= "z")),
        "digit_count": sum(1 for ch in text if ch.isdigit()),
    }


def prepare_output() -> None:
    if OUT_ROOT.exists():
        backup = OUT_ROOT.with_name(f"{OUT_ROOT.name}.backup_{time.strftime('%Y%m%d_%H%M%S')}")
        OUT_ROOT.rename(backup)
    (OUT_ROOT / "images").mkdir(parents=True)


def clean_row(row: dict, index: int) -> tuple[dict, dict]:
    old_meta = row.get("meta", {})
    source_name = old_meta.get("source_name", "")
    source_info = SOURCE_INFO.get(source_name)
    if not source_info:
        raise ValueError(f"unknown source_name: {source_name!r}")

    sample_type = old_meta.get("type", "")
    if sample_type not in {"line", "region", "page"}:
        raise ValueError(f"bad sample type for {row.get('id')}: {sample_type!r}")

    source_code = source_info["source_code"]
    clean_id = f"{source_code}_{sample_type}_{index:06d}"
    old_image = (row.get("images") or [""])[0]
    if not old_image:
        raise ValueError(f"missing image in row: {row.get('id')}")

    old_image_path = SRC_ROOT / old_image
    if not old_image_path.exists():
        raise FileNotFoundError(old_image_path)
    suffix = old_image_path.suffix.lower() or ".png"
    new_image = f"images/{clean_id}{suffix}"
    shutil.copy2(old_image_path, OUT_ROOT / new_image)

    gt = label_text(row)
    counts = char_counts(gt)
    meta = {
        "source_name": source_name,
        "source_code": source_code,
        "source_title": source_info["title"],
        "publisher": source_info["publisher"],
        "publication_year": source_info["year"],
        "source_material": source_info["source_material"],
        "source_category": old_meta.get("source_category", ""),
        "sample_type": sample_type,
        "scene": old_meta.get("scene", ""),
        "difficulty": old_meta.get("difficulty", ""),
        "script_mix": old_meta.get("script_mix", ""),
        "has_digit": bool(counts["digit_count"]),
        "score_included": True,
        "original_id": row.get("id", ""),
        "original_image": old_image,
        "page_file": old_meta.get("page_file", ""),
        "page": old_meta.get("pdf_page", ""),
        "box": old_meta.get("source_box", ""),
        "part": old_meta.get("part_index", ""),
        "region_kind": old_meta.get("region_kind", ""),
    }
    if old_meta.get("original_source_name"):
        meta["original_source_name"] = old_meta.get("original_source_name", "")
    if old_meta.get("original_source_id"):
        meta["original_source_code"] = old_meta.get("original_source_id", "")

    clean = {
        "id": clean_id,
        "images": [new_image],
        "messages": row.get("messages", []),
        "meta": meta,
    }

    sample_row = {
        "id": clean_id,
        "image": new_image,
        "gt": gt,
        **{k: meta.get(k, "") for k in [
            "source_name",
            "source_code",
            "source_title",
            "publisher",
            "publication_year",
            "source_material",
            "source_category",
            "sample_type",
            "scene",
            "difficulty",
            "script_mix",
            "has_digit",
            "original_id",
            "original_image",
            "page_file",
            "page",
            "box",
            "part",
            "region_kind",
            "original_source_name",
            "original_source_code",
        ]},
        **counts,
    }
    return clean, sample_row


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_summaries(rows: list[dict], sample_rows: list[dict]) -> None:
    by_source = Counter(r["source_name"] for r in sample_rows)
    by_type = Counter(r["sample_type"] for r in sample_rows)
    by_scene = Counter(r["scene"] for r in sample_rows)
    by_difficulty = Counter(r["difficulty"] for r in sample_rows)
    by_script = Counter(r["script_mix"] for r in sample_rows)
    by_digit = Counter("has_digit" if r["has_digit"] else "no_digit" for r in sample_rows)

    source_digit = defaultdict(Counter)
    for r in sample_rows:
        source_digit[r["source_name"]]["has_digit" if r["has_digit"] else "no_digit"] += 1

    summary = {
        "name": "NuosuBburma_OCR_Evaluation_Set",
        "rows": len(rows),
        "images": len(list((OUT_ROOT / "images").glob("*"))),
        "annotation_file": "annotations.jsonl",
        "all_samples_score_included": True,
        "blank_gt": sum(1 for r in sample_rows if not str(r["gt"]).strip()),
        "placeholder_rows": sum(1 for r in sample_rows if "？？" in str(r["gt"]) or "??" in str(r["gt"])),
        "digit_rows": sum(1 for r in sample_rows if r["has_digit"]),
        "no_digit_rows": sum(1 for r in sample_rows if not r["has_digit"]),
        "total_digit_chars": sum(int(r["digit_count"]) for r in sample_rows),
        "by_source_name": dict(by_source),
        "by_sample_type": dict(by_type),
        "by_scene": dict(by_scene),
        "by_difficulty": dict(by_difficulty),
        "by_script_mix": dict(by_script),
        "by_digit_presence": dict(by_digit),
        "by_source_digit_presence": {k: dict(v) for k, v in source_digit.items()},
    }
    (OUT_ROOT / "dataset_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    source_rows = []
    for source_name, info in SOURCE_INFO.items():
        subset = [r for r in sample_rows if r["source_name"] == source_name]
        if not subset:
            continue
        source_rows.append(
            {
                "source_name": source_name,
                "source_code": info["source_code"],
                "source_title": info["title"],
                "publisher": info["publisher"],
                "publication_year": info["year"],
                "source_material": info["source_material"],
                "rows": len(subset),
                "line": sum(1 for r in subset if r["sample_type"] == "line"),
                "region": sum(1 for r in subset if r["sample_type"] == "region"),
                "page": sum(1 for r in subset if r["sample_type"] == "page"),
                "has_digit": sum(1 for r in subset if r["has_digit"]),
                "digit_chars": sum(int(r["digit_count"]) for r in subset),
            }
        )
    write_csv(
        OUT_ROOT / "source_summary.csv",
        source_rows,
        [
            "source_name",
            "source_code",
            "source_title",
            "publisher",
            "publication_year",
            "source_material",
            "rows",
            "line",
            "region",
            "page",
            "has_digit",
            "digit_chars",
        ],
    )

    digit_rows = []
    for dimension in ["source_name", "sample_type", "scene", "difficulty", "script_mix"]:
        for value in sorted({str(r[dimension]) for r in sample_rows}):
            subset = [r for r in sample_rows if str(r[dimension]) == value]
            digit_rows.append(
                {
                    "dimension": dimension,
                    "value": value,
                    "rows": len(subset),
                    "has_digit": sum(1 for r in subset if r["has_digit"]),
                    "no_digit": sum(1 for r in subset if not r["has_digit"]),
                    "digit_chars": sum(int(r["digit_count"]) for r in subset),
                }
            )
    write_csv(OUT_ROOT / "digit_summary.csv", digit_rows, ["dimension", "value", "rows", "has_digit", "no_digit", "digit_chars"])

    if (SRC_ROOT / "removed_or_archived.csv").exists():
        shutil.copy2(SRC_ROOT / "removed_or_archived.csv", OUT_ROOT / "excluded_samples.csv")


def write_readme() -> None:
    text = """# NuosuBburma OCR 评估集

这是 NuosuBburma OCR 的 clean 评估集包。

本评估集共 603 条真实样本，全部计入主评分。样本来自真实书籍扫描件裁剪、规范手写、屏幕页面和真实照片。合成训练样本不进入本评估集。

书籍样本来源于扫描件。项目从扫描件中裁取文字区域，用于规范彝文 OCR 评估与模型验证。原始出版物版权归原出版社和权利人所有。

## 文件

| 文件/目录 | 说明 |
|---|---|
| `annotations.jsonl` | 主评估标注，603 条样本 |
| `images/` | 全部被引用图片，文件名与样本 ID 对齐 |
| `samples.csv` | 行级索引，便于人工检查和统计 |
| `source_summary.csv` | 来源书目/来源类型统计 |
| `dataset_summary.json` | 机器可读的数据分布摘要 |
| `digit_summary.csv` | 含数字样本统计 |
| `review.html` | 静态可视化复核页 |
| `excluded_samples.csv` | 从提交评估集中排除的样本记录 |

## 命名规则

样本 ID 使用：

```text
{source_code}_{line|region|page}_{000001}
```

示例：

```text
gen_yu_hua_line_000001
le_e_ma_mu_guide_line_000122
luoe_teyi_region_000277
screen_page_000597
```

## 来源

来源名称、出版社、年份、来源材料和样本数见 `source_summary.csv`。

## 任务

输入：包含规范彝文可见文本的图片。

输出：图片中可见的 Unicode 文本。

提示词：

```text
<image>OCR:
```
"""
    (OUT_ROOT / "README.md").write_text(text, encoding="utf-8")


def write_review_html(sample_rows: list[dict]) -> None:
    def esc(value: object) -> str:
        return html.escape(str(value), quote=True)

    cards = []
    for idx, r in enumerate(sample_rows, 1):
        chips = " ".join(
            f"<span>{esc(v)}</span>"
            for v in [r["source_name"], r["sample_type"], r["scene"], r["difficulty"], r["script_mix"], "has_digit" if r["has_digit"] else "no_digit"]
            if v
        )
        cards.append(
            f"""
<article class="card">
  <div class="meta"><b>#{idx:03d}</b> <code>{esc(r['id'])}</code><div class="chips">{chips}</div></div>
  <div class="grid">
    <a href="{esc(r['image'])}" target="_blank"><img loading="lazy" src="{esc(r['image'])}"></a>
    <div>
      <p><b>{esc(r['source_title'])}</b> · {esc(r['publisher'])} {esc(r['publication_year'])}</p>
      <p><small>original_id: <code>{esc(r['original_id'])}</code></small></p>
      <pre>{esc(r['gt'])}</pre>
    </div>
  </div>
</article>"""
        )
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>NuosuBburma OCR 评估集复核</title>
<style>
body{{margin:0;background:#f7f3ea;color:#211b14;font-family:"Avenir Next","Helvetica Neue",Arial,sans-serif;}}
header{{position:sticky;top:0;background:#fff8eaee;backdrop-filter:blur(10px);border-bottom:1px solid #d8c9ae;padding:16px 22px;z-index:2}}
h1{{margin:0 0 8px;font-size:22px}}
input{{width:min(720px,100%);padding:10px;border:1px solid #d8c9ae;border-radius:10px}}
main{{padding:18px 22px}}
.card{{background:white;border:1px solid #d8c9ae;border-radius:14px;margin:12px 0;overflow:hidden}}
.meta{{display:flex;gap:10px;align-items:center;justify-content:space-between;padding:10px 12px;background:#fff4dc;border-bottom:1px solid #eadcc4}}
.chips{{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}}
.chips span{{background:#eadcc4;border-radius:999px;padding:3px 8px;font-size:12px}}
.grid{{display:grid;grid-template-columns:minmax(240px,42%) 1fr;gap:14px;padding:12px}}
img{{max-width:100%;max-height:480px;border:1px solid #e5d7bd;background:#fafafa}}
pre{{white-space:pre-wrap;font-size:20px;line-height:1.55;font-family:"Kaiti SC","Songti SC",serif;background:#fffaf0;border-left:4px solid #0f6b5f;padding:10px;border-radius:8px}}
code{{word-break:break-all}}
.hidden{{display:none}}
@media(max-width:900px){{.grid{{grid-template-columns:1fr}}header{{position:static}}}}
</style>
</head>
<body>
<header>
<h1>NuosuBburma OCR 评估集复核</h1>
<input id="q" placeholder="Search id / source / type / GT ...">
<span id="count"> {len(sample_rows)} / {len(sample_rows)}</span>
</header>
<main>{''.join(cards)}</main>
<script>
const q=document.getElementById('q');
const cards=[...document.querySelectorAll('.card')];
const count=document.getElementById('count');
q.addEventListener('input',()=>{{
  const term=q.value.trim().toLowerCase();
  let shown=0;
  for(const card of cards){{
    const ok=!term || card.textContent.toLowerCase().includes(term);
    card.classList.toggle('hidden',!ok);
    if(ok) shown++;
  }}
  count.textContent=` ${{shown}} / ${{cards.length}}`;
}});
</script>
</body>
</html>"""
    (OUT_ROOT / "review.html").write_text(page, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建 NuosuBburma OCR clean 评估集")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=SRC_ROOT,
        help="输入评估集目录，需包含 eval_all_scored.jsonl 和图片",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=OUT_ROOT,
        help="输出 clean 评估集目录",
    )
    return parser.parse_args()


def main() -> None:
    global SRC_ROOT, OUT_ROOT
    args = parse_args()
    SRC_ROOT = args.source_root
    OUT_ROOT = args.output_root
    rows = read_jsonl(SRC_ROOT / "eval_all_scored.jsonl")
    prepare_output()
    clean_rows = []
    sample_rows = []
    for index, row in enumerate(rows, 1):
        clean, sample = clean_row(row, index)
        clean_rows.append(clean)
        sample_rows.append(sample)

    write_jsonl(OUT_ROOT / "annotations.jsonl", clean_rows)
    sample_fields = [
        "id",
        "image",
        "gt",
        "source_name",
        "source_code",
        "source_title",
        "publisher",
        "publication_year",
        "source_material",
        "source_category",
        "sample_type",
        "scene",
        "difficulty",
        "script_mix",
        "has_digit",
        "line_count",
        "nonspace_len",
        "yi_count",
        "han_count",
        "latin_count",
        "digit_count",
        "original_id",
        "original_image",
        "page_file",
        "page",
        "box",
        "part",
        "region_kind",
        "original_source_name",
        "original_source_code",
    ]
    write_csv(OUT_ROOT / "samples.csv", sample_rows, sample_fields)
    write_summaries(clean_rows, sample_rows)
    write_readme()
    write_review_html(sample_rows)
    print(json.dumps({"output": str(OUT_ROOT), "rows": len(clean_rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
