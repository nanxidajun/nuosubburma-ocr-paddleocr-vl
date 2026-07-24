from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import gradio as gr
from huggingface_hub import snapshot_download
from PIL import Image, ImageOps


DEFAULT_MODEL_ID = "nanxidajun/NuosuBburma-OCR"
DEFAULT_MODEL_REVISION = "12352adb52a26a3bcab0b5c38e42252009a3c12d"

MODEL_ID = os.environ.get("MODEL_ID", DEFAULT_MODEL_ID).strip()
MODEL_DIR = os.environ.get("MODEL_DIR", "").strip()
MODEL_REVISION = os.environ.get(
    "MODEL_REVISION",
    DEFAULT_MODEL_REVISION if MODEL_ID == DEFAULT_MODEL_ID else "",
).strip()
PADDLE_DEVICE = os.environ.get("PADDLE_DEVICE", "gpu").strip().lower()


def read_int_env(name: str, default: int, *, minimum: int) -> int:
    raw_value = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} 必须是整数，当前值为：{raw_value!r}") from exc
    if value < minimum:
        raise RuntimeError(f"{name} 不能小于 {minimum}，当前值为：{value}")
    return value


MAX_NEW_TOKENS = read_int_env("MAX_NEW_TOKENS", 2048, minimum=1)
MAX_IMAGE_SIDE = read_int_env("MAX_IMAGE_SIDE", 2400, minimum=0)
MAX_IMAGE_SIDE_DISPLAY = f"{MAX_IMAGE_SIDE}px" if MAX_IMAGE_SIDE > 0 else "不缩放"


def resize_for_space(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    if MAX_IMAGE_SIDE <= 0:
        return image
    width, height = image.size
    long_side = max(width, height)
    if long_side <= MAX_IMAGE_SIDE:
        return image
    scale = MAX_IMAGE_SIDE / long_side
    return image.resize(
        (max(1, int(width * scale)), max(1, int(height * scale))),
        Image.Resampling.LANCZOS,
    )


def require_gpu(paddle) -> str:
    if PADDLE_DEVICE != "gpu" and not PADDLE_DEVICE.startswith("gpu:"):
        raise RuntimeError(
            "本 Space 模板只支持 GPU。请在 Hugging Face Space 中选择 GPU 硬件，"
            "并把 PADDLE_DEVICE 设为 gpu 或 gpu:0。"
        )
    if not paddle.is_compiled_with_cuda():
        raise RuntimeError(
            "当前 PaddlePaddle 不支持 CUDA。请安装 requirements.txt 中锁定的 "
            "paddlepaddle-gpu。"
        )
    if paddle.device.cuda.device_count() < 1:
        raise RuntimeError("未检测到 CUDA GPU。请先为 Space 选择 L4、A10G 或其他 GPU 硬件。")
    return PADDLE_DEVICE


@lru_cache(maxsize=1)
def load_ocr_model():
    try:
        import paddle
        from paddleformers.generation import GenerationConfig
        from paddleformers.transformers import (
            AutoModelForConditionalGeneration,
            AutoProcessor,
        )
    except Exception as exc:  # pragma: no cover - depends on the Space image
        raise RuntimeError(
            "OCR 依赖未加载成功。请确认 requirements.txt 已完整安装。"
        ) from exc

    device = require_gpu(paddle)

    if MODEL_DIR:
        local_model_dir = Path(MODEL_DIR).expanduser()
        if not local_model_dir.is_dir():
            raise RuntimeError(f"本地模型目录不存在：{local_model_dir}")
        if not (local_model_dir / "config.json").is_file():
            raise RuntimeError(f"本地模型目录缺少 config.json：{local_model_dir}")
        model_dir = str(local_model_dir.resolve())
    else:
        if not MODEL_REVISION:
            raise RuntimeError(
                "使用远程模型时必须设置 MODEL_REVISION；请使用固定 commit，不要加载浮动版本。"
            )
        model_dir = snapshot_download(
            repo_id=MODEL_ID,
            repo_type="model",
            revision=MODEL_REVISION,
        )

    paddle.set_device(device)
    processor = AutoProcessor.from_pretrained(model_dir)
    model = AutoModelForConditionalGeneration.from_pretrained(
        model_dir,
        convert_from_hf=True,
    )
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


def run_ocr_on_pil(image: Image.Image) -> str:
    paddle, model, processor, generation_config = load_ocr_model()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
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


def run_demo(image):
    if image is None:
        return "请先上传图片。", ""
    try:
        text = run_ocr_on_pil(resize_for_space(image))
    except Exception as exc:
        return f"OCR 推理失败：{exc}", ""
    if not text:
        return "OCR 已完成，但结果为空。", ""
    return "OCR 已完成。", text


with gr.Blocks(title="NuosuBburma OCR Demo") as demo:
    gr.Markdown(
        """
# NuosuBburma OCR Demo

上传规范彝文、汉字或混排图片，整张图片会直接进入 OCR。
        """.strip()
    )
    input_image = gr.Image(
        label=f"输入图片（长边超过 {MAX_IMAGE_SIDE_DISPLAY} 时等比缩小，不裁剪）",
        type="pil",
        sources=["upload"],
    )
    run_button = gr.Button("开始识别", variant="primary")
    status = gr.Textbox(label="处理状态", interactive=False)
    result = gr.Textbox(label="OCR 结果", lines=16)
    run_button.click(
        run_demo,
        inputs=[input_image],
        outputs=[status, result],
    )


if __name__ == "__main__":
    demo.launch()
