from __future__ import annotations

import json
import os
import tempfile
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import gradio as gr
from huggingface_hub import snapshot_download
from PIL import Image, ImageOps


MODEL_ID = os.environ.get("MODEL_ID", "nanxidajun/NuosuBburma-OCR")
MODEL_DIR = os.environ.get("MODEL_DIR", "").strip()
DEFAULT_DEVICE = os.environ.get("PADDLE_DEVICE", "gpu")
LAYOUT_MODEL_NAME = os.environ.get("LAYOUT_MODEL_NAME", "PP-DocLayout_plus-L")
LAYOUT_THRESHOLD = float(os.environ.get("LAYOUT_THRESHOLD", "0.25"))
MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", "1024"))
MAX_LAYOUT_OCR_UNITS = int(os.environ.get("MAX_LAYOUT_OCR_UNITS", "32"))
MAX_IMAGE_SIDE_ENV = os.environ.get("MAX_IMAGE_SIDE", "2400")
MAX_IMAGE_SIDE = int(MAX_IMAGE_SIDE_ENV)
SPACE_DIR = Path(__file__).resolve().parent
MAX_IMAGE_SIDE_DISPLAY = "2400px" if MAX_IMAGE_SIDE_ENV == "2400" else (f"{MAX_IMAGE_SIDE}px" if MAX_IMAGE_SIDE > 0 else "不压缩")
UI_VERSION = "space-ui-20260629-2400-label-only"
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


@dataclass
class LayoutBlock:
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
    def caption(self) -> str:
        score_text = "" if self.score is None else f" score={self.score:.3f}"
        route_text = ROUTE_LABEL_ZH.get(self.route or "skip", self.route or "跳过")
        return f"{self.index:02d} · {route_text} · {self.label}{score_text}"


def resize_for_space(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    if MAX_IMAGE_SIDE <= 0:
        return image
    w, h = image.size
    long_side = max(w, h)
    if long_side <= MAX_IMAGE_SIDE:
        return image
    scale = MAX_IMAGE_SIDE / long_side
    return image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)


def yi_romanization(ch: str) -> str | None:
    name = unicodedata.name(ch, "")
    prefix = "YI SYLLABLE "
    if not name.startswith(prefix):
        return None
    return name[len(prefix) :].lower()


def pronunciation_text(text: str) -> str:
    out: list[str] = []

    def append_token(token: str) -> None:
        if out and out[-1] not in {" ", "\n"}:
            out.append(" ")
        out.append(token)

    for ch in text:
        roman = yi_romanization(ch)
        if roman:
            append_token(roman)
        elif ch == "\n":
            out.append("\n")
        elif ch.isspace():
            if out and out[-1] not in {" ", "\n"}:
                out.append(" ")
        else:
            out.append(ch)

    result = "".join(out)
    for punct in "，。；：、！？,.!?;:)）】』」》":
        result = result.replace(f" {punct}", punct)
    return "\n".join(line.strip() for line in result.splitlines())


def inline_pronunciation(text: str) -> str:
    parts: list[str] = []
    for ch in text:
        roman = yi_romanization(ch)
        parts.append(f"{ch}({roman})" if roman else ch)
    return "".join(parts)


@lru_cache(maxsize=1)
def load_ocr_model():
    try:
        import paddle
        from paddleformers.generation import GenerationConfig
        from paddleformers.transformers import AutoModelForConditionalGeneration, AutoProcessor
    except Exception as exc:  # pragma: no cover - runtime diagnostics for Space
        raise RuntimeError("OCR 依赖未加载成功。请确认 Space 已安装 PaddlePaddle 和 PaddleFormers。") from exc

    if MODEL_DIR:
        local_model_dir = Path(MODEL_DIR).expanduser()
        if not local_model_dir.exists():
            raise RuntimeError(f"本地模型目录不存在：{local_model_dir}")
        if not (local_model_dir / "config.json").exists():
            raise RuntimeError(f"本地模型目录缺少 config.json：{local_model_dir}")
        model_dir = str(local_model_dir.resolve())
    else:
        model_dir = snapshot_download(repo_id=MODEL_ID, repo_type="model")

    paddle.set_device(DEFAULT_DEVICE)

    processor = AutoProcessor.from_pretrained(model_dir)
    model = AutoModelForConditionalGeneration.from_pretrained(model_dir, convert_from_hf=True)
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
    return paddle, model, processor, generation_config


