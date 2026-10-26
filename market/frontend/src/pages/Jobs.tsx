import { FormEvent, useEffect, useRef, useState } from "react";
import { api } from "../api";
import Field from "../components/Field";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import type { Country, Job, Preview, ResumeMode, Run, StoredResume } from "../types";

const emptyJob = {
  company: "",
  role: "",
  contact_email: "",
  job_description: "",
  skills: "",
  referral_name: "",
};

function leadTitle(job: { company: string; role: string; contact_email: string }) {
  const name = job.company || job.contact_email;
  if (!name) return "Removed row";
  return `${name} · ${job.role || "Cold email"}`;
}

export default function Jobs() {
  const [countries, setCountries] = useState<Country[]>([]);
  const [resumes, setResumes] = useState<StoredResume[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [countryId, setCountryId] = useState("");
  const [resumeMode, setResumeMode] = useState<ResumeMode>("own");
  const [draft, setDraft] = useState(emptyJob);
  const [adding, setAdding] = useState(false);
  const [sheetHeaders, setSheetHeaders] = useState<string[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [previews, setPreviews] = useState<Preview[]>([]);
  const [dryRun, setDryRun] = useState(true);
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    api
      .jobs()
      .then((next) => {
        setJobs(next);
        const ids = new Set(next.map((job) => job.id));
        setSelected((current) => current.filter((id) => ids.has(id)));
        setPreviews((current) => current.filter((item) => ids.has(item.job_id)));
      })
      .catch((err: Error) => setError(err.message));
    api.countries().then(setCountries).catch(() => undefined);
    api.resumes().then(setResumes).catch(() => undefined);
  };

  useEffect(() => {
    load();
  }, []);

  const runId = run?.id;
  const runStatus = run?.status;
  useEffect(() => {
    if (!runId || runStatus !== "running") return;
    const timer = window.setInterval(() => {
      api.sendRun(runId).then(setRun).catch((err: Error) => setError(err.message));
    }, 800);
    return () => window.clearInterval(timer);
  }, [runId, runStatus]);

  const toggle = (id: string) => {
    setSelected((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  };

  const addJob = (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    api
      .createJob({ ...draft, country_id: countryId || null })
      .then(() => {
        setDraft(emptyJob);
        setAdding(false);
        load();
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setBusy(false));
  };

  const upload = (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    api
      .uploadJobs(file, countryId)
      .then((result) => {
        const resumeNote = resumeMode === "own" ? " Each row uses that country's default resume until you change it." : "";
        setNotice(`Replaced the list with ${result.created} job${result.created === 1 ? "" : "s"} from this file.${resumeNote}`);
        setSheetHeaders(result.columns);
        setJobs(result.jobs);
        setSelected([]);
        setPreviews([]);
        if (result.skipped.length) setError(result.skipped.join(" "));
        load();
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setBusy(false));
  };

  const preview = () => {
    const ids = selected.filter((id) => jobs.some((job) => job.id === id));
    if (!ids.length) {
      setPreviews([]);
      setError("Select a job from the current list. A new spreadsheet replaces the previous rows.");
      return;
    }
    setBusy(true);
    setError(null);
    setRun(null);
    api
      .preview(ids, countryId, resumeMode)
      .then((rows) => {
        const current = rows.filter((row) => !row.error.includes("not on your list"));
        setPreviews(current);
        if (current.length !== rows.length) {
          setError("Some selected rows were replaced by a newer spreadsheet. Preview the jobs that are in the list now.");
        }
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setBusy(false));
  };

  const updatePreview = (jobId: string, patch: Partial<Preview>) => {
    setPreviews((current) => current.map((item) => (item.job_id === jobId ? { ...item, ...patch } : item)));
  };

  const send = () => {
    const items = previews
      .filter((item) => !item.error && item.subject.trim() && item.body.trim())
      .map((item) => ({
        job_id: item.job_id,
        subject: item.subject,
        body: item.body,
        resume_mode: resumeMode,
        resume_id: jobs.find((job) => job.id === item.job_id)?.resume_id || item.resume_id || "",
        country_id: countryId,
      }));
    if (!items.length) {
      setError("Preview at least one job that has a subject and body.");
      return;
    }
    setBusy(true);
    setError(null);
    api
      .startSend(dryRun, items)
      .then(setRun)
      .catch((err: Error) => setError(err.message))
      .finally(() => setBusy(false));
  };

  const running = run?.status === "running";

  const resumesFor = (job: Job) => resumes.filter((resume) => resume.country_id === (job.country_id || countryId));

  const chooseResume = (job: Job, resumeId: string) => {
    if (!resumeId) return;
    api
      .setJobResume(job.id, resumeId)
      .then((updated) => setJobs((current) => current.map((item) => (item.id === updated.id ? updated : item))))
      .catch((err: Error) => setError(err.message));
  };

  return (
    <div className="page">
      <PageHeader
        title="Jobs"
        description="Pick a country, then either attach one of your resumes or generate one. Dry run is the default and does not use your mailbox."
      />
      {notice && <p className="text-sm text-emerald-700">{notice}</p>}
      {error && <p className="text-sm text-rose-600">{error}</p>}

      <section className="card">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Target country">
            <select className="field" value={countryId} onChange={(event) => setCountryId(event.target.value)}>
              <option value="">Use each job's country</option>
              {countries.map((country) => (
                <option key={country.id} value={country.id}>
                  {country.label}
                </option>
              ))}
            </select>
          </Field>
          <button type="button" className="btn-secondary" disabled={busy} onClick={() => fileRef.current?.click()}>
            Upload a spreadsheet
          </button>
          <button type="button" className="btn-secondary" onClick={() => setAdding((open) => !open)}>
            {adding ? "Close job form" : "Add a job"}
          </button>
          <div className="flex gap-2">
            {(["own", "generated"] as ResumeMode[]).map((mode) => (
              <button key={mode} type="button" className={resumeMode === mode ? "btn-primary" : "btn-secondary"} onClick={() => setResumeMode(mode)}>
                {mode === "own" ? "Use my resumes" : "Generate a resume"}
              </button>
            ))}
          </div>
        </div>
        <input
          ref={fileRef}
          className="sr-only"
          type="file"
          accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
          onChange={(event) => {
            upload(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
        <p className="text-sm text-slate-500">Email is required. A blank role sends a cold email. A new spreadsheet replaces the previous one.</p>
        {sheetHeaders.length > 0 && <p className="text-sm text-slate-700">Columns in this file: {sheetHeaders.join(", ")}</p>}
        {countries.length === 0 && <p className="text-sm text-slate-500">Add a country before you preview.</p>}
      </section>

      {adding && (
      <form onSubmit={addJob} className="card">
          <h2 className="font-semibold">Add a job</h2>
          <Field label="Company">
            <input className="field" value={draft.company} onChange={(event) => setDraft((current) => ({ ...current, company: event.target.value }))} placeholder="Optional" />
          </Field>
          <Field label="Role">
            <input className="field" value={draft.role} onChange={(event) => setDraft((current) => ({ ...current, role: event.target.value }))} placeholder="Leave blank for a cold email" />
          </Field>
          <Field label="Contact email">
            <input className="field" type="email" value={draft.contact_email} onChange={(event) => setDraft((current) => ({ ...current, contact_email: event.target.value }))} required />
          </Field>
          <Field label="Referral name">
            <input className="field" value={draft.referral_name} onChange={(event) => setDraft((current) => ({ ...current, referral_name: event.target.value }))} />
          </Field>
          <Field label="Skills">
            <input className="field" value={draft.skills} onChange={(event) => setDraft((current) => ({ ...current, skills: event.target.value }))} placeholder="Optional" />
          </Field>
          <Field label="Job description">
            <textarea className="field" rows={4} value={draft.job_description} onChange={(event) => setDraft((current) => ({ ...current, job_description: event.target.value }))} />
          </Field>
          <button type="submit" className="btn-primary w-fit" disabled={busy}>
            Add job
          </button>
      </form>
      )}

      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-semibold">Your jobs</h2>
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input type="checkbox" checked={dryRun} onChange={(event) => setDryRun(event.target.checked)} />
              Dry run
            </label>
            <button type="button" className="btn-secondary" disabled={busy || running || selected.length === 0} onClick={preview}>
              {busy ? "Working…" : "Preview"}
            </button>
            <button type="button" className="btn-primary" disabled={busy || running || previews.every((item) => Boolean(item.error))} onClick={send}>
              {running ? "Sending…" : dryRun ? "Run dry send" : "Send applications"}
            </button>
          </div>
        </div>
        {jobs.length === 0 && <p className="text-sm text-slate-500">No jobs yet.</p>}
        <div className="flex flex-col gap-2">
          {jobs.map((job) => (
            <article key={job.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 px-3 py-3">
              <label className="flex min-w-0 items-center gap-3">
                <input type="checkbox" checked={selected.includes(job.id)} onChange={() => toggle(job.id)} />
                <span className="flex min-w-0 flex-col">
                  <span className="truncate text-sm font-medium">{leadTitle(job)}</span>
                  <span className="truncate text-xs text-slate-500">
                    {job.contact_email}
                    {job.country_label ? ` · ${job.country_label}` : ""}
                  </span>
                </span>
              </label>
              {resumeMode === "own" ? (
                <select
                  className="field max-w-xs"
                  value={job.resume_id || resumesFor(job).find((resume) => resume.is_default)?.id || ""}
                  onChange={(event) => chooseResume(job, event.target.value)}
                >
                  <option value="">Choose a resume</option>
                  {resumesFor(job).map((resume) => (
                    <option key={resume.id} value={resume.id}>
                      {resume.filename}
                      {resume.is_default ? " (default)" : ""}
                    </option>
                  ))}
                </select>
              ) : (
                <span className="text-xs text-slate-500">Generated resume</span>
              )}
              <button
                type="button"
                className="btn-secondary"
                onClick={() =>
                  api
                    .deleteJob(job.id)
                    .then(() => {
                      setSelected((current) => current.filter((id) => id !== job.id));
                      setPreviews((current) => current.filter((item) => item.job_id !== job.id));
                      load();
                    })
                    .catch((err: Error) => setError(err.message))
                }
              >
                Remove
              </button>
            </article>
          ))}
        </div>
        {run && (
          <div className="flex flex-col gap-2 rounded-xl bg-slate-50 px-3 py-3 text-sm">
            <p>
              {run.status === "running" ? "Running" : "Finished"} · {run.processed}/{run.total} · {run.sent} sent · {run.dry_runs} dry runs · {run.failed} failed · {run.skipped} duplicates
            </p>
            {run.error && <p className="text-rose-600">{run.error}</p>}
            {run.results.map((result) => (
              <div key={result.job_id} className="flex items-center justify-between gap-3">
                <span>{result.company || result.job_id}</span>
                <span className="flex items-center gap-2">
                  {result.error && <span className="text-xs text-rose-600">{result.error}</span>}
                  <StatusBadge status={result.status} />
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {previews.length > 0 && (
        <section className="flex flex-col gap-4">
          {previews.map((preview) => (
            <article key={preview.job_id} className="card">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-semibold">{leadTitle(preview)}</h2>
                <span className="text-sm text-slate-500">{preview.country_label}</span>
              </div>
              {preview.error && <p className="text-sm text-rose-600">{preview.error}</p>}
              {preview.warning && <p className="text-sm text-amber-700">{preview.warning}</p>}
              {!preview.error && (
                <>
                  <Field label="Subject">
                    <input className="field" value={preview.subject} onChange={(event) => updatePreview(preview.job_id, { subject: event.target.value })} />
                  </Field>
                  <Field label="Body">
                    <textarea className="field" rows={8} value={preview.body} onChange={(event) => updatePreview(preview.job_id, { body: event.target.value })} />
                  </Field>
                  <p className="text-sm text-slate-500">
                    Resume: {preview.resume_filename || "not ready"}
                    {preview.pdf_ready && resumeMode === "generated" && (
                      <>
                        {" "}
                        ·{" "}
                        <a className="font-medium text-indigo-600" href={`/api/resumes/generated/${preview.job_id}`} target="_blank" rel="noreferrer">
                          Open PDF
                        </a>
                      </>
                    )}
                    {resumeMode === "own" && preview.resume_id && (
                      <>
                        {" "}
                        ·{" "}
                        <a className="font-medium text-indigo-600" href={`/api/resumes/file/${preview.resume_id}`} target="_blank" rel="noreferrer">
                          Open resume
                        </a>
                      </>
                    )}
                  </p>
                  {preview.markdown && (
                    <details className="flex flex-col gap-2">
                      <summary className="cursor-pointer text-sm font-medium text-indigo-600">Resume text</summary>
                      <pre className="whitespace-pre-wrap text-xs text-slate-600">{preview.markdown}</pre>
                    </details>
                  )}
                </>
              )}
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
