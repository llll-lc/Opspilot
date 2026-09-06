"""Markdown structure-aware parent/child chunking without token-level hard splits."""

from __future__ import annotations

import re
from dataclasses import dataclass

from opspilot.knowledge.contracts import ChunkDraft, KnowledgeSource, StructureType

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
ORDERED_STEP = re.compile(r"^\d+[.)]\s+")
CONFIGURATION = re.compile(r"^[A-Z][A-Z0-9_]+\s*=")


@dataclass(frozen=True)
class _Unit:
    content: str
    start_line: int
    end_line: int
    kind: StructureType


@dataclass(frozen=True)
class _Section:
    path: tuple[str, ...]
    start_line: int
    end_line: int
    units: tuple[_Unit, ...]


def _unit_type(lines: list[str], fenced: bool) -> StructureType:
    if fenced:
        return "CODE_BLOCK"
    if lines and all("|" in line for line in lines if line.strip()):
        return "TABLE"
    if lines and all(ORDERED_STEP.match(line) is not None for line in lines if line.strip()):
        return "PROCEDURE"
    if lines and all(CONFIGURATION.match(line) is not None for line in lines if line.strip()):
        return "CONFIGURATION"
    return "PROSE"


def _parse_sections(markdown: str) -> tuple[_Section, ...]:
    """Keep fenced blocks, tables, config and numbered procedures as indivisible units."""
    lines = markdown.splitlines()
    sections: list[_Section] = []
    path: list[str] = []
    section_start = 1
    units: list[_Unit] = []
    pending: list[str] = []
    pending_start = 1
    fenced = False

    def flush_pending(end_line: int, *, fenced_unit: bool | None = None) -> None:
        nonlocal pending
        if pending and any(line.strip() for line in pending):
            content = "\n".join(pending).strip()
            units.append(
                _Unit(
                    content,
                    pending_start,
                    end_line,
                    _unit_type(pending, fenced if fenced_unit is None else fenced_unit),
                )
            )
        pending = []

    def flush_section(end_line: int) -> None:
        nonlocal units
        flush_pending(end_line)
        if units:
            sections.append(
                _Section(tuple(path) or ("Document",), section_start, end_line, tuple(units))
            )
        units = []

    for line_number, line in enumerate(lines, start=1):
        heading = HEADING.match(line)
        if heading and not fenced:
            flush_section(line_number - 1)
            level = len(heading.group(1))
            title = heading.group(2)
            path = [*path[: level - 1], title]
            section_start = line_number
            pending_start = line_number
            continue
        if line.startswith("```"):
            if not pending:
                pending_start = line_number
            pending.append(line)
            if fenced:
                fenced = False
                flush_pending(line_number, fenced_unit=True)
            else:
                fenced = True
            continue
        if not fenced and not line.strip():
            flush_pending(line_number - 1)
            pending_start = line_number + 1
            continue
        if not pending:
            pending_start = line_number
        pending.append(line)
    flush_section(len(lines))
    return tuple(sections)


def chunk_markdown(
    source: KnowledgeSource, *, max_child_characters: int = 900
) -> tuple[ChunkDraft, ...]:
    """Create parent sections and bounded child groups while never splitting one structure unit."""
    if max_child_characters < 80:
        raise ValueError("max_child_characters must retain a meaningful structure unit")
    drafts: list[ChunkDraft] = []
    ordinal = 0
    common_metadata: dict[str, object] = {
        "source_key": source.source_key,
        "source_type": source.source_type,
        "visibility": source.visibility,
        "target_versions": list(source.target_versions),
        "locator": source.locator,
    }
    for parent_ordinal, section in enumerate(_parse_sections(source.content)):
        parent_content = "\n\n".join(unit.content for unit in section.units)
        drafts.append(
            ChunkDraft(
                "PARENT",
                None,
                ordinal,
                section.path,
                "HEADING",
                {"start_line": section.start_line, "end_line": section.end_line},
                parent_content,
                dict(common_metadata),
            )
        )
        ordinal += 1
        group: list[_Unit] = []
        group_size = 0

        def flush_group(
            parent_index: int = parent_ordinal,
            structure_path: tuple[str, ...] = section.path,
            *,
            oversized_structure_unit: bool = False,
        ) -> None:
            nonlocal ordinal, group, group_size
            if not group:
                return
            retrieval_metadata = dict(common_metadata)
            if oversized_structure_unit:
                # A fenced block/table/procedure must remain locatable and intact.  The
                # configured child bound is therefore a soft bound for one indivisible
                # structure unit, recorded explicitly for downstream audit.
                retrieval_metadata.update(
                    {
                        "oversized_structure_unit": True,
                        "configured_max_child_characters": max_child_characters,
                        "structure_unit_characters": len(group[0].content),
                    }
                )
            drafts.append(
                ChunkDraft(
                    "CHILD",
                    parent_index,
                    ordinal,
                    structure_path,
                    group[0].kind if len(group) == 1 else "PROSE",
                    {"start_line": group[0].start_line, "end_line": group[-1].end_line},
                    "\n\n".join(unit.content for unit in group),
                    retrieval_metadata,
                )
            )
            ordinal += 1
            group = []
            group_size = 0

        for unit in section.units:
            unit_size = len(unit.content)
            if group and group_size + unit_size + 2 > max_child_characters:
                flush_group()
            if unit_size > max_child_characters:
                # Flush before and after the exception so an over-bound unit never
                # absorbs adjacent prose and retains its original line locator.
                flush_group()
                group.append(unit)
                group_size = unit_size
                flush_group(oversized_structure_unit=True)
                continue
            group.append(unit)
            group_size += unit_size + 2
        flush_group()
    return tuple(drafts)
