import type { Country, Health, Job, Mailbox, Preview, Profile, ProfileDraft, ResumeMode, Run, SendRow, Stats, StoredResume, User } from "./types";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function messageFrom(data: unknown, fallback: string) {
  if (!data || typeof data !== "object" || !("detail" in data)) return fallback;
  const detail = (data as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === "object" && item && "msg" in item ? String((item as { msg: unknown }).msg) : String(item)))
      .join(" ");
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}, redirectOn401 = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...init, headers, credentials: "include" });
  if (response.status === 401 && redirectOn401 && !["/login", "/register"].includes(window.location.pathname)) {
    window.location.assign("/login");
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(response.status, messageFrom(data, response.statusText));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const profileDraftKey = "apply-desk-profile-draft";

export function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export const api = {
  me: () => request<User>("/api/auth/me", {}, false),
  register: (email: string, password: string) =>
    request<User>("/api/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }, false),
  login: (email: string, password: string) =>
    request<User>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }, false),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }, false),
  health: () => request<Health>("/api/health", {}, false),
  stats: () => request<Stats>("/api/stats"),
  history: () => request<SendRow[]>("/api/sends"),
  profile: () => request<Profile>("/api/profile"),
  saveProfile: (profile: Profile) => request<Profile>("/api/profile", { method: "PUT", body: JSON.stringify(profile) }),
  uploadResume: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<Profile>("/api/profile/resume", { method: "POST", body });
  },
  deleteResume: () => request<Profile>("/api/profile/resume", { method: "DELETE" }),
  importProfile: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<ProfileDraft>("/api/profile/import", { method: "POST", body });
  },
  resumes: () => request<StoredResume[]>("/api/resumes"),
  uploadCountryResume: (countryId: string, file: File) => {
    const body = new FormData();
    body.append("country_id", countryId);
    body.append("file", file);
    return request<StoredResume>("/api/resumes", { method: "POST", body });
  },
  makeDefaultResume: (id: string) => request<StoredResume>(`/api/resumes/${id}/default`, { method: "POST" }),
  deleteCountryResume: (id: string) => request<{ ok: boolean }>(`/api/resumes/${id}`, { method: "DELETE" }),
  fillFromResume: (id: string) => request<ProfileDraft>(`/api/resumes/${id}/fill`, { method: "POST" }),
  countries: () => request<Country[]>("/api/countries"),
  createCountry: (payload: Omit<Country, "id">) =>
    request<Country>("/api/countries", { method: "POST", body: JSON.stringify(payload) }),
  updateCountry: (id: string, payload: Omit<Country, "id">) =>
    request<Country>(`/api/countries/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteCountry: (id: string) => request<{ ok: boolean }>(`/api/countries/${id}`, { method: "DELETE" }),
  mailbox: () => request<Mailbox>("/api/mailbox"),
  saveMailbox: (payload: Mailbox & { password: string }) =>
    request<Mailbox>("/api/mailbox", { method: "PUT", body: JSON.stringify(payload) }),
  testMailbox: (payload: Mailbox & { password: string }) =>
    request<Mailbox>("/api/mailbox/test", { method: "POST", body: JSON.stringify(payload) }),
  jobs: () => request<Job[]>("/api/jobs"),
  createJob: (payload: {
    company: string;
    role: string;
    contact_email: string;
    job_description: string;
    skills: string;
    country_id: string | null;
    referral_name: string;
  }) => request<Job>("/api/jobs", { method: "POST", body: JSON.stringify(payload) }),
  setJobResume: (id: string, resumeId: string) =>
    request<Job>(`/api/jobs/${id}/resume`, { method: "PUT", body: JSON.stringify({ resume_id: resumeId }) }),
  deleteJob: (id: string) => request<{ ok: boolean }>(`/api/jobs/${id}`, { method: "DELETE" }),
  uploadJobs: (file: File, countryId: string) => {
    const body = new FormData();
    body.append("file", file);
    body.append("country_id", countryId);
    return request<{ created: number; skipped: string[]; columns: string[]; jobs: Job[] }>("/api/jobs/upload", { method: "POST", body });
  },
  preview: (jobIds: string[], countryId: string, resumeMode: ResumeMode) =>
    request<Preview[]>("/api/jobs/preview", {
      method: "POST",
      body: JSON.stringify({ job_ids: jobIds, country_id: countryId, resume_mode: resumeMode }),
    }),
  startSend: (dryRun: boolean, items: Array<{ job_id: string; subject: string; body: string; resume_mode: ResumeMode; resume_id: string; country_id: string }>) =>
    request<Run>("/api/sends", { method: "POST", body: JSON.stringify({ dry_run: dryRun, items }) }),
  sendRun: (id: string) => request<Run>(`/api/sends/runs/${id}`),
};
