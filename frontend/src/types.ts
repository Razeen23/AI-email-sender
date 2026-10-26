export type Region = "INR" | "UAE";

export type Health = {
  smtp_configured: boolean;
  smtp_host: string | null;
  smtp_port: number | null;
  from_email: string | null;
  ollama_reachable: boolean;
  ollama_base_url: string;
  ollama_model: string;
  ollama_models: string[];
  db_path: string;
  db_exists: boolean;
  profile_exists: boolean;
};

export type SendRecord = {
  id: number;
  created_at: string;
  recipient_email: string;
  success: number;
  dry_run: number;
  company: string | null;
  role: string | null;
  region: string | null;
  subject: string | null;
  pdf_path: string | null;
  pdf_filename: string | null;
  excel_path: string | null;
  failure_reason: string | null;
  source: string;
};

export type Stats = {
  total_attempts: number;
  sent: number;
  failed: number;
  dry_runs: number;
  skipped_dedup: number;
  today_sent: number;
  by_region: Record<string, number>;
  by_source: Record<string, { attempts: number; sent: number }>;
  recent: SendRecord[];
};

export type SendsPage = {
  items: SendRecord[];
  total: number;
  limit: number;
  offset: number;
};

export type ExcelFile = {
  path: string;
  name: string;
  region: Region;
  size: number;
  modified_at: string;
};

export type PreviewRow = {
  index: number;
  company: string;
  role: string;
  cold_email?: boolean;
  email: string;
  job_description: string | null;
  key_skills: string | null;
  why_match: string | null;
  referral_name: string | null;
  valid_email: boolean;
  resume_path: string | null;
  resume_filename: string | null;
  already_applied: boolean;
};

export type ExcelPreview = {
  path: string;
  region: Region;
  total_rows: number;
  invalid_email_count: number;
  already_applied_count: number;
  rows: PreviewRow[];
};

export type JobEvent = {
  type: string;
  index?: number;
  position?: number;
  total?: number;
  company?: string;
  role?: string;
  email?: string;
  reason?: string;
  resume_path?: string;
  dry_run?: boolean;
  seconds_left?: number;
  sent?: number;
  failed?: number;
  skipped?: number;
  processed?: number;
  status?: string;
};

export type Job = {
  id: string;
  status: string;
  dry_run: boolean;
  excel_path: string;
  region: string;
  total: number;
  processed: number;
  sent: number;
  failed: number;
  skipped: number;
  events: JobEvent[];
  error: string | null;
  started_at: string;
  finished_at: string | null;
};

export type ResumePdf = {
  path: string;
  filename: string;
  folder: string;
};

export type ResumeFolder = {
  name: string;
  generated: boolean;
  pdfs: ResumePdf[];
};

export type ResumeRegion = {
  region: Region;
  folders: ResumeFolder[];
};

export type GeneratedResume = {
  path: string;
  filename: string;
  region: string;
  existed: boolean;
  markdown_only: boolean;
};

export type SkillGroup = {
  id: string;
  group: string;
  items: string;
};

export type ExperienceEntry = {
  id: string;
  title: string;
  company: string;
  dates: string;
  location: string;
  bullets: string[];
};

export type ProjectEntry = {
  id: string;
  name: string;
  tech: string;
  bullets: string[];
};

export type EducationEntry = {
  id: string;
  degree: string;
  dates: string;
  school: string;
};

export type ProfileDocument = {
  identity: {
    name: string;
    headline: string;
    email: string;
    phones: { india: string; uae: string };
    location: { inr: string; uae: string };
    links: { linkedin: string; github: string; portfolio: string };
    languages: string[];
  };
  summaries: { inr: string; uae: string };
  skills: SkillGroup[];
  experience: ExperienceEntry[];
  projects: ProjectEntry[];
  education: EducationEntry[];
  certifications: string[];
  awards: string[];
  email_rules: string;
};
