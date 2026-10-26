export type User = {
  id: string;
  email: string;
};

export type Skill = {
  id: string;
  group: string;
  items: string;
};

export type Experience = {
  id: string;
  title: string;
  company: string;
  dates: string;
  location: string;
  bullets: string[];
};

export type Project = {
  id: string;
  name: string;
  tech: string;
  bullets: string[];
};

export type Education = {
  id: string;
  degree: string;
  school: string;
  dates: string;
};

export type Profile = {
  name: string;
  headline: string;
  email: string;
  phone: string;
  city: string;
  country: string;
  linkedin: string;
  github: string;
  portfolio: string;
  languages: string[];
  summary: string;
  skills: Skill[];
  experience: Experience[];
  projects: Project[];
  education: Education[];
  certifications: string[];
  has_base_resume: boolean;
  base_resume_filename: string;
};

export type ProfileDraft = Omit<Profile, "has_base_resume" | "base_resume_filename"> & {
  filled_by: "model" | "text";
};

export type StoredResume = {
  id: string;
  country_id: string;
  filename: string;
  is_default: boolean;
  created_at: string;
};

export type Country = {
  id: string;
  label: string;
  location_line: string;
  phone: string;
};

export type Mailbox = {
  configured: boolean;
  host: string;
  port: number;
  username: string;
  from_name: string;
  from_email: string;
  password_set: boolean;
};

export type Job = {
  id: string;
  company: string;
  role: string;
  contact_email: string;
  job_description: string;
  skills: string;
  country_id: string | null;
  country_label: string;
  resume_id: string | null;
  resume_filename: string;
  referral_name: string;
  created_at: string;
};

export type Preview = {
  job_id: string;
  company: string;
  role: string;
  contact_email: string;
  country_label: string;
  resume_id: string;
  subject: string;
  body: string;
  resume_filename: string;
  pdf_ready: boolean;
  markdown: string;
  warning: string;
  error: string;
};

export type SendResult = {
  job_id: string;
  company: string;
  status: string;
  error: string;
};

export type Run = {
  id: string;
  status: string;
  dry_run: boolean;
  total: number;
  processed: number;
  sent: number;
  failed: number;
  skipped: number;
  dry_runs: number;
  results: SendResult[];
  error: string;
};

export type SendRow = {
  id: string;
  company: string;
  role: string;
  contact_email: string;
  country_label: string;
  status: string;
  subject: string;
  body: string;
  error: string;
  resume_filename: string;
  created_at: string;
};

export type Stats = {
  today_sent: number;
  sent: number;
  failed: number;
  dry_runs: number;
  skipped_dedup: number;
  total_attempts: number;
  by_country: Record<string, number>;
  recent: SendRow[];
};

export type Health = {
  ollama_reachable: boolean;
  ollama_base_url: string;
  ollama_model: string;
  db_exists: boolean;
};

export type ResumeMode = "own" | "generated";
