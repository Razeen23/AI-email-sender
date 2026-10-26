from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    smtp_configured: bool
    smtp_host: str | None = None
    smtp_port: int | None = None
    from_email: str | None = None
    ollama_reachable: bool
    ollama_base_url: str
    ollama_model: str
    db_path: str
    db_exists: bool
    profile_exists: bool


class StatsOut(BaseModel):
    total_attempts: int
    sent: int
    failed: int
    dry_runs: int
    skipped_dedup: int
    today_sent: int
    by_region: dict[str, int]
    by_source: dict[str, Any]
    recent: list[dict[str, Any]] = Field(default_factory=list)


class SendRowOut(BaseModel):
    index: int
    company: str
    role: str
    cold_email: bool = False
    email: str
    job_description: str | None = None
    key_skills: str | None = None
    why_match: str | None = None
    referral_name: str | None = None
    valid_email: bool
    resume_path: str | None = None
    resume_filename: str | None = None
    already_applied: bool = False


class ExcelFileOut(BaseModel):
    path: str
    name: str
    region: str
    size: int
    modified_at: str


class ExcelPreviewOut(BaseModel):
    path: str
    region: str
    total_rows: int
    invalid_email_count: int
    already_applied_count: int
    rows: list[SendRowOut]


class SendJobRequest(BaseModel):
    excel_path: str
    region: str
    dry_run: bool = True
    row_indexes: list[int] = Field(default_factory=list)
    resume_overrides: dict[int, str] = Field(default_factory=dict)


class GenerateResumeRequest(BaseModel):
    company: str
    role: str
    region: str
    job_description: str | None = None
    overwrite: bool = False
    source_paths: list[str] = Field(default_factory=list)


class ProfilePhones(BaseModel):
    india: str = ""
    uae: str = ""


class ProfileLocation(BaseModel):
    inr: str = ""
    uae: str = ""


class ProfileLinks(BaseModel):
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""


class ProfileIdentity(BaseModel):
    name: str = ""
    headline: str = ""
    email: str = ""
    phones: ProfilePhones = Field(default_factory=ProfilePhones)
    location: ProfileLocation = Field(default_factory=ProfileLocation)
    links: ProfileLinks = Field(default_factory=ProfileLinks)
    languages: list[str] = Field(default_factory=list)


class ProfileSummaries(BaseModel):
    inr: str = ""
    uae: str = ""


class SkillGroup(BaseModel):
    id: str = ""
    group: str = ""
    items: str = ""


class ExperienceEntry(BaseModel):
    id: str = ""
    title: str = ""
    company: str = ""
    dates: str = ""
    location: str = ""
    bullets: list[str] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    id: str = ""
    name: str = ""
    tech: str = ""
    bullets: list[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    id: str = ""
    degree: str = ""
    dates: str = ""
    school: str = ""


class ProfileDocument(BaseModel):
    identity: ProfileIdentity = Field(default_factory=ProfileIdentity)
    summaries: ProfileSummaries = Field(default_factory=ProfileSummaries)
    skills: list[SkillGroup] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    awards: list[str] = Field(default_factory=list)
    email_rules: str = ""


class ImportBaseRequest(BaseModel):
    confirm: bool = False
