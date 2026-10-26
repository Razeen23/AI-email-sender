from __future__ import annotations

from pathlib import Path

from backend.paths import BASE_CV_INR, BASE_CV_UAE, RESUMES_DIR, infer_region_from_path, resolve_resume_path, to_rel
from backend.services.config_service import get_send_config
from backend.services.profile_service import (
    combine_parsed_resumes,
    load_profile_document,
    parse_docx,
    parse_resume_text,
    profile_has_content,
    render_resume_source,
)
from generate_resume import (
    assemble_resume_markdown,
    build_resume_prompt,
    generate_markdown,
    html_to_pdf,
    markdown_to_html,
    slugify,
)
from resume_selection import region_resume_dir


def _pdf_item(pdf: Path, folder: str) -> dict:
    return {
        "path": to_rel(pdf),
        "filename": pdf.name,
        "folder": folder,
    }


def _folder_pdfs(directory: Path, folder_name: str, generated: bool) -> dict | None:
    if not directory.is_dir():
        return None
    pdfs = [
        _pdf_item(pdf, folder_name)
        for pdf in sorted(directory.glob("*.pdf"))
        if not pdf.name.startswith("~$")
    ]
    if not pdfs and generated:
        return None
    return {"name": folder_name, "generated": generated, "pdfs": pdfs}


def list_resumes(region: str | None = None) -> dict:
    regions = []
    wanted = None
    if region:
        wanted = infer_region_from_path(RESUMES_DIR / region, region)
    for folder_region in ("INR", "UAE"):
        if wanted and folder_region != wanted:
            continue
        root = region_resume_dir(RESUMES_DIR, folder_region)
        folders: list[dict] = []
        stock = _folder_pdfs(root, root.name, False)
        if stock:
            folders.append(stock)
        generated = _folder_pdfs(root / "generated", "generated", True)
        if generated:
            folders.append(generated)
        legacy = _folder_pdfs(RESUMES_DIR / folder_region / "generated", "generated (legacy)", True)
        if legacy:
            folders.append(legacy)
        regions.append({"region": folder_region, "folders": folders})
    return {"regions": regions}


def open_resume_file(rel_path: str) -> Path:
    return resolve_resume_path(rel_path)


def delete_resume(rel_path: str) -> dict:
    path = resolve_resume_path(rel_path)
    if path.resolve() in {BASE_CV_INR.resolve(), BASE_CV_UAE.resolve()}:
        raise ValueError("The base CV can't be deleted.")
    removed: list[str] = []
    for candidate in (path, path.with_suffix(".docx"), path.with_suffix(".md")):
        if candidate.is_file() and not candidate.name.startswith("~$"):
            candidate.unlink()
            removed.append(candidate.name)
    if not removed:
        raise FileNotFoundError("Resume not found.")
    return {"deleted": removed}


def resume_facts(rel_path: str) -> dict:
    path = resolve_resume_path(rel_path)
    docx = path.with_suffix(".docx")
    markdown = path.with_suffix(".md")
    if docx.is_file() and not docx.name.startswith("~$"):
        return parse_docx(docx)
    text = markdown.read_text(encoding="utf-8") if markdown.is_file() else _pdf_text(path)
    if not text.strip():
        raise ValueError(f"Could not read details from {path.name}. Keep the Word file beside that PDF.")
    try:
        return parse_resume_text(text)
    except ValueError as exc:
        raise ValueError(f"Could not read details from {path.name}. {exc}") from exc


def _pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        reader = PdfReader(str(path))
    except Exception:
        return ""
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def generate_resume_for_row(
    *,
    company: str,
    role: str,
    region: str,
    job_description: str | None = None,
    overwrite: bool = False,
    source_paths: list[str] | None = None,
) -> dict:
    resolved_region = infer_region_from_path(RESUMES_DIR / region, region)
    config = get_send_config()
    profile = load_profile_document()
    selected = [path for path in (source_paths or []) if path]
    if selected:
        if not profile_has_content(profile):
            raise ValueError("Add your contact details on the Profile page before generating a resume.")
        profile = combine_parsed_resumes(profile, [resume_facts(path) for path in selected], resolved_region)
    elif not profile_has_content(profile):
        raise ValueError("Your profile is empty. Add your details on the Profile page before generating a resume.")
    if not (profile.get("experience") or profile.get("projects")):
        raise ValueError("The selected resumes did not contain experience or projects to combine.")
    profile_text = render_resume_source(profile, resolved_region)

    jd_text = (job_description or "").strip() or "(No job description provided.)"
    out_dir = region_resume_dir(RESUMES_DIR, resolved_region) / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{slugify(company)}-{slugify(role)}"
    pdf_path = out_dir / f"{base_name}.pdf"
    md_path = out_dir / f"{base_name}.md"

    if pdf_path.is_file() and not overwrite:
        return {
            "path": to_rel(pdf_path),
            "filename": pdf_path.name,
            "region": resolved_region,
            "existed": True,
            "markdown_only": False,
        }

    prompt = build_resume_prompt(profile_text, role, company, jd_text)
    markdown = generate_markdown(prompt, config)
    if not markdown:
        raise RuntimeError("Ollama did not return a resume. Is the model running?")

    markdown = assemble_resume_markdown(markdown, profile, resolved_region)
    md_path.write_text(markdown, encoding="utf-8")
    wrote_pdf = html_to_pdf(
        markdown_to_html(markdown, profile_text, role, profile=profile, region=resolved_region),
        pdf_path,
    )
    result_path = pdf_path if wrote_pdf and pdf_path.is_file() else md_path
    return {
        "path": to_rel(result_path),
        "filename": result_path.name,
        "region": resolved_region,
        "existed": False,
        "markdown_only": not wrote_pdf,
    }
