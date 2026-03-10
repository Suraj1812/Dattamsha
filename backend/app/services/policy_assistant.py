from pathlib import Path
import re

from app.core.config import get_settings


def _load_policy_text() -> str:
    settings = get_settings()
    path = Path(settings.policy_doc_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z]{3,}", text.lower())}


def _sections_with_line_numbers(text: str) -> list[tuple[str, int, int]]:
    lines = text.splitlines()
    sections: list[tuple[str, int, int]] = []
    buffer: list[str] = []
    start_line = 1

    for index, line in enumerate(lines, start=1):
        if line.strip().startswith("#") and buffer:
            sections.append(("\n".join(buffer).strip(), start_line, index - 1))
            buffer = [line]
            start_line = index
            continue

        if not buffer:
            start_line = index
        buffer.append(line)

    if buffer:
        sections.append(("\n".join(buffer).strip(), start_line, len(lines)))

    return [(body, start, end) for body, start, end in sections if body]


def answer_policy_question(question: str) -> tuple[str, str]:
    text = _load_policy_text()
    if not text.strip():
        return (
            "No policy knowledge base is configured yet. Add policy documents to policies/policies.md.",
            "Policy KB unavailable",
        )

    query_terms = _tokenize(question)
    query_phrase = question.strip().lower()
    best_section = ""
    best_score = 0.0
    best_start = 1
    best_end = 1

    for section_text, start_line, end_line in _sections_with_line_numbers(text):
        section_tokens = _tokenize(section_text)
        overlap = len(query_terms & section_tokens)
        coverage = overlap / max(1, len(query_terms))
        phrase_bonus = 0.35 if query_phrase and query_phrase in section_text.lower() else 0.0
        heading_bonus = 0.15 if section_text.strip().startswith("#") else 0.0
        score = coverage + phrase_bonus + heading_bonus
        if score > best_score:
            best_score = score
            best_section = section_text
            best_start = start_line
            best_end = end_line

    if not best_section or best_score <= 0:
        return (
            "I could not find an exact policy match. Please refine your question with policy keywords.",
            "No strong match",
        )

    preview_lines = [line.strip() for line in best_section.splitlines() if line.strip()][:3]
    preview = " ".join(preview_lines)
    if len(preview) > 360:
        preview = f"{preview[:357]}..."

    return (
        f"Based on policy documentation: {preview}",
        f"policies/policies.md (lines {best_start}-{best_end})",
    )
