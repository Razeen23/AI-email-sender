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
    if not role_clean:
        team = company_clean or "your team"
        lines.extend(
            [
                f"I am an AI Full Stack Developer, and I am writing because I am interested in {team} and would like to work with you. "
                "I know you may not have an opening right now. I am still glad to be considered.",
                "",
                "For the last three years I have built SaaS products and the AI inside them. "
                "That includes an AI support assistant in React and FastAPI that answers from internal documents, "
                "hosting dashboards used by thousands of customers, and a Kubernetes path where AI writes the Dockerfile and explains a failed release.",
                "",
                "If you need someone who can build the product and the AI features in it, I would like to contribute. "
                "My resume is attached. I am happy to talk now, or later if a role opens.",
            ]
        )
    else:
        if company_clean:
            lines.append(f"I am writing to apply for the {role_clean} position at {company_clean}.")
        else:
            lines.append(f"I am writing to apply for the {role_clean} position.")
        lines.extend(
            [
                "",
                "I am an AI Full Stack Developer with experience across SaaS products and the AI inside them. "
                "I would welcome the chance to contribute to your team.",
            ]
        )
    if name_clean:
        lines.extend(["", f"I was referred by {name_clean}."])
    if role_clean:
        lines.extend(["", "Please find my resume attached for your review."])
    lines.extend(["", "Thank you for your consideration."])
    return "\n".join(lines)[:max_chars]
