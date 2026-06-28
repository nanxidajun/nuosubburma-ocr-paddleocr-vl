#!/usr/bin/env python3
"""本地单图 OCR demo：加载已下载模型，识别一张规范彝文图片。"""

from __future__ import annotations

import argparse
import base64
import html
import io
import importlib.util
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = REPO_ROOT / "models" / "NuosuBburma-OCR"
DEFAULT_IMAGE = REPO_ROOT / "demo" / "sample_images" / "mixed_line.png"


def resolve_path(path_text: str | None, default_path: Path) -> Path:
    if not path_text:
        return default_path
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def list_sample_images() -> str:
    sample_dir = REPO_ROOT / "demo" / "sample_images"
    samples = sorted(path.relative_to(REPO_ROOT) for path in sample_dir.glob("*") if path.is_file())
    return "\n".join(f"- {sample}" for sample in samples)


def fail(message: str, exit_code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(exit_code)


def load_runtime():
    module_checks = [
        ("paddle", "PaddlePaddle"),
        ("PIL", "Pillow"),
        ("paddleformers", "paddleformers"),
    ]
    missing = [dist_name for module_name, dist_name in module_checks if importlib.util.find_spec(module_name) is None]
    if missing:
        fail(
            "缺少 demo 运行依赖：{}\n\n"
            "请先在仓库根目录安装依赖：\n"
            "python -m pip install -r requirements.txt\n\n"
            "如果还没有安装 PaddlePaddle，请先按 requirements.txt 顶部说明安装。".format(", ".join(missing))
        )

    try:
        import paddle
        from PIL import Image, ImageOps
        from paddleformers.generation import GenerationConfig
        from paddleformers.transformers import AutoModelForConditionalGeneration, AutoProcessor
    except ImportError as exc:
        fail(
            "缺少 demo 运行依赖：{}\n\n"
            "请先在仓库根目录安装依赖：\n"
            "python -m pip install -r requirements.txt\n\n"
            "如果还没有安装 PaddlePaddle，请先按 requirements.txt 顶部说明安装。".format(exc.name)
        )

    return paddle, Image, ImageOps, GenerationConfig, AutoModelForConditionalGeneration, AutoProcessor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="本地单图 OCR demo。默认读取 models/NuosuBburma-OCR 和 demo/sample_images/mixed_line.png。"
    )
    parser.add_argument("--model", default=None, help="模型目录，默认 models/NuosuBburma-OCR")
    parser.add_argument("--image", default=None, help="输入图片，默认 demo/sample_images/mixed_line.png")
    parser.add_argument("--prompt", default="<image>OCR:", help="推理提示词，默认 <image>OCR:")
    parser.add_argument("--max-new-tokens", type=int, default=1024, help="最大输出 token 数，默认 1024")
    parser.add_argument("--max-image-side", type=int, default=2400, help="输入图片长边压缩上限，默认 2400；设为 0 保留原图")
    parser.add_argument("--device", default="gpu", help="推理设备，默认 gpu")
    parser.add_argument("--output", default=None, help="可选：把识别文本写入指定 txt 文件")
    parser.add_argument("--html-output", default=None, help="可选：生成带图片和识别文本的 HTML 预览")
    return parser.parse_args()


def check_inputs(model_path: Path, image_path: Path) -> None:
    if not image_path.exists():
        fail(
            f"找不到输入图片：{image_path}\n\n"
            "仓库内可用样例图：\n"
            f"{list_sample_images()}"
        )
    if not image_path.is_file():
        fail(f"输入图片不是文件：{image_path}")

    if not model_path.exists():
        fail(
            f"找不到模型目录：{model_path}\n\n"
            "请先下载 Hugging Face 模型：\n"
            "hf download nanxidajun/NuosuBburma-OCR \\\n"
            "  --repo-type model \\\n"
            f"  --local-dir \"{model_path}\"\n\n"
            "国内网络较慢时，可先设置：\n"
            "export HF_ENDPOINT=https://hf-mirror.com"
        )
    if not model_path.is_dir():
        fail(f"模型路径不是目录：{model_path}")
    if not (model_path / "config.json").exists():
        fail(f"模型目录缺少 config.json：{model_path}")


def set_flashmask_if_available(model) -> None:
    if hasattr(model, "config"):
        model.config._attn_implementation = "flashmask"
    if hasattr(model, "visual") and hasattr(model.visual, "config"):
        model.visual.config._attn_implementation = "flashmask"


def resize_for_inference(image, image_module, image_ops, max_side: int):
    image = image_ops.exif_transpose(image).convert("RGB")
    if max_side <= 0:
        return image
    width, height = image.size
    long_side = max(width, height)
    if long_side <= max_side:
        return image
    scale = max_side / long_side
    return image.resize(
        (max(1, int(width * scale)), max(1, int(height * scale))),
        image_module.Resampling.LANCZOS,
    )


def write_output(output_path_text: str | None, text: str) -> None:
    if not output_path_text:
        return
    output_path = resolve_path(output_path_text, REPO_ROOT / "outputs" / "demo_result.txt")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text + "\n", encoding="utf-8")
    print(f"\n已写入：{output_path}")


