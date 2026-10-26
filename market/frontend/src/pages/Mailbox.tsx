import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";
import Field from "../components/Field";
import PageHeader from "../components/PageHeader";
import type { Mailbox } from "../types";

const empty: Mailbox & { password: string } = {
  configured: false,
  host: "",
  port: 587,
  username: "",
  from_name: "",
  from_email: "",
  password_set: false,
  password: "",
};

export default function Mailbox() {
  const [form, setForm] = useState(empty);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .mailbox()
      .then((mailbox) => setForm({ ...mailbox, password: "" }))
      .catch((err: Error) => setError(err.message));
  }, []);

  const payload = () => ({ ...form, port: Number(form.port) || 587 });

  const save = (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    api
      .saveMailbox(payload())
      .then((mailbox) => {
        setForm({ ...mailbox, password: "" });
        setNotice(mailbox.password_set ? "Mailbox saved. The app password stays on the server." : "Mailbox saved.");
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setBusy(false));
  };

  const test = () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    api
      .testMailbox(payload())
      .then((mailbox) => {
        setForm({ ...mailbox, password: "" });
        setNotice("Signed in to the mailbox.");
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setBusy(false));
  };

  const set = (patch: Partial<typeof form>) => setForm((current) => ({ ...current, ...patch }));

  return (
    <div className="page">
      <PageHeader
        title="Mailbox"
        description="Applications are sent from your address. For Gmail, the host is smtp.gmail.com and the username is the full Gmail address. Use an app password, not your normal password. It is encrypted and never shown again."
      />
      <form onSubmit={save} className="card max-w-xl">
        <Field label="Host">
          <input className="field" value={form.host} onChange={(event) => set({ host: event.target.value })} placeholder="smtp.gmail.com" required />
        </Field>
        <p className="text-sm text-slate-500">Gmail's host is smtp.gmail.com. Do not put your Gmail address here.</p>
        <Field label="Port">
          <input className="field" type="number" min={1} max={65535} value={form.port} onChange={(event) => set({ port: Number(event.target.value) })} required />
        </Field>
        <Field label="Username">
          <input className="field" value={form.username} onChange={(event) => set({ username: event.target.value })} placeholder="you@gmail.com" autoComplete="username" required />
        </Field>
        <Field label="From name">
          <input className="field" value={form.from_name} onChange={(event) => set({ from_name: event.target.value })} />
        </Field>
        <Field label="From email">
          <input className="field" type="email" value={form.from_email} onChange={(event) => set({ from_email: event.target.value })} required />
        </Field>
        <Field label={form.password_set ? "App password (leave blank to keep the saved one)" : "App password"}>
          <input className="field" type="password" autoComplete="new-password" value={form.password} onChange={(event) => set({ password: event.target.value })} />
        </Field>
        {form.password_set && <p className="text-sm text-emerald-700">An app password is saved for this account.</p>}
        {notice && <p className="text-sm text-emerald-700">{notice}</p>}
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <div className="flex gap-2">
          <button type="submit" className="btn-primary" disabled={busy}>
            Save mailbox
          </button>
          <button type="button" className="btn-secondary" onClick={test} disabled={busy}>
            Test connection
          </button>
        </div>
      </form>
    </div>
  );
}
