import { useEffect, useState } from "react";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { api, formatDate } from "../api";
import type { SendsPage } from "../types";

const PAGE_SIZE = 25;

export default function History() {
  const [query, setQuery] = useState("");
  const [success, setSuccess] = useState("");
  const [region, setRegion] = useState("");
  const [dryRun, setDryRun] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<SendsPage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    if (success) params.set("success", success);
    if (region) params.set("region", region);
    if (dryRun) params.set("dry_run", dryRun);
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(offset));
    api
      .sends(params)
      .then(setPage)
      .catch((err: Error) => setError(err.message));
  }, [query, success, region, dryRun, offset]);

  return (
    <div className="page">
      <PageHeader title="History" description="Search every send attempt from the dashboard and the CLI." />

      <div className="flex flex-wrap gap-3">
        <input
          value={query}
          onChange={(event) => {
            setOffset(0);
            setQuery(event.target.value);
          }}
          placeholder="Search email, company, or role"
          className="field min-w-56 flex-1"
        />
        <select value={success} onChange={(event) => { setOffset(0); setSuccess(event.target.value); }} className="field">
          <option value="">Any result</option>
          <option value="1">Success</option>
          <option value="0">Failed</option>
        </select>
        <select value={region} onChange={(event) => { setOffset(0); setRegion(event.target.value); }} className="field">
          <option value="">Any region</option>
          <option value="INR">INR</option>
          <option value="UAE">UAE</option>
        </select>
        <select value={dryRun} onChange={(event) => { setOffset(0); setDryRun(event.target.value); }} className="field">
          <option value="">Live + dry-run</option>
          <option value="0">Live only</option>
          <option value="1">Dry-run only</option>
        </select>
      </div>

      {error && <p className="text-sm text-rose-600">{error}</p>}

      <section className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full">
          <thead className="bg-slate-50">
            <tr>
              <th className="th">When</th>
              <th className="th">Company</th>
              <th className="th">Role</th>
              <th className="th">Email</th>
              <th className="th">Region</th>
              <th className="th">PDF</th>
              <th className="th">Status</th>
            </tr>
          </thead>
          <tbody>
            {page?.items.map((row) => (
              <tr key={`${row.source}-${row.id}`} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="td whitespace-nowrap text-slate-500">{formatDate(row.created_at)}</td>
                <td className="td font-medium">{row.company || "—"}</td>
                <td className="td">{row.role || "—"}</td>
                <td className="td">{row.recipient_email}</td>
                <td className="td">{row.region || "—"}</td>
                <td className="td">{row.pdf_filename || "—"}</td>
                <td className="td">
                  <StatusBadge success={row.success} dryRun={row.dry_run} reason={row.failure_reason} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {page && page.items.length === 0 && <p className="px-4 py-6 text-sm text-slate-500">No matching sends.</p>}
      </section>

      {page && page.total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-sm">
          <p className="text-slate-500">
            {page.offset + 1}–{Math.min(page.offset + page.items.length, page.total)} of {page.total}
          </p>
          <div className="flex gap-2">
            <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} className="btn-secondary">
              Previous
            </button>
            <button type="button" disabled={offset + PAGE_SIZE >= page.total} onClick={() => setOffset(offset + PAGE_SIZE)} className="btn-secondary">
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
