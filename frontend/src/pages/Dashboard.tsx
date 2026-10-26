import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import ResumePreview from "../components/ResumePreview";
import StatusBadge from "../components/StatusBadge";
import { api, formatDate } from "../api";
import type { Region, ResumePdf, Stats } from "../types";

const cards = [
  { key: "today_sent", label: "Sent today", hint: "Real emails today" },
  { key: "sent", label: "All sent", hint: "Successful live sends" },
  { key: "failed", label: "Failed", hint: "Errors and skips" },
  { key: "dry_runs", label: "Dry runs", hint: "Test sends" },
  { key: "skipped_dedup", label: "Duplicates", hint: "Already applied" },
  { key: "total_attempts", label: "Attempts", hint: "Every logged row" },
] as const;

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resumeRegion, setResumeRegion] = useState<Region>("INR");
  const [resumes, setResumes] = useState<ResumePdf[]>([]);
  const [preview, setPreview] = useState<ResumePdf | null>(null);

  useEffect(() => {
    api
      .stats()
      .then(setStats)
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    api
      .resumes(resumeRegion)
      .then((payload) => setResumes(payload.regions.flatMap((item) => item.folders.flatMap((folder) => folder.pdfs))))
      .catch(() => setResumes([]));
  }, [resumeRegion]);

  if (error) return <p className="text-sm text-rose-600">{error}</p>;
  if (!stats) return <p className="text-sm text-slate-500">Loading dashboard…</p>;

  return (
    <div className="page">
      <PageHeader
        title="Dashboard"
        description="See send volume, preview CVs, and jump into a new campaign."
        actions={
          <Link to="/send" className="btn-primary">
            New send
          </Link>
        }
      />

      <section className="grid grid-cols-2 gap-4 xl:grid-cols-3">
        {cards.map((card) => (
          <article key={card.key} className="card gap-1">
            <p className="text-sm text-slate-500">{card.label}</p>
            <p className="text-3xl font-semibold tracking-tight">{stats[card.key]}</p>
            <p className="text-xs text-slate-400">{card.hint}</p>
          </article>
        ))}
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <article className="card">
          <h2 className="font-semibold">By region</h2>
          <div className="flex flex-col gap-2">
            {Object.keys(stats.by_region).length === 0 && <p className="text-sm text-slate-500">No sends yet.</p>}
            {Object.entries(stats.by_region).map(([region, count]) => (
              <div key={region} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <span className="font-medium">{region}</span>
                <span className="text-slate-500">{count} sent</span>
              </div>
            ))}
          </div>
        </article>
        <article className="card">
          <h2 className="font-semibold">By source</h2>
          <div className="flex flex-col gap-2">
            {Object.entries(stats.by_source).map(([source, value]) => (
              <div key={source} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <span className="font-medium">{source.replace("sends_", "").replace(/_/g, " ")}</span>
                <span className="text-slate-500">
                  {value.sent} sent / {value.attempts} attempts
                </span>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-col gap-0.5">
            <h2 className="font-semibold">Resume library</h2>
            <p className="text-sm text-slate-500">Open a PDF without downloading it.</p>
          </div>
          <div className="flex gap-2">
            {(["INR", "UAE"] as Region[]).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setResumeRegion(value)}
                className={resumeRegion === value ? "btn-primary" : "btn-secondary"}
              >
                {value}
              </button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {resumes.length === 0 && <p className="text-sm text-slate-500">No PDFs in {resumeRegion}-CV&apos;s.</p>}
          {resumes.map((pdf) => (
            <button
              key={pdf.path}
              type="button"
              onClick={() => setPreview(pdf)}
              className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 px-3 py-3 text-left hover:border-indigo-300 hover:bg-indigo-50"
            >
              <span className="min-w-0 truncate text-sm font-medium">{pdf.filename.replace(/-CV-Razeen.*$/i, "")}</span>
              <span className="shrink-0 text-sm text-indigo-600">Preview</span>
            </button>
          ))}
        </div>
      </section>

      <section className="card">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Recent activity</h2>
          <Link to="/history" className="text-sm font-medium text-indigo-600">
            View all
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b border-slate-100">
              <tr>
                <th className="th">When</th>
                <th className="th">Company</th>
                <th className="th">Role</th>
                <th className="th">Email</th>
                <th className="th">Status</th>
              </tr>
            </thead>
            <tbody>
              {stats.recent.map((row) => (
                <tr key={`${row.source}-${row.id}`} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="td whitespace-nowrap text-slate-500">{formatDate(row.created_at)}</td>
                  <td className="td font-medium">{row.company || "—"}</td>
                  <td className="td">{row.role || "—"}</td>
                  <td className="td">{row.recipient_email}</td>
                  <td className="td">
                    <StatusBadge success={row.success} dryRun={row.dry_run} reason={row.failure_reason} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {preview && <ResumePreview path={preview.path} filename={preview.filename} onClose={() => setPreview(null)} />}
    </div>
  );
}
