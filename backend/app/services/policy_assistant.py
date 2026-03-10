from pathlib import Path

from app.core.config import get_settings


def _load_policy_text() -> str:
    settings = get_settings()
    path = Path(settings.policy_doc_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def answer_policy_question(question: str) -> tuple[str, str]:
    text = _load_policy_text()
    if not text.strip():
        return (
            "No policy knowledge base is configured yet. Add policy documents to policies/policies.md.",
            "Policy KB unavailable",
        )

    q_terms = {t.lower() for t in question.split() if len(t) > 2}
    best_line = ""
    best_overlap = 0
    for line in text.splitlines():
        tokens = {t.lower().strip('.,()') for t in line.split()}
        overlap = len(q_terms & tokens)
        if overlap > best_overlap:
            best_line = line.strip()
            best_overlap = overlap

    if not best_line:
        return (
            "I could not find an exact policy match. Please refine your question with policy keywords.",
            "No strong match",
        )

    return (
        f"Based on policy documentation: {best_line}",
        "policies/policies.md",
    )
