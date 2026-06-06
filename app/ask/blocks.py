"""Structured answer blocks for github_search API responses."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from app.config import github_search_answer_format

ANSWER_FORMAT_BLOCKS = "blocks"
ANSWER_FORMAT_TEXT = "text"

_BLOCK_TYPES = frozenset({"heading", "paragraph", "list", "service"})
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass(frozen=True)
class AnswerContent:
    """Parsed synthesis output for tool responses."""

    text: str
    blocks: list[dict[str, Any]]
    notes: list[str]
    format: str = ANSWER_FORMAT_BLOCKS


def _normalize_cite_ids(raw: Any) -> list[int]:
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for item in raw:
        try:
            n = int(item)
        except (TypeError, ValueError):
            continue
        if n > 0:
            out.append(n)
    return out


def _validate_block(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    block_type = str(raw.get("type") or "").strip().lower()
    if block_type not in _BLOCK_TYPES:
        return None

    cite_ids = _normalize_cite_ids(raw.get("cite_ids"))
    if block_type == "heading":
        text = str(raw.get("text") or "").strip()
        if not text:
            return None
        return {"type": "heading", "text": text, "cite_ids": cite_ids}
    if block_type == "paragraph":
        text = str(raw.get("text") or "").strip()
        if not text:
            return None
        return {"type": "paragraph", "text": text, "cite_ids": cite_ids}
    if block_type == "list":
        items_raw = raw.get("items")
        if not isinstance(items_raw, list):
            return None
        items = [str(x).strip() for x in items_raw if str(x).strip()]
        if not items:
            return None
        return {"type": "list", "items": items, "cite_ids": cite_ids}
    # service
    name = str(raw.get("name") or "").strip()
    description = str(raw.get("description") or "").strip()
    if not name or not description:
        return None
    out: dict[str, Any] = {
        "type": "service",
        "name": name,
        "description": description,
        "cite_ids": cite_ids,
    }
    role = str(raw.get("role") or "").strip()
    if role:
        out["role"] = role
    endpoint = str(raw.get("endpoint") or "").strip()
    if endpoint:
        out["endpoint"] = endpoint
    service_type = str(raw.get("service_type") or raw.get("kind") or "").strip()
    if service_type:
        out["service_type"] = service_type
    return out


def _validate_notes(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def blocks_to_text(blocks: list[dict[str, Any]], notes: list[str] | None = None) -> str:
    """Render blocks (+ optional notes) as markdown-ish text for ``answer.text``."""
    lines: list[str] = []
    for block in blocks:
        btype = block.get("type")
        cites = block.get("cite_ids") or []
        cite_suffix = ""
        if cites:
            cite_suffix = " " + "".join(f"[{c}]" for c in cites)

        if btype == "heading":
            lines.append(f"## {block.get('text', '')}{cite_suffix}")
        elif btype == "paragraph":
            lines.append(f"{block.get('text', '')}{cite_suffix}")
        elif btype == "list":
            for item in block.get("items") or []:
                lines.append(f"- {item}{cite_suffix}")
        elif btype == "service":
            name = block.get("name", "")
            role = block.get("role")
            endpoint = block.get("endpoint")
            title = f"**{name}**"
            if role:
                title = f"{title} ({role})"
            lines.append(f"- {title}{cite_suffix}")
            if endpoint:
                lines.append(f"  - Endpoint: `{endpoint}`")
            desc = block.get("description")
            if desc:
                lines.append(f"  - {desc}")
        if lines and lines[-1] != "":
            lines.append("")

    if notes:
        lines.append("**Notes**")
        for note in notes:
            lines.append(f"- {note}")
    return "\n".join(lines).strip()


def _strip_json_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = _FENCE_RE.sub("", text).strip()
    return text


def parse_text_answer(raw: str) -> AnswerContent:
    """Use LLM prose directly for the original text-only answer schema."""
    text = raw.strip()
    return AnswerContent(text=text, blocks=[], notes=[], format=ANSWER_FORMAT_TEXT)


def resolve_answer_content(raw: str) -> AnswerContent:
    """Parse synthesis output according to ``GITHUB_SEARCH_ANSWER_FORMAT``."""
    if github_search_answer_format() == "blocks":
        return parse_structured_answer(raw)
    return parse_text_answer(raw)


def parse_structured_answer(raw: str) -> AnswerContent:
    """Parse LLM JSON into blocks; fall back to a single paragraph block."""
    cleaned = _strip_json_fences(raw)
    if not cleaned:
        return AnswerContent(text="", blocks=[], notes=[], format=ANSWER_FORMAT_BLOCKS)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return _fallback_paragraph(cleaned)

    if not isinstance(parsed, dict):
        return _fallback_paragraph(cleaned)

    blocks_raw = parsed.get("blocks")
    if not isinstance(blocks_raw, list):
        return _fallback_paragraph(cleaned)

    blocks: list[dict[str, Any]] = []
    for item in blocks_raw:
        block = _validate_block(item)
        if block:
            blocks.append(block)

    notes = _validate_notes(parsed.get("notes"))
    if not blocks:
        return _fallback_paragraph(cleaned)

    text = blocks_to_text(blocks, notes)
    return AnswerContent(text=text, blocks=blocks, notes=notes, format=ANSWER_FORMAT_BLOCKS)


def _fallback_paragraph(text: str) -> AnswerContent:
    paragraph = text.strip()
    if not paragraph:
        return AnswerContent(text="", blocks=[], notes=[], format=ANSWER_FORMAT_BLOCKS)
    block = {"type": "paragraph", "text": paragraph, "cite_ids": []}
    return AnswerContent(
        text=paragraph,
        blocks=[block],
        notes=[],
        format=ANSWER_FORMAT_BLOCKS,
    )


def iter_text_chunks(text: str, *, chunk_size: int = 48):
    """Yield fixed-size chunks (tests and legacy replay helpers)."""
    if not text:
        return
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]