@lru_cache(maxsize=1)
def load_layout_model():
    try:
        from paddleocr import LayoutDetection
    except Exception as exc:  # pragma: no cover - runtime diagnostics for Space
        raise RuntimeError("PP-DocLayout 依赖未加载成功。请确认 Space 已安装 PaddleOCR 3.4.0。") from exc

    kwargs: dict[str, Any] = {
        "model_name": LAYOUT_MODEL_NAME,
        "threshold": LAYOUT_THRESHOLD,
    }
    if DEFAULT_DEVICE:
        kwargs["device"] = DEFAULT_DEVICE
    return LayoutDetection(**kwargs)


def run_ocr_on_pil(image: Image.Image) -> str:
    paddle, model, processor, generation_config = load_ocr_model()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image.convert("RGB")},
                {"type": "text", "text": "OCR:"},
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
            max_new_tokens=MAX_NEW_TOKENS,
        )
    output_ids = outputs[0].tolist()[0]
    return processor.decode(output_ids, skip_special_tokens=True).strip()


def run_single_ocr(image):
    if image is None:
        return "请先上传图片。", "", ""
    try:
        resized = resize_for_space(image)
        text = run_ocr_on_pil(resized)
    except Exception as exc:
        return f"OCR 推理失败：{exc}", "", ""
    return text, pronunciation_text(text), inline_pronunciation(text)


def result_to_dict(res) -> dict[str, Any]:
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


def collect_layout_blocks(image: Image.Image) -> list[LayoutBlock]:
    layout_model = load_layout_model()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "page.png"
        image.save(path)
        outputs = layout_model.predict(str(path))

        blocks: list[LayoutBlock] = []
        for res in outputs:
            data = result_to_dict(res)
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
                        index=len(blocks) + 1,
                        label=label,
                        route=route_for_label(label),
                        score=score,
                        bbox=bbox,
                    )
                )
    return sorted(blocks, key=lambda item: (item.bbox[1], item.bbox[0], item.index))


def crop_text_blocks(image: Image.Image, blocks: list[LayoutBlock]) -> list[tuple[LayoutBlock, Image.Image]]:
    crops: list[tuple[LayoutBlock, Image.Image]] = []
    w, h = image.size
    for block in blocks:
        if block.route is None:
            continue
        x1, y1, x2, y2 = block.bbox
        pad = 6
        box = (max(0, x1 - pad), max(0, y1 - pad), min(w, x2 + pad), min(h, y2 + pad))
        crops.append((block, image.crop(box)))
    return sorted(crops, key=lambda item: item[0].reading_order)


def maybe_pronunciation(text: str, enabled: bool) -> str:
    if not enabled or not text.strip():
        return ""
    return pronunciation_text(text)


def build_user_status(mode: str, text: str, failed_units: int = 0, empty_units: int = 0, no_text_units: bool = False) -> str:
    issues: list[str] = []
    suggestions: list[str] = []
    intro = "异常提示：会检查空结果、局部识别失败和是否需要复跑。"
    if no_text_units:
        issues.append("页面切割后没有找到可识别的文本区域。")
        suggestions.append("建议改用“直接识别”，或换一张更清晰、边缘完整的图片。")
    if failed_units:
        issues.append("有部分区域识别失败。")
        suggestions.append("建议复跑一次；如果仍失败，优先检查图片是否过大、过暗、反光或文字被裁掉。")
    if empty_units and not text.strip():
        issues.append("OCR 结果为空。")
        suggestions.append("建议改用另一种识别方式，或重新上传更清晰的图片。")
    elif empty_units:
        issues.append("有少量区域没有返回文字。")
        suggestions.append("如果缺字明显，建议复跑或改用直接识别对照。")
    if not text.strip() and not empty_units and not no_text_units:
        issues.append("OCR 结果为空。")
        suggestions.append("建议复跑，或换用另一种识别方式。")

    if not issues:
        return "\n".join(
            [
                f"处理方式：{mode}",
                intro,
                "检查结果：未发现明显异常。",
                "复跑建议：一般不需要复跑；如果肉眼发现漏行或顺序不对，可换另一种识别方式对照。",
            ]
        )

    return "\n".join(
        [
            f"处理方式：{mode}",
            intro,
            "检查结果：" + "；".join(issues),
            "复跑建议：" + "；".join(dict.fromkeys(suggestions)),
        ]
    )


