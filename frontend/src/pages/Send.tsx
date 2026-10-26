import { useEffect, useMemo, useState } from "react";
import PageHeader from "../components/PageHeader";
import ResumePreview from "../components/ResumePreview";
import { api, formatBytes, formatDate } from "../api";
import type { ExcelFile, ExcelPreview, Job, JobEvent, PreviewRow, Region, ResumePdf } from "../types";

const ACTIVE = new Set(["queued", "running", "cancelling"]);

export default function Send() {
  const [files, setFiles] = useState<ExcelFile[]>([]);
  const [region, setRegion] = useState<Region>("INR");
  const [selectedPath, setSelectedPath] = useState<string>("");
  const [preview, setPreview] = useState<ExcelPreview | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [overrides, setOverrides] = useState<Record<number, string>>({});
  const [resumes, setResumes] = useState<ResumePdf[]>([]);
  const [dryRun, setDryRun] = useState(true);
  const [confirmText, setConfirmText] = useState("");
  const [showConfirm, setShowConfirm] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [busyRow, setBusyRow] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [resumePreview, setResumePreview] = useState<ResumePdf | null>(null);

  const loadFiles = () => {
    api
      .excelFiles()
      .then((payload) => setFiles(payload.files))
      .catch((err: Error) => setError(err.message));
  };

  useEffect(() => {
    loadFiles();
    api
      .currentJob()
      .then((payload) => {
        if (payload.job) {
          setJob(payload.job);
          setEvents(ACTIVE.has(payload.job.status) ? [] : payload.job.events);
        }
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    api
      .resumes(region)
      .then((payload) => {
        const pdfs = payload.regions.flatMap((item) => item.folders.flatMap((folder) => folder.pdfs));
        setResumes(pdfs);
      })
      .catch(() => undefined);
  }, [region]);

  useEffect(() => {
    if (!job || !ACTIVE.has(job.status)) return;
    setEvents([]);
    const source = new EventSource(`/api/jobs/${job.id}/stream`);
    source.onmessage = (message) => {
      const event = JSON.parse(message.data) as JobEvent;
      setEvents((current) => [...current, event]);
      if (event.type === "done" || event.type === "cancelled" || event.type === "error") {
        source.close();
        api.getJob(job.id).then(setJob).catch(() => undefined);
      }
    };
    source.onerror = () => source.close();
    return () => source.close();
  }, [job?.id, job?.status]);

  const openPreview = async (path: string, nextRegion?: Region) => {
    setLoadingPreview(true);
    setError(null);
    setSelectedPath(path);
    try {
      const data = await api.previewExcel(path, nextRegion || region);
      setPreview(data);
      setRegion(data.region);
      const defaults = new Set(
        data.rows.filter((row) => row.valid_email && !row.already_applied).map((row) => row.index),
      );
      setSelected(defaults);
      setOverrides({});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setLoadingPreview(false);
    }
  };

  const onUpload = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const uploaded = await api.uploadExcel(file, region);
      loadFiles();
      await openPreview(uploaded.path, uploaded.region);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const toggleAll = (checked: boolean) => {
    if (!preview) return;
    setSelected(checked ? new Set(preview.rows.filter((row) => row.valid_email).map((row) => row.index)) : new Set());
  };

  const toggleRow = (index: number, checked: boolean) => {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(index);
      else next.delete(index);
      return next;
    });
  };

  const generateForRow = async (row: PreviewRow) => {
    setBusyRow(row.index);
    setError(null);
    try {
      const generated = await api.generateResume({
        company: row.company,
        role: row.role,
        region,
        job_description: row.job_description,
        overwrite: false,
      });
      if (generated.path.endsWith(".pdf")) {
        setOverrides((current) => ({ ...current, [row.index]: generated.path }));
        setResumes((current) => {
          if (current.some((item) => item.path === generated.path)) return current;
          return [...current, { path: generated.path, filename: generated.filename, folder: "generated" }];
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generate failed");
    } finally {
      setBusyRow(null);
    }
  };

  const startJob = async () => {
    if (!preview) return;
    setError(null);
    setEvents([]);
    try {
      const created = await api.startSend({
        excel_path: preview.path,
        region,
        dry_run: dryRun,
        row_indexes: [...selected],
        resume_overrides: overrides,
      });
      setJob(created);
      setShowConfirm(false);
      setConfirmText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start send");
    }
  };

  const onStartClick = () => {
    if (!dryRun) {
      setShowConfirm(true);
      return;
    }
    void startJob();
  };

  const selectedCount = selected.size;
  const jobActive = Boolean(job && ACTIVE.has(job.status));
  const regionFiles = useMemo(() => files.filter((file) => file.region === region), [files, region]);

  return (
    <div className="page">
      <PageHeader
        title="Send emails"
        description="Rows with a role get an application email. Rows with no role get a cold email as an AI Full Stack Developer, with that resume attached."
      />

      {error && <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

      <section className="card">
        <div className="flex flex-col gap-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Step 1</p>
          <h2 className="font-semibold">Pick an Excel file</h2>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex gap-2">
            {(["INR", "UAE"] as Region[]).map((value) => (
              <button key={value} type="button" onClick={() => setRegion(value)} className={region === value ? "btn-primary" : "btn-secondary"}>
                {value}
              </button>
            ))}
          </div>
          <label className="btn-secondary cursor-pointer">
            {uploading ? "Uploading…" : "Upload Excel"}
            <input
              type="file"
              accept=".xlsx,.xls"
              className="hidden"
              onChange={(event) => void onUpload(event.target.files?.[0])}
            />
          </label>
        </div>

        <div className="flex flex-col gap-2">
          {regionFiles.length === 0 && <p className="text-sm text-slate-500">No Excel files in {region}_Excel yet.</p>}
          {regionFiles.map((file) => (
            <button
              key={file.path}
              type="button"
              onClick={() => void openPreview(file.path, file.region)}
              className={`flex items-center justify-between rounded-xl border px-3 py-3 text-left text-sm ${
                selectedPath === file.path ? "border-indigo-400 bg-indigo-50" : "border-slate-200 hover:border-slate-300"
              }`}
            >
              <span className="font-medium">{file.name}</span>
              <span className="text-slate-500">
                {formatBytes(file.size)} · {formatDate(file.modified_at)}
              </span>
            </button>
          ))}
        </div>
      </section>

      {loadingPreview && <p className="text-sm text-slate-500">Reading Excel…</p>}

      {preview && (
        <section className="card">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-col gap-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Step 2</p>
              <h2 className="font-semibold">{preview.path}</h2>
              <p className="text-sm text-slate-500">
                {preview.total_rows} rows · {preview.rows.filter((row) => !row.role).length} cold emails · {preview.invalid_email_count} invalid emails · {preview.already_applied_count} already applied
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={dryRun} onChange={(event) => setDryRun(event.target.checked)} />
                Dry run (recommended)
              </label>
              <button
                type="button"
                disabled={selectedCount === 0 || jobActive}
                onClick={onStartClick}
                className={dryRun ? "btn-primary" : "btn-danger"}
              >
                {dryRun ? `Dry-run ${selectedCount}` : `Send ${selectedCount} live`}
              </button>
              {jobActive && job && (
                <button type="button" onClick={() => void api.cancelJob(job.id)} className="btn-secondary">
                  Cancel
                </button>
              )}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className="th">
                    <input
                      type="checkbox"
                      checked={preview.rows.filter((row) => row.valid_email).every((row) => selected.has(row.index)) && selectedCount > 0}
                      onChange={(event) => toggleAll(event.target.checked)}
                    />
                  </th>
                  <th className="th">Company</th>
                  <th className="th">Role</th>
                  <th className="th">Email</th>
                  <th className="th">Resume</th>
                  <th className="th">Status</th>
                  <th className="th">Actions</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row) => (
                  <tr key={row.index} className="border-t border-slate-100 align-top hover:bg-slate-50">
                    <td className="td">
                      <input
                        type="checkbox"
                        disabled={!row.valid_email}
                        checked={selected.has(row.index)}
                        onChange={(event) => toggleRow(row.index, event.target.checked)}
                      />
                    </td>
                    <td className="td font-medium">{row.company || "—"}</td>
                    <td className="td">
                      {row.role ? (
                        row.role
                      ) : (
                        <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
                          Cold mail
                        </span>
                      )}
                    </td>
                    <td className="td">{row.email || "—"}</td>
                    <td className="td">
                      <select
                        value={overrides[row.index] || row.resume_path || ""}
                        onChange={(event) => setOverrides((current) => ({ ...current, [row.index]: event.target.value }))}
                        className="field max-w-56"
                      >
                        {!row.resume_path && <option value="">No resume</option>}
                        {row.resume_path && !resumes.some((pdf) => pdf.path === row.resume_path) && (
                          <option value={row.resume_path}>{row.resume_filename}</option>
                        )}
                        {resumes.map((pdf) => (
                          <option key={pdf.path} value={pdf.path}>
                            {pdf.filename}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="td">
                      {!row.valid_email && <span className="text-rose-600">Invalid email</span>}
                      {row.valid_email && row.already_applied && <span className="text-amber-600">Already applied</span>}
                      {row.valid_email && !row.already_applied && <span className="text-emerald-600">Ready</span>}
                    </td>
                    <td className="td">
                      <div className="flex gap-3">
                        <button
                          type="button"
                          disabled={!(overrides[row.index] || row.resume_path)}
                          onClick={() => {
                            const path = overrides[row.index] || row.resume_path;
                            if (!path) return;
                            const match = resumes.find((pdf) => pdf.path === path);
                            setResumePreview({ path, filename: match?.filename || row.resume_filename || path, folder: match?.folder || "" });
                          }}
                          className="text-sm font-medium text-indigo-600 disabled:opacity-40"
                        >
                          Preview
                        </button>
                        <button
                          type="button"
                          disabled={busyRow === row.index || !row.role}
                          title={row.role ? "Generate a resume for this role" : "Cold mail uses the AI Full Stack resume"}
                          onClick={() => void generateForRow(row)}
                          className="text-sm font-medium text-indigo-600 disabled:opacity-40"
                        >
                          {busyRow === row.index ? "Generating…" : "Generate"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {(job || events.length > 0) && (
        <section className="card">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Live progress</h2>
            {job && (
              <p className="text-sm text-slate-500">
                {job.status} · sent {job.sent} · failed {job.failed} · skipped {job.skipped}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-1 rounded-lg bg-slate-950 p-3 font-mono text-xs text-slate-100">
            {events.length === 0 && <p>Waiting for events…</p>}
            {events.map((event, index) => (
              <p key={`${event.type}-${index}`}>
                {eventLabel(event)}
              </p>
            ))}
          </div>
        </section>
      )}

      {showConfirm && (
        <div className="fixed inset-0 z-10 flex items-center justify-center bg-slate-950/60">
          <div className="flex w-full max-w-md flex-col gap-4 rounded-2xl bg-white p-5">
            <h2 className="text-lg font-semibold">Send live emails?</h2>
            <p className="text-sm text-slate-600">
              This will send real messages through SMTP with a 10-second delay between emails. Type <span className="font-semibold">SEND</span> to confirm.
            </p>
            <input
              value={confirmText}
              onChange={(event) => setConfirmText(event.target.value)}
              className="field"
              placeholder="SEND"
            />
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setShowConfirm(false)} className="btn-secondary">
                Cancel
              </button>
              <button type="button" disabled={confirmText !== "SEND"} onClick={() => void startJob()} className="btn-danger">
                Send live
              </button>
            </div>
          </div>
        </div>
      )}
      {resumePreview && (
        <ResumePreview path={resumePreview.path} filename={resumePreview.filename} onClose={() => setResumePreview(null)} />
      )}
    </div>
  );
}

function eventLabel(event: JobEvent): string {
  if (event.type === "started") return `Started ${event.total} row(s)${event.dry_run ? " (dry-run)" : ""}`;
  if (event.type === "generating") return `[${event.position}/${event.total}] Generating body for ${event.company} <${event.email}>`;
  if (event.type === "sending") return `[${event.position}/${event.total}] ${event.dry_run ? "Dry-run" : "Sending"} ${event.email}`;
  if (event.type === "sent") return `[${event.position}/${event.total}] Sent ${event.email}`;
  if (event.type === "skipped") return `[${event.position}/${event.total}] Skipped ${event.email}: ${event.reason}`;
  if (event.type === "failed") return `[${event.position}/${event.total}] Failed ${event.email}: ${event.reason}`;
  if (event.type === "waiting") return `Waiting ${event.seconds_left}s before next email`;
  if (event.type === "cancelled") return "Job cancelled";
  if (event.type === "done") return `Done. sent=${event.sent} failed=${event.failed} skipped=${event.skipped}`;
  if (event.type === "error") return `Error: ${event.reason}`;
  return event.type;
}
