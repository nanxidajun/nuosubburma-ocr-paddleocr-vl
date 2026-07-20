#!/usr/bin/env python3
"""Reusable, layout-independent scheduling for audited Yi confusable pairs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class ConfusableEvent:
    line_index: int
    position: int
    pair_index: int
    pair_id: str
    ordered_chars: str
    font_index: int
    font_asset: str
    source: str
    context_variant: int

    def as_meta(self) -> dict[str, object]:
        return {
            "line_index": self.line_index,
            "positions": [self.position, self.position + 1],
            "pair_id": self.pair_id,
            "ordered_chars": self.ordered_chars,
            "font_asset": self.font_asset,
            "source": self.source,
            "context_variant": self.context_variant,
        }


class InjectableDraft(Protocol):
    granularity: str
    layout_family: str
    lines: list[str]
    confusable_eligible_lines: int
    confusable_events: list[ConfusableEvent] | None


class ConfusableScheduler:
    """Cycle every pair through all registered fonts and context variants."""

    def __init__(
        self,
        pairs: list[dict[str, object]],
        repeats: int,
        pair_order: list[int],
        font_assets: tuple[str, ...],
    ) -> None:
        if not pairs:
            raise ValueError("shape-pair bank is empty")
        if repeats < 1:
            raise ValueError("confusable repeats must be positive")
        if repeats != 1 and repeats % len(font_assets):
            raise ValueError("confusable repeats must be one or a multiple of the font count")
        if sorted(pair_order) != list(range(len(pairs))):
            raise ValueError("pair_order must be a permutation of all shape pairs")
        self.pairs = pairs
        self.repeats = repeats
        self.pair_order = pair_order
        self.font_assets = font_assets
        self.cursor = 0

    def next_event(self, line_index: int, position: int) -> ConfusableEvent:
        ordered_index = self.cursor // self.repeats
        pair_index = self.pair_order[ordered_index]
        repeat_index = self.cursor % self.repeats
        font_index = (
            repeat_index % len(self.font_assets)
            if self.repeats > 1
            else ordered_index % len(self.font_assets)
        )
        pair = self.pairs[pair_index]
        chars = (str(pair["a"]), str(pair["b"]))
        if (pair_index + font_index) % 2:
            chars = (chars[1], chars[0])
        event = ConfusableEvent(
            line_index=line_index,
            position=position,
            pair_index=pair_index,
            pair_id=f"cnn_r2_{pair_index:04d}",
            ordered_chars="".join(chars),
            font_index=font_index,
            font_asset=self.font_assets[font_index],
            source=str(pair["source"]),
            context_variant=(repeat_index // len(self.font_assets) if self.repeats > 1 else 0),
        )
        self.cursor += 1
        return event


def adjacent_yi_positions(line: str) -> list[int]:
    return [
        index
        for index in range(len(line) - 1)
        if 0xA000 <= ord(line[index]) <= 0xA48C
        and 0xA000 <= ord(line[index + 1]) <= 0xA48C
    ]


def inject_confusable_pairs(
    drafts: list[InjectableDraft],
    pairs: list[dict[str, object]],
    repeats: int,
    rng: np.random.Generator,
    font_assets: tuple[str, ...],
    complex_page_fraction: float = 0.0,
) -> dict[str, int]:
    """Inject an exact cycle while keeping complex-page exposure lightweight.

    Line and region anchors are consumed first. Single-column page anchors are
    the fallback (mainly needed by small dev builds). Complex pages receive at
    most one event per page and no more than ``complex_page_fraction`` of all
    selected events.
    """
    anchor: list[tuple[int, int, list[int]]] = []
    single_page: list[tuple[int, int, list[int]]] = []
    complex_page: list[tuple[int, int, list[int]]] = []
    complex_seen: set[int] = set()
    for draft_index, draft in enumerate(drafts):
        draft.confusable_events = []
        draft.confusable_eligible_lines = 0
        for line_index, line in enumerate(draft.lines):
            positions = adjacent_yi_positions(line)
            if not positions:
                continue
            draft.confusable_eligible_lines += 1
            item = (draft_index, line_index, positions)
            if draft.granularity in {"line", "region"}:
                anchor.append(item)
            elif draft.layout_family == "single_column_anchor":
                single_page.append(item)
            elif draft_index not in complex_seen:
                complex_page.append(item)
                complex_seen.add(draft_index)

    target = len(pairs) * repeats
    total_eligible = len(anchor)
    selected_count = min(target, total_eligible)
    complex_budget = min(len(complex_page), int(round(selected_count * complex_page_fraction)))
    core_budget = selected_count - complex_budget

    def shuffled(items: list[tuple[int, int, list[int]]]) -> list[tuple[int, int, list[int]]]:
        if not items:
            return []
        return [items[int(index)] for index in rng.permutation(len(items))]

    anchor_pool = shuffled(anchor)
    selected = anchor_pool[:core_budget]
    if complex_budget:
        selected.extend(shuffled(complex_page)[:complex_budget])
    selected = selected[:selected_count]

    pair_order = [int(index) for index in rng.permutation(len(pairs))]
    scheduler = ConfusableScheduler(pairs, repeats, pair_order, font_assets)
    for draft_index, line_index, positions in selected:
        position = int(rng.choice(positions))
        event = scheduler.next_event(line_index, position)
        draft = drafts[draft_index]
        chars = list(draft.lines[line_index])
        chars[position : position + 2] = list(event.ordered_chars)
        draft.lines[line_index] = "".join(chars)
        assert draft.confusable_events is not None
        draft.confusable_events.append(event)

    complex_events = sum(
        len(draft.confusable_events or [])
        for draft in drafts
        if draft.granularity == "page" and draft.layout_family != "single_column_anchor"
    )
    return {
        "eligible_lines": len(anchor) + len(single_page) + len(complex_page),
        "target_occurrences": target,
        "pair_occurrences": len(selected),
        "complex_page_occurrences": complex_events,
        "full_target_reached": int(len(selected) == target),
    }