def image_data_uri(image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def write_html_output(
    output_path_text: str | None,
    *,
    text: str,
    preview_image,
    image_path: Path,
    model_path: Path,
    prompt: str,
    device: str,
    max_new_tokens: int,
    max_image_side: int,
) -> None:
    if not output_path_text:
        return

    output_path = resolve_path(output_path_text, REPO_ROOT / "outputs" / "demo_result.html")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    escaped_text = html.escape(text)
    size_note = (
        f"输入图片超过长边限制 {max_image_side} 时，会先等比例压缩后再进入 OCR；原始文件不会被修改。"
        if max_image_side > 0
        else "当前未启用长边压缩限制。"
    )
    doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NuosuBburma OCR demo</title>
  <style>
    :root {{
      --bg: #f6f0df;
      --ink: #221f1a;
      --muted: #6e6658;
      --card: #fffaf0;
      --line: #dacdb8;
      --accent: #9a4b2f;
    }}
    body {{
      margin: 0;
      background: radial-gradient(circle at top left, #fff7df 0, var(--bg) 36%, #e9dfcc 100%);
      color: var(--ink);
      font-family: "Songti SC", "Noto Serif CJK SC", serif;
    }}
    main {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 36px 20px 48px;
    }}
    header {{
      margin-bottom: 22px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 30px;
      letter-spacing: 0.02em;
    }}
    .sub {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(320px, 0.9fr);
      gap: 18px;
      align-items: start;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: 0 18px 42px rgba(65, 48, 28, 0.14);
      overflow: hidden;
    }}
    .card h2 {{
      margin: 0;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      color: var(--accent);
      font-size: 17px;
    }}
    .image-wrap {{
      padding: 14px;
      background: #2a241d;
    }}
    img {{
      display: block;
      width: 100%;
      max-height: 720px;
      object-fit: contain;
      border-radius: 10px;
      background: white;
    }}
    pre {{
      margin: 0;
      padding: 16px;
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.8;
      font-size: 18px;
      font-family: "Kaiti SC", "Songti SC", "Noto Serif CJK SC", serif;
    }}
    dl {{
      display: grid;
      grid-template-columns: 120px minmax(0, 1fr);
      gap: 8px 12px;
      margin: 0;
      padding: 14px 16px 18px;
      font-size: 13px;
    }}
    dt {{
      color: var(--muted);
    }}
    dd {{
      margin: 0;
      overflow-wrap: anywhere;
    }}
    @media (max-width: 820px) {{
      .grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>NuosuBburma OCR 单图 demo</h1>
      <p class="sub">输入图片与模型输出并排展示，便于快速复核。</p>
      <p class="sub">{html.escape(size_note)}</p>
    </header>
    <section class="grid">
      <article class="card">
        <h2>输入图片</h2>
        <div class="image-wrap">
          <img src="{image_data_uri(preview_image)}" alt="input image">
        </div>
      </article>
      <article class="card">
        <h2>识别结果</h2>
        <pre>{escaped_text}</pre>
      </article>
    </section>
    <section class="card" style="margin-top: 18px;">
      <h2>运行信息</h2>
      <dl>
        <dt>生成时间</dt><dd>{html.escape(generated_at)}</dd>
        <dt>模型目录</dt><dd>{html.escape(str(model_path))}</dd>
        <dt>输入图片</dt><dd>{html.escape(str(image_path))}</dd>
        <dt>提示词</dt><dd>{html.escape(prompt)}</dd>
        <dt>推理设备</dt><dd>{html.escape(device)}</dd>
        <dt>最大 token</dt><dd>{max_new_tokens}</dd>
        <dt>长边限制</dt><dd>{html.escape(str(max_image_side if max_image_side > 0 else "不压缩"))}</dd>
      </dl>
    </section>
  </main>
</body>
</html>
"""
    output_path.write_text(doc, encoding="utf-8")
    print(f"HTML 预览：{output_path}")


def main() -> None:
    args = parse_args()
    model_path = resolve_path(args.model, DEFAULT_MODEL)
    image_path = resolve_path(args.image, DEFAULT_IMAGE)

    check_inputs(model_path, image_path)
    paddle, Image, ImageOps, GenerationConfig, AutoModelForConditionalGeneration, AutoProcessor = load_runtime()

    paddle.set_device(args.device)

    image = resize_for_inference(Image.open(image_path), Image, ImageOps, args.max_image_side)

    processor = AutoProcessor.from_pretrained(str(model_path))
    model = AutoModelForConditionalGeneration.from_pretrained(str(model_path), convert_from_hf=True)
    set_flashmask_if_available(model)
    model.eval()

    query = args.prompt.replace("<image>", "")
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
    generation_config = GenerationConfig(
        do_sample=False,
        bos_token_id=1,
        eos_token_id=2,
        pad_token_id=0,
        use_cache=True,
    )
    with paddle.no_grad():
        outputs = model.generate(
            **inputs,
            generation_config=generation_config,
            max_new_tokens=args.max_new_tokens,
        )
    output_ids = outputs[0].tolist()[0]
    text = processor.decode(output_ids, skip_special_tokens=True).strip()

    print("模型目录：", model_path)
    print("输入图片：", image_path)
    print("图片长边限制：", args.max_image_side)
    print("推理设备：", args.device)
    print("\n识别结果：")
    print(text)
    write_output(args.output, text)
    write_html_output(
        args.html_output,
        text=text,
        preview_image=image,
        image_path=image_path,
        model_path=model_path,
        prompt=args.prompt,
        device=args.device,
        max_new_tokens=args.max_new_tokens,
        max_image_side=args.max_image_side,
    )


if __name__ == "__main__":
    main()
