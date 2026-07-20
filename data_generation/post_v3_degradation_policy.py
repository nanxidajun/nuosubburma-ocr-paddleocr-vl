#!/usr/bin/env python3
"""Locked post-V3 attenuation policy for the seven owner-rejected tails."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_REL = "reports/v3_all_degradation_classes_seed23/attenuation_policy_20260716.json"
POLICY_PATH = PROJECT_ROOT / POLICY_REL
EXPECTED_POLICY_SHA256 = "a29eced8f87e0626e49e5dc579b72c6e30894051979b5902c38b72323470bbc8"
EXPECTED_STATUS = "OWNER_APPROVED_FINAL_STRENGTH_POLICY_FORMAL_GENERATOR_NOT_AUTHORIZED"
EXPECTED_METHOD = "pixelwise_linear_interpolation_from_clean_render_to_full_v3_degraded_render"


class PolicyError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def degradation_class_key(
    profile: str,
    operations: list[str] | tuple[str, ...],
    ink_mode: str | None,
) -> str:
    operation_list = [str(value) for value in operations]
    if not operation_list or operation_list[-1] != "tone_sensor":
        raise PolicyError("non-clear degradation must end with tone_sensor")
    if "ink" in operation_list and ink_mode not in {
        "spread_minfilter",
        "thinning_maxfilter",
    }:
        raise PolicyError("ink degradation lacks an audited ink_mode")
    if "ink" not in operation_list and ink_mode is not None:
        raise PolicyError("ink_mode is present without an ink operation")
    return f"{profile}|{' -> '.join(operation_list)}|{ink_mode or 'none'}"


@lru_cache(maxsize=1)
def load_policy() -> dict[str, Any]:
    actual_sha = sha256_file(POLICY_PATH)
    if actual_sha != EXPECTED_POLICY_SHA256:
        raise PolicyError(f"attenuation policy SHA changed: {actual_sha}")
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if policy.get("schema") != "post_v3_degradation_attenuation_policy/1.0":
        raise PolicyError("attenuation policy schema is wrong")
    if policy.get("status") != EXPECTED_STATUS:
        raise PolicyError("attenuation policy is not owner-approved")
    if policy.get("method") != EXPECTED_METHOD:
        raise PolicyError("attenuation method changed")
    constraints = policy.get("constraints", {})
    if constraints.get("delete_class") is not False:
        raise PolicyError("attenuation policy permits deleting a class")
    if constraints.get("preserve_all_seven_classes") is not True:
        raise PolicyError("attenuation policy does not preserve all seven classes")
    if constraints.get("formal_generator_implementation_authorized") is not False:
        raise PolicyError("policy lock unexpectedly authorizes a formal generator")

    special = policy.get("special_class", {})
    others = policy.get("other_six_classes", {})
    if special.get("strength") != 0.25 or special.get("sampling") != "fixed":
        raise PolicyError("special attenuation strength is not fixed at 0.25")
    other_keys = [str(value) for value in others.get("class_keys", [])]
    if others.get("strength") != 0.8 or others.get("sampling") != "fixed":
        raise PolicyError("other attenuation strength is not fixed at 0.80")
    if len(other_keys) != 6 or len(set(other_keys)) != 6:
        raise PolicyError("attenuation policy must contain six distinct ordinary classes")
    all_keys = [str(special.get("class_key")), *other_keys]
    if len(set(all_keys)) != 7:
        raise PolicyError("attenuation policy must contain seven distinct classes")
    return policy


def strength_by_class(policy: dict[str, Any] | None = None) -> dict[str, float]:
    locked = load_policy() if policy is None else policy
    special = locked["special_class"]
    others = locked["other_six_classes"]
    return {
        str(special["class_key"]): float(special["strength"]),
        **{str(key): float(others["strength"]) for key in others["class_keys"]},
    }


def apply_attenuation(
    clean: Image.Image,
    degraded: Image.Image,
    degradation: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> tuple[Image.Image, dict[str, Any]]:
    if clean.size != degraded.size:
        raise PolicyError("clean and degraded images have different sizes")
    profile = str(degradation.get("profile", ""))
    operations = degradation.get("operations")
    if not isinstance(operations, list):
        raise PolicyError("degradation operations are missing")
    key = degradation_class_key(profile, operations, degradation.get("ink_mode"))
    strengths = strength_by_class(policy)
    strength = strengths.get(key)
    if strength is None:
        return degraded, {
            "applied": False,
            "class_key": key,
            "strength": 1.0,
            "policy_sha256": EXPECTED_POLICY_SHA256,
        }
    if not 0.0 < strength < 1.0:
        raise PolicyError(f"invalid attenuation strength for {key}: {strength}")
    result = Image.blend(clean.convert("RGB"), degraded.convert("RGB"), strength)
    return result, {
        "applied": True,
        "class_key": key,
        "strength": strength,
        "method": EXPECTED_METHOD,
        "policy_sha256": EXPECTED_POLICY_SHA256,
    }
