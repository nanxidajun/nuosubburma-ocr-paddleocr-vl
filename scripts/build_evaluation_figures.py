#!/usr/bin/env python3
"""Recompute the frozen final-model NED analysis and render public SVG figures."""

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

SAMPLE_TYPE_LABELS = {
    "page": "整页",
    "region": "区域",
}

COLORS = {
    "ink": "#1F2933",
    "muted": "#5F6B76",
    "grid": "#D9E0E6",
    "blue": "#315F7D",
    "green": "#2F766D",
    "mint": "#70A99E",
    "amber": "#B27A2D",
    "red": "#A13A32",
    "purple": "#73556F",
    "white": "#FFFFFF",
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


def keep_yi(text: str) -> str:
    return "".join(ch for ch in text if 0xA000 <= ord(ch) <= 0xA48C)


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
    output: list[dict[str, Any]] = []
    for value in labels:
        metrics = summarize(groups[value])
        metrics.update(
            {
                "key": value,
                "label": labels[value],
            }
        )
        output.append(metrics)
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
        yi_gt = keep_yi(gt)
        yi_pred = keep_yi(pred)
        yi_distance, yi_ned = normalized_distance(yi_pred, yi_gt)
        meta = annotation.get("meta") or {}
        if not isinstance(meta, dict):
            raise ValueError(f"annotation {sample_id}: meta must be an object")
        scene = meta.get("scene")
        difficulty = meta.get("difficulty")
        sample_type = meta.get("sample_type")
        if (
            scene not in SCENE_LABELS
            or difficulty not in DIFFICULTY_LABELS
            or sample_type not in SAMPLE_TYPE_LABELS
        ):
            raise ValueError(
                f"annotation {sample_id}: unsupported scene/difficulty/sample_type "
                f"{scene}/{difficulty}/{sample_type}"
            )
        scored.append(
            {
                "id": sample_id,
                "scene": scene,
                "difficulty": difficulty,
                "sample_type": sample_type,
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
                "yi_gt_characters": len(yi_gt),
                "yi_prediction_characters": len(yi_pred),
                "yi_edit_distance": yi_distance,
                "yi_ned": yi_ned,
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
            "primary": "mean per-sample NED after NFC normalization and Unicode-whitespace removal",
            "normalization": "NFC, then remove all Unicode whitespace",
            "secondary": "corpus CER = sum Levenshtein distance / sum GT code points",
            "diagnostic": "NFKC results are diagnostic only because compatibility normalization can fold OCR-significant symbols",
        },
        "provenance": {
            "model_weight_sha256": model_sha256,
            "annotations_sha256": sha256_file(annotations_path),
            "predictions_sha256": sha256_file(predictions_path),
            "alignment": "unique image SHA-256; all 1,030 image hashes matched exactly",
        },
        "overall": overall,
        "character_slices": {
            "yi": {
                "gt_characters": sum(row["yi_gt_characters"] for row in scored),
                "prediction_characters": sum(
                    row["yi_prediction_characters"] for row in scored
                ),
                "edit_distance": sum(row["yi_edit_distance"] for row in scored),
                "cer": sum(row["yi_edit_distance"] for row in scored)
                / sum(row["yi_gt_characters"] for row in scored),
                "mean_sample_ned": sum(row["yi_ned"] for row in scored)
                / len(scored),
            }
        },
        "breakdowns": {
            "scene": build_breakdown(scored, "scene", SCENE_LABELS),
            "difficulty": build_breakdown(
                scored, "difficulty", DIFFICULTY_LABELS
            ),
            "book_scan_sample_type": build_breakdown(
                [row for row in scored if row["scene"] == "book_scan"],
                "sample_type",
                SAMPLE_TYPE_LABELS,
            ),
        },
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


def write_svg(path: Path, root: ET.Element) -> None:
    ET.indent(root, space="  ")
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def overview_panel(
    root: ET.Element,
    title_value: str,
    rows: list[dict[str, Any]],
    *,
    left: int,
    top: int,
    width: int,
    colors: list[str],
) -> None:
    label_width = 180
    plot_left = left + label_width
    plot_width = width - label_width - 80
    text(root, left, top, title_value, size=27, weight=500)
    for tick in (0.0, 0.05, 0.10, 0.15, 0.20):
        x = plot_left + plot_width * tick / 0.22
        line(root, x, top + 35, x, top + 75 + len(rows) * 82, COLORS["grid"], 1)
        text(root, x, top + 28, f"{tick:.2f}", size=16, fill=COLORS["muted"], anchor="middle")
    for index, (row, color) in enumerate(zip(rows, colors)):
        y = top + 70 + index * 82
        text(root, left, y + 25, f"{row['label']}  n={row['samples']}", size=19)
        bar_width = plot_width * row["mean_sample_ned"] / 0.22
        rect(root, plot_left, y, bar_width, 34, color)
        text(
            root,
            plot_left + bar_width + 10,
            y + 25,
            f"{row['mean_sample_ned']:.4f}",
            size=18,
        )


def render_performance_overview(metrics: dict[str, Any], path: Path) -> None:
    overall = metrics["overall"]
    yi = metrics["character_slices"]["yi"]
    root = svg_root(
        1600,
        1120,
        "最终模型总体、场景与难度 NED",
        "展示总彝文 NED、去空白平均 NED、原始平均 NED、完全正确样本的场景构成，以及按采集场景和难度划分的平均 NED。",
    )
    heading(
        root,
        "最终模型表现：总体、场景与难度",
        "1,030 张真实图片；NED 越低越好；场景与难度使用同一条 0-0.22 横轴",
    )

    columns = [80, 565, 1050]
    labels = ["总彝文 NED", "去空白平均 NED", "原始平均 NED"]
    values = [
        f"{yi['mean_sample_ned']:.4f}",
        f"{overall['mean_sample_ned']:.4f}",
        f"{overall['raw_mean_sample_ned']:.4f}",
    ]
    notes = ["只保留规范彝文字符", "忽略空格与换行差异", "保留模型原始输出格式"]
    accents = [COLORS["purple"], COLORS["blue"], COLORS["amber"]]
    for x, label, value, note, accent in zip(columns, labels, values, notes, accents):
        rect(root, x, 195, 8, 155, accent, 0)
        text(root, x + 28, 230, label, size=22, weight=500)
        text(root, x + 28, 300, value, size=48, fill=accent, weight=500)
        text(root, x + 28, 338, note, size=18, fill=COLORS["muted"])

    line(root, 70, 385, 1530, 385, COLORS["grid"], 2)

    scene_rows = {row["key"]: row for row in metrics["breakdowns"]["scene"]}
    book_type_rows = {
        row["key"]: row for row in metrics["breakdowns"]["book_scan_sample_type"]
    }
    exact_total = overall["exact_matches"]
    exact_groups = [
        (book_type_rows["page"]["exact_matches"], COLORS["green"]),
        (book_type_rows["region"]["exact_matches"], COLORS["mint"]),
        (scene_rows["real_screen_photo"]["exact_matches"], COLORS["amber"]),
        (scene_rows["phone_handwritten"]["exact_matches"], COLORS["red"]),
        (scene_rows["real_photo"]["exact_matches"], COLORS["blue"]),
    ]
    text(root, 70, 435, f"完全正确 {exact_total} 张的场景构成", size=23, weight=500)
    stack_left = 450
    stack_top = 405
    stack_width = 840
    cursor = stack_left
    for count, color in exact_groups:
        segment_width = stack_width * count / exact_total
        if segment_width:
            rect(root, cursor, stack_top, segment_width, 34, color, 0)
        cursor += segment_width
    text(
        root,
        450,
        468,
        "书籍整页 54（16.2%） · 书籍区域 228（68.5%） · 屏幕拍摄 45（13.5%） · 手写 0 · 实景 6（1.8%）",
        size=18,
    )
    text(
        root,
        450,
        495,
        "书籍整页完全正确率 54/437（12.4%）；书籍区域 228/350（65.1%）。构成受原始样本量影响。",
        size=17,
        fill=COLORS["muted"],
    )

    line(root, 70, 520, 1530, 520, COLORS["grid"], 2)
    overview_panel(
        root,
        "采集场景",
        metrics["breakdowns"]["scene"],
        left=70,
        top=575,
        width=725,
        colors=[COLORS["green"], COLORS["amber"], COLORS["red"], COLORS["blue"]],
    )
    overview_panel(
        root,
        "难度",
        metrics["breakdowns"]["difficulty"],
        left=835,
        top=575,
        width=695,
        colors=[COLORS["green"], COLORS["amber"], COLORS["red"]],
    )
    write_svg(path, root)


def render_figures(metrics: dict[str, Any], figure_dir: Path) -> None:
    render_performance_overview(
        metrics, figure_dir / "evaluation-performance-overview.svg"
    )


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
