import { useEffect, useMemo, useState } from "react";
import PageHeader from "../components/PageHeader";
import ResumePreview from "../components/ResumePreview";
import { api } from "../api";
import type { Region, ResumePdf, SingleSuggestion } from "../types";

const COUNTRIES: { region: Region; label: string }[] = [
  { region: "INR", label: "India" },
  { region: "UAE", label: "UAE" },
];

function fieldKey(region: Region, role: string, skills: string, jobDescription: string): string {
  return JSON.stringify({ region, role: role.trim(), skills: skills.trim(), jobDescription: jobDescription.trim() });
}

export default function Single() {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [skills, setSkills] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [region, setRegion] = useState<Region>("INR");
  const [resumes, setResumes] = useState<ResumePdf[]>([]);
  const [suggestion, setSuggestion] = useState<SingleSuggestion | null>(null);
  const [resumeOverride, setResumeOverride] = useState<string | null>(null);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [draftKey, setDraftKey] = useState<string | null>(null);
  const [dryRun, setDryRun] = useState(true);
  const [confirmText, setConfirmText] = useState("");
  const [showConfirm, setShowConfirm] = useState(false);
  const [resumePreview, setResumePreview] = useState<ResumePdf | null>(null);
  const [writing, setWriting] = useState(false);
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const currentKey = fieldKey(region, role, skills, jobDescription);
  const selectedResume = resumeOverride ?? suggestion?.resume_path ?? "";
  const draftStale = Boolean(body) && draftKey !== currentKey;
  const canSend = Boolean(email.trim() && selectedResume && subject.trim() && body.trim() && !draftStale);

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
    let cancelled = false;
    const timer = window.setTimeout(() => {
      api
        .suggestSingle({
          email,
          role,
          skills,
          job_description: jobDescription,
          region,
        })
        .then((result) => {
          if (!cancelled) setSuggestion(result);
        })
        .catch(() => undefined);
    }, 300);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [email, role, skills, jobDescription, region]);

  const resumeOptions = useMemo(() => {
    if (!suggestion?.resume_path || resumes.some((pdf) => pdf.path === suggestion.resume_path)) {
      return resumes;
    }
    return [
      {
        path: suggestion.resume_path,
        filename: suggestion.resume_filename || suggestion.resume_path,
        folder: "",
      },
      ...resumes,
    ];
  }, [resumes, suggestion]);

  const writeEmail = async () => {
    setWriting(true);
    setError(null);
    setNotice(null);
    try {
      const draft = await api.draftSingle({
        email,
        role,
        skills,
        job_description: jobDescription,
        region,
      });
      setSubject(draft.subject);
      setBody(draft.body);
      setDraftKey(currentKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not write the email");
    } finally {
      setWriting(false);
    }
  };

  const sendEmail = async () => {
    setSending(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.sendSingle({
        email,
        role,
        skills,
        job_description: jobDescription,
        region,
        resume_path: selectedResume,
        subject,
        body,
        dry_run: dryRun,
      });
      setShowConfirm(false);
      setConfirmText("");
      setNotice(
        result.dry_run
          ? `Dry run ready for ${result.email} with ${result.resume_filename}. No email was sent.`
          : `Sent to ${result.email} with ${result.resume_filename}.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the email");
    } finally {
      setSending(false);
    }
  };

  const onSendClick = () => {
    if (!dryRun) {
      setShowConfirm(true);
      return;
    }
    void sendEmail();
  };

  const changeCountry = (next: Region) => {
    setRegion(next);
    setResumeOverride(null);
  };

  return (
    <div className="page">
      <PageHeader
        title="One email"
        description="Fill the address and country. Role, skills, and job description are optional. The matching resume is selected for you, and you can change it before the email is written."
      />

      {error && <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      {notice && <p className="rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice}</p>}

      <section className="card">
        <div className="flex flex-col gap-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Details</p>
          <h2 className="font-semibold">Who this email is for</h2>
        </div>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Email</span>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="field"
            placeholder="hr@company.com"
          />
        </label>

        <div className="grid gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">Job role <span className="font-normal text-slate-400">optional</span></span>
            <input
              value={role}
              onChange={(event) => setRole(event.target.value)}
              className="field"
              placeholder="Frontend Developer"
            />
          </label>
          <div className="flex flex-col gap-1 text-sm">
            <span className="font-medium">Country</span>
            <div className="flex gap-2">
              {COUNTRIES.map((country) => (
                <button
                  key={country.region}
                  type="button"
                  onClick={() => changeCountry(country.region)}
                  className={region === country.region ? "btn-primary" : "btn-secondary"}
                >
                  {country.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Skills <span className="font-normal text-slate-400">optional</span></span>
          <textarea
            value={skills}
            onChange={(event) => setSkills(event.target.value)}
            className="field min-h-20"
            placeholder="React, TypeScript, FastAPI"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Job description <span className="font-normal text-slate-400">optional</span></span>
          <textarea
            value={jobDescription}
            onChange={(event) => setJobDescription(event.target.value)}
            className="field min-h-32"
            placeholder="Paste the job description"
          />
        </label>

        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm font-medium">Resume</span>
            {suggestion?.kind === "cold" && (
              <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
                Cold email
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={selectedResume}
              onChange={(event) => setResumeOverride(event.target.value)}
              className="field min-w-64"
            >
              {!selectedResume && <option value="">No resume</option>}
              {resumeOptions.map((pdf) => (
                <option key={pdf.path} value={pdf.path}>
                  {pdf.filename}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={!selectedResume}
              onClick={() => {
                const match = resumeOptions.find((pdf) => pdf.path === selectedResume);
                if (!match) return;
                setResumePreview(match);
              }}
              className="btn-secondary"
            >
              Preview
            </button>
            {resumeOverride && suggestion?.resume_path && resumeOverride !== suggestion.resume_path && (
              <button type="button" onClick={() => setResumeOverride(null)} className="text-sm font-medium text-indigo-600">
                Use suggested
              </button>
            )}
          </div>
          <p className="text-xs text-slate-500">
            {suggestion?.resume_filename
              ? `Suggested from the ${region === "INR" ? "India" : "UAE"} resumes: ${suggestion.resume_filename}.`
              : "No resume matched this country yet."}
            {suggestion?.already_applied ? " This address was already emailed for this role recently." : ""}
          </p>
        </div>

        <div>
          <button type="button" disabled={writing} onClick={() => void writeEmail()} className="btn-primary">
            {writing ? "Writing…" : "Write email"}
          </button>
        </div>
      </section>

      <section className="card">
        <div className="flex flex-col gap-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Message</p>
          <h2 className="font-semibold">Review, then send</h2>
        </div>
        {draftStale && (
          <p className="rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-800">
            The role, skills, job description, or country changed. Write the email again before sending.
          </p>
        )}
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Subject</span>
          <input value={subject} onChange={(event) => setSubject(event.target.value)} className="field" />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Email</span>
          <textarea value={body} onChange={(event) => setBody(event.target.value)} className="field min-h-64 font-mono text-xs" />
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={dryRun} onChange={(event) => setDryRun(event.target.checked)} />
            Dry run
          </label>
          <button
            type="button"
            disabled={!canSend || sending}
            onClick={onSendClick}
            className={dryRun ? "btn-primary" : "btn-danger"}
          >
            {sending ? "Sending…" : dryRun ? "Dry-run send" : "Send live"}
          </button>
        </div>
      </section>

      {showConfirm && (
        <div className="fixed inset-0 z-10 flex items-center justify-center bg-slate-950/60">
          <div className="flex w-full max-w-md flex-col gap-4 rounded-2xl bg-white p-5">
            <h2 className="text-lg font-semibold">Send this email?</h2>
            <p className="text-sm text-slate-600">
              This sends one real message to {email.trim() || "the address above"}. Type <span className="font-semibold">SEND</span> to confirm.
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
              <button type="button" disabled={confirmText !== "SEND" || sending} onClick={() => void sendEmail()} className="btn-danger">
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
