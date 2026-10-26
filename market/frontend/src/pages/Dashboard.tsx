import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatDate } from "../api";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import type { Profile, Stats } from "../types";

const cards = [
  { key: "today_sent", label: "Sent today", hint: "Live emails today" },
  { key: "sent", label: "All sent", hint: "Successful live sends" },
  { key: "failed", label: "Failed", hint: "Errors and the daily cap" },
  { key: "dry_runs", label: "Dry runs", hint: "Test sends" },
  { key: "skipped_dedup", label: "Duplicates", hint: "Already applied" },
  { key: "total_attempts", label: "Attempts", hint: "Every logged row" },
] as const;

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.stats().then(setStats).catch((err: Error) => setError(err.message));
    api.profile().then(setProfile).catch(() => undefined);
  }, []);

  if (error) return <p className="text-sm text-rose-600">{error}</p>;
  if (!stats) return <p className="text-sm text-slate-500">Loading dashboard…</p>;

  return (
    <div className="page">
      <PageHeader
        title="Dashboard"
        description="Your applications only. Other accounts cannot see this history."
        actions={
          <Link to="/jobs" className="btn-primary">
            New application
          </Link>
        }
      />

      {profile && !profile.name && (
        <article className="card">
          <h2 className="font-semibold">Finish your profile</h2>
          <p className="text-sm text-slate-500">Add your name and experience before previewing an application.</p>
          <Link to="/profile" className="btn-primary w-fit">
            Open profile
          </Link>
        </article>
      )}

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
          <h2 className="font-semibold">By country</h2>
          <div className="flex flex-col gap-2">
            {Object.keys(stats.by_country).length === 0 && <p className="text-sm text-slate-500">No sends yet.</p>}
            {Object.entries(stats.by_country).map(([country, count]) => (
              <div key={country} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <span className="font-medium">{country}</span>
                <span className="text-slate-500">{count} sent</span>
              </div>
            ))}
          </div>
        </article>
        <article className="card">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-semibold">Recent</h2>
            <Link to="/history" className="text-sm font-medium text-indigo-600">
              History
            </Link>
          </div>
          <div className="flex flex-col gap-2">
            {stats.recent.length === 0 && <p className="text-sm text-slate-500">No attempts yet.</p>}
            {stats.recent.map((row) => (
              <div key={row.id} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <div className="flex min-w-0 flex-col">
                  <span className="truncate font-medium">
                    {row.company} · {row.role}
                  </span>
                  <span className="text-xs text-slate-400">{formatDate(row.created_at)}</span>
                </div>
                <StatusBadge status={row.status} />
              </div>
            ))}
          </div>
        </article>
      </section>
    </div>
  );
}
