import { FormEvent, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import AuthCard from "../components/AuthCard";
import Field from "../components/Field";

export default function Register() {
  const { user, ready, setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!ready) return <p className="text-sm text-slate-500">Loading…</p>;
  if (user) return <Navigate to="/" replace />;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    setError(null);
    api
      .register(email, password)
      .then(setUser)
      .catch((err: Error) => setError(err.message))
      .finally(() => setBusy(false));
  };

  return (
    <AuthCard title="Create your account">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field label="Email">
          <input className="field" type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </Field>
        <Field label="Password">
          <input className="field" type="password" autoComplete="new-password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required />
        </Field>
        <Field label="Confirm password">
          <input className="field" type="password" autoComplete="new-password" minLength={8} value={confirm} onChange={(event) => setConfirm(event.target.value)} required />
        </Field>
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? "Creating…" : "Create account"}
        </button>
        <p className="text-sm text-slate-500">
          Already registered? <Link to="/login" className="font-medium text-indigo-600">Sign in</Link>
        </p>
      </form>
    </AuthCard>
  );
}
