"""Plain-text application body when Ollama is unavailable or returns nothing."""


def _norm_cell(val: object) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    return "" if not s or s.lower() == "nan" else s


def build_fallback_application_body(
    company: str,
    role: str,
    name: str = "",
    *,
    max_chars: int = 2000,
) -> str:
    company_clean = _norm_cell(company)
    role_clean = _norm_cell(role)
    name_clean = _norm_cell(name)

    lines = ["Dear Hiring Team,", ""]
    if company_clean and role_clean:
        lines.append(f"I am writing to apply for the {role_clean} position at {company_clean}.")
    elif role_clean:
        lines.append(f"I am writing to apply for the {role_clean} position.")
    elif company_clean:
        lines.append(f"I am writing to express my interest in opportunities at {company_clean}.")
    else:
        lines.append("I am writing to express my interest in suitable opportunities with your team.")

    lines.extend(
        [
            "",
            "I am a software developer with experience across full-stack engineering and Gen-AI-related work. "
            "I would welcome the chance to contribute to your team.",
        ]
    )
    if name_clean:
        lines.extend(["", f"I was referred by {name_clean}."])
    lines.extend(
        [
            "",
            "Please find my resume attached for your review.",
            "",
            "Thank you for your consideration.",
        ]
    )
    return "\n".join(lines)[:max_chars]
