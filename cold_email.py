"""Cold outreach used when a spreadsheet row has no role."""

from __future__ import annotations

COLD_TITLE = "AI Full Stack Developer"


def normalize_role(role: str | None) -> str:
    if role is None:
        return ""
    text = str(role).strip()
    if not text or text.lower() == "nan":
        return ""
    return text


def is_cold_email(role: str | None) -> bool:
    return not normalize_role(role)


def ensure_role_column(df):
    """Sheets of company + HR email only are valid. Missing Role means every row is a cold email."""
    if "Role" not in df.columns:
        df = df.copy()
        df["Role"] = ""
    return df


def cold_subject(company: str | None) -> str:
    name = (company or "").strip()
    if not name or name.lower() == "nan":
        return f"{COLD_TITLE} — open to working with your team"
    return f"{COLD_TITLE} interested in {name}"


def cold_prompt(company: str | None, profile_text: str | None) -> str:
    name = (company or "").strip()
    if not name or name.lower() == "nan":
        audience = (
            "Address the hiring team. Do not guess a company name. "
            'Say "your team" or "your company".'
        )
    else:
        audience = f"Address the hiring team at {name}. Mention {name} by name."

    prompt = f"""Write a cold outreach email, not a job application. This spreadsheet row has no role.
The company may have no opening. Do not invent a job title. Do not say you are applying for a position.

{audience}

Write in the first person as an {COLD_TITLE}.
Follow this order:
1. Greeting
2. Who you are, that you are interested in their company, and that you are willing to work with them even if they have no opening right now
3. What you do, using 1–2 real achievements from the candidate profile (SaaS products, AI assistants, RAG, React, FastAPI, or the Kubernetes path). Do not list everything. Do not claim anything that is not in the profile.
4. How you could help if they need someone who builds the product and the AI inside it
5. Ask them to consider the attached resume now, or keep it for when they need an {COLD_TITLE}

Tone: professional, confident, concise. About 140–190 words.
Do not write "Subject:" or any email header. Start with the greeting.
Do not add a sign-off, name, email, phone, or links. A signature is added automatically.
Never use the word "nan"."""

    if profile_text:
        prompt += f"""

Candidate profile (use only these facts):
{profile_text}"""
    return prompt
