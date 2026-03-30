from __future__ import annotations

import re
from pathlib import Path

from .models import RequirementItem, RoadmapEpic, RoadmapTicket, SpecDocument, SpecSection


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
METADATA_PATTERN = re.compile(r"^\*\*(.+?)\*\*\s*:?\s*(.+?)\s*$")
TICKET_PATTERN = re.compile(r"^(TICKET-\d+)\s+[·-]\s+(.+?)$")
EPIC_PATTERN = re.compile(r"^(EP-\d+)\s+[·-]\s+(.+?)$")
TICKET_ID_PATTERN = re.compile(r"TICKET-(\d+)")


def parse_markdown_sections(markdown_text: str) -> list[SpecSection]:
    sections: list[SpecSection] = []
    current_section: dict[str, object] | None = None
    in_code_block = False

    def flush_current() -> None:
        nonlocal current_section
        if current_section is None:
            return
        body = "\n".join(current_section["lines"]).strip()
        sections.append(
            SpecSection(
                heading_level=int(current_section["heading_level"]),
                title=str(current_section["title"]),
                body=body,
            )
        )
        current_section = None

    for line in markdown_text.splitlines():
        if line.strip().startswith("```"):
            in_code_block = not in_code_block

        heading_match = None if in_code_block else HEADING_PATTERN.match(line)
        if heading_match:
            flush_current()
            current_section = {
                "heading_level": len(heading_match.group(1)),
                "title": heading_match.group(2).strip(),
                "lines": [],
            }
            continue

        if current_section is None:
            current_section = {
                "heading_level": 0,
                "title": "Preamble",
                "lines": [],
            }
        current_section["lines"].append(line)

    flush_current()
    return sections


def extract_metadata(markdown_text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in markdown_text.splitlines()[:40]:
        match = METADATA_PATTERN.match(line.strip())
        if match:
            metadata[match.group(1).strip().rstrip(":")] = match.group(2).strip()
    return metadata


def parse_spec_text(markdown_text: str, *, doc_type: str, path: str) -> SpecDocument:
    sections = parse_markdown_sections(markdown_text)
    title = next((section.title for section in sections if section.heading_level == 1), Path(path).stem)
    return SpecDocument(
        doc_type=doc_type,
        path=path,
        title=title,
        metadata=extract_metadata(markdown_text),
        sections=sections,
    )


def parse_spec_document(path: str | Path, *, doc_type: str) -> SpecDocument:
    resolved_path = Path(path).resolve()
    markdown_text = resolved_path.read_text(encoding="utf-8")
    return parse_spec_text(markdown_text, doc_type=doc_type, path=str(resolved_path))


def infer_requirement_category(section_title: str) -> str:
    lowered = section_title.lower()
    if "agent" in lowered:
        return "agent"
    if "modelo" in lowered or "data" in lowered:
        return "data_model"
    if "arquitect" in lowered:
        return "architecture"
    if "tool" in lowered or "herramient" in lowered:
        return "tooling"
    if "flujo" in lowered or "ejecuci" in lowered:
        return "workflow"
    return "functional"


def extract_bullets(section_body: str) -> list[str]:
    bullet_items: list[str] = []
    for line in section_body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            bullet_items.append(stripped[2:].strip())
    return bullet_items


def summarize_section(section_body: str) -> str:
    paragraphs = [chunk.strip() for chunk in section_body.split("\n\n") if chunk.strip()]
    if not paragraphs:
        return ""
    return re.sub(r"\s+", " ", paragraphs[0])


def parse_requirements(document: SpecDocument) -> list[RequirementItem]:
    requirements: list[RequirementItem] = []
    counter = 1
    for section in document.sections:
        if section.heading_level < 2:
            continue
        summary = summarize_section(section.body)
        bullets = extract_bullets(section.body)
        if not summary and not bullets:
            continue
        requirements.append(
            RequirementItem(
                requirement_id=f"REQ-{counter:03d}",
                title=section.title,
                source_section=section.title,
                category=infer_requirement_category(section.title),
                summary=summary,
                constraints=bullets,
                acceptance_hints=[item for item in bullets if "[ ]" in item or "[x]" in item],
            )
        )
        counter += 1
    return requirements


def extract_markdown_block(section_body: str, heading: str) -> str:
    pattern = re.compile(
        rf"\*\*{re.escape(heading)}\*\*\s*(.*?)(?=\n\*\*|\Z)",
        flags=re.DOTALL,
    )
    match = pattern.search(section_body)
    return match.group(1).strip() if match else ""


def parse_ticket_metadata(section_body: str) -> tuple[str | None, str | None, str | None, list[str]]:
    ticket_type = None
    priority = None
    estimate = None
    dependencies: list[str] = []

    type_match = re.search(r"^Tipo:\s+(.+?)$", section_body, flags=re.MULTILINE)
    priority_match = re.search(r"^Prioridad:\s+(.+?)$", section_body, flags=re.MULTILINE)
    estimate_match = re.search(r"^Est(?:\.|imaci[oó]n)?:\s+(.+?)$", section_body, flags=re.MULTILINE)
    deps_match = re.search(r"^Deps?\.:\s+(.+?)$", section_body, flags=re.MULTILINE)

    if type_match:
        ticket_type = type_match.group(1).strip()
    if priority_match:
        priority = priority_match.group(1).strip()
    if estimate_match:
        estimate = estimate_match.group(1).strip()
    if deps_match:
        raw_dependencies = deps_match.group(1).strip()
        if raw_dependencies.lower() != "ninguna":
            dependencies = parse_dependencies(raw_dependencies)

    return ticket_type, priority, estimate, dependencies


def parse_dependencies(raw_dependencies: str) -> list[str]:
    lowered = raw_dependencies.strip().lower()
    if lowered in {"ninguna", "todos los agentes"}:
        return []

    range_match = re.search(r"TICKET-(\d+)\s+al\s+TICKET-(\d+)", raw_dependencies, flags=re.IGNORECASE)
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
        if start <= end:
            return [f"TICKET-{index:03d}" for index in range(start, end + 1)]

    return [f"TICKET-{match}" for match in TICKET_ID_PATTERN.findall(raw_dependencies)]


def parse_roadmap(document: SpecDocument) -> list[RoadmapEpic]:
    epics: list[RoadmapEpic] = []
    current_epic: RoadmapEpic | None = None

    for section in document.sections:
        if section.heading_level == 2:
            epic_match = EPIC_PATTERN.match(section.title)
            if epic_match:
                current_epic = RoadmapEpic(
                    epic_id=epic_match.group(1),
                    name=epic_match.group(2),
                    objective=summarize_section(section.body),
                )
                epics.append(current_epic)
            continue

        if section.heading_level != 3 or current_epic is None:
            continue

        ticket_match = TICKET_PATTERN.match(section.title)
        if not ticket_match:
            continue

        ticket_type, priority, estimate, dependencies = parse_ticket_metadata(section.body)
        description = extract_markdown_block(section.body, "Descripción")
        acceptance_block = extract_markdown_block(section.body, "Criterios de aceptación")
        acceptance_criteria = extract_bullets(acceptance_block)
        current_epic.tickets.append(
            RoadmapTicket(
                ticket_id=ticket_match.group(1),
                title=ticket_match.group(2),
                epic_id=current_epic.epic_id,
                epic_name=current_epic.name,
                ticket_type=ticket_type,
                priority=priority,
                estimate=estimate,
                dependencies=dependencies,
                description=description,
                acceptance_criteria=acceptance_criteria,
            )
        )

    return epics