def run_demo(image, mode: str, with_pronunciation: bool):
    if image is None:
        return "请先上传图片。", "", ""

    page = resize_for_space(image)

    if mode == "直接识别":
        try:
            text = run_ocr_on_pil(page)
        except Exception as exc:
            return f"直接识别失败：{exc}", "", ""
        return (
            build_user_status("直接识别", text),
            text,
            maybe_pronunciation(text, with_pronunciation),
        )

    try:
        blocks = collect_layout_blocks(page)
    except Exception as exc:
        return f"页面切割失败：{exc}", "", ""

    crops = crop_text_blocks(page, blocks)
    if not crops:
        return build_user_status("页面切割后识别", "", no_text_units=True), "", ""

    ocr_rows: list[dict[str, Any]] = []
    for block, crop in crops[:MAX_LAYOUT_OCR_UNITS]:
        try:
            text = run_ocr_on_pil(crop)
            status = "ok"
            error = ""
        except Exception as exc:
            text = ""
            status = "error"
            error = str(exc)
        ocr_rows.append(
            {
                "id": f"block_{block.index:04d}",
                "route": block.route,
                "label": block.label,
                "bbox": block.bbox,
                "reading_order": block.reading_order,
                "text": text,
                "status": status,
                "error": error,
            }
        )

    assembled = "\n".join(row["text"] for row in sorted(ocr_rows, key=lambda row: row["reading_order"]) if row["text"].strip())
    failed_units = sum(1 for row in ocr_rows if row["status"] == "error")
    empty_units = sum(1 for row in ocr_rows if row["status"] == "ok" and not row["text"].strip())
    summary = build_user_status("页面切割后识别", assembled, failed_units=failed_units, empty_units=empty_units)

    return summary, assembled, maybe_pronunciation(assembled, with_pronunciation)


with gr.Blocks(title="NuosuBburma OCR Demo") as demo:
    gr.Markdown(
        """
# NuosuBburma OCR Demo

上传规范彝文图片，选择识别方式后得到 OCR 文本；需要注音时勾选“生成注音”。

界面版本：space-ui-20260629-2400-label-only
        """.strip()
    )
    input_image = gr.Image(
        label=f"输入图片（长边超过 {MAX_IMAGE_SIDE_DISPLAY} 会自动等比压缩，原图不改）",
        type="pil",
        sources=["upload"],
    )
    gr.Examples(
        examples=[
            str(SPACE_DIR / "sample_images" / "mixed_line.png"),
            str(SPACE_DIR / "sample_images" / "handwriting_region.jpg"),
            str(SPACE_DIR / "sample_images" / "sign_photo.jpg"),
            str(SPACE_DIR / "sample_images" / "screen_page.jpg"),
        ],
        inputs=input_image,
        label="样例图片",
        cache_examples=False,
    )

    with gr.Row():
        mode = gr.Radio(
            choices=[
                "直接识别",
                "页面切割后识别",
            ],
            value="直接识别",
            label="处理方式",
            info=f"行图、区域图和标牌可直接识别；整页和复杂混排页面建议使用“页面切割后识别”。超过长边 {MAX_IMAGE_SIDE_DISPLAY} 的图片会先等比例压缩。",
        )
        with_pronunciation = gr.Checkbox(
            label="生成注音",
            value=False,
            info="注音是 OCR 后处理，不改写 OCR 正文。",
        )
    run_button = gr.Button("开始处理", variant="primary")

    summary = gr.Textbox(
        label="异常提示",
        lines=6,
        info="用于提示 OCR 是否出现空结果、局部识别失败，以及是否建议复跑。",
    )
    text = gr.Textbox(label="OCR 结果", lines=12)
    pronunciation = gr.Textbox(label="注音结果", lines=8)

    run_button.click(
        run_demo,
        inputs=[input_image, mode, with_pronunciation],
        outputs=[summary, text, pronunciation],
    )


if __name__ == "__main__":
    demo.launch()
