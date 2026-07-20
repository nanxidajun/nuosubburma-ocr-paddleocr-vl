#!/usr/bin/env python3
"""Recompute the frozen final-model evaluation and render public SVG figures.

The primary metric is corpus CER after NFC normalization and removal of all
Unicode whitespace. Mean per-sample NED is reported separately because it gives
every image equal weight and therefore answers a different question.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET


SCENE_LABELS = {
    "book_scan": "书籍扫描",
    "real_screen_photo": "屏幕拍摄",
    "phone_handwritten": "手写拍照",
    "real_photo": "实景拍照",
}

DIFFICULTY_LABELS = {
    "easy": "低难度",
    "medium": "中难度",
    "hard": "高难度",
}

NED_BINS = (
    ("完全一致", 0.0, 0.0),
    ("0-1%", 0.0, 0.01),
    ("1-5%", 0.01, 0.05),
    ("5-10%", 0.05, 0.10),
    ("10-25%", 0.10, 0.25),
    (">25%", 0.25, None),
)

COLORS = {
    "ink": "#1F2933",
    "muted": "#5F6B76",
    "grid": "#D9E0E6",
    "blue": "#315F7D",
    "green": "#2F766D",
    "amber": "#B27A2D",
    "red": "#A13A32",
    "purple": "#73556F",
    "light_blue": "#B8CBD8",
    "light_red": "#DDB7B2",
    "white": "#FFFFFF",
    "soft": "#F5F7F8",
}

FONT = (
    '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC", '
    '"Microsoft YaHei", sans-serif'
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no}: row must be a JSON object")
            rows.append(value)
    return rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assistant_text(row: dict[str, Any]) -> str:
    messages = row.get("messages")
    if not isinstance(messages, list):
        raise ValueError(f"annotation {row.get('id')}: messages must be a list")
    answers = [
        message.get("content")
        for message in messages
        if isinstance(message, dict) and message.get("role") == "assistant"
    ]
    if len(answers) != 1 or not isinstance(answers[0], str):
        raise ValueError(f"annotation {row.get('id')}: expected one assistant answer")
    return answers[0]


def prediction_text(row: dict[str, Any]) -> str:
    for key in ("prediction", "answer", "assistant"):
        value = row.get(key)
        if isinstance(value, str):
            return value
    return assistant_text(row)


def normalize_primary(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFC", text) if not ch.isspace())


def normalize_nfkc(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKC", text) if not ch.isspace())


def levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if len(left) < len(right):
        left, right = right, left
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, 1):
        current = [left_index]
        for right_index, right_char in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def normalized_distance(prediction: str, ground_truth: str) -> tuple[int, float]:
    distance = levenshtein(prediction, ground_truth)
    denominator = max(len(prediction), len(ground_truth))
    return distance, distance / denominator if denominator else 0.0


def index_unique(rows: Iterable[dict[str, Any]], kind: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        sample_id = row.get("id")
        if not isinstance(sample_id, str) or not sample_id:
            raise ValueError(f"{kind}: every row needs a non-empty id")
        if sample_id in indexed:
            raise ValueError(f"{kind}: duplicate id {sample_id}")
        indexed[sample_id] = row
    return indexed


def annotation_image_sha256(row: dict[str, Any]) -> str:
    meta = row.get("meta")
    image = meta.get("image") if isinstance(meta, dict) else None
    value = image.get("sha256") if isinstance(image, dict) else None
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"annotation {row.get('id')}: missing meta.image.sha256")
    return value


def prediction_image_sha256(row: dict[str, Any]) -> str:
    meta = row.get("meta")
    value = None
    if isinstance(meta, dict):
        for key in ("image_sha256", "evaluation_image_sha256", "inference_image_sha256"):
            candidate = meta.get(key)
            if isinstance(candidate, str):
                value = candidate
                break
        if value is None:
            image = meta.get("image")
            candidate = image.get("sha256") if isinstance(image, dict) else None
            if isinstance(candidate, str):
                value = candidate
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"prediction {row.get('id')}: missing meta.image_sha256")
    return value


def index_by_image_sha256(
    rows: Iterable[dict[str, Any]], kind: str, extractor: Any
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        image_sha256 = extractor(row)
        if image_sha256 in indexed:
            raise ValueError(f"{kind}: duplicate image SHA-256 {image_sha256}")
        indexed[image_sha256] = row
    return indexed


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    gt_characters = sum(row["gt_characters"] for row in rows)
    prediction_characters = sum(row["prediction_characters"] for row in rows)
    edit_distance = sum(row["edit_distance"] for row in rows)
    return {
        "samples": count,
        "gt_characters": gt_characters,
        "prediction_characters": prediction_characters,
        "edit_distance": edit_distance,
        "cer": edit_distance / gt_characters if gt_characters else None,
        "mean_sample_ned": (
            sum(row["ned"] for row in rows) / count if count else None
        ),
        "exact_matches": sum(row["exact"] for row in rows),
        "exact_match_rate": (
            sum(row["exact"] for row in rows) / count if count else None
        ),
    }


def build_breakdown(
    rows: list[dict[str, Any]], key: str, labels: dict[str, str]
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    overall = summarize(rows)
    output: list[dict[str, Any]] = []
    for value in labels:
        metrics = summarize(groups[value])
        metrics.update(
            {
                "key": value,
                "label": labels[value],
                "sample_share": metrics["samples"] / overall["samples"],
                "character_share": metrics["gt_characters"]
                / overall["gt_characters"],
                "error_share": metrics["edit_distance"] / overall["edit_distance"],
            }
        )
        output.append(metrics)
    return output


def bin_distribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total_errors = sum(row["edit_distance"] for row in rows)
    output: list[dict[str, Any]] = []
    for label, low, high in NED_BINS:
        if label == "完全一致":
            selected = [row for row in rows if row["ned"] == 0]
        elif high is None:
            selected = [row for row in rows if row["ned"] > low]
        else:
            selected = [row for row in rows if low < row["ned"] <= high]
        errors = sum(row["edit_distance"] for row in selected)
        output.append(
            {
                "label": label,
                "samples": len(selected),
                "sample_share": len(selected) / len(rows),
                "edit_distance": errors,
                "error_share": errors / total_errors if total_errors else 0.0,
            }
        )
    if sum(item["samples"] for item in output) != len(rows):
        raise ValueError("NED bins do not partition all samples")
    return output


def compute_metrics(
    annotations_path: Path,
    predictions_path: Path,
    model_sha256: str,
) -> dict[str, Any]:
    annotation_rows = read_jsonl(annotations_path)
    prediction_rows = read_jsonl(predictions_path)
    index_unique(annotation_rows, "annotations")
    index_unique(prediction_rows, "predictions")
    annotations = index_by_image_sha256(
        annotation_rows, "annotations", annotation_image_sha256
    )
    predictions = index_by_image_sha256(
        prediction_rows, "predictions", prediction_image_sha256
    )
    if annotations.keys() != predictions.keys():
        missing = sorted(annotations.keys() - predictions.keys())
        extra = sorted(predictions.keys() - annotations.keys())
        raise ValueError(
            f"image SHA-256 mismatch: missing={missing[:5]}, extra={extra[:5]}"
        )

    scored: list[dict[str, Any]] = []
    for image_sha256, annotation in annotations.items():
        sample_id = str(annotation["id"])
        prediction_row = predictions[image_sha256]
        gt_raw = assistant_text(annotation)
        pred_raw = prediction_text(prediction_row)
        gt = normalize_primary(gt_raw)
        pred = normalize_primary(pred_raw)
        distance, ned = normalized_distance(pred, gt)
        raw_distance, raw_ned = normalized_distance(pred_raw, gt_raw)
        nfkc_gt = normalize_nfkc(gt_raw)
        nfkc_pred = normalize_nfkc(pred_raw)
        nfkc_distance, nfkc_ned = normalized_distance(nfkc_pred, nfkc_gt)
        meta = annotation.get("meta") or {}
        if not isinstance(meta, dict):
            raise ValueError(f"annotation {sample_id}: meta must be an object")
        scene = meta.get("scene")
        difficulty = meta.get("difficulty")
        if scene not in SCENE_LABELS or difficulty not in DIFFICULTY_LABELS:
            raise ValueError(
                f"annotation {sample_id}: unsupported scene/difficulty {scene}/{difficulty}"
            )
        scored.append(
            {
                "id": sample_id,
                "scene": scene,
                "difficulty": difficulty,
                "gt_characters": len(gt),
                "prediction_characters": len(pred),
                "edit_distance": distance,
                "ned": ned,
                "exact": gt == pred,
                "raw_gt_characters": len(gt_raw),
                "raw_edit_distance": raw_distance,
                "raw_ned": raw_ned,
                "nfkc_gt_characters": len(nfkc_gt),
                "nfkc_edit_distance": nfkc_distance,
                "nfkc_ned": nfkc_ned,
            }
        )

    overall = summarize(scored)
    overall.update(
        {
            "raw_cer": sum(row["raw_edit_distance"] for row in scored)
            / sum(row["raw_gt_characters"] for row in scored),
            "raw_mean_sample_ned": sum(row["raw_ned"] for row in scored)
            / len(scored),
            "nfkc_ws_cer": sum(row["nfkc_edit_distance"] for row in scored)
            / sum(row["nfkc_gt_characters"] for row in scored),
            "nfkc_ws_mean_sample_ned": sum(row["nfkc_ned"] for row in scored)
            / len(scored),
        }
    )
    return {
        "schema": "nuosubburma_final_evaluation/1.0",
        "scope": "frozen_final_release_model_full_1030_sample_evaluation",
        "metric": {
            "primary": "corpus CER = sum Levenshtein distance / sum GT code points",
            "normalization": "NFC, then remove all Unicode whitespace",
            "secondary": "mean per-sample NED = mean(distance / max(pred length, GT length))",
            "diagnostic": "NFKC results are diagnostic only because compatibility normalization can fold OCR-significant symbols",
        },
        "provenance": {
            "model_weight_sha256": model_sha256,
            "annotations_sha256": sha256_file(annotations_path),
            "predictions_sha256": sha256_file(predictions_path),
            "alignment": "unique image SHA-256; all 1,030 image hashes matched exactly",
        },
        "overall": overall,
        "breakdowns": {
            "scene": build_breakdown(scored, "scene", SCENE_LABELS),
            "difficulty": build_breakdown(
                scored, "difficulty", DIFFICULTY_LABELS
            ),
        },
        "ned_distribution": bin_distribution(scored),
    }


def svg_root(width: int, height: int, title: str, description: str) -> ET.Element:
    root = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(width),
            "height": str(height),
            "viewBox": f"0 0 {width} {height}",
            "role": "img",
            "aria-labelledby": "chart-title chart-desc",
        },
    )
    ET.SubElement(root, "title", {"id": "chart-title"}).text = title
    ET.SubElement(root, "desc", {"id": "chart-desc"}).text = description
    ET.SubElement(root, "rect", {"width": str(width), "height": str(height), "fill": COLORS["white"]})
    return root


def text(
    root: ET.Element,
    x: float,
    y: float,
    value: str,
    *,
    size: int = 26,
    fill: str | None = None,
    weight: int = 400,
    anchor: str = "start",
) -> ET.Element:
    node = ET.SubElement(
        root,
        "text",
        {
            "x": f"{x:.1f}",
            "y": f"{y:.1f}",
            "fill": fill or COLORS["ink"],
            "font-family": FONT,
            "font-size": str(size),
            "font-weight": str(weight),
            "text-anchor": anchor,
        },
    )
    node.text = value
    return node


def line(
    root: ET.Element, x1: float, y1: float, x2: float, y2: float, color: str, width: int = 2
) -> None:
    ET.SubElement(
        root,
        "line",
        {
            "x1": f"{x1:.1f}",
            "y1": f"{y1:.1f}",
            "x2": f"{x2:.1f}",
            "y2": f"{y2:.1f}",
            "stroke": color,
            "stroke-width": str(width),
        },
    )


def rect(
    root: ET.Element,
    x: float,
    y: float,
    width: float,
    height: float,
    color: str,
    radius: int = 4,
) -> None:
    ET.SubElement(
        root,
        "rect",
        {
            "x": f"{x:.1f}",
            "y": f"{y:.1f}",
            "width": f"{max(width, 0):.1f}",
            "height": f"{height:.1f}",
            "rx": str(radius),
            "fill": color,
        },
    )


def heading(root: ET.Element, title_value: str, subtitle: str) -> None:
    text(root, 70, 72, title_value, size=38, weight=500)
    text(root, 70, 112, subtitle, size=21, fill=COLORS["muted"])
    line(root, 70, 142, 1530, 142, COLORS["grid"], 2)


def format_share(value: float) -> str:
    percent = value * 100
    if 0 < percent < 0.1:
        return "<0.1%"
    return f"{percent:.1f}%"


def write_svg(path: Path, root: ET.Element) -> None:
    ET.indent(root, space="  ")
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def render_overview(metrics: dict[str, Any], path: Path) -> None:
    overall = metrics["overall"]
    provenance = metrics["provenance"]
    root = svg_root(
        1600,
        820,
        "最终发布模型评估口径与结果",
        "展示语料级 CER、逐样本平均 NED、完全一致率及模型和评估输入哈希。",
    )
    heading(root, "最终发布模型：完整评估结果", "同一模型、同一评估集、同一评分公式；1,030 张全部纳入")

    columns = [80, 565, 1050]
    labels = ["主指标：语料级 CER", "分布指标：平均 NED", "严格指标：完全一致"]
    formulas = [
        "总编辑距离 / GT 总字符数",
        "逐样本 NED 的等权平均",
        "预测与 GT 规范化后完全相同",
    ]
    values = [
        f"{overall['cer'] * 100:.2f}%",
        f"{overall['mean_sample_ned'] * 100:.2f}%",
        f"{overall['exact_match_rate'] * 100:.1f}%",
    ]
    details = [
        f"{overall['edit_distance']:,} / {overall['gt_characters']:,}",
        f"1,030 张逐张归一后再平均",
        f"{overall['exact_matches']:,} / {overall['samples']:,}",
    ]
    accents = [COLORS["red"], COLORS["blue"], COLORS["green"]]
    for x, label, formula, value, detail, accent in zip(
        columns, labels, formulas, values, details, accents
    ):
        rect(root, x, 205, 8, 210, accent, 0)
        text(root, x + 28, 240, label, size=23, weight=500)
        text(root, x + 28, 282, formula, size=19, fill=COLORS["muted"])
        text(root, x + 28, 358, value, size=52, fill=accent, weight=500)
        text(root, x + 28, 400, detail, size=20, fill=COLORS["muted"])

    line(root, 70, 480, 1530, 480, COLORS["grid"], 2)
    text(root, 70, 535, "可复核证据链", size=25, weight=500)
    proof = [
        ("最终权重", provenance["model_weight_sha256"]),
        ("最终标注", provenance["annotations_sha256"]),
        ("固定预测", provenance["predictions_sha256"]),
    ]
    for index, (label, digest) in enumerate(proof):
        y = 586 + index * 60
        text(root, 70, y, label, size=20, fill=COLORS["muted"])
        text(root, 210, y, digest, size=20)
    text(
        root,
        70,
        785,
        "主口径：NFC 后删除 Unicode 空白；NFKC 仅作诊断，不用于主成绩。",
        size=19,
        fill=COLORS["muted"],
    )
    write_svg(path, root)


def contribution_panel(
    root: ET.Element,
    title_value: str,
    rows: list[dict[str, Any]],
    top: int,
) -> None:
    left = 255
    plot_width = 1100
    text(root, 70, top, title_value, size=27, weight=500)
    text(root, 1375, top, "组内 CER", size=19, fill=COLORS["muted"])
    for tick in range(0, 101, 20):
        x = left + plot_width * tick / 100
        line(root, x, top + 35, x, top + 65 + len(rows) * 92, COLORS["grid"], 1)
        text(root, x, top + 28, f"{tick}%", size=17, fill=COLORS["muted"], anchor="middle")
    for index, row in enumerate(rows):
        y = top + 65 + index * 92
        text(root, 70, y + 22, f"{row['label']}  n={row['samples']}", size=20)
        rect(root, left, y, plot_width * row["character_share"], 24, COLORS["light_blue"])
        rect(root, left, y + 32, plot_width * row["error_share"], 24, COLORS["red"])
        text(
            root,
            left + plot_width * row["character_share"] + 10,
            y + 19,
            format_share(row["character_share"]),
            size=17,
            fill=COLORS["muted"],
        )
        text(
            root,
            left + plot_width * row["error_share"] + 10,
            y + 52,
            format_share(row["error_share"]),
            size=17,
            fill=COLORS["red"],
        )
        text(root, 1450, y + 38, f"{row['cer'] * 100:.2f}%", size=20, anchor="middle")


def render_contribution(metrics: dict[str, Any], path: Path) -> None:
    root = svg_root(
        1600,
        1160,
        "评估字符与编辑错误贡献",
        "按采集场景和难度比较 GT 字符占比、总编辑错误贡献以及组内 CER。",
    )
    heading(
        root,
        "误差从哪里来：曝光量、错误贡献与组内 CER",
        "浅蓝表示该组占全部 GT 字符的比例；红色表示该组占全部编辑错误的比例；每组错误贡献之和为 100%",
    )
    rect(root, 70, 165, 34, 16, COLORS["light_blue"])
    text(root, 116, 180, "GT 字符占比", size=18)
    rect(root, 280, 165, 34, 16, COLORS["red"])
    text(root, 326, 180, "编辑错误贡献", size=18)

    contribution_panel(root, "按采集场景", metrics["breakdowns"]["scene"], 245)
    line(root, 70, 675, 1530, 675, COLORS["grid"], 2)
    contribution_panel(root, "按难度", metrics["breakdowns"]["difficulty"], 730)
    write_svg(path, root)


def render_distribution(metrics: dict[str, Any], path: Path) -> None:
    rows = metrics["ned_distribution"]
    root = svg_root(
        1600,
        900,
        "逐样本 NED 分布与错误贡献",
        "每个 NED 区间同时展示样本占比和其贡献的编辑错误占比。",
    )
    heading(
        root,
        "均值背后的分布：多少样本、贡献多少错误",
        "同一 NED 区间内，蓝色为样本占比，红色为编辑错误贡献；错误贡献按编辑距离计算",
    )
    left = 300
    plot_width = 1150
    for tick in range(0, 101, 20):
        x = left + plot_width * tick / 100
        line(root, x, 190, x, 805, COLORS["grid"], 1)
        text(root, x, 178, f"{tick}%", size=17, fill=COLORS["muted"], anchor="middle")
    for index, row in enumerate(rows):
        y = 220 + index * 96
        text(root, 70, y + 24, f"{row['label']}  n={row['samples']}", size=21)
        rect(root, left, y, plot_width * row["sample_share"], 25, COLORS["blue"])
        rect(root, left, y + 35, plot_width * row["error_share"], 25, COLORS["red"])
        text(
            root,
            left + plot_width * row["sample_share"] + 10,
            y + 20,
            f"样本 {row['sample_share'] * 100:.1f}%",
            size=17,
        )
        text(
            root,
            left + plot_width * row["error_share"] + 10,
            y + 55,
            f"错误 {row['error_share'] * 100:.1f}%",
            size=17,
            fill=COLORS["red"],
        )
    write_svg(path, root)


def render_figures(metrics: dict[str, Any], figure_dir: Path) -> None:
    render_overview(metrics, figure_dir / "evaluation-final-model-overview.svg")
    render_contribution(metrics, figure_dir / "evaluation-error-contribution.svg")
    render_distribution(metrics, figure_dir / "evaluation-ned-distribution.svg")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--model-sha256")
    parser.add_argument(
        "--metrics",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs" / "evaluation_metrics.json",
    )
    parser.add_argument(
        "--figure-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs" / "figures",
    )
    args = parser.parse_args()

    raw_mode = any((args.annotations, args.predictions, args.model_sha256))
    if raw_mode:
        if not all((args.annotations, args.predictions, args.model_sha256)):
            parser.error(
                "--annotations, --predictions and --model-sha256 are all required when recomputing"
            )
        metrics = compute_metrics(args.annotations, args.predictions, args.model_sha256)
        args.metrics.parent.mkdir(parents=True, exist_ok=True)
        args.metrics.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    else:
        metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    render_figures(metrics, args.figure_dir)
    print(json.dumps(metrics["overall"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
