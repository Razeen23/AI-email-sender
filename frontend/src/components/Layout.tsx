import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "../api";
import type { Health } from "../types";

const links = [
  { to: "/", label: "Dashboard", hint: "Stats and resumes" },
  { to: "/send", label: "Send", hint: "Excel and campaigns" },
  { to: "/single", label: "One email", hint: "Fill and send" },
  { to: "/history", label: "History", hint: "Every attempt" },
  { to: "/profile", label: "Profile", hint: "Details and experience" },
  { to: "/resumes", label: "Resumes", hint: "Browse and generate" },
  { to: "/settings", label: "Settings", hint: "SMTP and Ollama" },
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
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => undefined);
    const timer = window.setInterval(() => {
      api.health().then(setHealth).catch(() => undefined);
    }, 20000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="flex w-60 shrink-0 flex-col justify-between gap-8 overflow-y-auto bg-slate-950 px-5 py-6 text-slate-100">
        <div className="flex flex-col gap-8">
          <div className="flex flex-col gap-1">
            <p className="text-lg font-semibold tracking-tight">Email Sender</p>
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
        {health && (
          <div className="flex flex-col gap-2 rounded-xl bg-slate-900 px-3 py-3">
            <p className="text-xs font-medium text-slate-300">Services</p>
            <Dot ok={health.smtp_configured} label="SMTP" />
            <Dot ok={health.ollama_reachable} label="Ollama" />
            <Dot ok={health.db_exists} label="Database" />
          </div>
        )}
      </aside>
      <main className="min-h-0 min-w-0 flex-1 overflow-y-auto">
        <div className="flex flex-col gap-6 px-8 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
