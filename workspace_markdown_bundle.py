from __future__ import annotations

import re
from dataclasses import dataclass

from architecture_guardrails import normalize_relative_path


MARKDOWN_BUNDLE_PATTERN = re.compile(
    r"```(?P<language>[\w.+-]*)\s*\n"
    r"\s*(?:#|//|<!--)\s*filepath:\s*(?P<path>.+?)\s*(?:-->)?\s*\n"
    r"(?P<content>.*?)"
    r"\n```",
    re.DOTALL,
)


@dataclass(frozen=True)
class MarkdownBundleFile:
    path: str
    content: str
    language: str = ""


def extract_markdown_file_bundle(markdown: str) -> list[MarkdownBundleFile]:
    files: list[MarkdownBundleFile] = []
    seen_paths: set[str] = set()

    for match in MARKDOWN_BUNDLE_PATTERN.finditer(markdown):
        raw_path = match.group("path").strip().rstrip(")")
        cleaned_path = re.sub(r"\s*\([^)]*\)\s*$", "", raw_path).strip()
        normalized_path = normalize_relative_path(cleaned_path)
        if normalized_path in seen_paths:
            raise ValueError(f"Duplicate filepath directive in markdown bundle: {normalized_path}")
        seen_paths.add(normalized_path)
        files.append(
            MarkdownBundleFile(
                path=normalized_path,
                content=match.group("content"),
                language=(match.group("language") or "").strip(),
            )
        )

    if not files:
        raise ValueError("No filepath directives found in markdown bundle")
    return files
