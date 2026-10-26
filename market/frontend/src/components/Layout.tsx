import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import type { Country, Health, Mailbox } from "../types";

const baseLinks = [
  { to: "/", label: "Dashboard", hint: "Your send counts" },
  { to: "/jobs", label: "Jobs", hint: "Preview and send" },
  { to: "/history", label: "History", hint: "Every attempt" },
  { to: "/profile", label: "Profile", hint: "Your experience" },
  { to: "/countries", label: "Countries", hint: "Where you apply" },
];

function Dot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center justify-between gap-2 text-xs">
      <span className="text-slate-400">{label}</span>
      <span className={ok ? "text-emerald-400" : "text-rose-400"}>{ok ? "Online" : "Offline"}</span>
    </div>
  );
}

export default function Layout() {
  const { user, setUser } = useAuth();
  const [health, setHealth] = useState<Health | null>(null);
  const [mailbox, setMailbox] = useState<Mailbox | null>(null);
  const [countries, setCountries] = useState<Country[]>([]);

  useEffect(() => {
    const loadCountries = () => {
      api.countries().then(setCountries).catch(() => undefined);
    };
    loadCountries();
    window.addEventListener("countries-changed", loadCountries);
    return () => window.removeEventListener("countries-changed", loadCountries);
  }, []);

  const links = [
    ...baseLinks,
    ...(countries.length ? [{ to: "/resumes", label: "Resumes", hint: "Files by country" }] : []),
    { to: "/mailbox", label: "Mailbox", hint: "Your own inbox" },
  ];

  useEffect(() => {
    const load = () => {
      api.health().then(setHealth).catch(() => undefined);
      api.mailbox().then(setMailbox).catch(() => undefined);
    };
    load();
    const timer = window.setInterval(load, 20000);
    return () => window.clearInterval(timer);
  }, []);

  const signOut = () => {
    api.logout().finally(() => setUser(null));
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="flex w-60 shrink-0 flex-col justify-between gap-8 overflow-y-auto bg-slate-950 px-5 py-6 text-slate-100">
        <div className="flex flex-col gap-8">
          <div className="flex flex-col gap-1">
            <p className="text-lg font-semibold tracking-tight">Apply Desk</p>
            <p className="text-xs text-slate-400">Job applications</p>
          </div>
          <nav className="flex flex-col gap-1">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === "/"}
                className={({ isActive }) =>
                  `flex flex-col gap-0.5 rounded-xl px-3 py-2 ${
                    isActive ? "bg-indigo-600 text-white" : "text-slate-300 hover:bg-slate-900"
                  }`
                }
              >
                <span className="text-sm font-medium">{link.label}</span>
                <span className="text-xs opacity-70">{link.hint}</span>
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex flex-col gap-3">
          {health && (
            <div className="flex flex-col gap-2 rounded-xl bg-slate-900 px-3 py-3">
              <p className="text-xs font-medium text-slate-300">Services</p>
              <Dot ok={Boolean(mailbox?.configured)} label="Mailbox" />
              <Dot ok={health.ollama_reachable} label="Ollama" />
              <Dot ok={health.db_exists} label="Database" />
            </div>
          )}
          <div className="flex flex-col gap-2">
            <p className="truncate text-xs text-slate-400">{user?.email}</p>
            <button type="button" onClick={signOut} className="btn-secondary">
              Sign out
            </button>
          </div>
        </div>
      </aside>
      <main className="min-h-0 min-w-0 flex-1 overflow-y-auto">
        <div className="flex flex-col gap-6 px-8 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
