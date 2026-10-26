import { FormEvent, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import AuthCard from "../components/AuthCard";
import Field from "../components/Field";

export default function Login() {
  const { user, ready, setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!ready) return <p className="text-sm text-slate-500">Loading…</p>;
  if (user) return <Navigate to="/" replace />;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    api
      .login(email, password)
      .then(setUser)
      .catch((err: Error) => setError(err.message))
      .finally(() => setBusy(false));
  };

  return (
    <AuthCard title="Sign in">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field label="Email">
          <input className="field" type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </Field>
        <Field label="Password">
          <input className="field" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        </Field>
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="text-sm text-slate-500">
          New here? <Link to="/register" className="font-medium text-indigo-600">Create an account</Link>
        </p>
      </form>
    </AuthCard>
  );
}
