from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=72)


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    id: str
    email: str


class SkillIn(BaseModel):
    id: str = ""
    group: str = ""
    items: str = ""


class ExperienceIn(BaseModel):
    id: str = ""
    title: str = ""
    company: str = ""
    dates: str = ""
    location: str = ""
    bullets: list[str] = Field(default_factory=list)


class ProjectIn(BaseModel):
    id: str = ""
    name: str = ""
    tech: str = ""
    bullets: list[str] = Field(default_factory=list)


class EducationIn(BaseModel):
    id: str = ""
    degree: str = ""
    school: str = ""
    dates: str = ""


class ProfileIn(BaseModel):
    name: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    country: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    languages: list[str] = Field(default_factory=list)
    summary: str = ""
    skills: list[SkillIn] = Field(default_factory=list)
    experience: list[ExperienceIn] = Field(default_factory=list)
    projects: list[ProjectIn] = Field(default_factory=list)
    education: list[EducationIn] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class ProfileOut(ProfileIn):
    has_base_resume: bool = False
    base_resume_filename: str = ""


class ProfileDraftOut(ProfileIn):
    filled_by: Literal["model", "text"] = "model"


class CountryIn(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    location_line: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=40)


class CountryOut(CountryIn):
    id: str


class ResumeOut(BaseModel):
    id: str
    country_id: str
    filename: str
    is_default: bool
    created_at: str


class ResumeChoiceIn(BaseModel):
    resume_id: str = ""


class MailboxIn(BaseModel):
    host: str = ""
    port: int = 587
    username: str = ""
    from_name: str = ""
    from_email: str = ""
    password: str = ""


class MailboxOut(BaseModel):
    configured: bool
    host: str
    port: int
    username: str
    from_name: str
    from_email: str
    password_set: bool


class JobIn(BaseModel):
    company: str = ""
    role: str = ""
    contact_email: str = ""
    job_description: str = ""
    skills: str = ""
    country_id: str | None = None
    referral_name: str = ""


class JobOut(BaseModel):
    id: str
    company: str
    role: str
    contact_email: str
    job_description: str
    skills: str = ""
    country_id: str | None = None
    country_label: str = ""
    resume_id: str | None = None
    resume_filename: str = ""
    referral_name: str = ""
    created_at: str


class UploadOut(BaseModel):
    created: int
    skipped: list[str]
    columns: list[str] = Field(default_factory=list)
    jobs: list[JobOut] = Field(default_factory=list)


class PreviewIn(BaseModel):
    job_ids: list[str] = Field(default_factory=list)
    country_id: str = ""
    resume_mode: Literal["base", "own", "generated"] = "own"


class PreviewOut(BaseModel):
    job_id: str
    company: str = ""
    role: str = ""
    contact_email: str = ""
    country_label: str = ""
    subject: str = ""
    body: str = ""
    resume_id: str = ""
    resume_filename: str = ""
    pdf_ready: bool = False
    markdown: str = ""
    warning: str = ""
    error: str = ""


class SendItemIn(BaseModel):
    job_id: str
    subject: str = ""
    body: str = ""
    resume_mode: Literal["base", "own", "generated"] = "own"
    resume_id: str = ""
    country_id: str = ""


class SendIn(BaseModel):
    dry_run: bool = True
    items: list[SendItemIn] = Field(default_factory=list)


class SendResultOut(BaseModel):
    job_id: str
    company: str = ""
    status: str
    error: str = ""


class RunOut(BaseModel):
    id: str
    status: str
    dry_run: bool
    total: int
    processed: int
    sent: int
    failed: int
    skipped: int
    dry_runs: int
    results: list[SendResultOut]
    error: str = ""


class SendRowOut(BaseModel):
    id: str
    company: str
    role: str
    contact_email: str
    country_label: str
    status: str
    subject: str
    body: str
    error: str
    resume_filename: str
    created_at: str


class StatsOut(BaseModel):
    today_sent: int
    sent: int
    failed: int
    dry_runs: int
    skipped_dedup: int
    total_attempts: int
    by_country: dict[str, int]
    recent: list[SendRowOut]


class HealthOut(BaseModel):
    ollama_reachable: bool
    ollama_base_url: str
    ollama_model: str
    db_exists: bool
