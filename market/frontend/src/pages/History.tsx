import { useEffect, useState } from "react";
import { api, formatDate } from "../api";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import type { SendRow } from "../types";

export default function History() {
  const [rows, setRows] = useState<SendRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.history().then(setRows).catch((err: Error) => setError(err.message));
  }, []);

  if (error) return <p className="text-sm text-rose-600">{error}</p>;
  if (!rows) return <p className="text-sm text-slate-500">Loading history…</p>;

  return (
    <div className="page">
      <PageHeader title="History" description="Every preview send, live send, duplicate, and failure on your account." />
      <section className="card">
        {rows.length === 0 && <p className="text-sm text-slate-500">No attempts yet.</p>}
        {rows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">When</th>
                  <th className="th">Company</th>
                  <th className="th">Role</th>
                  <th className="th">Country</th>
                  <th className="th">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-t border-slate-100 align-top">
                    <td className="td whitespace-nowrap">{formatDate(row.created_at)}</td>
                    <td className="td">
                      <div className="flex flex-col gap-1">
                        <span className="font-medium">{row.company}</span>
                        <span className="text-xs text-slate-400">{row.contact_email}</span>
                        {row.error && <span className="text-xs text-rose-600">{row.error}</span>}
                        {row.body && (
                          <details className="flex flex-col gap-2">
                            <summary className="cursor-pointer text-xs font-medium text-indigo-600">Email</summary>
                            <p className="whitespace-pre-wrap text-xs text-slate-600">{row.body}</p>
                          </details>
                        )}
                      </div>
                    </td>
                    <td className="td">{row.role}</td>
                    <td className="td">{row.country_label || "—"}</td>
                    <td className="td">
                      <StatusBadge status={row.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
