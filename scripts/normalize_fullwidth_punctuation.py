#!/usr/bin/env python3
"""Normalize OCR labels to a full-width punctuation policy.

The script is intentionally conservative: it only rewrites punctuation in OCR
target text, leaving Yi, Han, Latin letters, and digits unchanged.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


FULLWIDTH_MAP = {
    "!": "！",
    "?": "？",
    ",": "，",
    ";": "；",
    ":": "：",
    "/": "／",
    "\\": "＼",
    "-": "－",
    "(": "（",
    ")": "）",
    "[": "［",
    "]": "］",
    "{": "｛",
    "}": "｝",
    "<": "＜",
    ">": "＞",
    "+": "＋",
    "=": "＝",
    "*": "＊",
    "#": "＃",
    "%": "％",
    "&": "＆",
    "@": "＠",
    "~": "～",
    "_": "＿",
    "|": "｜",
    "$": "＄",
    "^": "＾",
    '"': "＂",
    "'": "＇",
    "`": "｀",
}

ASCII_PUNCT_RE = re.compile(r"""[!"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~]""")


def normalize_fullwidth_punctuation(text: str) -> str:
    """Return text with ASCII punctuation normalized to full-width forms."""

    # Preserve the conventional Chinese ellipsis when source text uses ASCII.
    text = text.replace("...", "……")
    text = text.replace("--", "——")

    chars: list[str] = []
    for i, ch in enumerate(text):
        if ch == ".":
            prev_ch = text[i - 1] if i else ""
            next_ch = text[i + 1] if i + 1 < len(text) else ""
            if prev_ch.isascii() and prev_ch.isalnum() and next_ch.isascii() and next_ch.isalnum():
                chars.append("．")
            else:
                chars.append("。")
        else:
            chars.append(FULLWIDTH_MAP.get(ch, ch))

    normalized = "".join(chars)
    # OCR labels should not contain cosmetic spaces around full-width separators.
    normalized = re.sub(r"[ \t]+([／：；，。！？）］｝】》〉、])", r"\1", normalized)
    normalized = re.sub(r"([／：；，。！？（［｛【《〈、])[ \t]+", r"\1", normalized)
    return normalized


def assistant_content(row: dict[str, Any]) -> str | None:
    messages = row.get("messages")
    if isinstance(messages, list) and messages:
        last = messages[-1]
        if isinstance(last, dict) and last.get("role") == "assistant":
            content = last.get("content")
            return content if isinstance(content, str) else None
    return None


def set_assistant_content(row: dict[str, Any], value: str) -> None:
    row["messages"][-1]["content"] = value


def normalize_jsonl(in_path: Path, out_path: Path) -> dict[str, Any]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = changed = 0
    char_changes: Counter[tuple[str, str]] = Counter()
    with in_path.open("r", encoding="utf-8") as fin, out_path.open("w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            rows += 1
            row = json.loads(line)
            fields: list[tuple[str, str]] = []

            content = assistant_content(row)
            if content is not None:
                fields.append(("messages[-1].content", content))
            for key in ("label", "answer"):
                value = row.get(key)
                if isinstance(value, str):
                    fields.append((key, value))

            row_changed = False
            for field, value in fields:
                normalized = normalize_fullwidth_punctuation(value)
                if normalized != value:
                    row_changed = True
                    for before, after in zip(value, normalized):
                        if before != after:
                            char_changes[(before, after)] += 1
                    if len(value) != len(normalized):
                        char_changes[("<len_changed>", f"{len(value)}->{len(normalized)}")] += 1
                    if field == "messages[-1].content":
                        set_assistant_content(row, normalized)
                    else:
                        row[field] = normalized

            if row_changed:
                changed += 1
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {
        "input": str(in_path),
        "output": str(out_path),
        "rows": rows,
        "changed_rows": changed,
        "char_changes": [{"from": k[0], "to": k[1], "count": v} for k, v in char_changes.most_common()],
    }


def normalize_csv(in_path: Path, out_path: Path) -> dict[str, Any]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = changed = 0
    with in_path.open("r", encoding="utf-8-sig", newline="") as fin:
        reader = csv.DictReader(fin)
        fieldnames = reader.fieldnames or []
        with out_path.open("w", encoding="utf-8", newline="") as fout:
            writer = csv.DictWriter(fout, fieldnames=fieldnames)
            writer.writeheader()
            for row in reader:
                rows += 1
                row_changed = False
                for key in ("gt", "label", "text", "content"):
                    if key in row and row[key]:
                        new_value = normalize_fullwidth_punctuation(row[key])
                        if new_value != row[key]:
                            row[key] = new_value
                            row_changed = True
                if row_changed:
                    changed += 1
                writer.writerow(row)
    return {"input": str(in_path), "output": str(out_path), "rows": rows, "changed_rows": changed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    if args.input.suffix == ".jsonl":
        report = normalize_jsonl(args.input, args.output)
    elif args.input.suffix == ".csv":
        report = normalize_csv(args.input, args.output)
    else:
        raise SystemExit(f"Unsupported file type: {args.input}")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
