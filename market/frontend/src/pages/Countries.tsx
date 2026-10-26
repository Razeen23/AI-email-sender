import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";
import Field from "../components/Field";
import PageHeader from "../components/PageHeader";
import type { Country } from "../types";

const empty = { label: "", location_line: "", phone: "" };

export default function Countries() {
  const [countries, setCountries] = useState<Country[]>([]);
  const [draft, setDraft] = useState(empty);
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    api.countries().then(setCountries).catch((err: Error) => setError(err.message));
  };

  useEffect(() => {
    load();
  }, []);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const action = editing ? api.updateCountry(editing, draft) : api.createCountry(draft);
    action
      .then(() => {
        setDraft(empty);
        setEditing(null);
        load();
        window.dispatchEvent(new Event("countries-changed"));
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setBusy(false));
  };

  const remove = (country: Country) => {
    if (!window.confirm(`Remove ${country.label}? Its resumes are removed. Jobs keep their company and role.`)) return;
    api
      .deleteCountry(country.id)
      .then(() => {
        load();
        window.dispatchEvent(new Event("countries-changed"));
      })
      .catch((err: Error) => setError(err.message));
  };

  return (
    <div className="page">
      <PageHeader
        title="Countries"
        description="Add any place you want to apply. A campaign uses one of these for the resume location and phone. There is no built-in country list."
      />
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <form onSubmit={submit} className="card">
          <h2 className="font-semibold">{editing ? "Edit country" : "Add a country"}</h2>
          <Field label="Name">
            <input className="field" value={draft.label} onChange={(event) => setDraft((current) => ({ ...current, label: event.target.value }))} placeholder="Germany, Remote, UAE" required />
          </Field>
          <Field label="Location line on the resume">
            <input className="field" value={draft.location_line} onChange={(event) => setDraft((current) => ({ ...current, location_line: event.target.value }))} placeholder="Berlin, Germany" />
          </Field>
          <Field label="Phone for this country">
            <input className="field" value={draft.phone} onChange={(event) => setDraft((current) => ({ ...current, phone: event.target.value }))} placeholder="Leave blank to use your profile phone" />
          </Field>
          {error && <p className="text-sm text-rose-600">{error}</p>}
          <div className="flex gap-2">
            <button type="submit" className="btn-primary" disabled={busy}>
              {editing ? "Save country" : "Add country"}
            </button>
            {editing && (
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setEditing(null);
                  setDraft(empty);
                }}
              >
                Cancel
              </button>
            )}
          </div>
        </form>
        <section className="card">
          <h2 className="font-semibold">Your markets</h2>
          {countries.length === 0 && <p className="text-sm text-slate-500">None yet. Add the first country you want to apply in.</p>}
          <div className="flex flex-col gap-2">
            {countries.map((country) => (
              <article key={country.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 px-3 py-3">
                <div className="flex min-w-0 flex-col">
                  <span className="font-medium">{country.label}</span>
                  <span className="truncate text-xs text-slate-500">
                    {[country.location_line, country.phone].filter(Boolean).join(" · ") || "Uses your profile contact details"}
                  </span>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => {
                      setEditing(country.id);
                      setDraft({ label: country.label, location_line: country.location_line, phone: country.phone });
                    }}
                  >
                    Edit
                  </button>
                  <button type="button" className="btn-danger" onClick={() => remove(country)}>
                    Remove
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      </section>
    </div>
  );
}
