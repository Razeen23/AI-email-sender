from __future__ import annotations

import re
from io import BytesIO

FILE_LIMIT = 8_000_000
EMAIL_FIND = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
PHONE_FIND = re.compile(r"(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{3,4}")
LINKEDIN_FIND = re.compile(r"https?://(?:www\.)?linkedin\.com/[^\s]+", re.I)
GITHUB_FIND = re.compile(r"https?://(?:www\.)?github\.com/[^\s]+", re.I)


def read_document(filename: str, content: bytes) -> str:
    if len(content) > FILE_LIMIT:
        raise ValueError("The document must be under 8 MB.")
    lower = filename.lower()
    if lower.endswith(".pdf") or content.startswith(b"%PDF"):
        text = _pdf_text(content)
    elif lower.endswith(".docx"):
        text = _docx_text(content)
    else:
        raise ValueError("Upload a PDF or a Word document (.docx).")
    text = text.strip()
    if not text:
        raise ValueError("No readable text was found in that file.")
    return text


def fields_from_text(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    name = lines[0] if lines and "@" not in lines[0] and len(lines[0]) <= 80 else ""
    emails = EMAIL_FIND.findall(text)
    phones = [item.strip() for item in PHONE_FIND.findall(text) if len(re.sub(r"\D", "", item)) >= 8]
    linkedin = LINKEDIN_FIND.search(text)
    github = GITHUB_FIND.search(text)
    return {
        "name": name,
        "email": emails[0] if emails else "",
        "phone": phones[0] if phones else "",
        "linkedin": linkedin.group(0).rstrip(".,)") if linkedin else "",
        "github": github.group(0).rstrip(".,)") if github else "",
        "summary": text[:1500],
    }


def _pdf_text(content: bytes) -> str:
    if not content.startswith(b"%PDF"):
        raise ValueError("That file is not a PDF.")
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Could not read that PDF.") from exc


def _docx_text(content: bytes) -> str:
    if not content.startswith(b"PK"):
        raise ValueError("That file is not a Word document.")
    try:
        from docx import Document

        document = Document(BytesIO(content))
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" ".join(cell.text for cell in row.cells))
        return "\n".join(parts)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Could not read that Word document.") from exc
