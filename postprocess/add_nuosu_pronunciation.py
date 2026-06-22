#!/usr/bin/env python3
"""Add Nuosu romanization to OCR text.

The default character table is postprocess/nuosu_unicode.csv. It contains the
Unicode Yi Syllables block with a romanization column.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


TEXT_FIELDS = ("text", "answer", "ocr_text", "prediction", "pred", "label")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add Nuosu romanization to OCR result text")
    parser.add_argument("--input", type=Path, required=True, help="Input .jsonl/.json/.txt file")
    parser.add_argument("--output", type=Path, required=True, help="Output path")
    parser.add_argument(
        "--chars-csv",
        type=Path,
        default=Path(__file__).resolve().parent / "nuosu_unicode.csv",
        help="CSV with columns char and romanization",
    )
    parser.add_argument("--field", default="auto", help="Text field for JSON/JSONL. Default: auto")
    parser.add_argument(
        "--non-yi",
        choices=("keep", "drop"),
        default="keep",
        help="Whether non-Yi characters are kept in pronunciation output.",
    )
    parser.add_argument(
        "--inline-style",
        choices=("paren", "ruby"),
        default="paren",
        help="Inline annotation style for JSON output.",
    )
    return parser.parse_args()


def load_char_map(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"char", "romanization"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} missing columns: {', '.join(sorted(missing))}")
        return {
            row["char"]: row["romanization"]
            for row in reader
            if row.get("char") and row.get("romanization")
        }


def is_yi_syllable(ch: str) -> bool:
    return len(ch) == 1 and 0xA000 <= ord(ch) <= 0xA48F


def pronunciation_text(text: str, char_map: dict[str, str], non_yi: str) -> str:
    out: list[str] = []

    def append_roman(token: str) -> None:
        if out and out[-1] not in {" ", "\n"}:
            out.append(" ")
        out.append(token)

    for ch in text:
        if ch in char_map:
            append_roman(char_map[ch])
        elif ch == "\n":
            out.append("\n")
        elif ch.isspace():
            if out and out[-1] not in {" ", "\n"}:
                out.append(" ")
        elif non_yi == "keep":
            out.append(ch)
        elif is_yi_syllable(ch):
            append_roman("?")

    # Remove spaces introduced immediately before punctuation.
    result = "".join(out)
    for punct in "，。；：、！？,.!?;:)）】』」》":
        result = result.replace(f" {punct}", punct)
    return "\n".join(line.strip() for line in result.splitlines())


def inline_pronunciation(text: str, char_map: dict[str, str], style: str) -> str:
    out: list[str] = []
    for ch in text:
        roman = char_map.get(ch)
        if not roman:
            out.append(ch)
        elif style == "ruby":
            out.append(f"<ruby>{ch}<rt>{roman}</rt></ruby>")
        else:
            out.append(f"{ch}({roman})")
    return "".join(out)


def read_json_rows(path: Path) -> tuple[str, Any]:
    if path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return "jsonl", rows
    if path.suffix.lower() == ".json":
        return "json", json.loads(path.read_text(encoding="utf-8"))
    return "text", path.read_text(encoding="utf-8")


def get_text(row: dict[str, Any], field: str) -> str:
    if field != "auto":
        return "" if row.get(field) is None else str(row.get(field))
    for key in TEXT_FIELDS:
        if row.get(key) is not None:
            return str(row[key])
    return ""


def annotate_row(row: dict[str, Any], field: str, char_map: dict[str, str], non_yi: str, style: str) -> dict[str, Any]:
    text = get_text(row, field)
    return {
        **row,
        "pronunciation": pronunciation_text(text, char_map, non_yi),
        "inline_pronunciation": inline_pronunciation(text, char_map, style),
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_output(path: Path, input_kind: str, payload: Any, char_map: dict[str, str], args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if input_kind == "text":
        text = str(payload)
        out = "\n".join(
            [
                text,
                "",
                "## pronunciation",
                pronunciation_text(text, char_map, args.non_yi),
                "",
                "## inline",
                inline_pronunciation(text, char_map, args.inline_style),
            ]
        )
        path.write_text(out, encoding="utf-8")
        return

    if input_kind == "jsonl":
        rows = [annotate_row(row, args.field, char_map, args.non_yi, args.inline_style) for row in payload]
        write_jsonl(path, rows)
        return

    if isinstance(payload, list):
        rows = [annotate_row(row, args.field, char_map, args.non_yi, args.inline_style) for row in payload]
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    if isinstance(payload, dict):
        if isinstance(payload.get("rows"), list):
            payload = {
                **payload,
                "rows": [annotate_row(row, args.field, char_map, args.non_yi, args.inline_style) for row in payload["rows"]],
            }
        else:
            payload = annotate_row(payload, args.field, char_map, args.non_yi, args.inline_style)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    raise ValueError("Unsupported JSON payload")


def main() -> None:
    args = parse_args()
    char_map = load_char_map(args.chars_csv)
    input_kind, payload = read_json_rows(args.input)
    write_output(args.output, input_kind, payload, char_map, args)
    print(json.dumps({"input": str(args.input), "output": str(args.output), "chars": len(char_map)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
