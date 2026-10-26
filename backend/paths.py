from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXCEL_DIRS = {
    "INR": PROJECT_ROOT / "INR_Excel",
    "UAE": PROJECT_ROOT / "UAE_Excel",
}
RESUMES_DIR = PROJECT_ROOT / "resumes"
ENV_PATH = PROJECT_ROOT / ".env"
PROFILE_PATH = PROJECT_ROOT / "profile.txt"
PROFILE_JSON = PROJECT_ROOT / "data" / "profile.json"
BASE_CV_INR = PROJECT_ROOT / "resumes" / "base-cv-for-inr.docx"
BASE_CV_UAE = PROJECT_ROOT / "resumes" / "base-cv-for-uae.docx"


def load_dotenv(path: Path | None = None) -> None:
    import os

    env_file = path or ENV_PATH
    if not env_file.is_file():
        return
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)


def to_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.name


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_excel_path(rel_path: str) -> Path:
    if not rel_path or ".." in Path(rel_path).parts:
        raise ValueError("Invalid Excel path.")
    path = (PROJECT_ROOT / rel_path).resolve()
    allowed = [d.resolve() for d in EXCEL_DIRS.values()]
    if path.parent not in allowed:
        raise ValueError("Excel file must be inside INR_Excel/ or UAE_Excel/.")
    if path.suffix.lower() not in {".xlsx", ".xls"}:
        raise ValueError("Only .xlsx or .xls files are allowed.")
    if not path.is_file():
        raise FileNotFoundError(f"Excel file not found: {rel_path}")
    return path


def resolve_resume_path(rel_path: str) -> Path:
    if not rel_path or ".." in Path(rel_path).parts:
        raise ValueError("Invalid resume path.")
    path = (PROJECT_ROOT / rel_path).resolve()
    if not _is_under(path, RESUMES_DIR):
        raise ValueError("Resume file must be inside resumes/.")
    if path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF resumes are allowed.")
    if not path.is_file():
        raise FileNotFoundError(f"Resume not found: {rel_path}")
    return path


def infer_region_from_path(path: Path, region_arg: str | None = None) -> str:
    if region_arg:
        region = region_arg.strip().upper()
        if region not in EXCEL_DIRS:
            raise ValueError("Region must be INR or UAE.")
        return region
    parts = [part.lower() for part in path.parts]
    if "inr_excel" in parts:
        return "INR"
    if "uae_excel" in parts:
        return "UAE"
    name = path.name.lower()
    if "inr" in name:
        return "INR"
    if "uae" in name:
        return "UAE"
    raise ValueError("Could not infer region. Choose INR or UAE.")
