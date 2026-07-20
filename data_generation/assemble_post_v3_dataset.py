#!/usr/bin/env python3
"""Assemble audited post-V3 core and addon builds into one training dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import post_v3_degradation_policy as attenuation_policy


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_VERSION = "assemble_post_v3_dataset/1.0"
FORMAL_SPEC = PROJECT_ROOT / "POST_V3_FORMAL_SPEC.json"
FORMAL_AUTHORIZATION = PROJECT_ROOT / "POST_V3_AUTHORIZATION.json"


class AssembleError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        for row in rows
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssembleError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def require_formal_authorization() -> None:
    if not FORMAL_AUTHORIZATION.is_file():
        raise AssembleError("formal post-V3 assembly lacks owner authorization")
    authorization = load_json(FORMAL_AUTHORIZATION)
    if authorization.get("phase") != "formal_build_authorized":
        raise AssembleError("post-V3 authorization phase is not formal_build_authorized")
    if authorization.get("formal_build") is not True:
        raise AssembleError("post-V3 formal build is not authorized")


def check_core_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    expected_strengths = attenuation_policy.strength_by_class()
    flagged_counts: Counter[str] = Counter()
    profiles: Counter[str] = Counter()
    ink_modes: Counter[str] = Counter()
    logical_lines: Counter[str] = Counter()
    for row in rows:
        meta = row.get("meta", {})
        granularity = str(meta.get("granularity"))
        target = str(row["messages"][1]["content"])
        line_count = len(target.splitlines())
        if granularity not in {"line", "region", "page"}:
            raise AssembleError(f"unknown core granularity: {row.get('id')}")
        if granularity == "line" and line_count != 1:
            raise AssembleError(
                f"core target line count differs for {granularity}: "
                f"{row.get('id')} has {line_count}"
            )
        if granularity == "region" and line_count < 3:
            raise AssembleError(
                f"core target line count differs for region: {row.get('id')} has {line_count}"
            )
        if granularity == "page":
            layout_data = meta.get("layout_data")
            target_line_blocks = (
                layout_data.get("target_line_block_ids")
                if isinstance(layout_data, dict)
                else None
            )
            if not isinstance(target_line_blocks, list) or line_count != len(target_line_blocks):
                raise AssembleError(
                    f"page target lines do not match positioned reading-order rows: "
                    f"{row.get('id')} has {line_count}"
                )
        logical_lines[granularity] += line_count
        degradation = meta.get("degradation")
        if not isinstance(degradation, dict):
            raise AssembleError(f"core row lacks degradation metadata: {row.get('id')}")
        profile = str(degradation.get("profile"))
        profiles[profile] += 1
        operations = degradation.get("operations")
        if not isinstance(operations, list):
            raise AssembleError(f"core row lacks operations: {row.get('id')}")
        if any(value in {"shear", "gamma"} for value in operations):
            raise AssembleError(f"V1-only degradation returned: {row.get('id')}")
        if profile == "clear_print":
            if operations:
                raise AssembleError(f"clear row contains degradation operations: {row.get('id')}")
            continue
        core_operations = [str(value) for value in operations if value != "tone_sensor"]
        expected_budget = 2 if profile == "heavy" else 1
        if len(core_operations) != expected_budget or operations[-1] != "tone_sensor":
            raise AssembleError(f"core operation budget differs: {row.get('id')}")
        ink_mode = degradation.get("ink_mode")
        if "ink" in operations:
            if ink_mode not in {"spread_minfilter", "thinning_maxfilter"}:
                raise AssembleError(f"ink branch is unaudited: {row.get('id')}")
            ink_modes[str(ink_mode)] += 1
        elif ink_mode is not None:
            raise AssembleError(f"ink_mode exists without ink: {row.get('id')}")
        key = attenuation_policy.degradation_class_key(profile, operations, ink_mode)
        attenuation = degradation.get("attenuation")
        if not isinstance(attenuation, dict):
            raise AssembleError(f"attenuation metadata is missing: {row.get('id')}")
        expected_strength = expected_strengths.get(key)
        if expected_strength is None:
            if attenuation.get("applied") or float(attenuation.get("strength", -1)) != 1.0:
                raise AssembleError(f"unflagged row was altered: {row.get('id')}")
        else:
            if not attenuation.get("applied") or float(attenuation.get("strength", -1)) != expected_strength:
                raise AssembleError(f"flagged row has wrong strength: {row.get('id')}")
            flagged_counts[key] += 1
    return {
        "profiles": dict(sorted(profiles.items())),
        "ink_modes": dict(sorted(ink_modes.items())),
        "flagged_classes": dict(sorted(flagged_counts.items())),
        "logical_lines_by_granularity": dict(sorted(logical_lines.items())),
    }


def check_addon_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    families: Counter[str] = Counter()
    pair_roles: Counter[str] = Counter()
    logical_lines: Counter[str] = Counter()
    for row in rows:
        meta = row.get("meta", {})
        family = str(meta.get("family"))
        if family not in {"latin_retention", "residual_pair"}:
            raise AssembleError(f"unknown addon family: {row.get('id')}")
        families[family] += 1
        logical_lines[family] += len(str(row["messages"][1]["content"]).splitlines())
        if family == "residual_pair":
            pair_roles[str(meta.get("pair_role"))] += 1
    return {
        "families": dict(sorted(families.items())),
        "residual_pair_roles": dict(sorted(pair_roles.items())),
        "logical_lines_by_family": dict(sorted(logical_lines.items())),
    }


def link_images(rows: list[dict[str, Any]], source: Path, stage: Path, seen_paths: set[str]) -> set[str]:
    hashes: set[str] = set()
    for row in rows:
        images = row.get("images")
        if not isinstance(images, list) or len(images) != 1:
            raise AssembleError(f"row must contain exactly one image: {row.get('id')}")
        relative = Path(str(images[0]))
        if relative.is_absolute() or not relative.parts or relative.parts[0] != "images" or ".." in relative.parts:
            raise AssembleError(f"unsafe image path: {relative}")
        relative_text = relative.as_posix()
        if relative_text in seen_paths:
            raise AssembleError(f"duplicate image path: {relative_text}")
        seen_paths.add(relative_text)
        source_image = source / relative
        if not source_image.is_file():
            raise AssembleError(f"missing source image: {source_image}")
        destination = stage / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(source_image, destination)
        except OSError:
            shutil.copy2(source_image, destination)
        digest = sha256_file(destination)
        if digest in hashes:
            raise AssembleError(f"duplicate image bytes inside source: {relative_text}")
        hashes.add(digest)
    return hashes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-dir", type=Path, required=True)
    parser.add_argument("--addons-dir", type=Path, required=True)
    parser.add_argument("--build-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    core_dir = args.core_dir.resolve()
    addons_dir = args.addons_dir.resolve()
    builds_root = (PROJECT_ROOT / "builds").resolve()
    probes_root = (PROJECT_ROOT / "probes").resolve()
    if core_dir.parent != builds_root:
        raise AssembleError("core source must be an immutable direct child of builds/")
    if addons_dir.parent not in {builds_root, probes_root}:
        raise AssembleError("addon source must be a direct child of builds/ or probes/")
    core_manifest = load_json(core_dir / "build_manifest.json")
    addons_manifest = load_json(addons_dir / "build_manifest.json")
    core = {split: load_jsonl(core_dir / f"jsonl/{split}.jsonl") for split in ("train", "dev")}
    addons = {split: load_jsonl(addons_dir / f"jsonl/{split}_addons.jsonl") for split in ("train", "dev")}
    is_formal = (
        len(core["train"]), len(core["dev"]), len(addons["train"]), len(addons["dev"])
    ) == (18000, 800, 800, 160)
    if is_formal:
        if addons_dir.parent != builds_root:
            raise AssembleError("formal addon source must be an immutable direct child of builds/")
        require_formal_authorization()
    final_dir = builds_root / args.build_id
    stage = builds_root / f".{args.build_id}.staging"
    if final_dir.exists() or stage.exists():
        raise AssembleError(f"refusing to overwrite build or staging path: {final_dir}")
    stage.mkdir(parents=True)
    try:
        train_rows = core["train"] + addons["train"]
        dev_rows = core["dev"] + addons["dev"]
        ids = [str(row.get("id")) for row in train_rows + dev_rows]
        if len(ids) != len(set(ids)):
            raise AssembleError("combined row IDs are not unique")
        train_targets = {str(row["messages"][1]["content"]) for row in train_rows}
        dev_targets = {str(row["messages"][1]["content"]) for row in dev_rows}
        if train_targets.intersection(dev_targets):
            raise AssembleError("combined train/dev targets overlap")

        core_checks = {split: check_core_rows(core[split]) for split in ("train", "dev")}
        addon_checks = {split: check_addon_rows(addons[split]) for split in ("train", "dev")}
        if is_formal:
            expected_classes = set(attenuation_policy.strength_by_class())
            actual_classes = set(core_checks["train"]["flagged_classes"])
            if actual_classes != expected_classes:
                raise AssembleError(
                    "formal core train does not contain every locked attenuation class"
                )
        seen_paths: set[str] = set()
        train_hashes = link_images(core["train"], core_dir, stage, seen_paths)
        train_hashes |= link_images(addons["train"], addons_dir, stage, seen_paths)
        dev_hashes = link_images(core["dev"], core_dir, stage, seen_paths)
        dev_hashes |= link_images(addons["dev"], addons_dir, stage, seen_paths)
        if train_hashes.intersection(dev_hashes):
            raise AssembleError("combined train/dev image hashes overlap")
        if len(train_hashes) != len(train_rows) or len(dev_hashes) != len(dev_rows):
            raise AssembleError("combined image bytes are not globally unique")

        outputs: dict[str, dict[str, Any]] = {}
        for split, rows in (("train", train_rows), ("dev", dev_rows)):
            data = canonical_jsonl(rows)
            path = stage / f"jsonl/{split}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            outputs[f"jsonl/{split}.jsonl"] = {
                "rows": len(rows),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        manifest = {
            "schema": "post_v3_combined_dataset/1.0",
            "status": "PASS_POST_V3_STAGING",
            "build_id": args.build_id,
            "build_profile": "normative_post_v3" if is_formal else "post_v3_smoke",
            "training_data_origin": "synthetic_only",
            "generator": GENERATOR_VERSION,
            "generator_sha256": sha256_file(Path(__file__).resolve()),
            "formal": is_formal,
            "counts": {
                "train": {"core": len(core["train"]), "addons": len(addons["train"]), "total": len(train_rows)},
                "dev": {"core": len(core["dev"]), "addons": len(addons["dev"]), "total": len(dev_rows)},
            },
            "checks": {
                "core": core_checks,
                "addons": addon_checks,
                "unique_ids": len(ids),
                "unique_image_paths": len(seen_paths),
                "train_dev_target_overlap": 0,
                "train_dev_image_hash_overlap": 0,
            },
            "inputs": {
                "core_manifest": {"path": str((core_dir / 'build_manifest.json').relative_to(PROJECT_ROOT)), "sha256": sha256_file(core_dir / "build_manifest.json")},
                "addons_manifest": {"path": str((addons_dir / 'build_manifest.json').relative_to(PROJECT_ROOT)), "sha256": sha256_file(addons_dir / "build_manifest.json")},
                "attenuation_policy": {"path": attenuation_policy.POLICY_REL, "sha256": attenuation_policy.EXPECTED_POLICY_SHA256},
                "formal_spec": {"path": str(FORMAL_SPEC.relative_to(PROJECT_ROOT)), "sha256": sha256_file(FORMAL_SPEC)} if is_formal else None,
                "formal_authorization": {"path": str(FORMAL_AUTHORIZATION.relative_to(PROJECT_ROOT)), "sha256": sha256_file(FORMAL_AUTHORIZATION)} if is_formal else None,
            },
            "outputs": outputs,
            "training_authorized": False,
        }
        (stage / "build_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(stage, final_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    print(final_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
