import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import { api } from "../api";
import type { Health } from "../types";

function Pill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${ok ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"}`}>
      {label}
    </span>
  );
}

export default function Settings() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    api
      .health()
      .then(setHealth)
      .catch((err: Error) => setError(err.message));
  };

  useEffect(() => {
    load();
  }, []);

  if (error) return <p className="text-sm text-rose-600">{error}</p>;
  if (!health) return <p className="text-sm text-slate-500">Checking services…</p>;

  const modelReady = health.ollama_reachable && (health.ollama_models || []).some((name) => name.startsWith(health.ollama_model));

  return (
    <div className="page">
      <PageHeader
        title="Settings"
        description="Local service status. SMTP passwords stay in .env and are never shown here."
        actions={
          <button type="button" onClick={load} className="btn-secondary">
            Refresh
          </button>
        }
      />

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <article className="card">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">SMTP</h2>
            <Pill ok={health.smtp_configured} label={health.smtp_configured ? "Configured" : "Missing"} />
          </div>
          <dl className="flex flex-col gap-2 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Host</dt>
              <dd className="font-medium">{health.smtp_host || "—"}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Port</dt>
              <dd className="font-medium">{health.smtp_port ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">From</dt>
              <dd className="font-medium">{health.from_email || "—"}</dd>
            </div>
          </dl>
        </article>

        <article className="card">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Ollama</h2>
            <Pill ok={health.ollama_reachable} label={health.ollama_reachable ? "Online" : "Offline"} />
          </div>
          <dl className="flex flex-col gap-2 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">URL</dt>
              <dd className="font-medium">{health.ollama_base_url}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Model</dt>
              <dd className="font-medium">{health.ollama_model}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Ready</dt>
              <dd className="font-medium">{modelReady ? "Yes" : health.ollama_reachable ? "Model not pulled" : "No"}</dd>
            </div>
          </dl>
          {!health.ollama_reachable && (
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
              Ollama is not running. Start it with <span className="font-medium">ollama serve</span>, then click Refresh.
            </p>
          )}
          {health.ollama_reachable && (health.ollama_models || []).length > 0 && (
            <p className="text-xs text-slate-500">Installed: {health.ollama_models.join(", ")}</p>
          )}
        </article>

        <article className="card">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Database</h2>
            <Pill ok={health.db_exists} label={health.db_exists ? "Found" : "Missing"} />
          </div>
          <p className="text-sm text-slate-600">{health.db_path}</p>
        </article>

        <article className="card">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Profile</h2>
            <Pill ok={health.profile_exists} label={health.profile_exists ? "Found" : "Missing"} />
          </div>
          <p className="text-sm text-slate-600">
            Used for email bodies and generated resumes.{" "}
            <Link className="font-medium text-indigo-600" to="/profile">
              Edit profile
            </Link>
          </p>
        </article>
      </section>
    </div>
  );
}
