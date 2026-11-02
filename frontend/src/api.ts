import type {
  ExcelFile,
  ExcelPreview,
  GeneratedResume,
  Health,
  Job,
  ProfileDocument,
  ResumeRegion,
  SendsPage,
  SingleDraft,
  SingleSendResult,
  SingleSuggestion,
  Stats,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return data as T;
}

export const api = {
  health: () => request<Health>("/api/health"),
  stats: () => request<Stats>("/api/stats"),
  sends: (params: URLSearchParams) => request<SendsPage>(`/api/sends?${params.toString()}`),
  excelFiles: () => request<{ files: ExcelFile[] }>("/api/excel"),
  previewExcel: (path: string, region?: string) => {
    const params = new URLSearchParams({ path });
    if (region) params.set("region", region);
    return request<ExcelPreview>(`/api/excel/preview?${params.toString()}`);
  },
  uploadExcel: async (file: File, region: string) => {
    const body = new FormData();
    body.append("region", region);
    body.append("file", file);
    return request<ExcelFile>("/api/excel/upload", { method: "POST", body });
  },
  startSend: (payload: {
    excel_path: string;
    region: string;
    dry_run: boolean;
    row_indexes: number[];
    resume_overrides: Record<number, string>;
  }) => request<Job>("/api/jobs/send", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
  currentJob: () => request<{ job: Job | null }>("/api/jobs/current"),
  getJob: (id: string) => request<Job>(`/api/jobs/${id}`),
  cancelJob: (id: string) => request<Job>(`/api/jobs/${id}/cancel`, { method: "POST" }),
  resumes: (region?: string) => request<{ regions: ResumeRegion[] }>(region ? `/api/resumes?region=${region}` : "/api/resumes"),
  resumeFileUrl: (path: string) => `/api/resumes/file?path=${encodeURIComponent(path)}`,
  profile: () => request<ProfileDocument>("/api/profile"),
  saveProfile: (profile: ProfileDocument) =>
    request<ProfileDocument>("/api/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    }),
  importBaseProfile: () =>
    request<ProfileDocument>("/api/profile/import/base", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true }),
    }),
  importDocx: async (file: File, region: string) => {
    const body = new FormData();
    body.append("region", region);
    body.append("confirm", "true");
    body.append("file", file);
    return request<ProfileDocument>("/api/profile/import/docx", { method: "POST", body });
  },
  generateResume: (payload: {
    company: string;
    role: string;
    region: string;
    job_description?: string | null;
    overwrite?: boolean;
    source_paths?: string[];
  }) =>
    request<GeneratedResume>("/api/resumes/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  suggestSingle: (payload: {
    email?: string;
    role?: string;
    skills?: string;
    job_description?: string;
    region: string;
  }) =>
    request<SingleSuggestion>("/api/single/suggest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  draftSingle: (payload: {
    email?: string;
    role?: string;
    skills?: string;
    job_description?: string;
    region: string;
  }) =>
    request<SingleDraft>("/api/single/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  sendSingle: (payload: {
    email: string;
    role?: string;
    skills?: string;
    job_description?: string;
    region: string;
    resume_path: string;
    subject: string;
    body: string;
    dry_run: boolean;
  }) =>
    request<SingleSendResult>("/api/single/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  deleteResume: (path: string) =>
    request<{ deleted: string[] }>(`/api/resumes?path=${encodeURIComponent(path)}`, { method: "DELETE" }),
};

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}
